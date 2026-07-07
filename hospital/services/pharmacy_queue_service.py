"""
Pharmacy prescription queue helpers: bump order activity, notify pharmacists, sort/display.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.db.models import Max, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

FULLY_HANDLED_DISPENSING = ('fully_dispensed', 'cancelled')


def bump_medication_order_queue_time(order, when=None):
    """Move medication order to top of pharmacy queue when a new drug is added."""
    if not order:
        return
    when = when or timezone.now()
    from hospital.models import Order

    Order.objects.filter(pk=order.pk).update(requested_at=when, modified=when)
    order.requested_at = when
    order.modified = when


def _pharmacy_recipient_user_ids():
    from hospital.models import Staff

    recipient_ids = set(
        Staff.objects.filter(
            is_deleted=False,
            user__isnull=False,
        )
        .filter(
            Q(profession__in=('pharmacist', 'pharmacy_technician'))
            | Q(department__name__icontains='pharmacy')
        )
        .values_list('user_id', flat=True)
    )
    group_ids = Group.objects.filter(name__in=['Pharmacy', 'Pharmacist']).values_list('id', flat=True)
    recipient_ids.update(
        User.objects.filter(groups__id__in=group_ids, is_active=True).values_list('id', flat=True)
    )
    return recipient_ids


def notify_pharmacy_new_prescription(prescription, encounter, doctor, *, inpatient=False, changed=False):
    """
    Alert pharmacy staff when a doctor adds a medication. Notifications stay unread
    until the prescription is fully dispensed (see resolve_prescription_pharmacy_alerts).
    """
    if not prescription or not encounter:
        return
    try:
        from hospital.models import Notification

        patient = getattr(encounter, 'patient', None)
        patient_name = getattr(patient, 'full_name', '') or 'patient'
        patient_mrn = getattr(patient, 'mrn', '') or ''
        drug_name = ''
        if getattr(prescription, 'drug', None):
            drug_name = prescription.drug.name or 'Medication'
        doctor_name = ''
        if doctor and getattr(doctor, 'user', None):
            doctor_name = doctor.user.get_full_name() or doctor.user.username
        doctor_bit = f' by {doctor_name}' if doctor_name else ''
        mrn_bit = f' ({patient_mrn})' if patient_mrn else ''
        added_at = timezone.localtime(getattr(prescription, 'created', timezone.now())).strftime('%H:%M')

        if inpatient:
            if changed:
                title = 'Inpatient Prescription Changed — Review Required'
                message = (
                    f'{drug_name} changed for {patient_name}{mrn_bit}{doctor_bit} at {added_at}. '
                    'Open the pharmacy dispensing queue to review and dispense.'
                )
            else:
                title = 'New Inpatient Medication — Dispense Required'
                message = (
                    f'{drug_name} added for {patient_name}{mrn_bit}{doctor_bit} at {added_at}. '
                    'Open the pharmacy dispensing queue to verify and dispense. '
                    'This alert clears when the medication is fully dispensed.'
                )
            notif_type = 'order_urgent'
        else:
            consultation_completed = bool(
                getattr(encounter, 'status', None) == 'completed'
                or getattr(encounter, 'ended_at', None)
            )
            is_start_dose = bool(getattr(prescription, 'is_start_dose', False))
            if consultation_completed or changed:
                title = 'Prescription Updated — Dispense Required'
                message = (
                    f'{drug_name} updated for {patient_name}{mrn_bit}{doctor_bit} at {added_at}. '
                    'Open pharmacy queue to review and dispense.'
                )
                notif_type = 'order_urgent'
            elif is_start_dose:
                title = 'Stat dose — prepare now'
                message = (
                    f'Stat/start dose: {drug_name} for {patient_name}{mrn_bit}{doctor_bit} at {added_at}. '
                    'Prepare and dispense the stat dose now. Other meds on this visit stay held '
                    'until the doctor completes the consultation.'
                )
                notif_type = 'order_urgent'
            else:
                title = 'Temporary Prescription Added'
                message = (
                    f'{drug_name} for {patient_name}{mrn_bit}{doctor_bit}. '
                    'Consultation is not completed yet — do not dispense until the doctor completes the visit.'
                )
                notif_type = 'other'

        recipient_ids = _pharmacy_recipient_user_ids()
        if not recipient_ids:
            return

        recent = timezone.now() - timedelta(minutes=2)
        for user in User.objects.filter(id__in=recipient_ids, is_active=True):
            if Notification.objects.filter(
                recipient=user,
                notification_type=notif_type,
                title=title,
                related_object_id=prescription.id,
                related_object_type='Prescription',
                is_deleted=False,
                created__gte=recent,
            ).exists():
                continue
            Notification.objects.create(
                recipient=user,
                notification_type=notif_type,
                title=title,
                message=message,
                related_object_id=prescription.id,
                related_object_type='Prescription',
                is_read=False,
            )
    except Exception as exc:
        logger.warning('Pharmacy new-prescription notification failed: %s', exc, exc_info=True)


def queue_prescription_for_pharmacy(prescription, encounter, doctor, *, inpatient=None, changed=False):
    """
    After a prescription is created: ensure dispensing row, bump order queue time, notify pharmacy.
    """
    from hospital.services.auto_billing_service import AutoBillingService

    if inpatient is None:
        inpatient = AutoBillingService._encounter_is_inpatient_active(encounter)

    if prescription and getattr(prescription, 'order', None):
        bump_medication_order_queue_time(prescription.order)

    result = AutoBillingService.create_pharmacy_dispensing_record_only(
        prescription,
        force=inpatient,
    )
    if not result.get('success') and not result.get('gated'):
        logger.warning(
            'Could not queue prescription %s for pharmacy: %s',
            getattr(prescription, 'id', '?'),
            result.get('error') or result.get('message'),
        )

    notify_pharmacy_new_prescription(
        prescription,
        encounter,
        doctor,
        inpatient=inpatient,
        changed=changed,
    )
    return result


def resolve_prescription_pharmacy_alerts(prescription_ids):
    """Mark pharmacy alert notifications read once medication is fully dispensed."""
    if not prescription_ids:
        return 0
    try:
        from hospital.models import Notification

        ids = [pid for pid in prescription_ids if pid]
        if not ids:
            return 0
        now = timezone.now()
        updated = Notification.objects.filter(
            related_object_id__in=ids,
            related_object_type='Prescription',
            is_read=False,
            is_deleted=False,
        ).update(is_read=True, read_at=now, modified=now)
        return updated
    except Exception as exc:
        logger.warning('resolve_prescription_pharmacy_alerts failed: %s', exc, exc_info=True)
        return 0


def _undispensed_prescription_filter():
    from hospital.models import Prescription

    return Prescription.objects.filter(is_deleted=False).exclude(
        Q(dispensing_record__dispensing_status='fully_dispensed')
        | Q(
            dispensing_record__dispensing_status='cancelled',
            dispensing_record__quantity_ordered=0,
        )
    )


def enrich_pending_medication_orders(orders):
    """Attach latest undispensed prescription time for queue display/sort."""
    if not orders:
        return orders
    from hospital.models import Prescription
    from hospital.consultation_status import encounter_consultation_complete

    order_ids = [o.id for o in orders if getattr(o, 'id', None)]
    latest_map = {}
    start_dose_order_ids = set()
    if order_ids:
        for row in (
            _undispensed_prescription_filter()
            .filter(order_id__in=order_ids, order__is_deleted=False)
            .values('order_id')
            .annotate(
                latest_created=Max('created'),
                latest_modified=Max('modified'),
            )
        ):
            candidates = [row['latest_created'], row['latest_modified']]
            latest_map[row['order_id']] = max(
                (t for t in candidates if t is not None),
                default=None,
            )
        start_dose_order_ids = set(
            Prescription.objects.filter(
                order_id__in=order_ids,
                is_deleted=False,
                is_start_dose=True,
            ).values_list('order_id', flat=True)
        )

    now = timezone.now()
    for order in orders:
        latest_rx = latest_map.get(order.id)
        requested_at = getattr(order, 'requested_at', None)
        candidates = [t for t in (latest_rx, requested_at) if t is not None]
        latest = max(candidates, default=None) or getattr(order, 'created', None)
        order.latest_prescription_at = latest
        order.queue_sort_at = latest
        if latest:
            order.is_new_pharmacy_item = (now - latest) <= timedelta(minutes=45)
        else:
            order.is_new_pharmacy_item = False
        encounter = getattr(order, 'encounter', None)
        order.consultation_pending = bool(
            encounter and not encounter_consultation_complete(encounter)
        )
        order.has_start_dose = order.id in start_dose_order_ids
    return orders


def pending_pharmacy_alert_items(*, since=None, limit=40):
    """
    Undispensed prescriptions for pharmacy alert banner / pulse API.
    Returns list of dicts with patient, drug, order, prescription ids and added_at ISO.
    """
    from hospital.consultation_status import encounter_consultation_complete

    qs = (
        _undispensed_prescription_filter()
        .filter(
            order__order_type='medication',
            order__status='pending',
            order__is_deleted=False,
        )
        .select_related(
            'drug',
            'order__encounter__patient',
            'order__encounter__admission__ward',
        )
        .order_by('-modified', '-created')
    )
    if since:
        qs = qs.filter(
            Q(created__gt=since)
            | Q(modified__gt=since)
            | Q(order__requested_at__gt=since)
        )

    items = []
    for rx in qs[:limit]:
        order = rx.order
        patient = order.encounter.patient if order and order.encounter else None
        enc = order.encounter if order else None
        ward = ''
        if enc and getattr(enc, 'admission', None) and enc.admission.ward:
            ward = enc.admission.ward.name
        items.append(
            {
                'prescription_id': str(rx.id),
                'order_id': str(order.id) if order else '',
                'patient_name': getattr(patient, 'full_name', '') or '',
                'patient_mrn': getattr(patient, 'mrn', '') or '',
                'drug_name': rx.drug.name if rx.drug_id else '',
                'added_at': timezone.localtime(
                    max(
                        (t for t in (rx.modified, rx.created, getattr(order, 'requested_at', None)) if t),
                        default=rx.created,
                    )
                ).isoformat() if rx.created else '',
                'inpatient': bool(
                    enc
                    and getattr(enc, 'admission', None)
                    and enc.admission.status == 'admitted'
                    and enc.admission.discharge_date is None
                ),
                'ward': ward,
                'consultation_pending': bool(
                    enc and not encounter_consultation_complete(enc)
                ),
                'is_start_dose': bool(getattr(rx, 'is_start_dose', False)),
            }
        )
    return items

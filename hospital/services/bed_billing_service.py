"""
Automatic Bed Billing Service

Billing logic:
- DETENTION: Stay < 12 hours → detention fee (GHS 120) + doctor care + nursing care + consumables (1 day equivalent each)
- ADMISSION: Stay >= 12 hours → count by **nights** = calendar-style 24-hour periods (rounded up), not 12-hour half-day units
  - Accommodation: GHS 150 per night (regular), GHS 300 per night (VIP)
  - Doctor care, nursing care, consumables: same per-night count × their rates
"""
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging
import math

logger = logging.getLogger(__name__)

# Service codes for accommodation-related charges
ACCOM_SERVICE_CODES = ['DETENTION', 'ADM-ACCOM', 'ADM-DOCTOR-CARE', 'ADM-NURSING-CARE', 'ADM-CONSUMABLES']


class BedBillingService:
    """Service for automatic bed billing with detention vs admission logic."""

    # Pricing (GHS) – per **night** for admission (stay >= 12h); night = 24-hour billing unit (ceil of stay length)
    DETENTION_RATE = Decimal('120.00')           # Stay < 12 hours (flat)
    ADMISSION_NIGHTLY_RATE = Decimal('150.00')   # Stay >= 12 hours, regular ward (per night)
    VIP_ADMISSION_NIGHTLY_RATE = Decimal('300.00')  # VIP ward (per night)
    DOCTOR_CARE_PER_NIGHT = Decimal('80.00')
    NURSING_CARE_PER_NIGHT = Decimal('70.00')
    CONSUMABLES_PER_NIGHT = Decimal('50.00')

    DETENTION_THRESHOLD_HOURS = 12
    # Backwards-compatible aliases (same values)
    ADMISSION_DAILY_RATE = ADMISSION_NIGHTLY_RATE
    VIP_ADMISSION_DAILY_RATE = VIP_ADMISSION_NIGHTLY_RATE
    DOCTOR_CARE_PER_DAY = DOCTOR_CARE_PER_NIGHT
    NURSING_CARE_PER_DAY = NURSING_CARE_PER_NIGHT
    CONSUMABLES_PER_DAY = CONSUMABLES_PER_NIGHT

    @staticmethod
    def _ward_is_vip(ward):
        """VIP accommodation if ward name contains 'vip' (case-insensitive)."""
        return bool(ward and 'vip' in (ward.name or '').lower())

    @staticmethod
    def _is_vip_ward(admission):
        """Check if ward is VIP (name contains 'vip')."""
        if admission and admission.ward:
            return BedBillingService._ward_is_vip(admission.ward)
        return False

    @staticmethod
    def _get_admission_daily_rate(admission):
        """Return accommodation nightly rate: 150 regular, 300 VIP."""
        return (
            BedBillingService.VIP_ADMISSION_NIGHTLY_RATE
            if BedBillingService._is_vip_ward(admission)
            else BedBillingService.ADMISSION_NIGHTLY_RATE
        )

    @staticmethod
    def _billable_ward_segments(admission):
        """
        Return [(ward, bed, hours), ...] from admit_date through discharge or now.
        Hours sum to the total stay length; uses AdmissionWardStay when present.
        """
        end = admission.discharge_date or timezone.now()
        admit = admission.admit_date
        total_hours = max(0.0, (end - admit).total_seconds() / 3600.0)
        from hospital.models import AdmissionWardStay

        stays = list(
            AdmissionWardStay.objects.filter(admission=admission, is_deleted=False).order_by(
                'started_at', 'id'
            )
        )
        if not stays:
            return [(admission.ward, admission.bed, total_hours)]

        segments = []
        for st in stays:
            s = max(st.started_at, admit)
            e = min(st.ended_at or end, end)
            if e > s:
                segments.append((st.ward, st.bed, (e - s).total_seconds() / 3600.0))

        if not segments:
            return [(admission.ward, admission.bed, total_hours)]

        sh = sum(h for *_, h in segments)
        if sh <= 0:
            return [(admission.ward, admission.bed, total_hours)]
        if abs(sh - total_hours) > 1e-6:
            if sh < total_hours:
                segments.append((admission.ward, admission.bed, total_hours - sh))
            else:
                scale = total_hours / sh
                segments = [(w, b, h * scale) for w, b, h in segments]
        return segments

    @staticmethod
    def _allocate_nights_by_hours(total_nights, hours_per_segment):
        """Split integer nights across segments proportionally to hours (largest remainder)."""
        n = len(hours_per_segment)
        if total_nights <= 0 or n == 0:
            return [0] * n
        th = sum(hours_per_segment)
        if th <= 0:
            out = [0] * n
            out[0] = total_nights
            return out
        quotas = [total_nights * (h / th) for h in hours_per_segment]
        floors = [int(q) for q in quotas]
        rem = total_nights - sum(floors)
        order = sorted(range(n), key=lambda i: quotas[i] - floors[i], reverse=True)
        j = 0
        while rem > 0:
            floors[order[j % n]] += 1
            rem -= 1
            j += 1
        return floors

    @staticmethod
    def _admission_night_count(admission, total_hours):
        """
        Nights for admission (>= 12h): at least one night; use the greater of
        (local calendar dates spanned − 1 day boundary count) and ceil(hours/24).
        Same end instant as _get_stay_hours so the two stay consistent.
        """
        if total_hours < BedBillingService.DETENTION_THRESHOLD_HOURS:
            return 0
        end = admission.discharge_date or timezone.now()
        start_local = timezone.localtime(admission.admit_date)
        end_local = timezone.localtime(end)
        cal_gap = (end_local.date() - start_local.date()).days
        hour_nights = int(math.ceil(total_hours / 24.0))
        return max(1, max(cal_gap, hour_nights))

    @staticmethod
    def _get_or_create_service_code(code, description, unit_price, category='accommodation'):
        """Get or create a ServiceCode. Unit_price used for InvoiceLine; ServiceCode has no default_price."""
        from hospital.models import ServiceCode
        desc = (description or '')[:200]
        return ServiceCode.objects.get_or_create(
            code=code,
            defaults={
                'description': desc,
                'category': category,
                'is_active': True,
            }
        )[0]

    @staticmethod
    def _get_stay_hours(admission):
        """Return total stay hours. Uses discharge_date if set, else now."""
        end = admission.discharge_date or timezone.now()
        delta = end - admission.admit_date
        return delta.total_seconds() / 3600

    @staticmethod
    def _repair_adm_lines_on_open_admission_invoice(admission):
        """
        Final ADM-* lines belong on the encounter invoice after discharge (provisional DETENTION only
        while admitted). If ADM-* rows are present during an open admission, remove them and ensure
        a provisional DETENTION line so Total Bill does not show stale night counts or double-count
        bed charges (live bed row + invoice lines).
        """
        from hospital.models import Invoice, InvoiceLine

        if admission.status != 'admitted' or not admission.encounter_id:
            return
        try:
            invoice = Invoice.all_objects.get(
                patient=admission.encounter.patient,
                encounter=admission.encounter,
                is_deleted=False,
            )
        except Invoice.DoesNotExist:
            return

        adm_codes = [
            'ADM-ACCOM',
            'ADM-DOCTOR-CARE',
            'ADM-NURSING-CARE',
            'ADM-CONSUMABLES',
        ]
        qs = InvoiceLine.objects.filter(
            invoice=invoice,
            is_deleted=False,
            waived_at__isnull=True,
            service_code__code__in=adm_codes,
        )
        if not qs.exists():
            return

        try:
            with transaction.atomic():
                qs.delete()
                invoice.update_totals()
                invoice.save(update_fields=['total_amount', 'balance', 'modified'])
                result = BedBillingService.create_admission_bill(admission, days=1)
                if not result.get('success'):
                    raise RuntimeError(result.get('error') or 'create_admission_bill failed')
        except Exception:
            logger.exception(
                'Could not repair ADM invoice lines for open admission %s', admission.pk
            )

    @staticmethod
    def calculate_admission_charges(admission, include_partial_days=True):
        """
        Calculate charges based on stay duration (detention vs admission).

        Returns dict with:
        - is_detention: bool
        - total_hours: float
        - days: int (for admission: nights billed; key kept for compatibility)
        - nights: int (same as days when admission)
        - daily_rate: Decimal (nightly accommodation rate)
        - total_charge: Decimal
        - line_items: list of {code, description, quantity, unit_price, line_total}
        """
        _ = include_partial_days  # API compatibility; billing uses 24h night units
        if admission.status == 'admitted':
            BedBillingService._repair_adm_lines_on_open_admission_invoice(admission)

        total_hours = BedBillingService._get_stay_hours(admission)
        is_detention = total_hours < BedBillingService.DETENTION_THRESHOLD_HOURS

        segments = BedBillingService._billable_ward_segments(admission)
        bed_num = admission.bed.bed_number if admission.bed else 'N/A'
        ward_name = admission.ward.name if admission.ward else 'N/A'
        if segments:
            w0, b0, _ = segments[0]
            if w0:
                ward_name = w0.name or ward_name
            if b0:
                bed_num = b0.bed_number or bed_num

        if is_detention:
            # Detention: base fee + doctor care + nursing care + consumables (1 night equivalent each)
            doctor_care_total = BedBillingService.DOCTOR_CARE_PER_NIGHT * 1
            nursing_care_total = BedBillingService.NURSING_CARE_PER_NIGHT * 1
            consumables_total = BedBillingService.CONSUMABLES_PER_NIGHT * 1
            total_detention_charge = (
                BedBillingService.DETENTION_RATE
                + doctor_care_total
                + nursing_care_total
                + consumables_total
            )
            line_items = [
                {
                    'code': 'DETENTION',
                    'description': f'Detention (< 12 hrs) - {ward_name} - Bed {bed_num}',
                    'quantity': 1,
                    'unit_price': BedBillingService.DETENTION_RATE,
                    'line_total': BedBillingService.DETENTION_RATE,
                },
                {
                    'code': 'ADM-DOCTOR-CARE',
                    'description': f'Doctor Care (detention) @ GHS {BedBillingService.DOCTOR_CARE_PER_NIGHT}/night',
                    'quantity': 1,
                    'unit_price': BedBillingService.DOCTOR_CARE_PER_NIGHT,
                    'line_total': doctor_care_total,
                },
                {
                    'code': 'ADM-NURSING-CARE',
                    'description': f'Nursing Care (detention) @ GHS {BedBillingService.NURSING_CARE_PER_NIGHT}/night',
                    'quantity': 1,
                    'unit_price': BedBillingService.NURSING_CARE_PER_NIGHT,
                    'line_total': nursing_care_total,
                },
                {
                    'code': 'ADM-CONSUMABLES',
                    'description': f'Consumables (detention) @ GHS {BedBillingService.CONSUMABLES_PER_NIGHT}/night',
                    'quantity': 1,
                    'unit_price': BedBillingService.CONSUMABLES_PER_NIGHT,
                    'line_total': consumables_total,
                },
            ]
            return {
                'is_detention': True,
                'total_hours': total_hours,
                'days': 0,
                'nights': 0,
                'daily_rate': BedBillingService.DETENTION_RATE,
                'total_charge': total_detention_charge,
                'admission_date': admission.admit_date,
                'discharge_date': admission.discharge_date or timezone.now(),
                'bed': bed_num,
                'ward': ward_name,
                'line_items': line_items,
            }

        # Admission: bill by nights (24-hour units, ceil)
        nights = BedBillingService._admission_night_count(admission, total_hours)
        hours_list = [h for *_, h in segments]
        allocated = BedBillingService._allocate_nights_by_hours(nights, hours_list)

        accom_lines = []
        accom_total = Decimal('0.00')
        for (w, b, _), nseg in zip(segments, allocated):
            if nseg <= 0:
                continue
            wname = w.name if w else 'N/A'
            bnum = b.bed_number if b else 'N/A'
            rate = (
                BedBillingService.VIP_ADMISSION_NIGHTLY_RATE
                if BedBillingService._ward_is_vip(w)
                else BedBillingService.ADMISSION_NIGHTLY_RATE
            )
            seg_total = rate * nseg
            accom_total += seg_total
            accom_lines.append(
                {
                    'code': 'ADM-ACCOM',
                    'description': (
                        f'Admission - {wname} - Bed {bnum} '
                        f'({nseg} night{"s" if nseg != 1 else ""} @ GHS {rate}/night)'
                    ),
                    'quantity': nseg,
                    'unit_price': rate,
                    'line_total': seg_total,
                }
            )

        if not accom_lines and nights > 0:
            nightly_rate = BedBillingService._get_admission_daily_rate(admission)
            accom_total = nightly_rate * nights
            accom_lines = [
                {
                    'code': 'ADM-ACCOM',
                    'description': (
                        f'Admission - {ward_name} - Bed {bed_num} '
                        f'({nights} night{"s" if nights != 1 else ""} @ GHS {nightly_rate}/night)'
                    ),
                    'quantity': nights,
                    'unit_price': nightly_rate,
                    'line_total': accom_total,
                }
            ]

        nightly_blended = (
            (accom_total / nights) if nights > 0 else BedBillingService.ADMISSION_NIGHTLY_RATE
        )

        doctor_care_total = BedBillingService.DOCTOR_CARE_PER_NIGHT * nights
        nursing_care_total = BedBillingService.NURSING_CARE_PER_NIGHT * nights
        consumables_total = BedBillingService.CONSUMABLES_PER_NIGHT * nights

        ward_labels = []
        for w, _, _ in segments:
            if w and w.name and w.name not in ward_labels:
                ward_labels.append(w.name)
        ward_display = ', '.join(ward_labels) if ward_labels else ward_name

        line_items = accom_lines + [
            {
                'code': 'ADM-DOCTOR-CARE',
                'description': f'Doctor Care ({nights} night{"s" if nights != 1 else ""} @ GHS {BedBillingService.DOCTOR_CARE_PER_NIGHT}/night)',
                'quantity': nights,
                'unit_price': BedBillingService.DOCTOR_CARE_PER_NIGHT,
                'line_total': doctor_care_total,
            },
            {
                'code': 'ADM-NURSING-CARE',
                'description': f'Nursing Care ({nights} night{"s" if nights != 1 else ""} @ GHS {BedBillingService.NURSING_CARE_PER_NIGHT}/night)',
                'quantity': nights,
                'unit_price': BedBillingService.NURSING_CARE_PER_NIGHT,
                'line_total': nursing_care_total,
            },
            {
                'code': 'ADM-CONSUMABLES',
                'description': f'Consumables ({nights} night{"s" if nights != 1 else ""} @ GHS {BedBillingService.CONSUMABLES_PER_NIGHT}/night)',
                'quantity': nights,
                'unit_price': BedBillingService.CONSUMABLES_PER_NIGHT,
                'line_total': consumables_total,
            },
        ]

        total_charge = accom_total + doctor_care_total + nursing_care_total + consumables_total

        return {
            'is_detention': False,
            'total_hours': total_hours,
            'days': nights,
            'nights': nights,
            'daily_rate': nightly_blended,
            'total_charge': total_charge,
            'admission_date': admission.admit_date,
            'discharge_date': admission.discharge_date or timezone.now(),
            'bed': bed_num,
            'ward': ward_display,
            'line_items': line_items,
        }

    @staticmethod
    def _clear_accommodation_lines(invoice, admission):
        """
        Remove all accommodation-related invoice lines (BED-*, DETENTION, ADM-*, etc.).
        Returns total amount removed.
        """
        from hospital.models import InvoiceLine, ServiceCode

        removed = Decimal('0.00')
        codes_to_remove = list(ACCOM_SERVICE_CODES)
        # Include legacy BED-* and accommodation codes (don't filter is_deleted on ServiceCode - lines may reference old codes)
        bed_codes = ServiceCode.objects.filter(code__startswith='BED-').values_list('id', flat=True)
        accom_codes = ServiceCode.objects.filter(code__in=codes_to_remove).values_list('id', flat=True)
        code_ids = list(bed_codes) + list(accom_codes)

        lines = InvoiceLine.objects.filter(
            invoice=invoice,
            service_code_id__in=code_ids,
            is_deleted=False,
        )
        for line in lines:
            removed += line.line_total or Decimal('0.00')
        lines.delete()
        return removed

    @staticmethod
    def _add_accommodation_lines(invoice, admission, charge_breakdown):
        """Add invoice lines from charge_breakdown['line_items']."""
        from hospital.models import InvoiceLine

        added = Decimal('0.00')
        for item in charge_breakdown['line_items']:
            sc = BedBillingService._get_or_create_service_code(
                item['code'],
                item['description'],
                item['unit_price'],
            )
            InvoiceLine.objects.create(
                invoice=invoice,
                service_code=sc,
                description=(item['description'] or '')[:200],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                line_total=item['line_total'],
            )
            added += item['line_total']
        return added

    @staticmethod
    def create_admission_bill(admission, days=1):
        """
        Create provisional bed/accommodation charges on admission.
        Uses detention rate (GHS 120) as placeholder; final charges applied on discharge.
        """
        from hospital.models import Invoice, InvoiceLine

        try:
            with transaction.atomic():
                patient = admission.encounter.patient
                encounter = admission.encounter
                if getattr(encounter, 'billing_closed_at', None):
                    return {
                        'success': False,
                        'error': 'Billing is closed for this encounter',
                        'message': 'No new accommodation charges can be added after discharge.',
                    }

                # Provisional: detention rate (120) until discharge recalculates
                total_charge = BedBillingService.DETENTION_RATE
                sc = BedBillingService._get_or_create_service_code(
                    'DETENTION',
                    'Accommodation (provisional - final on discharge)',
                    BedBillingService.DETENTION_RATE,
                )

                from hospital.models import Payer
                payer = patient.primary_insurance or Payer.objects.filter(
                    payer_type='cash', is_active=True, is_deleted=False
                ).first() or Payer.objects.filter(is_active=True, is_deleted=False).first()
                if not payer:
                    raise ValueError('No payer configured. Please add a Cash payer in the system.')

                invoice, _ = Invoice.all_objects.get_or_create(
                    patient=patient,
                    encounter=encounter,
                    is_deleted=False,
                    defaults={
                        'payer': payer,
                        'issued_at': timezone.now(),
                        'total_amount': Decimal('0.00'),
                        'balance': Decimal('0.00'),
                        'status': 'draft',
                    },
                )

                # Avoid duplicate provisional line
                existing = invoice.lines.filter(
                    service_code=sc,
                    is_deleted=False,
                ).exists()
                if existing:
                    return {
                        'success': True,
                        'invoice': invoice,
                        'days': 1,
                        'daily_rate': BedBillingService.DETENTION_RATE,
                        'total_charge': total_charge,
                        'message': 'Provisional accommodation charge already exists; final charges on discharge.',
                    }

                ward_name = admission.ward.name if admission.ward else 'N/A'
                bed_num = admission.bed.bed_number if admission.bed else 'N/A'
                desc = f'Accommodation (provisional) - {ward_name} - Bed {bed_num}'[:200]

                InvoiceLine.objects.create(
                    invoice=invoice,
                    service_code=sc,
                    description=desc,
                    quantity=1,
                    unit_price=BedBillingService.DETENTION_RATE,
                    line_total=total_charge,
                )
                invoice.update_totals()
                invoice.status = 'issued'
                invoice.save(update_fields=['status'])

                logger.info(
                    f"✅ Provisional accommodation billing created: {patient.full_name} - "
                    f"GHS {total_charge} (final on discharge)"
                )

                return {
                    'success': True,
                    'invoice': invoice,
                    'days': 1,
                    'daily_rate': BedBillingService.DETENTION_RATE,
                    'total_charge': total_charge,
                    'message': (
                        f'Provisional charge GHS {total_charge}. '
                        'Final charges (detention or admission + care) applied on discharge.'
                    ),
                }

        except Exception as e:
            logger.error(f"Error creating admission bill: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': str(e),
            }

    @staticmethod
    def update_provisional_accommodation_description(admission):
        """Refresh DETENTION provisional line text after ward/bed change (e.g. transfer)."""
        from hospital.models import Invoice, ServiceCode

        if not admission.encounter_id:
            return
        try:
            invoice = Invoice.all_objects.get(
                patient=admission.encounter.patient,
                encounter=admission.encounter,
                is_deleted=False,
            )
        except Invoice.DoesNotExist:
            return
        sc_det = ServiceCode.objects.filter(code='DETENTION', is_deleted=False).first()
        if not sc_det:
            return
        line = invoice.lines.filter(service_code=sc_det, is_deleted=False).first()
        if not line:
            return
        desc = (line.description or '').lower()
        if 'provisional' not in desc:
            return
        ward_name = admission.ward.name if admission.ward else 'N/A'
        bed_num = admission.bed.bed_number if admission.bed else 'N/A'
        line.description = f'Accommodation (provisional) - {ward_name} - Bed {bed_num}'[:200]
        line.save(update_fields=['description', 'modified'])

    @staticmethod
    def update_bed_charges_on_discharge(admission):
        """
        Finalize accommodation charges on discharge.
        Applies detention (120) or full admission (accommodation + doctor + nursing care).
        """
        from hospital.models import Invoice, InvoiceLine

        try:
            with transaction.atomic():
                patient = admission.encounter.patient
                encounter = admission.encounter

                charge_breakdown = BedBillingService.calculate_admission_charges(
                    admission,
                    include_partial_days=True,
                )

                try:
                    invoice = Invoice.all_objects.get(
                        patient=patient,
                        encounter=encounter,
                        is_deleted=False,
                    )
                except Invoice.DoesNotExist:
                    from hospital.models import Payer
                    payer = patient.primary_insurance or Payer.objects.filter(
                        payer_type='cash', is_active=True, is_deleted=False
                    ).first() or Payer.objects.filter(is_active=True, is_deleted=False).first()
                    if not payer:
                        raise ValueError('No payer configured. Please add a Cash payer in the system.')
                    invoice = Invoice.objects.create(
                        patient=patient,
                        encounter=encounter,
                        payer=payer,
                        issued_at=timezone.now(),
                        total_amount=Decimal('0.00'),
                        balance=Decimal('0.00'),
                        status='draft',
                    )

                removed = BedBillingService._clear_accommodation_lines(invoice, admission)
                BedBillingService._add_accommodation_lines(invoice, admission, charge_breakdown)

                invoice.update_totals()
                if invoice.balance > 0:
                    invoice.status = 'issued'
                if not invoice.issued_at:
                    invoice.issued_at = timezone.now()
                invoice.save(update_fields=['status', 'issued_at'])

                from django.db.models.signals import post_save
                post_save.send(sender=Invoice, instance=invoice, created=False)

                logger.info(
                    f"✅ Accommodation charges finalized on discharge: {patient.full_name} - "
                    f"{'Detention' if charge_breakdown['is_detention'] else 'Admission'} "
                    f"GHS {charge_breakdown['total_charge']}"
                )

                return {
                    'success': True,
                    'invoice': invoice,
                    'charge_breakdown': charge_breakdown,
                    'message': (
                        f"{'Detention' if charge_breakdown['is_detention'] else 'Admission'} charges: "
                        f"GHS {charge_breakdown['total_charge']}"
                    ),
                }

        except Exception as e:
            logger.error(f"Error updating bed charges on discharge: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': str(e),
            }

    @staticmethod
    def get_bed_charges_summary(admission):
        """Return summary dict for display."""
        breakdown = BedBillingService.calculate_admission_charges(admission)

        return {
            'days_admitted': breakdown['days'] if not breakdown['is_detention'] else 0,
            'nights_admitted': breakdown.get('nights', breakdown['days']) if not breakdown['is_detention'] else 0,
            'daily_rate': breakdown['daily_rate'],
            'current_charges': breakdown['total_charge'],
            'bed_number': breakdown['bed'],
            'ward_name': breakdown['ward'],
            'admission_date': breakdown['admission_date'],
            'discharge_date': breakdown['discharge_date'],
            'is_discharged': admission.status == 'discharged',
            'is_detention': breakdown['is_detention'],
            'total_hours': breakdown.get('total_hours', 0),
        }


bed_billing_service = BedBillingService()

"""
Fast POST handlers for consultation: lab orders and prescriptions.
Invoked before heavy catalog/context loading in consultation_view.
"""
import logging
import traceback
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone

from .consultation_batch import set_skip_prescription_encounter_note
from .models import Drug, LabResult, LabTest, Order, Prescription
from .services.auto_billing_service import AutoBillingService

logger = logging.getLogger(__name__)


def _notify_lab_batch_pending_payment(patient, test_count: int, total_amount: Decimal) -> None:
    try:
        from hospital.services.pending_payment_notification_service import (
            SERVICE_TYPE_LAB,
            notify_patient_pending_payment,
        )

        notify_patient_pending_payment(
            patient,
            SERVICE_TYPE_LAB,
            f'{test_count} lab test(s)',
            total_amount,
            message_type='pending_payment_lab',
        )
    except Exception as exc:
        logger.warning('Lab batch pending payment notify failed: %s', exc, exc_info=True)


def handle_order_lab_test_post(request, encounter, doctor, encounter_id):
    test_ids = [tid for tid in request.POST.getlist('test_ids') if tid]
    single_test_id = (request.POST.get('test_id') or '').strip()
    if single_test_id and single_test_id not in test_ids:
        test_ids.append(single_test_id)
    priority = request.POST.get('priority', 'routine')
    notes = request.POST.get('notes', '')
    lab_redirect = f'/hms/consultation/{encounter_id}/?tab=lab'

    if not test_ids:
        messages.error(request, 'Please select at least one test.')
        return redirect(lab_redirect)

    try:
        from hospital.models_lab_management import LabReagent
    except ImportError:
        LabReagent = None

    try:
        tests_qs = LabTest.objects.filter(
            pk__in=test_ids,
            is_active=True,
            is_deleted=False,
            name__isnull=False,
        ).exclude(name__iexact='').exclude(name__icontains='INVALID')
        if LabReagent is not None:
            tests_qs = tests_qs.prefetch_related(
                Prefetch(
                    'required_reagents',
                    queryset=LabReagent.objects.filter(is_deleted=False),
                )
            )
        tests_list_raw = list(tests_qs)
        seen_pk = set()
        tests = []
        for t in tests_list_raw:
            if t.pk not in seen_pk:
                seen_pk.add(t.pk)
                tests.append(t)

        if not tests:
            messages.error(request, 'No valid tests selected.')
            return redirect(lab_redirect)

        reagent_warnings = []
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        total_notify_amount = Decimal('0.00')
        results_list = []
        patient_for_notify = None
        final_count = 0

        with transaction.atomic():
            lab_order = Order.objects.create(
                encounter=encounter,
                order_type='lab',
                status='pending',
                priority=priority,
                notes=notes,
                requested_by=doctor,
            )
            to_bulk = []
            for test in tests:
                existing_result = LabResult.objects.filter(
                    order=lab_order,
                    test=test,
                    is_deleted=False,
                ).first()
                if existing_result:
                    continue
                recent_duplicate = (
                    LabResult.objects.filter(
                        order__encounter=encounter,
                        test=test,
                        is_deleted=False,
                        created__gte=five_minutes_ago,
                    )
                    .exclude(order=lab_order)
                    .first()
                )
                if recent_duplicate:
                    recent_duplicate.order = lab_order
                    recent_duplicate.save(update_fields=['order'])
                    continue
                to_bulk.append(LabResult(order=lab_order, test=test, status='pending'))
                try:
                    for reagent in test.required_reagents.all():
                        if reagent.is_low_stock:
                            reagent_warnings.append(f'{reagent.name} (low stock)')
                        if reagent.is_expired:
                            reagent_warnings.append(f'{reagent.name} (expired)')
                except Exception as reagent_err:
                    logger.warning('Reagent availability check skipped: %s', reagent_err)

            if to_bulk:
                LabResult.objects.bulk_create(to_bulk)

            results_list = list(
                LabResult.objects.filter(order=lab_order, is_deleted=False).select_related(
                    'test', 'order', 'order__encounter', 'order__encounter__patient'
                )
            )
            final_count = len(results_list)

            for lr in results_list:
                res = AutoBillingService.create_lab_bill(lr, notify_patient=False)
                if res.get('success') and res.get('amount') is not None:
                    try:
                        total_notify_amount += Decimal(str(res['amount']))
                    except Exception:
                        pass

            encounter.refresh_from_db()
            if encounter.status == 'active':
                try:
                    encounter.update_activity('lab')
                except Exception:
                    pass
                lab_note = (
                    f"\n[Lab] Tests ordered ({len(tests)}). Total bill: GHS {total_notify_amount:.2f} — "
                    f"{timezone.now().strftime('%Y-%m-%d %H:%M')}"
                )
                encounter.notes = (encounter.notes or '') + lab_note
                encounter.save(update_fields=['notes'])

            patient_for_notify = encounter.patient

            if final_count > 0 and patient_for_notify:
                pf = patient_for_notify
                fc = final_count
                ta = total_notify_amount
                transaction.on_commit(
                    lambda: _notify_lab_batch_pending_payment(pf, fc, ta)
                )

        if reagent_warnings:
            messages.warning(
                request,
                f'Lab order created. Reagent warnings: {", ".join(set(reagent_warnings))}',
            )
        else:
            messages.success(request, f'Lab order created with {final_count} test(s)')
    except Exception as e:
        messages.error(request, f'Error creating lab order: {str(e)}')
        logger.exception('order_lab_test failed')

    return redirect(lab_redirect)


def handle_prescribe_drug_post(request, encounter, doctor, encounter_id):
    is_auto_save = request.POST.get('auto_save') == 'true' or request.META.get(
        'HTTP_X_AUTO_SAVE'
    ) == 'true'

    if is_auto_save:
        logger.warning(
            'AUTO-SAVE BLOCKED on prescription creation - User: %s, Encounter: %s',
            request.user.username,
            encounter_id,
        )
        return JsonResponse(
            {
                'status': 'ignored',
                'message': 'Prescription creation cannot be auto-saved',
            }
        )

    drug_ids = request.POST.getlist('drug_id')
    if not drug_ids:
        single = request.POST.get('drug_id', '').strip()
        if single:
            drug_ids = [single]
    quantity_fallback = request.POST.get('quantity', '1')
    dose_fallback = request.POST.get('dose', '')[:100]
    route_fallback = (request.POST.get('route') or 'oral')[:50]
    frequency_fallback = (request.POST.get('frequency') or '')[:50]
    duration_fallback = (request.POST.get('duration') or '')[:50]
    instructions_fallback = request.POST.get('instructions', '') or ''

    if not drug_ids:
        messages.error(request, 'Please select at least one drug.')
        return redirect(f'/hms/consultation/{encounter_id}/')

    try:
        for did in drug_ids:
            uuid.UUID(did.strip())
    except (ValueError, AttributeError):
        messages.error(request, 'Invalid drug selected. Please select valid drug(s).')
        logger.error('Invalid drug_id format in list: %s', drug_ids)
        return redirect(f'/hms/consultation/{encounter_id}/')

    try:
        _q = int(quantity_fallback)
        if _q < 1:
            raise ValueError('Quantity must be at least 1')
    except (ValueError, TypeError):
        messages.error(
            request, 'Invalid quantity. Please enter a valid number (at least 1).'
        )
        return redirect(f'/hms/consultation/{encounter_id}/')

    created_count = 0
    created_names = []
    last_error = None
    set_skip_prescription_encounter_note(True)
    try:
        for drug_id in drug_ids:
            drug_id = drug_id.strip()
            if not drug_id:
                continue
            dose = (request.POST.get('dose_' + drug_id) or dose_fallback)[:100]
            route = (request.POST.get('route_' + drug_id) or route_fallback)[:50]
            frequency = (
                request.POST.get('frequency_' + drug_id) or frequency_fallback
            )[:50]
            duration = (
                request.POST.get('duration_' + drug_id) or duration_fallback
            ).strip()[:50]
            instructions = (
                request.POST.get('instructions_' + drug_id) or instructions_fallback
            )[:500]
            quantity_raw = request.POST.get('quantity_' + drug_id) or quantity_fallback
            try:
                quantity = int(quantity_raw)
                if quantity < 1:
                    quantity = int(quantity_fallback)
                    if quantity < 1:
                        quantity = 1
            except (ValueError, TypeError):
                quantity = int(quantity_fallback) if quantity_fallback else 1
                if quantity < 1:
                    quantity = 1
            if not duration:
                last_error = (
                    'Duration is required for each medication (e.g., "7 days").'
                )
                continue
            try:
                drug = (
                    Drug.objects.filter(
                        pk=drug_id,
                        is_active=True,
                        is_deleted=False,
                        name__isnull=False,
                    )
                    .exclude(name__iexact='')
                    .exclude(name__icontains='INVALID')
                    .first()
                )
                if not drug:
                    last_error = 'Selected drug is invalid or has been removed.'
                    continue
                thirty_minutes_ago = timezone.now() - timedelta(minutes=30)

                medication_order = (
                    Order.objects.filter(
                        encounter=encounter,
                        order_type='medication',
                        is_deleted=False,
                        created__gte=thirty_minutes_ago,
                    )
                    .order_by('-created')
                    .first()
                )

                if not medication_order:
                    medication_order = Order.objects.create(
                        encounter=encounter,
                        order_type='medication',
                        status='pending',
                        requested_by=doctor,
                        priority='routine',
                    )

                existing_prescription = Prescription.objects.filter(
                    order=medication_order,
                    drug=drug,
                    is_deleted=False,
                ).first()

                if not existing_prescription:
                    five_minutes_ago = timezone.now() - timedelta(minutes=5)
                    recent_duplicate = (
                        Prescription.objects.filter(
                            order__encounter=encounter,
                            drug=drug,
                            is_deleted=False,
                            created__gte=five_minutes_ago,
                        )
                        .exclude(order=medication_order)
                        .first()
                    )

                    if recent_duplicate:
                        recent_duplicate.order = medication_order
                        recent_duplicate.quantity = max(
                            recent_duplicate.quantity, quantity
                        )
                        recent_duplicate.save(update_fields=['order', 'quantity'])
                        existing_prescription = recent_duplicate

                if not existing_prescription:
                    try:
                        with transaction.atomic():
                            prescription_data = {
                                'order': medication_order,
                                'drug': drug,
                                'quantity': quantity,
                                'dose': (dose or 'As directed')[:100],
                                'route': (route or 'oral')[:50],
                                'frequency': (frequency or 'Once daily')[:50],
                                'duration': duration[:50],
                                'instructions': (instructions or '')[:500],
                                'prescribed_by': doctor,
                            }
                            prescription = Prescription.objects.create(
                                **prescription_data
                            )
                            logger.info(
                                'Prescription created: %s for drug %s',
                                prescription.id,
                                drug.name,
                            )
                    except Exception as create_error:
                        logger.error(
                            'Error in Prescription.objects.create(): %s\n%s',
                            create_error,
                            traceback.format_exc(),
                        )
                        raise
                else:
                    prescription = existing_prescription
                    if quantity > prescription.quantity:
                        prescription.quantity = quantity
                    prescription.dose = dose
                    prescription.route = route
                    prescription.frequency = frequency
                    prescription.duration = duration
                    prescription.instructions = instructions
                    prescription.save()

                created_count += 1
                created_names.append(drug.name)
            except ValueError as ve:
                logger.error(
                    'ValueError creating prescription: %s\n%s',
                    str(ve),
                    traceback.format_exc(),
                )
                last_error = str(ve)
            except Exception as e:
                error_details = str(e)
                logger.error(
                    'Error creating prescription for drug_id %s: %s\n%s',
                    drug_id,
                    error_details,
                    traceback.format_exc(),
                )
                last_error = error_details[:100]
    finally:
        set_skip_prescription_encounter_note(False)

    if created_count > 0:
        encounter.refresh_from_db()
        if encounter.status == 'active':
            try:
                encounter.update_activity('consulting')
            except Exception:
                pass
            ts = timezone.now().strftime('%Y-%m-%d %H:%M')
            names_str = ', '.join(created_names[:8])
            if len(created_names) > 8:
                names_str += f' and {len(created_names) - 8} more'
            prescription_note = (
                f'\n[Consulting] Prescription(s) issued: {names_str} ({ts})'
            )
            encounter.notes = (encounter.notes or '') + prescription_note
            encounter.save(update_fields=['notes'])

        names_str = ', '.join(created_names[:5])
        if len(created_names) > 5:
            names_str += f' and {len(created_names) - 5} more'
        messages.success(
            request,
            f'✅ Prescription(s) created for {names_str}. '
            f'Patient should proceed to pharmacy for payment and dispensing.',
        )
        return redirect(f'/hms/consultation/{encounter_id}/?prescription_created=1')
    if last_error:
        messages.error(request, last_error)
    return redirect(f'/hms/consultation/{encounter_id}/')

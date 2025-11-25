"""
🔒 PHARMACY DISPENSING - PAYMENT ENFORCED
Cannot dispense drugs without payment verification
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction, OperationalError, connection
from decimal import Decimal
import time
import logging

from .models import Prescription, Patient, Staff
from .models_accounting import PaymentReceipt
from .models_payment_verification import PharmacyDispensing, PharmacyDispenseHistory
from .services.auto_billing_service import AutoBillingService
from .models_pharmacy_walkin import WalkInPharmacySale

logger = logging.getLogger(__name__)

DB_LOCK_RETRY_ATTEMPTS = 3


def _get_user_display_name(staff, user):
    """Return a human-friendly name for logging purposes."""
    if staff and staff.user:
        full_name = staff.user.get_full_name()
        return full_name or staff.user.username
    if user:
        full_name = getattr(user, 'get_full_name', lambda: '')()
        return full_name or getattr(user, 'username', 'Unknown User')
    return ''


@login_required
def pharmacy_pending_dispensing(request):
    """
    Show prescriptions awaiting payment or ready for dispensing
    Pharmacists use this to see what can/cannot be dispensed
    """
    # Ensure every prescription has a dispensing record
    missing_dispensing = Prescription.objects.filter(
        is_deleted=False,
        dispensing_record__isnull=True
    ).select_related('drug')[:100]
    
    for rx in missing_dispensing:
        AutoBillingService.create_pharmacy_bill(rx)
    
    dispensing_qs = PharmacyDispensing.objects.select_related(
        'prescription__drug',
        'prescription__order__encounter__patient',
        'prescription__prescribed_by__user',
        'patient',
        'payment_receipt',
        'dispensed_by__user'
    ).order_by('-created')
    
    pending_payment_qs = dispensing_qs.filter(dispensing_status='pending_payment')
    paid_ready_qs = dispensing_qs.filter(dispensing_status='ready_to_dispense')
    dispensed_qs = dispensing_qs.filter(dispensing_status__in=['partially_dispensed', 'fully_dispensed'])
    
    pending_payment = list(pending_payment_qs[:40])
    paid_ready_to_dispense = list(paid_ready_qs[:40])
    recently_dispensed = list(dispensed_qs.order_by('-dispensed_at', '-created')[:20])
    
    history_qs = PharmacyDispenseHistory.objects.select_related(
        'prescription__drug',
        'patient',
        'dispensed_by__user',
        'payment_receipt'
    ).order_by('-dispensed_at')[:100]
    
    walkin_pending_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial']
    ).order_by('-sale_date')
    walkin_ready_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status='paid',
        is_dispensed=False
    ).order_by('-sale_date')
    walkin_dispensed_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        is_dispensed=True
    ).order_by('-dispensed_at')

    walkin_pending = list(walkin_pending_qs[:40])
    walkin_ready = list(walkin_ready_qs[:40])
    walkin_recently_dispensed = list(walkin_dispensed_qs[:20])

    stats = {
        'pending_payment': pending_payment_qs.count(),
        'paid_ready': paid_ready_qs.count(),
        'dispensed': dispensed_qs.count(),
        'total': dispensing_qs.count(),
        'history_total': PharmacyDispenseHistory.objects.count(),
        'walkin_pending': walkin_pending_qs.count(),
        'walkin_ready': walkin_ready_qs.count(),
        'walkin_dispensed': walkin_dispensed_qs.count(),
    }
    stats['pending_payment_total'] = stats['pending_payment'] + stats['walkin_pending']
    stats['paid_ready_total'] = stats['paid_ready'] + stats['walkin_ready']
    stats['dispensed_total'] = stats['dispensed'] + stats['walkin_dispensed']
    stats['total_all'] = stats['total'] + stats['walkin_pending'] + stats['walkin_ready'] + stats['walkin_dispensed']
    
    context = {
        'title': '💊 Pharmacy Dispensing - Payment Enforced',
        'pending_payment': pending_payment,
        'paid_ready_to_dispense': paid_ready_to_dispense,
        'recently_dispensed': recently_dispensed,
        'dispense_history': history_qs,
        'history_total': stats['history_total'],
        'stats': stats,
        'walkin_pending': walkin_pending,
        'walkin_ready': walkin_ready,
        'walkin_recently_dispensed': walkin_recently_dispensed,
    }
    return render(request, 'hospital/pharmacy_dispensing_enforced.html', context)


@login_required
def pharmacy_dispense_enforced(request, prescription_id):
    """
    Dispense medication - with integrated payment option
    """
    prescription = get_object_or_404(Prescription, id=prescription_id, is_deleted=False)
    patient = prescription.order.encounter.patient
    drug = prescription.drug
    
    # Get or create dispensing record
    try:
        dispensing_record = prescription.dispensing_record
    except:
        # Create dispensing record if not exists
        result = AutoBillingService.create_pharmacy_bill(prescription)
        try:
            dispensing_record = prescription.dispensing_record
        except:
            dispensing_record = None
    
    # Calculate cost
    unit_price = getattr(drug, 'unit_price', Decimal('0.00'))
    total_cost = unit_price * prescription.quantity
    
    # Check payment status
    payment_status = AutoBillingService.check_payment_status('pharmacy', prescription_id)
    is_already_dispensed = bool(dispensing_record and dispensing_record.dispensing_status in ['partially_dispensed', 'fully_dispensed'])
    
    # Check payment BEFORE allowing any action
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # ENFORCE: Payment must be made at CASHIER first
        if action == 'dispense':
            if is_already_dispensed:
                messages.info(request, 'This medication has already been dispensed. No further action required.')
                return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)
            # Double-check payment before dispensing
            if not payment_status['paid']:
                messages.error(
                    request,
                    f'🔒 PAYMENT REQUIRED AT CASHIER! Patient must pay at cashier FIRST. '
                    f'Amount: GHS {total_cost}. Status: {payment_status["message"]}'
                )
                return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)
            
            # Payment verified - can dispense
            try:
                success = False
                for attempt in range(DB_LOCK_RETRY_ATTEMPTS):
                    try:
                        with transaction.atomic():
                            dispensing_record = prescription.dispensing_record
                            
                            # Get current staff
                            try:
                                current_staff = Staff.objects.get(user=request.user, is_active=True)
                            except:
                                current_staff = None
                            
                            # Record dispensing details
                            quantity = int(request.POST.get('quantity', prescription.quantity))
                            instructions = request.POST.get('instructions', f"{prescription.dose}, {prescription.frequency}, {prescription.duration}")
                            counselling_given = request.POST.get('counselling_given') == 'on'
                            notes = request.POST.get('notes', '')
                            
                            # Check if patient is inpatient - create MAR if needed
                            encounter = prescription.order.encounter
                            is_inpatient = encounter.encounter_type == 'inpatient'
                            
                            # Prevent overdosing
                            quantity = min(quantity, dispensing_record.quantity_ordered)
                            
                            # Update dispensing record manually to guarantee status change
                            dispensing_record.quantity_dispensed = min(
                                dispensing_record.quantity_dispensed + quantity,
                                dispensing_record.quantity_ordered
                            )
                            
                            if dispensing_record.quantity_dispensed >= dispensing_record.quantity_ordered:
                                dispensing_record.dispensing_status = 'fully_dispensed'
                            else:
                                dispensing_record.dispensing_status = 'partially_dispensed'
                            
                            dispensing_record.dispensed_by = current_staff or dispensing_record.dispensed_by
                            dispensing_record.dispensed_at = timezone.now()
                            dispensing_record.dispensing_instructions = instructions
                            dispensing_record.dispensing_notes = notes
                            dispensing_record.counselling_given = counselling_given
                            if current_staff:
                                dispensing_record.counselled_by = current_staff
                            
                            dispensing_record.save(update_fields=[
                                'quantity_dispensed',
                                'dispensing_status',
                                'dispensed_by',
                                'dispensed_at',
                                'dispensing_instructions',
                                'dispensing_notes',
                                'counselling_given',
                                'counselled_by'
                            ])
                            
                            dispensed_timestamp = dispensing_record.dispensed_at or timezone.now()
                            
                            PharmacyDispenseHistory.objects.create(
                                dispensing_record=dispensing_record,
                                prescription=prescription,
                                patient=patient,
                                patient_name=getattr(patient, 'full_name', str(patient)),
                                drug=drug,
                                drug_name=getattr(drug, 'name', str(drug)),
                                quantity_dispensed=quantity,
                                instructions=instructions,
                                notes=notes,
                                counselling_given=counselling_given,
                                dispensed_by=current_staff,
                                dispensed_by_name=_get_user_display_name(current_staff, request.user),
                                payment_receipt=dispensing_record.payment_receipt,
                                dispensed_at=dispensed_timestamp,
                            )
                            
                            is_already_dispensed = dispensing_record.is_dispensed
                            
                            # If inpatient, create MAR schedule
                            if is_inpatient:
                                try:
                                    from hospital.services.mar_generator import create_mar_schedule
                                    create_mar_schedule(prescription)
                                    messages.info(request, '📋 MAR schedule created for inpatient medication administration')
                                except Exception as e:
                                    logger.error(f"Error creating MAR: {str(e)}")
                            
                            success = True
                            break
                    except OperationalError as oe:
                        if 'database is locked' in str(oe).lower() and attempt < DB_LOCK_RETRY_ATTEMPTS - 1:
                            wait_time = 0.5 * (attempt + 1)
                            logger.warning(
                                "SQLite database locked while dispensing %s (attempt %s). Retrying in %.1fs",
                                prescription.id,
                                attempt + 1,
                                wait_time
                            )
                            connection.close()
                            time.sleep(wait_time)
                            continue
                        raise
                
                if not success:
                    raise OperationalError('database is locked')
                
                is_already_dispensed = True
                
                messages.success(
                    request,
                    f'✅ Medication dispensed to {patient.full_name}. Payment verified via receipt {payment_status["receipt"].receipt_number}'
                )
                
                # Send SMS notification
                try:
                    from .services.sms_service import sms_service
                    if patient.phone_number:
                        message = (
                            f"Your medication {drug.name} has been dispensed. "
                            f"Instructions: {instructions}. PrimeCare Medical"
                        )
                        sms_log = sms_service.send_sms(
                            phone_number=patient.phone_number,
                            message=message,
                            message_type='pharmacy_dispensing',
                            recipient_name=patient.full_name,
                            related_object_id=dispensing_record.id if hasattr(dispensing_record, 'id') else prescription.id if hasattr(prescription, 'id') else None,
                            related_object_type='DispensingRecord'
                        )
                        if sms_log.status == 'sent':
                            logger.info(f"✅ SMS sent to {patient.phone_number}")
                        else:
                            logger.warning(f"⚠️ SMS failed: {sms_log.error_message or 'Unknown error'}")
                except Exception as e:
                    logger.error(f"❌ Error sending SMS: {str(e)}", exc_info=True)
                
                return redirect('hospital:pharmacy_pending_dispensing')
            
            except OperationalError as e:
                logger.warning(f"Operational error while dispensing medication: {str(e)}", exc_info=True)
                if 'database is locked' in str(e).lower():
                    messages.error(request, '❌ Pharmacy database is busy. Please wait a few seconds and try again.')
                else:
                    messages.error(request, f'❌ Error dispensing: {str(e)}')
                return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)
            except Exception as e:
                logger.error(f"Error dispensing medication: {str(e)}", exc_info=True)
                messages.error(request, f'❌ Error dispensing: {str(e)}')
                return redirect('hospital:pharmacy_dispense_enforced', prescription_id=prescription.id)
    
    # Get dispensing record
    try:
        dispensing_record = prescription.dispensing_record
    except:
        dispensing_record = None
    
    # Check for existing receipts for this patient (in case payment was made but not linked)
    recent_receipts = PaymentReceipt.objects.filter(
        patient=patient,
        service_type='pharmacy',
        is_deleted=False
    ).order_by('-created')[:5]
    
    context = {
        'title': f'Dispense Medication - {drug.name}',
        'prescription': prescription,
        'patient': patient,
        'drug': drug,
        'unit_price': unit_price,
        'total_cost': total_cost,
        'payment_status': payment_status,
        'dispensing_record': dispensing_record,
        'receipt': payment_status.get('receipt'),
        'is_already_dispensed': is_already_dispensed,
        'recent_receipts': recent_receipts,
    }
    return render(request, 'hospital/pharmacy_dispense_enforced.html', context)


@login_required
def check_pharmacy_payment_required(request, prescription_id):
    """
    API to check if prescription requires payment
    Used by pharmacists before dispensing
    """
    payment_status = AutoBillingService.check_payment_status('pharmacy', prescription_id)
    
    return JsonResponse({
        'paid': payment_status['paid'],
        'status': payment_status['status'],
        'message': payment_status['message'],
        'receipt_number': payment_status['receipt'].receipt_number if payment_status.get('receipt') else None
    })






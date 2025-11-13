"""
🔒 PHARMACY DISPENSING - PAYMENT ENFORCED
Cannot dispense drugs without payment verification
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from decimal import Decimal
import logging

from .models import Prescription, Patient, Staff
from .models_accounting import PaymentReceipt
from .models_payment_verification import PharmacyDispensing
from .services.auto_billing_service import AutoBillingService

logger = logging.getLogger(__name__)


@login_required
def pharmacy_pending_dispensing(request):
    """
    Show prescriptions awaiting payment or ready for dispensing
    Pharmacists use this to see what can/cannot be dispensed
    """
    # Get all active prescriptions
    prescriptions = Prescription.objects.filter(
        is_deleted=False
    ).select_related(
        'drug', 'order__encounter__patient', 'prescribed_by'
    ).order_by('-created')
    
    # Categorize by payment status
    pending_payment = []
    paid_ready_to_dispense = []
    already_dispensed = []
    
    for rx in prescriptions:
        try:
            dispensing_record = rx.dispensing_record
            
            if dispensing_record.dispensing_status == 'pending_payment':
                pending_payment.append(rx)
            elif dispensing_record.dispensing_status == 'ready_to_dispense':
                paid_ready_to_dispense.append(rx)
            elif dispensing_record.dispensing_status in ['fully_dispensed', 'partially_dispensed']:
                already_dispensed.append(rx)
        except:
            # No dispensing record - create bill and record
            from hospital.services.auto_billing_service import AutoBillingService
            AutoBillingService.create_pharmacy_bill(rx)
            pending_payment.append(rx)
    
    stats = {
        'pending_payment': len(pending_payment),
        'paid_ready': len(paid_ready_to_dispense),
        'dispensed': len(already_dispensed),
        'total': prescriptions.count()
    }
    
    context = {
        'title': '💊 Pharmacy Dispensing - Payment Enforced',
        'pending_payment': pending_payment[:20],
        'paid_ready_to_dispense': paid_ready_to_dispense[:20],
        'already_dispensed': already_dispensed[:10],
        'stats': stats,
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
        from hospital.services.auto_billing_service import AutoBillingService
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
    
    # Check payment BEFORE allowing any action
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # ENFORCE: Payment must be made at CASHIER first
        if action == 'dispense':
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
                
                # Mark as dispensed
                dispensing_record.mark_dispensed(
                    user=request.user,
                    quantity=quantity,
                    instructions=instructions,
                    notes=notes
                )
                
                dispensing_record.counselling_given = counselling_given
                if current_staff:
                    dispensing_record.counselled_by = current_staff
                dispensing_record.save()
                
                # If inpatient, create MAR schedule
                if is_inpatient:
                    try:
                        from hospital.services.mar_generator import create_mar_schedule
                        create_mar_schedule(prescription)
                        messages.info(request, '📋 MAR schedule created for inpatient medication administration')
                    except Exception as e:
                        logger.error(f"Error creating MAR: {str(e)}")
                
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
                        sms_service.send_sms(patient.phone_number, message, 'pharmacy_dispensing', patient)
                except Exception as e:
                    logger.error(f"Error sending SMS: {str(e)}")
                
                return redirect('hospital:pharmacy_pending_dispensing')
                
            except Exception as e:
                logger.error(f"Error dispensing medication: {str(e)}")
                messages.error(request, f'❌ Error dispensing: {str(e)}')
    
    # Get dispensing record
    try:
        dispensing_record = prescription.dispensing_record
    except:
        dispensing_record = None
    
    # Check for existing receipts for this patient (in case payment was made but not linked)
    recent_receipts = PaymentReceipt.objects.filter(
        patient=patient,
        payment_type='pharmacy',
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






"""
IMPROVED Pharmacy Payment Verification System
Simplified workflow for better usability
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from decimal import Decimal
import logging

from .models import Prescription, Patient, Staff, Drug
from .models_payment_verification import PharmacyDispensing
from .models_accounting import PaymentReceipt
from .utils_billing import get_drug_price_for_prescription

logger = logging.getLogger(__name__)


@login_required
def pharmacy_quick_payment(request, prescription_id):
    """
    SIMPLIFIED: One-click payment and dispensing for pharmacy
    Combines payment recording + dispensing in one smooth flow
    """
    prescription = get_object_or_404(Prescription, id=prescription_id, is_deleted=False)
    patient = prescription.order.encounter.patient
    drug = prescription.drug
    payer = getattr(patient, 'primary_insurance', None)
    # Use main pharmacy dispensary price (same as cashier and doctor prescribing)
    unit_price = get_drug_price_for_prescription(drug, payer=payer)
    total_cost = unit_price * prescription.quantity
    
    # Pharmacy queue row must exist before payer billing (same rule as main workflow)
    from .services.auto_billing_service import AutoBillingService

    AutoBillingService.create_pharmacy_dispensing_record_only(prescription)
    billing_result = AutoBillingService.create_pharmacy_bill(prescription)
    dispensing_record = PharmacyDispensing.objects.filter(
        prescription=prescription, is_deleted=False
    ).first()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'record_payment':
            # Record payment
            try:
                amount_paid = Decimal(request.POST.get('amount_paid', str(total_cost)))
                payment_method = request.POST.get('payment_method', 'cash')
                
                # Get current staff
                try:
                    staff = Staff.objects.get(user=request.user, is_active=True)
                except Staff.DoesNotExist:
                    staff = None
                
                # Create payment receipt
                # Check for duplicate receipt before creating
                from datetime import timedelta
                from django.utils import timezone
                recent_cutoff = timezone.now() - timedelta(minutes=1)
                
                existing_receipt = PaymentReceipt.objects.filter(
                    patient=patient,
                    amount=amount_paid,
                    payment_method=payment_method,
                    payment_type='pharmacy',
                    receipt_date__gte=recent_cutoff,
                    notes__icontains=f"Prescription #{prescription.id}",
                    is_deleted=False
                ).first()
                
                if not existing_receipt:
                    receipt = PaymentReceipt.objects.create(
                        patient=patient,
                        amount=amount_paid,
                        payment_method=payment_method,
                        payment_type='pharmacy',
                        received_by=staff,
                        notes=f"Pharmacy: {drug.name} x{prescription.quantity} (Prescription #{prescription.id})"
                    )
                else:
                    receipt = existing_receipt
                
                # Link receipt to dispensing record
                if dispensing_record:
                    dispensing_record.payment_receipt = receipt
                    dispensing_record.payment_verified_at = timezone.now()
                    dispensing_record.payment_verified_by = request.user
                    dispensing_record.dispensing_status = 'ready_to_dispense'
                    dispensing_record.save()
                    
                    messages.success(
                        request,
                        f'✅ Payment received: GHS {amount_paid}. Receipt: {receipt.receipt_number}. '
                        f'Ready to dispense!'
                    )
                else:
                    messages.success(
                        request,
                        f'✅ Payment received: GHS {amount_paid}. Receipt: {receipt.receipt_number}.'
                    )
                
                # If user wants to dispense immediately
                if request.POST.get('dispense_now') == 'yes':
                    return redirect('hospital:pharmacy_quick_dispense', prescription_id=prescription.id)
                
                return redirect('hospital:pharmacy_pending_dispensing')
                
            except Exception as e:
                logger.error(f"Error recording payment: {str(e)}", exc_info=True)
                messages.error(request, f'❌ Error recording payment: {str(e)}')
        
        elif action == 'mark_paid':
            # Mark as paid without creating new receipt (if already paid elsewhere)
            try:
                receipt_number = request.POST.get('receipt_number', '')
                
                # Find existing receipt
                receipt = PaymentReceipt.objects.filter(
                    Q(receipt_number=receipt_number) | Q(patient=patient),
                    is_deleted=False
                ).order_by('-created').first()
                
                if receipt and dispensing_record:
                    dispensing_record.payment_receipt = receipt
                    dispensing_record.payment_verified_at = timezone.now()
                    dispensing_record.payment_verified_by = request.user
                    dispensing_record.dispensing_status = 'ready_to_dispense'
                    dispensing_record.save()
                    
                    messages.success(
                        request,
                        f'✅ Payment verified with receipt {receipt.receipt_number}. Ready to dispense!'
                    )
                else:
                    messages.error(request, '❌ Receipt not found. Please record payment first.')
                
                return redirect('hospital:pharmacy_pending_dispensing')
                
            except Exception as e:
                logger.error(f"Error marking as paid: {str(e)}", exc_info=True)
                messages.error(request, f'❌ Error: {str(e)}')
    
    # Check existing payments
    existing_receipts = PaymentReceipt.objects.filter(
        patient=patient,
        payment_type='pharmacy',
        is_deleted=False
    ).order_by('-created')[:5]
    
    context = {
        'title': f'Payment - {drug.name}',
        'prescription': prescription,
        'patient': patient,
        'drug': drug,
        'unit_price': unit_price,
        'total_cost': total_cost,
        'dispensing_record': dispensing_record,
        'existing_receipts': existing_receipts,
    }
    return render(request, 'hospital/pharmacy_quick_payment.html', context)


@login_required
def pharmacy_quick_dispense(request, prescription_id):
    """
    SIMPLIFIED: Quick dispense after payment verified
    """
    prescription = get_object_or_404(Prescription, id=prescription_id, is_deleted=False)
    patient = prescription.order.encounter.patient
    drug = prescription.drug
    
    # Get dispensing record
    try:
        dispensing_record = prescription.dispensing_record
    except:
        messages.error(request, '❌ No dispensing record found. Create bill first.')
        return redirect('hospital:pharmacy_pending_dispensing')
    
    # Check payment
    if not dispensing_record.can_dispense():
        messages.error(
            request,
            f'❌ PAYMENT REQUIRED! Patient must pay first. Status: {dispensing_record.get_dispensing_status_display()}'
        )
        return redirect('hospital:pharmacy_quick_payment', prescription_id=prescription.id)
    
    if request.method == 'POST':
        try:
            # Get current staff
            try:
                staff = Staff.objects.get(user=request.user, is_active=True)
            except Staff.DoesNotExist:
                staff = None
            
            # Get dispensing details
            quantity = int(request.POST.get('quantity', prescription.quantity))
            instructions = request.POST.get('instructions', f"{prescription.dose}, {prescription.frequency}, {prescription.duration}")
            counselling_given = request.POST.get('counselling_given') == 'on'
            notes = request.POST.get('notes', '')
            
            # Mark as dispensed
            dispensing_record.mark_dispensed(
                user=request.user,
                quantity=quantity,
                instructions=instructions,
                notes=notes
            )
            
            dispensing_record.counselling_given = counselling_given
            if staff:
                dispensing_record.counselled_by = staff
                dispensing_record.dispensed_by = staff
            dispensing_record.dispensed_at = timezone.now()
            dispensing_record.save()
            
            # Reduce stock (skip if already reduced at Send to Payer)
            if not getattr(dispensing_record, 'stock_reduced_at', None):
                try:
                    from .pharmacy_stock_utils import reduce_pharmacy_stock
                    drug_to_dispense = dispensing_record.drug_to_dispense or drug
                    shortfall = reduce_pharmacy_stock(drug_to_dispense, quantity)
                    if shortfall > 0:
                        messages.warning(request, f'⚠️ Insufficient stock. Short by {shortfall} units.')
                except Exception as e:
                    logger.error(f"Error reducing stock: {str(e)}", exc_info=True)
                    messages.error(request, f'Could not update stock: {str(e)}')
            
            # Do not send payment/dispensing feedback SMS for insurance/corporate billing.
            patient_payer = getattr(patient, 'primary_insurance', None)
            payer_type = getattr(patient_payer, 'payer_type', '') if patient_payer else ''
            should_send_feedback_sms = payer_type not in ('insurance', 'private', 'nhis', 'corporate')
            if should_send_feedback_sms:
                try:
                    from .services.patient_feedback_service import send_customer_service_review_sms
                    send_customer_service_review_sms(
                        patient,
                        message_type='pharmacy_dispensing_feedback',
                        related_object_id=dispensing_record.id if hasattr(dispensing_record, 'id') else None,
                        related_object_type='PharmacyDispensing',
                    )
                except Exception as e:
                    logger.warning("Could not send customer service review SMS: %s", e)
            
            messages.success(
                request,
                f'✅ Medication dispensed to {patient.full_name}! '
                f'Receipt: {dispensing_record.payment_receipt.receipt_number}'
            )
            
            return redirect('hospital:pharmacy_pending_dispensing')
            
        except Exception as e:
            logger.error(f"Error dispensing: {str(e)}", exc_info=True)
            messages.error(request, f'❌ Error: {str(e)}')
    
    context = {
        'title': f'Dispense - {drug.name}',
        'prescription': prescription,
        'patient': patient,
        'drug': drug,
        'dispensing_record': dispensing_record,
    }
    return render(request, 'hospital/pharmacy_quick_dispense.html', context)


@login_required
def pharmacy_payment_status_check(request, prescription_id):
    """
    API endpoint to check payment status
    """
    try:
        prescription = Prescription.objects.get(id=prescription_id, is_deleted=False)
        
        try:
            dispensing_record = prescription.dispensing_record
            has_payment = dispensing_record.payment_receipt is not None
            
            return JsonResponse({
                'success': True,
                'paid': has_payment,
                'status': dispensing_record.dispensing_status,
                'status_display': dispensing_record.get_dispensing_status_display(),
                'can_dispense': dispensing_record.can_dispense(),
                'receipt_number': dispensing_record.payment_receipt.receipt_number if has_payment else None,
                'amount': str(dispensing_record.payment_receipt.amount) if has_payment else None,
            })
        except:
            return JsonResponse({
                'success': True,
                'paid': False,
                'status': 'pending_payment',
                'status_display': 'Pending Payment',
                'can_dispense': False,
                'message': 'No dispensing record found'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })






















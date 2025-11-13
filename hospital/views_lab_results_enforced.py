"""
🔒 LAB RESULTS - PAYMENT ENFORCED
Cannot release results without payment verification
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from decimal import Decimal
import logging

from .models import LabResult, Patient
from .models_accounting import PaymentReceipt
from .models_payment_verification import LabResultRelease
from .services.auto_billing_service import AutoBillingService

logger = logging.getLogger(__name__)


@login_required
def lab_results_pending_release(request):
    """
    Show lab results that are completed but awaiting payment
    Lab technicians use this to see which results cannot be released yet
    """
    # Get all completed lab results
    completed_results = LabResult.objects.filter(
        is_deleted=False,
        verified_by__isnull=False  # Results verified by lab
    ).select_related(
        'test', 'order__encounter__patient', 'verified_by'
    ).order_by('-verified_at')
    
    # Categorize by payment status
    pending_payment = []
    paid_ready_to_release = []
    already_released = []
    
    for lab in completed_results:
        try:
            release_record = lab.release_record
            
            if release_record.release_status == 'pending_payment':
                pending_payment.append(lab)
            elif release_record.release_status == 'ready_for_release':
                paid_ready_to_release.append(lab)
            elif release_record.release_status in ['released', 'emailed']:
                already_released.append(lab)
        except:
            # No release record - create one
            from hospital.services.auto_billing_service import AutoBillingService
            AutoBillingService.create_lab_bill(lab)
            pending_payment.append(lab)
    
    stats = {
        'pending_payment': len(pending_payment),
        'paid_ready': len(paid_ready_to_release),
        'released': len(already_released),
        'total': completed_results.count()
    }
    
    context = {
        'title': '🧪 Lab Results - Payment Enforced',
        'pending_payment': pending_payment[:20],
        'paid_ready_to_release': paid_ready_to_release[:20],
        'already_released': already_released[:10],
        'stats': stats,
    }
    return render(request, 'hospital/lab_results_payment_enforced.html', context)


@login_required
def lab_result_release_enforced(request, lab_result_id):
    """
    Release lab result - ONLY if payment verified
    """
    lab_result = get_object_or_404(LabResult, id=lab_result_id, is_deleted=False)
    patient = lab_result.order.encounter.patient
    
    # Check payment status
    payment_status = AutoBillingService.check_payment_status('lab', lab_result_id)
    
    if not payment_status['paid']:
        messages.error(
            request,
            f'❌ PAYMENT REQUIRED! Patient must pay at cashier before results can be released. '
            f'Status: {payment_status["message"]}'
        )
        return redirect('hospital:lab_results_pending_release')
    
    # Payment verified - can release
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'release':
            try:
                release_record = lab_result.release_record
                
                # Record release details
                released_to = request.POST.get('released_to', patient.full_name)
                relationship = request.POST.get('relationship', 'Self')
                id_type = request.POST.get('id_type', '')
                id_number = request.POST.get('id_number', '')
                notes = request.POST.get('notes', '')
                
                release_record.mark_released(
                    user=request.user,
                    released_to_name=released_to,
                    relationship=relationship,
                    id_type=id_type,
                    id_number=id_number,
                    notes=notes
                )
                
                messages.success(
                    request,
                    f'✅ Lab results released to {released_to}. Payment verified via receipt {payment_status["receipt"].receipt_number}'
                )
                
                # Send multi-channel notification (SMS, WhatsApp, Email)
                try:
                    from .services.multichannel_notification_service import multichannel_service
                    multichannel_service.send_lab_result_notification(
                        lab_result=lab_result,
                        include_attachment=False,  # Set to True if you want to include PDF
                        pdf_path=''  # Add PDF path if available
                    )
                    logger.info(f"Multi-channel notification sent for lab result {lab_result.id}")
                except Exception as e:
                    logger.error(f"Error sending multi-channel notification: {str(e)}")
                
                return redirect('hospital:lab_results_pending_release')
                
            except Exception as e:
                logger.error(f"Error releasing results: {str(e)}")
                messages.error(request, f'❌ Error releasing results: {str(e)}')
    
    # Get release record
    try:
        release_record = lab_result.release_record
    except:
        release_record = None
    
    # Get test info
    test = lab_result.test
    
    context = {
        'title': f'Release Lab Results - {test.name}',
        'lab_result': lab_result,
        'patient': patient,
        'test': test,
        'payment_status': payment_status,
        'release_record': release_record,
        'receipt': payment_status.get('receipt'),
    }
    return render(request, 'hospital/lab_result_release_enforced.html', context)


@login_required  
def check_lab_payment_required(request, lab_result_id):
    """
    API to check if lab result requires payment
    Used by lab technicians before releasing results
    """
    payment_status = AutoBillingService.check_payment_status('lab', lab_result_id)
    
    return JsonResponse({
        'paid': payment_status['paid'],
        'status': payment_status['status'],
        'message': payment_status['message'],
        'receipt_number': payment_status['receipt'].receipt_number if payment_status.get('receipt') else None
    })


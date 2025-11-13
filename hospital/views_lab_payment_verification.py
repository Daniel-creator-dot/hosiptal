"""
🔒 LAB PAYMENT VERIFICATION SYSTEM
Lab staff verifies payment by receipt number before releasing results
World-class payment verification workflow
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q

from .models import LabResult
from .models_accounting import PaymentReceipt
from .models_payment_verification import LabResultRelease


@login_required
def lab_payment_verification_dashboard(request):
    """
    Lab payment verification dashboard
    Shows tests awaiting payment verification
    """
    # Get completed lab results without payment verification
    pending_verification = LabResult.objects.filter(
        status='completed',
        is_deleted=False
    ).select_related(
        'test', 
        'order__encounter__patient',
        'verified_by__user'
    ).exclude(
        release_record__payment_verified=True
    ).order_by('-verified_at')
    
    # Get recently verified results
    recently_verified = LabResult.objects.filter(
        status='completed',
        is_deleted=False,
        release_record__payment_verified=True,
        release_record__payment_verified_at__gte=timezone.now() - timezone.timedelta(hours=24)
    ).select_related(
        'test',
        'order__encounter__patient',
        'release_record__payment_verified_by'
    ).order_by('-release_record__payment_verified_at')[:10]
    
    context = {
        'title': 'Lab Payment Verification',
        'pending_verification': pending_verification,
        'recently_verified': recently_verified,
    }
    
    return render(request, 'hospital/lab/payment_verification_dashboard.html', context)


@login_required
def lab_verify_payment_by_receipt(request, lab_result_id):
    """
    Verify payment for lab result using receipt number
    Lab staff enters receipt number to verify payment
    """
    lab_result = get_object_or_404(LabResult, id=lab_result_id, is_deleted=False)
    patient = lab_result.order.encounter.patient
    
    if request.method == 'POST':
        receipt_number = request.POST.get('receipt_number', '').strip()
        
        if not receipt_number:
            messages.error(request, "❌ Please enter receipt number")
            return redirect('hospital:lab_verify_payment', lab_result_id=lab_result_id)
        
        # Search for receipt
        try:
            receipt = PaymentReceipt.objects.get(
                receipt_number=receipt_number,
                is_deleted=False
            )
            
            # Verify receipt is for this patient
            if receipt.patient.id != patient.id:
                messages.error(
                    request, 
                    f"❌ Receipt {receipt_number} belongs to different patient: {receipt.patient.full_name}"
                )
                return redirect('hospital:lab_verify_payment', lab_result_id=lab_result_id)
            
            # Check if receipt is for lab test
            if 'lab' not in receipt.description.lower() and lab_result.test.name.lower() not in receipt.description.lower():
                messages.warning(
                    request,
                    f"⚠️ Receipt found but may not be for this test. Receipt description: {receipt.description}"
                )
            
            # Create or update release record with payment verification
            release_record, created = LabResultRelease.objects.get_or_create(
                lab_result=lab_result,
                defaults={
                    'payment_verified': True,
                    'payment_verified_by': request.user,
                    'payment_verified_at': timezone.now(),
                    'payment_receipt': receipt,
                    'release_status': 'verified'
                }
            )
            
            if not created:
                # Update existing record
                release_record.payment_verified = True
                release_record.payment_verified_by = request.user
                release_record.payment_verified_at = timezone.now()
                release_record.payment_receipt = receipt
                release_record.release_status = 'verified'
                release_record.save()
            
            messages.success(
                request,
                f"✅ Payment verified! Receipt {receipt_number} - GHS {receipt.amount_paid}. "
                f"Results can now be released to {patient.full_name}."
            )
            
            return redirect('hospital:lab_payment_verification_dashboard')
            
        except PaymentReceipt.DoesNotExist:
            messages.error(
                request,
                f"❌ Receipt {receipt_number} not found. Please verify the receipt number and try again."
            )
            return redirect('hospital:lab_verify_payment', lab_result_id=lab_result_id)
    
    # GET request - show verification form
    # Check if already has payment record
    existing_receipt = None
    try:
        if hasattr(lab_result, 'release_record') and lab_result.release_record.payment_receipt:
            existing_receipt = lab_result.release_record.payment_receipt
    except:
        pass
    
    context = {
        'title': 'Verify Payment',
        'lab_result': lab_result,
        'patient': patient,
        'test_price': lab_result.test.price if hasattr(lab_result.test, 'price') else None,
        'existing_receipt': existing_receipt,
    }
    
    return render(request, 'hospital/lab/verify_payment_form.html', context)


@require_POST
@login_required
def lab_search_receipt_api(request):
    """
    API endpoint to search for receipt
    Returns receipt details if found
    """
    import json
    
    try:
        data = json.loads(request.body)
        receipt_number = data.get('receipt_number', '').strip()
        
        if not receipt_number:
            return JsonResponse({
                'success': False,
                'message': 'Receipt number required'
            }, status=400)
        
        receipt = PaymentReceipt.objects.get(
            receipt_number=receipt_number,
            is_deleted=False
        )
        
        return JsonResponse({
            'success': True,
            'receipt': {
                'receipt_number': receipt.receipt_number,
                'amount': float(receipt.amount_paid),
                'date': receipt.receipt_date.strftime('%d %b %Y %I:%M %p'),
                'patient_name': receipt.patient.full_name,
                'patient_mrn': receipt.patient.mrn,
                'description': receipt.description,
                'payment_method': receipt.payment_method,
                'received_by': receipt.received_by.get_full_name() if receipt.received_by else '',
            }
        })
        
    except PaymentReceipt.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': f'Receipt {receipt_number} not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
def lab_release_result(request, lab_result_id):
    """
    Release lab result to patient/doctor
    Requires payment verification
    """
    lab_result = get_object_or_404(LabResult, id=lab_result_id, is_deleted=False)
    patient = lab_result.order.encounter.patient
    
    # Check if payment verified
    if not hasattr(lab_result, 'release_record') or not lab_result.release_record.payment_verified:
        messages.error(
            request,
            "❌ Payment not verified. Please verify payment before releasing results."
        )
        return redirect('hospital:lab_verify_payment', lab_result_id=lab_result_id)
    
    if request.method == 'POST':
        released_to = request.POST.get('released_to', 'patient')
        notes = request.POST.get('notes', '')
        
        # Update release record
        release_record = lab_result.release_record
        release_record.release_status = 'released'
        release_record.released_at = timezone.now()
        release_record.released_by = request.user
        release_record.released_to = released_to
        release_record.release_notes = notes
        release_record.save()
        
        messages.success(
            request,
            f"✅ Lab results released to {released_to}. Receipt: {release_record.payment_receipt.receipt_number}"
        )
        
        return redirect('hospital:lab_payment_verification_dashboard')
    
    context = {
        'title': 'Release Lab Result',
        'lab_result': lab_result,
        'patient': patient,
        'release_record': lab_result.release_record,
    }
    
    return render(request, 'hospital/lab/release_result_form.html', context)


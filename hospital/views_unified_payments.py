"""
🏆 WORLD-CLASS UNIFIED PAYMENT VIEWS
Handles payments from all service points with automatic QR receipts
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from decimal import Decimal
import json
import logging

from .services.unified_receipt_service import (
    UnifiedReceiptService,
    LabPaymentService,
    PharmacyPaymentService,
    ImagingPaymentService,
    ConsultationPaymentService,
    ProcedurePaymentService
)
from .models import Patient, Encounter, LabResult, Prescription
from .models_accounting import PaymentReceipt, Transaction

logger = logging.getLogger(__name__)


# ========== LAB PAYMENT ==========

@login_required
def lab_payment_process(request, lab_result_id):
    """
    Process payment for lab test
    """
    lab_result = get_object_or_404(LabResult, id=lab_result_id, is_deleted=False)
    patient = lab_result.order.encounter.patient
    
    # Get test price
    test_price = lab_result.test.price if hasattr(lab_result.test, 'price') else Decimal('0.00')
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', test_price))
        payment_method = request.POST.get('payment_method', 'cash')
        notes = request.POST.get('notes', '')
        
        # Create receipt with QR code
        result = LabPaymentService.create_lab_payment_receipt(
            lab_result=lab_result,
            amount=amount,
            payment_method=payment_method,
            received_by_user=request.user,
            notes=notes
        )
        
        if result['success']:
            messages.success(
                request,
                f"✅ Payment received! Receipt {result['receipt'].receipt_number} with QR code generated."
            )
            return redirect('hospital:receipt_print', receipt_id=result['receipt'].id)
        else:
            messages.error(request, f"❌ Payment failed: {result.get('message', 'Unknown error')}")
    
    context = {
        'title': 'Lab Test Payment',
        'lab_result': lab_result,
        'patient': patient,
        'test_price': test_price,
        'payment_methods': Transaction.PAYMENT_METHODS,
    }
    return render(request, 'hospital/unified_payment_form.html', context)


@login_required
def pharmacy_payment_process(request, prescription_id):
    """
    Process payment for pharmacy prescription
    """
    prescription = get_object_or_404(Prescription, id=prescription_id, is_deleted=False)
    patient = prescription.order.encounter.patient
    
    # Calculate drug cost
    drug_price = prescription.drug.unit_price if hasattr(prescription.drug, 'unit_price') else Decimal('0.00')
    total_cost = drug_price * prescription.quantity
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', total_cost))
        payment_method = request.POST.get('payment_method', 'cash')
        notes = request.POST.get('notes', '')
        
        # Create receipt with QR code
        result = PharmacyPaymentService.create_pharmacy_payment_receipt(
            prescription=prescription,
            amount=amount,
            payment_method=payment_method,
            received_by_user=request.user,
            notes=notes
        )
        
        if result['success']:
            messages.success(
                request,
                f"✅ Payment received! Receipt {result['receipt'].receipt_number} with QR code generated."
            )
            return redirect('hospital:receipt_print', receipt_id=result['receipt'].id)
        else:
            messages.error(request, f"❌ Payment failed: {result.get('message', 'Unknown error')}")
    
    context = {
        'title': 'Pharmacy Payment',
        'prescription': prescription,
        'patient': patient,
        'drug_price': drug_price,
        'total_cost': total_cost,
        'payment_methods': Transaction.PAYMENT_METHODS,
    }
    return render(request, 'hospital/unified_payment_form.html', context)


@login_required
def imaging_payment_process(request, imaging_study_id):
    """
    Process payment for imaging study
    """
    from .models_advanced import ImagingStudy
    
    imaging_study = get_object_or_404(ImagingStudy, id=imaging_study_id, is_deleted=False)
    patient = imaging_study.order.encounter.patient if hasattr(imaging_study, 'order') else imaging_study.patient
    
    # Get imaging cost
    imaging_cost = Decimal('50.00')  # Default or fetch from pricing
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', imaging_cost))
        payment_method = request.POST.get('payment_method', 'cash')
        notes = request.POST.get('notes', '')
        
        # Create receipt with QR code
        result = ImagingPaymentService.create_imaging_payment_receipt(
            imaging_study=imaging_study,
            amount=amount,
            payment_method=payment_method,
            received_by_user=request.user,
            notes=notes
        )
        
        if result['success']:
            # Mark imaging study as paid
            imaging_study.mark_as_paid(
                amount=amount,
                receipt_number=result['receipt'].receipt_number
            )
            
            messages.success(
                request,
                f"✅ Payment received! Receipt {result['receipt'].receipt_number} with QR code generated."
            )
            return redirect('hospital:receipt_print', receipt_id=result['receipt'].id)
        else:
            messages.error(request, f"❌ Payment failed: {result.get('message', 'Unknown error')}")
    
    context = {
        'title': 'Imaging Payment',
        'imaging_study': imaging_study,
        'patient': patient,
        'imaging_cost': imaging_cost,
        'payment_methods': Transaction.PAYMENT_METHODS,
    }
    return render(request, 'hospital/unified_payment_form.html', context)


@login_required
def consultation_payment_process(request, encounter_id):
    """
    Process payment for consultation
    """
    encounter = get_object_or_404(Encounter, id=encounter_id, is_deleted=False)
    patient = encounter.patient
    
    # Get consultation fee
    consultation_fee = Decimal('30.00')  # Default or fetch from pricing
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', consultation_fee))
        payment_method = request.POST.get('payment_method', 'cash')
        notes = request.POST.get('notes', '')
        
        # Create receipt with QR code
        result = ConsultationPaymentService.create_consultation_payment_receipt(
            encounter=encounter,
            amount=amount,
            payment_method=payment_method,
            received_by_user=request.user,
            notes=notes
        )
        
        if result['success']:
            messages.success(
                request,
                f"✅ Payment received! Receipt {result['receipt'].receipt_number} with QR code generated."
            )
            return redirect('hospital:receipt_print', receipt_id=result['receipt'].id)
        else:
            messages.error(request, f"❌ Payment failed: {result.get('message', 'Unknown error')}")
    
    context = {
        'title': 'Consultation Payment',
        'encounter': encounter,
        'patient': patient,
        'consultation_fee': consultation_fee,
        'payment_methods': Transaction.PAYMENT_METHODS,
    }
    return render(request, 'hospital/unified_payment_form.html', context)


# ========== RECEIPT VERIFICATION ==========

@login_required
def receipt_verify_qr(request):
    """
    Verify receipt by scanning QR code
    """
    if request.method == 'POST':
        qr_data = request.POST.get('qr_data')
        
        result = UnifiedReceiptService.verify_receipt_by_qr(
            qr_data_string=qr_data,
            verified_by_user=request.user
        )
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('hospital:receipt_detail', receipt_id=result['receipt'].id)
        else:
            messages.error(request, result['message'])
    
    context = {
        'title': 'Verify Receipt - QR Code',
    }
    return render(request, 'hospital/receipt_verify_qr.html', context)


@login_required
def receipt_verify_number(request):
    """
    Verify receipt by entering receipt number
    """
    if request.method == 'POST':
        receipt_number = request.POST.get('receipt_number')
        
        result = UnifiedReceiptService.verify_receipt_by_number(
            receipt_number=receipt_number,
            verified_by_user=request.user
        )
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('hospital:receipt_detail', receipt_id=result['receipt'].id)
        else:
            messages.error(request, result['message'])
    
    context = {
        'title': 'Verify Receipt - Number',
    }
    return render(request, 'hospital/receipt_verify_number.html', context)


@login_required
def receipt_detail(request, receipt_id):
    """
    View receipt details
    """
    receipt = get_object_or_404(PaymentReceipt, id=receipt_id, is_deleted=False)
    
    # Get QR code if exists
    qr_code = None
    try:
        qr_code = receipt.qr_code
    except:
        pass
    
    context = {
        'title': f'Receipt {receipt.receipt_number}',
        'receipt': receipt,
        'qr_code': qr_code,
    }
    return render(request, 'hospital/receipt_detail.html', context)


@login_required
def receipt_print(request, receipt_id):
    """
    Print receipt with QR code
    """
    receipt = get_object_or_404(PaymentReceipt, id=receipt_id, is_deleted=False)
    
    # Get QR code
    qr_code = None
    try:
        qr_code = receipt.qr_code
    except:
        # Generate QR code if not exists
        from .models_payment_verification import ReceiptQRCode
        qr_data = UnifiedReceiptService._generate_qr_data(receipt)
        qr_code = ReceiptQRCode.objects.create(
            receipt=receipt,
            qr_code_data=qr_data
        )
        qr_code.generate_qr_code()
        qr_code.save()
    
    context = {
        'title': f'Print Receipt {receipt.receipt_number}',
        'receipt': receipt,
        'qr_code': qr_code,
    }
    return render(request, 'hospital/receipt_print.html', context)


# ========== API ENDPOINTS ==========

@require_POST
@login_required
def api_verify_receipt_qr(request):
    """
    API endpoint to verify receipt by QR code
    """
    try:
        data = json.loads(request.body)
        qr_data = data.get('qr_data')
        
        result = UnifiedReceiptService.verify_receipt_by_qr(
            qr_data_string=qr_data,
            verified_by_user=request.user
        )
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'receipt_number': result['receipt'].receipt_number,
                'patient_name': result['patient'].full_name,
                'amount': str(result['amount']),
                'date': result['date'].isoformat(),
                'service_type': result.get('service_type', 'general'),
                'message': result['message']
            })
        else:
            return JsonResponse({
                'success': False,
                'message': result['message']
            }, status=400)
            
    except Exception as e:
        logger.error(f"Error in API verify receipt: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@require_GET
@login_required
def api_receipt_details(request, receipt_number):
    """
    API endpoint to get receipt details
    """
    try:
        receipt = PaymentReceipt.objects.get(
            receipt_number=receipt_number,
            is_deleted=False
        )
        
        return JsonResponse({
            'success': True,
            'receipt': {
                'receipt_number': receipt.receipt_number,
                'amount': str(receipt.amount_paid),
                'payment_method': receipt.payment_method,
                'date': receipt.receipt_date.isoformat(),
                'patient': {
                    'mrn': receipt.patient.mrn,
                    'name': receipt.patient.full_name,
                },
                'received_by': receipt.received_by.get_full_name() if receipt.received_by else '',
            }
        })
        
    except PaymentReceipt.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Receipt not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)



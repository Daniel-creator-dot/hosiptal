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
from .utils_billing import get_drug_price_for_prescription, get_consultation_price_for_encounter

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
            # Redirect to POS receipt with auto-print
            from django.urls import reverse
            pos_url = reverse('hospital:receipt_pos_print', args=[result['receipt'].id]) + '?auto_print=1'
            return redirect(pos_url)
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
    payer = getattr(patient, 'primary_insurance', None)
    # Use main pharmacy dispensary price (same source as cashier)
    drug_price = get_drug_price_for_prescription(prescription.drug, payer=payer)
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
            # Redirect to POS receipt with auto-print
            from django.urls import reverse
            pos_url = reverse('hospital:receipt_pos_print', args=[result['receipt'].id]) + '?auto_print=1'
            return redirect(pos_url)
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
            # Redirect to POS receipt with auto-print
            from django.urls import reverse
            pos_url = reverse('hospital:receipt_pos_print', args=[result['receipt'].id]) + '?auto_print=1'
            return redirect(pos_url)
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
    
    # Get consultation fee (same as billing: 150 general / 300 specialist / doctor-specific)
    consultation_fee = get_consultation_price_for_encounter(encounter)
    
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
            # Redirect to POS receipt with auto-print
            from django.urls import reverse
            pos_url = reverse('hospital:receipt_pos_print', args=[result['receipt'].id]) + '?auto_print=1'
            return redirect(pos_url)
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


def _receipt_items_paid_for(receipt):
    """Build list of items paid for for receipt display. Each item: {'description': str, 'amount': Decimal}."""
    items = []
    details = getattr(receipt, 'service_details', None) or {}
    if not isinstance(details, dict):
        details = {}
    # Get services list: from receipt.service_details first, then QR code
    services_list = details.get('services') if isinstance(details.get('services'), list) else None
    if not services_list:
        try:
            qr = getattr(receipt, 'qr_code', None)
            if qr and getattr(qr, 'qr_code_data', None):
                qr_data = json.loads(qr.qr_code_data) if isinstance(qr.qr_code_data, str) else (qr.qr_code_data or {})
                inner = qr_data.get('service_details')
                if isinstance(inner, dict) and isinstance(inner.get('services'), list):
                    services_list = inner['services']
                elif isinstance(qr_data.get('services'), list):
                    services_list = qr_data['services']
        except Exception:
            pass
    # Show line items if we have a services list (combined) or receipt is marked combined
    is_combined = (
        getattr(receipt, 'service_type', None) == 'combined'
        or (getattr(receipt, 'notes', None) or '').strip().lower().find('combined') >= 0
        or (details.get('combined_bill') in (True, 'true', 1))
    )
    if services_list and (is_combined or len(services_list) > 1):
        for svc in services_list:
            if not isinstance(svc, dict):
                continue
            # Prescribe Sale (and any service with breakdown): show each line on receipt/invoice
            breakdown = svc.get('breakdown') if isinstance(svc.get('breakdown'), list) else None
            if breakdown:
                for row in breakdown:
                    if row.get('is_waived'):
                        continue
                    try:
                        amt = Decimal(str(row.get('amount', 0)))
                    except Exception:
                        amt = Decimal('0.00')
                    if amt <= 0:
                        continue
                    desc = (row.get('description') or 'Item').strip()
                    qty = row.get('quantity', 1)
                    if qty != 1:
                        desc = f"{desc} x{qty}"
                    items.append({'description': desc, 'amount': amt})
            else:
                name = svc.get('name') or 'Service'
                try:
                    amt = Decimal(str(svc.get('price', 0)))
                except Exception:
                    amt = Decimal('0.00')
                items.append({'description': name, 'amount': amt})
    if not items:
        # Single line: deposit applied, invoice, or service type
        desc = None
        if details.get('deposit_applied'):
            desc = details.get('description') or 'Deposit applied to bill'
        if not desc and getattr(receipt, 'invoice_id', None):
            try:
                desc = f"Invoice: {receipt.invoice.invoice_number}"
            except Exception:
                desc = "Invoice payment"
        if not desc and getattr(receipt, 'service_type', None):
            desc = receipt.get_service_type_display() or "Payment"
        if not desc:
            desc = "Payment"
        items.append({'description': desc, 'amount': receipt.amount_paid or Decimal('0.00')})
    return items


@login_required
def receipt_pos_print(request, receipt_id):
    """
    Print POS receipt (thermal printer format)
    Auto-prints if auto_print=1 in query string
    """
    from django.shortcuts import get_object_or_404
    from .models_accounting import PaymentReceipt
    from .models_payment_verification import ReceiptQRCode
    from .services.unified_receipt_service import UnifiedReceiptService
    
    receipt = get_object_or_404(PaymentReceipt, id=receipt_id, is_deleted=False)
    
    # Get hospital settings
    from .models_settings import HospitalSettings
    hospital_settings = HospitalSettings.get_settings()
    
    # Printer preferences from settings — default 80 (78) × 810 mm for full horizontal fit
    width_mm = getattr(hospital_settings, 'pos_receipt_width_mm', 80)
    printable_mm = getattr(hospital_settings, 'pos_receipt_printable_width_mm', 78)
    length_mm = getattr(hospital_settings, 'pos_receipt_length_mm', 810)
    receipt_config = {
        'width_mm': width_mm,
        'printable_width_mm': min(float(printable_mm), width_mm),  # content width so it fits (avoids "half cut off")
        'length_mm': length_mm,
        'font_body': max(12, getattr(hospital_settings, 'pos_receipt_font_size_body', 12)),
        'font_header': max(14, getattr(hospital_settings, 'pos_receipt_font_size_header', 14)),
        'font_footer': max(10, getattr(hospital_settings, 'pos_receipt_font_size_footer', 10)),
        'margin_mm': getattr(hospital_settings, 'pos_receipt_margin_mm', 4),
        'padding_mm': getattr(hospital_settings, 'pos_receipt_padding_mm', 3),
        'show_qr': getattr(hospital_settings, 'pos_receipt_show_qr', True),
        'qr_size_px': max(56, getattr(hospital_settings, 'pos_receipt_qr_size_px', 64)),
    }
    
    # Get QR code (only if settings say show)
    qr_code = None
    if receipt_config['show_qr']:
        try:
            qr_code = receipt.qr_code
        except Exception:
            qr_data = UnifiedReceiptService._generate_qr_data(receipt)
            qr_code = ReceiptQRCode.objects.create(
                receipt=receipt,
                qr_code_data=qr_data
            )
            qr_code.generate_qr_code()
            qr_code.save()
    
    receipt_items = _receipt_items_paid_for(receipt)
    service_details = getattr(receipt, 'service_details', None) or {}
    is_deposit_applied = service_details.get('deposit_applied', False) if isinstance(service_details, dict) else False
    context = {
        'title': f'POS Receipt - {receipt.receipt_number}',
        'receipt': receipt,
        'receipt_items': receipt_items,
        'qr_code': qr_code,
        'hospital_settings': hospital_settings,
        'receipt_config': receipt_config,
        'is_deposit_applied': is_deposit_applied,
    }
    return render(request, 'hospital/receipt_pos.html', context)


@login_required
def receipt_pos_print_preview(request, receipt_id):
    """
    Minimal standalone receipt page for print preview.
    Renders only the receipt (no nav/sidebar) so the browser can show print preview.
    """
    from django.shortcuts import get_object_or_404
    from .models_accounting import PaymentReceipt
    from .models_payment_verification import ReceiptQRCode
    from .services.unified_receipt_service import UnifiedReceiptService
    from .models_settings import HospitalSettings

    receipt = get_object_or_404(PaymentReceipt, id=receipt_id, is_deleted=False)
    hospital_settings = HospitalSettings.get_settings()
    width_mm = getattr(hospital_settings, 'pos_receipt_width_mm', 80)
    printable_mm = getattr(hospital_settings, 'pos_receipt_printable_width_mm', 78)
    length_mm = getattr(hospital_settings, 'pos_receipt_length_mm', 810)
    receipt_config = {
        'width_mm': width_mm,
        'printable_width_mm': min(float(printable_mm), width_mm),
        'length_mm': length_mm,
        'margin_mm': getattr(hospital_settings, 'pos_receipt_margin_mm', 4),
    }
    qr_code = None
    if getattr(hospital_settings, 'pos_receipt_show_qr', True):
        try:
            qr_code = receipt.qr_code
        except Exception:
            qr_data = UnifiedReceiptService._generate_qr_data(receipt)
            qr_code = ReceiptQRCode.objects.create(receipt=receipt, qr_code_data=qr_data)
            qr_code.generate_qr_code()
            qr_code.save()
    receipt_items = _receipt_items_paid_for(receipt)
    service_details = getattr(receipt, 'service_details', None) or {}
    is_deposit_applied = service_details.get('deposit_applied', False) if isinstance(service_details, dict) else False
    context = {
        'receipt': receipt,
        'receipt_items': receipt_items,
        'qr_code': qr_code,
        'hospital_settings': hospital_settings,
        'receipt_config': receipt_config,
        'is_deposit_applied': is_deposit_applied,
    }
    return render(request, 'hospital/receipt_pos_print_only.html', context)


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



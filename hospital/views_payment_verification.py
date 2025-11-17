"""
World-Class Payment Verification System Views
Receipt verification for lab results and pharmacy dispensing
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from decimal import Decimal
import json
import logging

from .models import Patient, Encounter
from .models_workflow import Bill, PaymentRequest
from .models_accounting import PaymentReceipt, Transaction
from .models_payment_verification import (
    ServicePaymentRequirement, PaymentVerification,
    LabResultRelease, PharmacyDispensing, ReceiptQRCode
)
from .models_pharmacy_walkin import WalkInPharmacySale

logger = logging.getLogger(__name__)


@login_required
def payment_verification_dashboard(request):
    """
    Main dashboard for payment verification
    Shows pending lab results and prescriptions awaiting payment
    """
    # Pending lab results (completed but not released)
    from .models import LabResult
    
    try:
        pending_lab_releases = LabResult.objects.filter(
            is_deleted=False,
            verified_by__isnull=False
        ).select_related(
            'test', 'order__encounter__patient'
        ).order_by('-created')[:50]
        
        # Filter for those without release record or pending payment
        pending_labs = []
        for lab in pending_lab_releases:
            try:
                if not hasattr(lab, 'release_record'):
                    pending_labs.append(lab)
                elif lab.release_record.release_status == 'pending_payment':
                    pending_labs.append(lab)
            except:
                pending_labs.append(lab)
    except Exception as e:
        logger.error(f"Error fetching lab results: {str(e)}")
        pending_labs = []
    
    # Pending prescriptions (not yet dispensed)
    from .models import Prescription
    
    try:
        pending_prescriptions = Prescription.objects.filter(
            is_deleted=False
        ).select_related(
            'drug', 'order__encounter__patient', 'prescribed_by'
        ).order_by('-created')[:50]
        
        # Filter for those without dispensing record or pending payment
        pending_pharmacy = []
        for rx in pending_prescriptions:
            try:
                if not hasattr(rx, 'dispensing_record'):
                    pending_pharmacy.append(rx)
                elif rx.dispensing_record.dispensing_status == 'pending_payment':
                    pending_pharmacy.append(rx)
            except:
                pending_pharmacy.append(rx)
    except Exception as e:
        logger.error(f"Error fetching prescriptions: {str(e)}")
        pending_pharmacy = []
    
    # Statistics
    try:
        verified_today = PaymentVerification.objects.filter(
            verified_at__date=timezone.now().date(),
            verification_status='verified'
        ).count()
    except:
        verified_today = 0
    
    try:
        total_revenue = Transaction.objects.filter(
            transaction_date__date=timezone.now().date()
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    except:
        total_revenue = Decimal('0.00')
    
    stats = {
        'pending_lab_results': len(pending_labs),
        'pending_prescriptions': len(pending_pharmacy),
        'verified_today': verified_today,
        'total_revenue_today': total_revenue,
    }
    
    context = {
        'title': 'Payment Verification Dashboard',
        'pending_labs': pending_labs[:10],
        'pending_pharmacy': pending_pharmacy[:10],
        'stats': stats,
    }
    return render(request, 'hospital/payment_verification_dashboard.html', context)


@login_required  
def lab_result_release_workflow(request):
    """
    Workflow for releasing lab results after payment verification
    """
    from .models import LabResult
    
    # Get all verified lab results
    lab_results = LabResult.objects.filter(
        is_deleted=False,
        verified_by__isnull=False
    ).select_related(
        'test', 'order__encounter__patient'
    ).order_by('-created')
    
    # Add release status to each
    lab_results_with_status = []
    for lab in lab_results:
        try:
            release_record = lab.release_record
            status = release_record.release_status
            payment_verified = release_record.payment_receipt is not None
        except:
            # No release record - create one
            from .models_payment_verification import LabResultRelease
            release_record = LabResultRelease.objects.create(
                lab_result=lab,
                patient=lab.order.encounter.patient,
                release_status='pending_payment'
            )
            status = 'pending_payment'
            payment_verified = False
        
        lab_results_with_status.append({
            'lab_result': lab,
            'release_record': release_record,
            'status': status,
            'payment_verified': payment_verified,
        })
    
    # Filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        lab_results_with_status = [
            item for item in lab_results_with_status 
            if item['status'] == status_filter
        ]
    
    # Calculate stats
    stats = {
        'pending_payment': sum(1 for item in lab_results_with_status if item['status'] == 'pending_payment'),
        'ready_for_release': sum(1 for item in lab_results_with_status if item['status'] == 'ready_for_release'),
        'released': sum(1 for item in lab_results_with_status if item['status'] in ['released', 'emailed']),
    }
    
    context = {
        'title': 'Lab Result Release - Payment Verification',
        'lab_results_with_status': lab_results_with_status[:50],
        'status_filter': status_filter,
        'stats': stats,
    }
    return render(request, 'hospital/lab_result_release_workflow.html', context)


@login_required
def verify_payment_for_lab_result(request, lab_result_id):
    """
    Verify payment and release lab result
    """
    from .models import LabResult
    
    lab_result = get_object_or_404(LabResult, pk=lab_result_id, is_deleted=False)
    
    # Get or create release record
    try:
        release_record = lab_result.release_record
    except:
        release_record = LabResultRelease.objects.create(
            lab_result=lab_result,
            patient=lab_result.order.encounter.patient,
            release_status='pending_payment'
        )
    
    if request.method == 'POST':
        receipt_number = request.POST.get('receipt_number')
        released_to = request.POST.get('released_to')
        relationship = request.POST.get('relationship', 'Self')
        id_type = request.POST.get('id_type')
        id_number = request.POST.get('id_number')
        delivery_method = request.POST.get('delivery_method', 'in_person')
        notes = request.POST.get('notes', '')
        
        try:
            # Verify receipt exists and is valid
            receipt = PaymentReceipt.objects.get(
                receipt_number=receipt_number,
                patient=lab_result.order.encounter.patient,
                is_deleted=False
            )
            
            # Link receipt to release record
            release_record.payment_receipt = receipt
            release_record.payment_verified_at = timezone.now()
            release_record.payment_verified_by = request.user
            release_record.delivery_method = delivery_method
            release_record.mark_released(
                user=request.user,
                released_to_name=released_to,
                relationship=relationship,
                id_type=id_type,
                id_number=id_number,
                notes=notes
            )
            
            # Create payment verification record
            PaymentVerification.objects.create(
                receipt=receipt,
                service_type='lab_result',
                lab_result=lab_result,
                verified_by=request.user,
                verified_at=timezone.now(),
                verification_status='verified',
                verification_method='receipt_number',
                verification_notes=f"Released to {released_to} ({relationship})"
            )
            
            messages.success(
                request,
                f'Payment verified! Lab result for {lab_result.test.name} released to {released_to}.'
            )
            
            # Send SMS notification to patient
            try:
                from .services.sms_service import sms_service
                patient = lab_result.order.encounter.patient
                
                if patient.phone_number:
                    message = (
                        f"Dear {patient.first_name},\n\n"
                        f"Your lab result for {lab_result.test.name} is ready.\n"
                        f"Collected by: {released_to}\n"
                        f"Receipt: {receipt_number}\n\n"
                        f"- PrimeCare Medical Center"
                    )
                    sms_service.send_sms(
                        phone_number=patient.phone_number,
                        message=message,
                        message_type='lab_result_released',
                        recipient_name=patient.full_name
                    )
            except Exception as e:
                logger.error(f"Error sending lab release SMS: {str(e)}")
            
            return redirect('hospital:lab_result_release_workflow')
            
        except PaymentReceipt.DoesNotExist:
            messages.error(request, f'Receipt number {receipt_number} not found or invalid for this patient.')
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'title': f'Verify Payment - {lab_result.test.name}',
        'lab_result': lab_result,
        'release_record': release_record,
        'patient': lab_result.order.encounter.patient,
    }
    return render(request, 'hospital/verify_payment_lab.html', context)


@login_required
def pharmacy_dispensing_workflow(request):
    """
    Workflow for dispensing medications after payment verification
    """
    from .models import Prescription
    
    # Get all prescriptions
    prescriptions = Prescription.objects.filter(
        is_deleted=False
    ).select_related(
        'drug', 'order__encounter__patient', 'prescribed_by'
    ).order_by('-created')
    
    # Add dispensing status to each
    prescriptions_with_status = []
    for rx in prescriptions:
        try:
            dispensing_record = rx.dispensing_record
            status = dispensing_record.dispensing_status
            payment_verified = dispensing_record.payment_receipt is not None
        except:
            # No dispensing record - create one
            dispensing_record = PharmacyDispensing.objects.create(
                prescription=rx,
                patient=rx.order.encounter.patient,
                quantity_ordered=rx.quantity if hasattr(rx, 'quantity') else 1,
                dispensing_status='pending_payment'
            )
            status = 'pending_payment'
            payment_verified = False
        
        prescriptions_with_status.append({
            'prescription': rx,
            'dispensing_record': dispensing_record,
            'status': status,
            'payment_verified': payment_verified,
        })
    
    # Filter by status (optional)
    status_filter = request.GET.get('status', '')
    if status_filter:
        prescriptions_with_status = [
            item for item in prescriptions_with_status 
            if item['status'] == status_filter
        ]
    
    # Build statistics
    from collections import Counter
    status_counts = Counter(item['status'] for item in prescriptions_with_status)
    stats = {
        'pending_payment': status_counts.get('pending_payment', 0),
        'ready_to_dispense': status_counts.get('ready_to_dispense', 0),
        'dispensed': (
            status_counts.get('fully_dispensed', 0)
            + status_counts.get('partially_dispensed', 0)
            + status_counts.get('dispensed', 0)
        ),
    }
    
    # Pagination (so huge lists don't freeze the page)
    paginator = Paginator(prescriptions_with_status, 40)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_items = page_obj.object_list

    # Walk-in sales (live payment verification for OTC)
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

    walkin_stats = {
        'pending': walkin_pending_qs.count(),
        'ready': walkin_ready_qs.count(),
        'dispensed': walkin_dispensed_qs.count(),
    }

    # Receipt search (manual verification by receipt number)
    receipt_query = request.GET.get('receipt_query', '').strip()
    receipt_search_result = None
    receipt_search_error = None

    if receipt_query:
        try:
            receipt = PaymentReceipt.objects.select_related('patient', 'invoice').get(
                receipt_number__iexact=receipt_query,
                is_deleted=False
            )

            dispensing_record = (
                PharmacyDispensing.objects.select_related(
                    'prescription__drug',
                    'prescription__order__encounter__patient'
                )
                .filter(payment_receipt=receipt)
                .first()
            )

            walkin_sale = None
            details = receipt.service_details if isinstance(receipt.service_details, dict) else {}
            sale_id = details.get('sale_id')
            if sale_id:
                try:
                    walkin_sale = WalkInPharmacySale.objects.get(id=sale_id, is_deleted=False)
                except WalkInPharmacySale.DoesNotExist:
                    walkin_sale = None

            receipt_search_result = {
                'receipt': receipt,
                'dispensing_record': dispensing_record,
                'walkin_sale': walkin_sale,
                'service_type': receipt.service_type,
                'patient': receipt.patient,
                'amount': receipt.amount_paid,
                'method': receipt.get_payment_method_display(),
            }
        except PaymentReceipt.DoesNotExist:
            receipt_search_error = f"Receipt {receipt_query} not found. Please confirm the code and try again."
        except Exception as exc:
            logger.error("Error searching receipt %s: %s", receipt_query, exc, exc_info=True)
            receipt_search_error = f"Error searching receipt: {exc}"

    context = {
        'title': 'Pharmacy Dispensing - Payment Verification',
        'status_filter': status_filter,
        'stats': stats,
        'page_obj': page_obj,
        'prescriptions_with_status': page_items,
        'walkin_pending': list(walkin_pending_qs[:25]),
        'walkin_ready': list(walkin_ready_qs[:25]),
        'walkin_recently_dispensed': list(walkin_dispensed_qs[:25]),
        'walkin_stats': walkin_stats,
        'receipt_query': receipt_query,
        'receipt_search_result': receipt_search_result,
        'receipt_search_error': receipt_search_error,
    }
    return render(request, 'hospital/pharmacy_dispensing_workflow.html', context)


@login_required
def verify_payment_for_pharmacy(request, prescription_id):
    """
    Verify payment and dispense medication
    """
    from .models import Prescription
    
    prescription = get_object_or_404(Prescription, pk=prescription_id, is_deleted=False)
    
    # Get or create dispensing record
    try:
        dispensing_record = prescription.dispensing_record
    except:
        dispensing_record = PharmacyDispensing.objects.create(
            prescription=prescription,
            patient=prescription.order.encounter.patient,
            quantity_ordered=prescription.quantity if hasattr(prescription, 'quantity') else 1,
            dispensing_status='pending_payment'
        )
    
    if request.method == 'POST':
        receipt_number = request.POST.get('receipt_number')
        quantity = int(request.POST.get('quantity', dispensing_record.quantity_ordered))
        instructions = request.POST.get('instructions', '')
        counselling_given = request.POST.get('counselling_given') == 'on'
        notes = request.POST.get('notes', '')
        
        try:
            # Verify receipt exists and is valid
            receipt = PaymentReceipt.objects.get(
                receipt_number=receipt_number,
                patient=prescription.order.encounter.patient,
                is_deleted=False
            )
            
            # Link receipt to dispensing record
            dispensing_record.payment_receipt = receipt
            dispensing_record.payment_verified_at = timezone.now()
            dispensing_record.payment_verified_by = request.user
            dispensing_record.counselling_given = counselling_given
            if counselling_given and hasattr(request.user, 'staff_profile'):
                dispensing_record.counselled_by = request.user.staff
            
            dispensing_record.mark_dispensed(
                user=request.user,
                quantity=quantity,
                instructions=instructions,
                notes=notes
            )
            
            # Create payment verification record
            PaymentVerification.objects.create(
                receipt=receipt,
                service_type='pharmacy_prescription',
                prescription=prescription,
                verified_by=request.user,
                verified_at=timezone.now(),
                verification_status='verified',
                verification_method='receipt_number',
                verification_notes=f"Dispensed {quantity} units"
            )
            
            messages.success(
                request,
                f'Payment verified! {prescription.drug.name} dispensed to patient.'
            )
            
            # Send SMS notification to patient
            try:
                from .services.sms_service import sms_service
                patient = prescription.order.encounter.patient
                
                if patient.phone_number:
                    message = (
                        f"Dear {patient.first_name},\n\n"
                        f"Medication dispensed: {prescription.drug.name}\n"
                        f"Quantity: {quantity}\n"
                        f"Receipt: {receipt_number}\n\n"
                        f"{instructions[:100] if instructions else 'Please follow doctor instructions.'}\n\n"
                        f"- PrimeCare Pharmacy"
                    )
                    sms_service.send_sms(
                        phone_number=patient.phone_number,
                        message=message,
                        message_type='medication_dispensed',
                        recipient_name=patient.full_name
                    )
            except Exception as e:
                logger.error(f"Error sending dispensing SMS: {str(e)}")
            
            return redirect('hospital:pharmacy_dispensing_workflow')
            
        except PaymentReceipt.DoesNotExist:
            messages.error(request, f'Receipt number {receipt_number} not found or invalid for this patient.')
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            messages.error(request, f'Error: {str(e)}')
    
    context = {
        'title': f'Verify Payment - {prescription.drug.name}',
        'prescription': prescription,
        'dispensing_record': dispensing_record,
        'patient': prescription.order.encounter.patient,
    }
    return render(request, 'hospital/verify_payment_pharmacy.html', context)


@login_required
def auto_generate_bill_for_lab_order(order):
    """
    Automatically generate bill when lab tests are ordered
    """
    from .models import LabResult
    from decimal import Decimal
    
    try:
        # Calculate total cost of lab tests
        total = Decimal('0.00')
        lab_results = order.lab_results.filter(is_deleted=False)
        
        for result in lab_results:
            if result.test.price:
                total += result.test.price
        
        if total > Decimal('0.00'):
            # Check if bill already exists
            existing_bill = Bill.objects.filter(
                encounter=order.encounter,
                notes__icontains=f'Lab Order {order.id}',
                is_deleted=False
            ).first()
            
            if not existing_bill:
                # Create bill
                bill = Bill.objects.create(
                    encounter=order.encounter,
                    patient=order.encounter.patient,
                    bill_type='cash',
                    total_amount=total,
                    patient_portion=total,
                    issued_by=order.ordered_by,
                    due_date=timezone.now().date() + timezone.timedelta(days=1),
                    status='issued',
                    notes=f'Laboratory tests for Order {order.id}'
                )
                
                logger.info(f"Auto-generated bill {bill.bill_number} for lab order {order.id}, Amount: GHS {total}")
                return bill
        
        return None
        
    except Exception as e:
        logger.error(f"Error auto-generating lab bill: {str(e)}")
        return None


@login_required
def auto_generate_bill_for_prescription(prescription):
    """
    Automatically generate bill when medication is prescribed
    """
    from decimal import Decimal
    
    try:
        # Get drug price
        if hasattr(prescription.drug, 'unit_price') and prescription.drug.unit_price:
            quantity = prescription.quantity if hasattr(prescription, 'quantity') else 1
            total = prescription.drug.unit_price * quantity
            
            # Check if bill already exists
            existing_bill = Bill.objects.filter(
                encounter=prescription.order.encounter,
                notes__icontains=f'Prescription {prescription.id}',
                is_deleted=False
            ).first()
            
            if not existing_bill:
                # Create bill
                bill = Bill.objects.create(
                    encounter=prescription.order.encounter,
                    patient=prescription.order.encounter.patient,
                    bill_type='cash',
                    total_amount=total,
                    patient_portion=total,
                    issued_by=prescription.prescribed_by.user if prescription.prescribed_by else None,
                    due_date=timezone.now().date() + timezone.timedelta(days=1),
                    status='issued',
                    notes=f'Medication: {prescription.drug.name} x{quantity} for Prescription {prescription.id}'
                )
                
                logger.info(f"Auto-generated bill {bill.bill_number} for prescription {prescription.id}, Amount: GHS {total}")
                return bill
        
        return None
        
    except Exception as e:
        logger.error(f"Error auto-generating prescription bill: {str(e)}")
        return None


@login_required
def scan_receipt_qr_api(request):
    """
    API endpoint for scanning receipt QR codes
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        qr_data = request.POST.get('qr_data')
        
        if not qr_data:
            return JsonResponse({'error': 'No QR data provided'}, status=400)
        
        # Parse QR data (format: RECEIPT:RCP20251106123456)
        if not qr_data.startswith('RECEIPT:'):
            return JsonResponse({'error': 'Invalid QR code format'}, status=400)
        
        receipt_number = qr_data.replace('RECEIPT:', '')
        
        # Find receipt
        receipt = PaymentReceipt.objects.get(
            receipt_number=receipt_number,
            is_deleted=False
        )
        
        # Record scan
        try:
            qr_code = receipt.qr_code
            qr_code.record_scan(request.user)
        except:
            pass
        
        return JsonResponse({
            'success': True,
            'receipt_number': receipt.receipt_number,
            'patient_name': receipt.patient.full_name,
            'amount_paid': str(receipt.amount_paid),
            'payment_method': receipt.get_payment_method_display(),
            'receipt_date': receipt.receipt_date.strftime('%Y-%m-%d %H:%M'),
        })
        
    except PaymentReceipt.DoesNotExist:
        return JsonResponse({'error': 'Receipt not found'}, status=404)
    except Exception as e:
        logger.error(f"Error scanning QR code: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def print_receipt_with_qr(request, receipt_id):
    """
    Generate printable receipt with QR code
    """
    receipt = get_object_or_404(PaymentReceipt, pk=receipt_id, is_deleted=False)
    
    # Get or create QR code
    try:
        qr_code = receipt.qr_code
    except:
        qr_data = f"RECEIPT:{receipt.receipt_number}"
        qr_code = ReceiptQRCode.objects.create(
            receipt=receipt,
            qr_code_data=qr_data
        )
        qr_code.generate_qr_code()
        qr_code.save()
    
    context = {
        'receipt': receipt,
        'qr_code': qr_code,
        'patient': receipt.patient,
        'items': [],  # Would list invoice items here
    }
    return render(request, 'hospital/receipt_print_qr.html', context)


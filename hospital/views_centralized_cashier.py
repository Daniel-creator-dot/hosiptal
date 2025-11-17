"""
💰 CENTRALIZED CASHIER SYSTEM
All payments processed through cashier first
Complete payment control and audit trail
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, Count
from decimal import Decimal
import logging

from .models import Patient, Encounter, LabResult, Prescription, Admission
from .models_accounting import PaymentReceipt, Transaction
from .models_payment_verification import LabResultRelease, PharmacyDispensing
from .services.unified_receipt_service import (
    UnifiedReceiptService,
    LabPaymentService,
    PharmacyPaymentService,
    ImagingPaymentService,
    ConsultationPaymentService,
    BedPaymentService
)
from .services.auto_billing_service import AutoBillingService
from .utils_roles import user_has_cashier_access
from .models_pharmacy_walkin import WalkInPharmacySale
from .services.pharmacy_walkin_service import WalkInPharmacyService

logger = logging.getLogger(__name__)


def is_cashier(user):
    """Only Administrators and Accountants can access cashier tools."""
    return user_has_cashier_access(user)


@login_required
@user_passes_test(is_cashier)
def centralized_cashier_dashboard(request):
    """
    Main cashier dashboard - shows all pending payments
    ALL payments must come through here first
    """
    today = timezone.now().date()
    
    # Get ALL lab tests and prescriptions (paid and unpaid)
    # Get all lab results
    all_labs = LabResult.objects.filter(
        is_deleted=False
    ).filter(
        Q(verified_by__isnull=False) | Q(release_record__sent_to_cashier_at__isnull=False)
    ).select_related(
        'test', 'order__encounter__patient', 'release_record'
    ).order_by('-created')
    
    # Filter for unpaid
    pending_labs = []
    for lab in all_labs:
        release_record = getattr(lab, 'release_record', None)
        if release_record:
            if release_record.payment_receipt_id:
                continue
            if release_record.sent_to_cashier_at or lab.verified_by_id:
                pending_labs.append(lab)
        else:
            try:
                AutoBillingService.create_lab_bill(lab)
            except Exception:
                pass
            pending_labs.append(lab)
    
    # Get all prescriptions
    all_prescriptions = Prescription.objects.filter(
        is_deleted=False
    ).select_related(
        'drug', 'order__encounter__patient', 'prescribed_by'
    ).order_by('-created')
    
    # Filter for unpaid
    pending_pharmacy = []
    for rx in all_prescriptions:
        try:
            # Check if has dispensing record with payment
            if hasattr(rx, 'dispensing_record'):
                if not rx.dispensing_record.payment_receipt:
                    pending_pharmacy.append(rx)
            else:
                # No dispensing record - create bill and add to pending
                AutoBillingService.create_pharmacy_bill(rx)
                pending_pharmacy.append(rx)
        except:
            # No dispensing record - create bill
            AutoBillingService.create_pharmacy_bill(rx)
            pending_pharmacy.append(rx)
    
    # Get all active admissions (for bed charges)
    pending_admissions = []
    active_admissions = Admission.objects.filter(
        is_deleted=False,
        status='admitted'
    ).select_related('encounter__patient', 'ward', 'bed').order_by('-admit_date')
    
    for admission in active_admissions:
        try:
            # Calculate current bed charges
            from .services.bed_billing_service import bed_billing_service
            charges = bed_billing_service.get_bed_charges_summary(admission)
            admission.bed_charges = charges
            pending_admissions.append(admission)
        except Exception as e:
            logger.error(f"Error calculating bed charges for admission {admission.pk}: {str(e)}")
    
    # Walk-in pharmacy sales pending payment
    walkin_sales_qs = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial']
    ).select_related('patient').order_by('-sale_date')
    pending_walkin_sales = list(walkin_sales_qs[:20])
    total_pending_walkin = walkin_sales_qs.count()

    # Get all imaging studies (completed ones ready for payment)
    from .models_advanced import ImagingStudy
    from .models_accounting import PaymentReceipt
    all_imaging = ImagingStudy.objects.filter(
        is_deleted=False,
        status__in=['completed', 'reported']
    ).select_related('order__encounter__patient', 'patient').order_by('-created')
    
    # Filter for unpaid imaging
    pending_imaging = []
    for imaging in all_imaging:
        # Check if already paid
        patient_for_check = imaging.patient if hasattr(imaging, 'patient') else imaging.order.encounter.patient
        already_paid = PaymentReceipt.objects.filter(
            is_deleted=False,
            patient=patient_for_check,
            service_type='imaging_study',
            receipt_date__gte=imaging.created.date()
        ).exists()
        
        # More detailed check for imaging payment
        if not already_paid:
            recent_receipts = PaymentReceipt.objects.filter(
                is_deleted=False,
                patient=patient_for_check,
                receipt_date__gte=imaging.created.date()
            )
            for receipt in recent_receipts:
                if receipt.service_type == 'imaging_study':
                    try:
                        if isinstance(receipt.service_details, dict):
                            if receipt.service_details.get('study_type') == imaging.study_type:
                                already_paid = True
                                break
                    except:
                        pass
        
        if not already_paid:
            pending_imaging.append(imaging)
    
    # Today's receipts - get base queryset for stats (without slice)
    todays_receipts_base = PaymentReceipt.objects.filter(
        receipt_date__date=today,
        is_deleted=False
    )
    
    # For display - with slice and relations
    todays_receipts_display = todays_receipts_base.select_related(
        'patient', 'received_by'
    ).order_by('-receipt_date')[:20]
    
    # Statistics
    stats = {
        'pending_lab': len(pending_labs),
        'pending_pharmacy': len(pending_pharmacy),
        'pending_imaging': len(pending_imaging),
        'pending_admissions': len(pending_admissions),
        'todays_receipts': todays_receipts_base.count(),
        'todays_revenue': todays_receipts_base.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00'),
        'pending_walkin': total_pending_walkin,
    }
    
    # Revenue by payment method
    stats['by_method'] = {}
    for method in ['cash', 'card', 'mobile_money', 'bank_transfer']:
        amount = todays_receipts_base.filter(payment_method=method).aggregate(Sum('amount_paid'))['amount_paid__sum']
        stats['by_method'][method] = amount or Decimal('0.00')
    
    # Debug logging
    logger.info(f"Cashier Dashboard: {len(pending_labs)} pending labs, {len(pending_pharmacy)} pending pharmacy")
    
    context = {
        'title': '💰 Centralized Cashier Dashboard',
        'pending_labs': pending_labs[:20],  # Show more
        'pending_pharmacy': pending_pharmacy[:20],  # Show more
        'pending_imaging': pending_imaging[:20],  # Show imaging studies
        'pending_admissions': pending_admissions[:20],  # Show bed charges
        'pending_walkin_sales': pending_walkin_sales,
        'total_pending_walkin': total_pending_walkin,
        'todays_receipts': todays_receipts_display,
        'stats': stats,
        'total_pending_labs': len(pending_labs),
        'total_pending_pharmacy': len(pending_pharmacy),
        'total_pending_imaging': len(pending_imaging),
        'total_pending_admissions': len(pending_admissions),
    }
    return render(request, 'hospital/centralized_cashier_dashboard.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_patient_bills(request):
    """
    Patient-centric billing - Show all pending services grouped by patient
    Allows processing all services for a patient in one payment
    """
    from .models_advanced import ImagingStudy
    from .models_accounting import PaymentReceipt
    
    search = request.GET.get('search', '')
    
    # Get all pending items grouped by patient
    patients_bills = {}  # {patient_id: {'patient': Patient, 'services': [], 'total': Decimal}}
    
    # Get all lab results
    labs_query = LabResult.objects.filter(
        is_deleted=False,
        verified_by__isnull=False
    ).select_related('test', 'order__encounter__patient')
    
    if search:
        labs_query = labs_query.filter(
            Q(order__encounter__patient__first_name__icontains=search) |
            Q(order__encounter__patient__last_name__icontains=search) |
            Q(order__encounter__patient__mrn__icontains=search)
        )
    
    for lab in labs_query:
        # Check if lab has been paid - improved check
        try:
            # Check if there's a release record with payment
            if hasattr(lab, 'release_record'):
                release = lab.release_record
                if release and release.payment_receipt_id is not None:
                    continue  # Already paid
        except LabResultRelease.DoesNotExist:
            pass  # No release record, need payment
        except AttributeError:
            pass  # No release record attribute, need payment
        
        patient = lab.order.encounter.patient
        patient_id = str(patient.id)
        
        if patient_id not in patients_bills:
            patients_bills[patient_id] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
        
        price = lab.test.price if hasattr(lab.test, 'price') else Decimal('0.00')
        patients_bills[patient_id]['services'].append({
            'type': 'lab',
            'id': str(lab.id),
            'name': lab.test.name,
            'price': price,
            'date': lab.created,
            'encounter': lab.order.encounter,
        })
        patients_bills[patient_id]['total'] += price
    
    # Get all prescriptions
    rx_query = Prescription.objects.filter(
        is_deleted=False
    ).select_related('drug', 'order__encounter__patient')
    
    if search:
        rx_query = rx_query.filter(
            Q(order__encounter__patient__first_name__icontains=search) |
            Q(order__encounter__patient__last_name__icontains=search) |
            Q(order__encounter__patient__mrn__icontains=search)
        )
    
    for rx in rx_query:
        # Check if prescription has been paid - improved check
        try:
            # Check if there's a dispensing record with payment
            if hasattr(rx, 'dispensing_record'):
                dispensing = rx.dispensing_record
                if dispensing and dispensing.payment_receipt_id is not None:
                    continue  # Already paid
        except PharmacyDispensing.DoesNotExist:
            pass  # No dispensing record, need payment
        except AttributeError:
            pass  # No dispensing record attribute, need payment
        
        patient = rx.order.encounter.patient
        patient_id = str(patient.id)
        
        if patient_id not in patients_bills:
            patients_bills[patient_id] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
        
        drug_price = getattr(rx.drug, 'unit_price', Decimal('0.00'))
        total = drug_price * rx.quantity
        
        patients_bills[patient_id]['services'].append({
            'type': 'pharmacy',
            'id': str(rx.id),
            'name': f"{rx.drug.name} {rx.drug.strength} x {rx.quantity}",
            'price': total,
            'date': rx.created,
            'encounter': rx.order.encounter,
        })
        patients_bills[patient_id]['total'] += total
    
    # Walk-in pharmacy sales
    walkin_query = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial']
    ).select_related('patient')
    
    if search:
        walkin_query = walkin_query.filter(
            Q(customer_name__icontains=search) |
            Q(sale_number__icontains=search) |
            Q(patient__mrn__icontains=search)
        )
    
    for sale in walkin_query:
        patient = WalkInPharmacyService.ensure_sale_patient(sale)
        patient_id = str(patient.id)
        
        if patient_id not in patients_bills:
            patients_bills[patient_id] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
        
        amount_due = sale.amount_due or (sale.total_amount - sale.amount_paid)
        if amount_due < 0:
            amount_due = Decimal('0.00')
        
        patients_bills[patient_id]['services'].append({
            'type': 'pharmacy_walkin',
            'id': str(sale.id),
            'name': f"Walk-in Sale {sale.sale_number}",
            'price': amount_due,
            'date': sale.sale_date,
            'obj': sale,
        })
        patients_bills[patient_id]['total'] += amount_due
    
    # Get all imaging studies
    imaging_query = ImagingStudy.objects.filter(
        is_deleted=False,
        status__in=['completed', 'reported']
    ).select_related('order__encounter__patient', 'patient')
    
    if search:
        imaging_query = imaging_query.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__mrn__icontains=search)
        )
    
    for imaging in imaging_query:
        # Check if already paid
        patient_for_check = imaging.patient if hasattr(imaging, 'patient') else imaging.order.encounter.patient
        already_paid = PaymentReceipt.objects.filter(
            is_deleted=False,
            patient=patient_for_check,
            service_type='imaging_study',
            receipt_date__gte=imaging.created.date()
        ).exists()
        
        if not already_paid:
            recent_receipts = PaymentReceipt.objects.filter(
                is_deleted=False,
                patient=patient_for_check,
                receipt_date__gte=imaging.created.date()
            )
            for receipt in recent_receipts:
                if receipt.service_type == 'imaging_study':
                    try:
                        if isinstance(receipt.service_details, dict):
                            if receipt.service_details.get('study_type') == imaging.study_type:
                                already_paid = True
                                break
                    except:
                        pass
        
        if not already_paid:
            patient = patient_for_check
            patient_id = str(patient.id)
            
            if patient_id not in patients_bills:
                patients_bills[patient_id] = {
                    'patient': patient,
                    'services': [],
                    'total': Decimal('0.00')
                }
            
            imaging_price = Decimal('50.00')  # Default
            
            patients_bills[patient_id]['services'].append({
                'type': 'imaging',
                'id': str(imaging.id),
                'name': f"{imaging.study_type} - {imaging.body_part}",
                'price': imaging_price,
                'date': imaging.performed_at or imaging.created,
                'encounter': imaging.order.encounter if hasattr(imaging, 'order') else None,
            })
            patients_bills[patient_id]['total'] += imaging_price
    
    # Get consultations (if any pending)
    consultations_query = Encounter.objects.filter(
        is_deleted=False,
        status='active'
    ).select_related('patient')
    
    if search:
        consultations_query = consultations_query.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__mrn__icontains=search)
        )
    
    # Get active admissions (bed charges)
    admissions_query = Admission.objects.filter(
        is_deleted=False,
        status='admitted'
    ).select_related('encounter__patient', 'ward', 'bed')
    
    if search:
        admissions_query = admissions_query.filter(
            Q(encounter__patient__first_name__icontains=search) |
            Q(encounter__patient__last_name__icontains=search) |
            Q(encounter__patient__mrn__icontains=search)
        )
    
    for admission in admissions_query:
        patient = admission.encounter.patient
        patient_id = str(patient.id)
        
        if patient_id not in patients_bills:
            patients_bills[patient_id] = {
                'patient': patient,
                'services': [],
                'total': Decimal('0.00')
            }
        
        # Calculate current bed charges
        try:
            from .services.bed_billing_service import bed_billing_service
            charges = bed_billing_service.get_bed_charges_summary(admission)
            bed_charge = charges['current_charges']
            days = charges['days_admitted']
        except:
            bed_charge = Decimal('120.00')  # Default 1 day
            days = 1
        
        patients_bills[patient_id]['services'].append({
            'type': 'bed',
            'id': str(admission.id),
            'name': f"Bed Charges - {admission.ward.name} - Bed {admission.bed.bed_number} ({days} day{'s' if days != 1 else ''})",
            'price': bed_charge,
            'date': admission.admit_date,
            'encounter': admission.encounter,
        })
        patients_bills[patient_id]['total'] += bed_charge
    
    # Check if consultation already paid
    for encounter in consultations_query:
        already_paid = PaymentReceipt.objects.filter(
            is_deleted=False,
            patient=encounter.patient,
            service_type='consultation',
            receipt_date__gte=encounter.started_at.date()
        ).exists()
        
        if not already_paid:
            patient = encounter.patient
            patient_id = str(patient.id)
            
            if patient_id not in patients_bills:
                patients_bills[patient_id] = {
                    'patient': patient,
                    'services': [],
                    'total': Decimal('0.00')
                }
            
            consultation_price = Decimal('30.00')  # Default
            
            patients_bills[patient_id]['services'].append({
                'type': 'consultation',
                'id': str(encounter.id),
                'name': f"{encounter.get_encounter_type_display()} Consultation",
                'price': consultation_price,
                'date': encounter.started_at,
                'encounter': encounter,
            })
            patients_bills[patient_id]['total'] += consultation_price
    
    # Convert to list and sort by total amount (highest first)
    patients_list = list(patients_bills.values())
    patients_list.sort(key=lambda x: x['total'], reverse=True)
    
    # Calculate overall totals
    total_patients = len(patients_list)
    total_amount = sum(p['total'] for p in patients_list)
    total_services = sum(len(p['services']) for p in patients_list)
    
    context = {
        'title': 'Patient Bills - Combined Billing',
        'patients_bills': patients_list,
        'search': search,
        'total_patients': total_patients,
        'total_amount': total_amount,
        'total_services': total_services,
    }
    return render(request, 'hospital/cashier_patient_bills.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_all_pending_bills(request):
    """
    Show ALL pending bills - comprehensive view
    Search by patient name, MRN, or service
    """
    search = request.GET.get('search', '')
    service_filter = request.GET.get('service_type', 'all')
    
    pending_items = []
    
    # Get all lab results
    labs_query = LabResult.objects.filter(
        is_deleted=False,
        verified_by__isnull=False
    ).select_related('test', 'order__encounter__patient')
    
    if search:
        labs_query = labs_query.filter(
            Q(order__encounter__patient__first_name__icontains=search) |
            Q(order__encounter__patient__last_name__icontains=search) |
            Q(order__encounter__patient__mrn__icontains=search) |
            Q(test__name__icontains=search)
        )
    
    for lab in labs_query:
        try:
            if hasattr(lab, 'release_record') and lab.release_record.payment_receipt:
                continue  # Already paid
        except:
            pass
        
        # Unpaid - add to list
        if service_filter == 'all' or service_filter == 'lab':
            pending_items.append({
                'type': 'lab',
                'id': str(lab.id),
                'patient': lab.order.encounter.patient,
                'patient_name': lab.order.encounter.patient.full_name,
                'patient_mrn': lab.order.encounter.patient.mrn,
                'service': lab.test.name,
                'price': lab.test.price,
                'date': lab.created,
                'encounter': lab.order.encounter,
            })
    
    # Get all prescriptions
    rx_query = Prescription.objects.filter(
        is_deleted=False
    ).select_related('drug', 'order__encounter__patient')
    
    if search:
        rx_query = rx_query.filter(
            Q(order__encounter__patient__first_name__icontains=search) |
            Q(order__encounter__patient__last_name__icontains=search) |
            Q(order__encounter__patient__mrn__icontains=search) |
            Q(drug__name__icontains=search)
        )
    
    for rx in rx_query:
        try:
            if hasattr(rx, 'dispensing_record') and rx.dispensing_record.payment_receipt:
                continue  # Already paid
        except:
            pass
        
        # Unpaid - add to list
        if service_filter == 'all' or service_filter == 'pharmacy':
            drug_price = getattr(rx.drug, 'unit_price', Decimal('0.00'))
            total = drug_price * rx.quantity
            
            pending_items.append({
                'type': 'pharmacy',
                'id': str(rx.id),
                'patient': rx.order.encounter.patient,
                'patient_name': rx.order.encounter.patient.full_name,
                'patient_mrn': rx.order.encounter.patient.mrn,
                'service': f"{rx.drug.name} {rx.drug.strength} x {rx.quantity}",
                'price': total,
                'date': rx.created,
                'encounter': rx.order.encounter,
            })
    
    # Walk-in pharmacy sales
    walkin_sales = WalkInPharmacySale.objects.filter(
        is_deleted=False,
        payment_status__in=['pending', 'partial']
    ).select_related('patient')
    
    if search:
        walkin_sales = walkin_sales.filter(
            Q(customer_name__icontains=search) |
            Q(sale_number__icontains=search) |
            Q(patient__mrn__icontains=search)
        )
    
    if service_filter in ['all', 'pharmacy', 'pharmacy_walkin']:
        for sale in walkin_sales:
            patient = WalkInPharmacyService.ensure_sale_patient(sale)
            amount_due = sale.amount_due or (sale.total_amount - sale.amount_paid)
            if amount_due < 0:
                amount_due = Decimal('0.00')
            
            pending_items.append({
                'type': 'pharmacy_walkin',
                'id': str(sale.id),
                'patient': patient,
                'patient_name': patient.full_name,
                'patient_mrn': patient.mrn,
                'service': f"Walk-in Sale {sale.sale_number}",
                'price': amount_due,
                'date': sale.sale_date,
                'sale': sale,
            })
    
    # Get all imaging studies (completed ones ready for payment)
    from .models_advanced import ImagingStudy
    imaging_query = ImagingStudy.objects.filter(
        is_deleted=False,
        status__in=['completed', 'reported']  # Completed imaging studies
    ).select_related('order__encounter__patient', 'patient')
    
    if search:
        imaging_query = imaging_query.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__mrn__icontains=search) |
            Q(study_type__icontains=search) |
            Q(body_part__icontains=search)
        )
    
    # Check if imaging study has been paid (by checking for receipts with this study)
    for imaging in imaging_query:
        # Check if already paid - look for payment receipts linked to this imaging study
        from .models_accounting import PaymentReceipt
        
        # FIXED: SQLite doesn't support __contains on JSONField
        # Instead, get all imaging receipts for this patient and check in Python
        patient_for_check = imaging.patient if hasattr(imaging, 'patient') else imaging.order.encounter.patient
        imaging_receipts = PaymentReceipt.objects.filter(
            is_deleted=False,
            patient=patient_for_check,
            service_type='imaging_study',
            receipt_date__gte=imaging.created.date()
        )
        
        already_paid = False
        for receipt in imaging_receipts:
            try:
                if isinstance(receipt.service_details, dict):
                    # Check if this receipt is for this specific imaging study
                    if receipt.service_details.get('study_id') == str(imaging.id):
                        already_paid = True
                        break
                    # Also check by study_type as fallback
                    if receipt.service_details.get('study_type') == imaging.study_type:
                        already_paid = True
                        break
            except:
                pass
        
        if not already_paid:
            # Unpaid - add to list
            if service_filter == 'all' or service_filter == 'imaging':
                # Default pricing or get from order/encounter pricing
                imaging_price = Decimal('50.00')  # Default - can be made configurable
                
                # Try to get price from order if available
                try:
                    if hasattr(imaging, 'order') and imaging.order:
                        # Could add pricing logic here based on order
                        pass
                except:
                    pass
                
                patient_for_list = imaging.patient if hasattr(imaging, 'patient') else imaging.order.encounter.patient
                
                pending_items.append({
                    'type': 'imaging',
                    'id': str(imaging.id),
                    'patient': patient_for_list,
                    'patient_name': patient_for_list.full_name,
                    'patient_mrn': patient_for_list.mrn,
                    'service': f"{imaging.study_type} - {imaging.body_part}",
                    'price': imaging_price,
                    'date': imaging.performed_at or imaging.created,
                    'encounter': imaging.order.encounter if hasattr(imaging, 'order') else None,
                })
    
    # Get active admissions (bed charges)
    if service_filter == 'all' or service_filter == 'bed':
        admissions_query = Admission.objects.filter(
            is_deleted=False,
            status='admitted'
        ).select_related('encounter__patient', 'ward', 'bed')
        
        if search:
            admissions_query = admissions_query.filter(
                Q(encounter__patient__first_name__icontains=search) |
                Q(encounter__patient__last_name__icontains=search) |
                Q(encounter__patient__mrn__icontains=search)
            )
        
        for admission in admissions_query:
            try:
                from .services.bed_billing_service import bed_billing_service
                charges = bed_billing_service.get_bed_charges_summary(admission)
                bed_charge = charges['current_charges']
                days = charges['days_admitted']
                
                patient = admission.encounter.patient
                
                pending_items.append({
                    'type': 'bed',
                    'id': str(admission.id),
                    'patient': patient,
                    'patient_name': patient.full_name,
                    'patient_mrn': patient.mrn,
                    'service': f"Bed Charges - {admission.ward.name} - Bed {admission.bed.bed_number} ({days} day{'s' if days != 1 else ''})",
                    'price': bed_charge,
                    'date': admission.admit_date,
                    'encounter': admission.encounter,
                })
            except Exception as e:
                logger.error(f"Error adding bed charges to pending: {str(e)}")
    
    # Sort by date
    pending_items.sort(key=lambda x: x['date'], reverse=True)
    
    context = {
        'title': 'All Pending Bills',
        'pending_items': pending_items,
        'search': search,
        'service_filter': service_filter,
        'total_pending': len(pending_items),
        'total_amount': sum(item['price'] for item in pending_items),
    }
    return render(request, 'hospital/cashier_all_pending_bills.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_process_service_payment(request, service_type, service_id):
    """
    Process payment for any service
    Universal payment processor
    """
    # Get service details
    service_obj = None
    patient = None
    service_name = ""
    service_price = Decimal('0.00')
    
    if service_type == 'lab':
        service_obj = get_object_or_404(LabResult, id=service_id, is_deleted=False)
        patient = service_obj.order.encounter.patient
        service_name = service_obj.test.name
        service_price = service_obj.test.price if hasattr(service_obj.test, 'price') else Decimal('0.00')
        
    elif service_type == 'pharmacy':
        service_obj = get_object_or_404(Prescription, id=service_id, is_deleted=False)
        patient = service_obj.order.encounter.patient
        service_name = f"{service_obj.drug.name} x {service_obj.quantity}"
        drug_price = service_obj.drug.unit_price if hasattr(service_obj.drug, 'unit_price') else Decimal('0.00')
        service_price = drug_price * service_obj.quantity
        
        dispensing_record = getattr(service_obj, 'dispensing_record', None)
        if not dispensing_record:
            AutoBillingService.create_pharmacy_bill(service_obj)
            dispensing_record = getattr(service_obj, 'dispensing_record', None)
        if not dispensing_record:
            messages.error(request, '❌ Pharmacy has not sent this medication to the cashier yet.')
            return redirect('hospital:centralized_cashier_dashboard')
        if dispensing_record.payment_receipt_id:
            messages.error(request, '✅ Payment for this medication has already been recorded.')
            return redirect('hospital:centralized_cashier_dashboard')
    elif service_type == 'pharmacy_walkin':
        service_obj = get_object_or_404(WalkInPharmacySale, id=service_id, is_deleted=False)
        if service_obj.payment_status == 'paid':
            messages.error(request, '✅ Payment for this walk-in sale has already been recorded.')
            return redirect('hospital:centralized_cashier_dashboard')
        patient = WalkInPharmacyService.ensure_sale_patient(service_obj)
        service_name = f"Walk-in Sale {service_obj.sale_number}"
        service_price = service_obj.amount_due or (service_obj.total_amount - service_obj.amount_paid)
        if service_price < 0:
            service_price = Decimal('0.00')
        
    elif service_type == 'imaging':
        from .models_advanced import ImagingStudy
        service_obj = get_object_or_404(ImagingStudy, id=service_id, is_deleted=False)
        patient = service_obj.order.encounter.patient if hasattr(service_obj, 'order') else service_obj.patient
        service_name = service_obj.study_type
        service_price = Decimal('50.00')  # Default or fetch from pricing
        
    elif service_type == 'consultation':
        service_obj = get_object_or_404(Encounter, id=service_id, is_deleted=False)
        patient = service_obj.patient
        service_name = f"{service_obj.get_encounter_type_display()} Consultation"
        service_price = Decimal('30.00')  # Default or fetch from pricing
        
    elif service_type == 'bed':
        service_obj = get_object_or_404(Admission, id=service_id, is_deleted=False)
        patient = service_obj.encounter.patient
        # Calculate current bed charges
        try:
            from .services.bed_billing_service import bed_billing_service
            charges = bed_billing_service.get_bed_charges_summary(service_obj)
            service_price = charges['current_charges']
            days = charges['days_admitted']
            service_name = f"Bed Charges - {service_obj.ward.name} - Bed {service_obj.bed.bed_number} ({days} days)"
        except:
            service_price = Decimal('120.00')
            service_name = f"Bed Charges - {service_obj.ward.name} - Bed {service_obj.bed.bed_number}"
    
    if service_type == 'lab':
        release_record = getattr(service_obj, 'release_record', None)
        if not release_record:
            AutoBillingService.create_lab_bill(service_obj)
            release_record = getattr(service_obj, 'release_record', None)
        if not release_record:
            messages.error(request, '❌ Lab result has not been sent to the cashier yet.')
            return redirect('hospital:centralized_cashier_dashboard')
        if release_record.payment_receipt_id:
            messages.error(request, '✅ Payment for this lab test has already been recorded.')
            return redirect('hospital:centralized_cashier_dashboard')

    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', service_price))
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '')
        notes = request.POST.get('notes', '')
        
        # Process payment based on service type
        result = None
        
        if service_type == 'lab':
            result = LabPaymentService.create_lab_payment_receipt(
                lab_result=service_obj,
                amount=amount,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=notes
            )
        elif service_type == 'pharmacy':
            result = PharmacyPaymentService.create_pharmacy_payment_receipt(
                prescription=service_obj,
                amount=amount,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=notes
            )
        elif service_type == 'pharmacy_walkin':
            result = WalkInPharmacyService.create_payment_receipt(
                sale=service_obj,
                amount=amount,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=notes or f"Walk-in sale {service_obj.sale_number}"
            )
        elif service_type == 'imaging':
            result = ImagingPaymentService.create_imaging_payment_receipt(
                imaging_study=service_obj,
                amount=amount,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=notes
            )
        elif service_type == 'consultation':
            result = ConsultationPaymentService.create_consultation_payment_receipt(
                encounter=service_obj,
                amount=amount,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=notes
            )
        elif service_type == 'bed':
            result = BedPaymentService.create_bed_payment_receipt(
                admission=service_obj,
                amount=amount,
                payment_method=payment_method,
                received_by_user=request.user,
                notes=notes
            )
        
        if result and result.get('success'):
            # Show digital receipt info
            digital = result.get('digital_receipt', {})
            accounting = result.get('accounting_sync', {})
            
            msg = f"✅ Payment processed! Receipt {result['receipt'].receipt_number} generated."
            if digital.get('email', {}).get('sent'):
                msg += " 📧 Email sent."
            if digital.get('sms', {}).get('sent'):
                msg += " 📱 SMS sent."
            if accounting.get('success'):
                msg += " 💰 Accounting synced."
            
            messages.success(request, msg)
            return redirect('hospital:receipt_print', receipt_id=result['receipt'].id)
        elif result:
            error_msg = result.get('message', result.get('error', 'Unknown error'))
            messages.error(request, f"❌ Payment failed: {error_msg}")
            logger.error(f"Payment failed for {service_type} {service_id}: {error_msg}")
        else:
            messages.error(request, "❌ Payment processing failed - no result returned")
            logger.error(f"Payment processing returned None for {service_type} {service_id}")
    
    context = {
        'title': f'Process Payment - {service_name}',
        'service_type': service_type,
        'service_obj': service_obj,
        'patient': patient,
        'service_name': service_name,
        'service_price': service_price,
        'payment_methods': Transaction.PAYMENT_METHODS,
    }
    return render(request, 'hospital/cashier_process_payment.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_process_patient_combined_payment(request, patient_id):
    """
    Process combined payment for all pending services of a patient
    Creates one receipt with all services itemized
    """
    from .models_advanced import ImagingStudy
    from .models_accounting import PaymentReceipt
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    
    # Get all pending services for this patient (same logic as patient_bills view)
    services_list = []
    total_amount = Decimal('0.00')
    
    # Get pending labs
    labs_query = LabResult.objects.filter(
        is_deleted=False,
        verified_by__isnull=False,
        order__encounter__patient=patient
    ).select_related('test', 'order__encounter__patient')
    
    for lab in labs_query:
        # Check if lab has been paid - improved check
        try:
            if hasattr(lab, 'release_record'):
                release = lab.release_record
                if release and release.payment_receipt_id is not None:
                    continue  # Already paid
        except LabResultRelease.DoesNotExist:
            pass  # No release record, need payment
        except AttributeError:
            pass  # No release record attribute, need payment
        
        price = lab.test.price if hasattr(lab.test, 'price') else Decimal('0.00')
        services_list.append({
            'type': 'lab',
            'id': str(lab.id),
            'obj': lab,
            'name': lab.test.name,
            'price': price,
        })
        total_amount += price
    
    # Get pending prescriptions
    rx_query = Prescription.objects.filter(
        is_deleted=False,
        order__encounter__patient=patient
    ).select_related('drug', 'order__encounter__patient')
    
    for rx in rx_query:
        # Check if prescription has been paid - improved check
        try:
            if hasattr(rx, 'dispensing_record'):
                dispensing = rx.dispensing_record
                if dispensing and dispensing.payment_receipt_id is not None:
                    continue  # Already paid
        except PharmacyDispensing.DoesNotExist:
            pass  # No dispensing record, need payment
        except AttributeError:
            pass  # No dispensing record attribute, need payment
        
        drug_price = getattr(rx.drug, 'unit_price', Decimal('0.00'))
        total = drug_price * rx.quantity
        services_list.append({
            'type': 'pharmacy',
            'id': str(rx.id),
            'obj': rx,
            'name': f"{rx.drug.name} {rx.drug.strength} x {rx.quantity}",
            'price': total,
        })
        total_amount += total
    
    # Get pending imaging
    imaging_query = ImagingStudy.objects.filter(
        is_deleted=False,
        status__in=['completed', 'reported'],
        patient=patient
    ).select_related('order__encounter__patient', 'patient')
    
    for imaging in imaging_query:
        already_paid = PaymentReceipt.objects.filter(
            is_deleted=False,
            patient=patient,
            service_type='imaging_study',
            receipt_date__gte=imaging.created.date()
        ).exists()
        
        if not already_paid:
            imaging_price = Decimal('50.00')
            services_list.append({
                'type': 'imaging',
                'id': str(imaging.id),
                'obj': imaging,
                'name': f"{imaging.study_type} - {imaging.body_part}",
                'price': imaging_price,
            })
            total_amount += imaging_price
    
    # Get pending consultations
    consultations_query = Encounter.objects.filter(
        is_deleted=False,
        status='active',
        patient=patient
    ).select_related('patient')
    
    for encounter in consultations_query:
        already_paid = PaymentReceipt.objects.filter(
            is_deleted=False,
            patient=patient,
            service_type='consultation',
            receipt_date__gte=encounter.started_at.date()
        ).exists()
        
        if not already_paid:
            consultation_price = Decimal('30.00')
            services_list.append({
                'type': 'consultation',
                'id': str(encounter.id),
                'obj': encounter,
                'name': f"{encounter.get_encounter_type_display()} Consultation",
                'price': consultation_price,
            })
            total_amount += consultation_price
    
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', total_amount))
        payment_method = request.POST.get('payment_method', 'cash')
        reference_number = request.POST.get('reference_number', '')
        notes = request.POST.get('notes', '')
        
        # Build service details list for combined receipt
        service_details_list = []
        for service in services_list:
            service_details_list.append({
                'type': service['type'],
                'name': service['name'],
                'price': str(service['price']),
                'service_id': service['id']
            })
        
        # Create combined receipt using UnifiedReceiptService
        from .services.unified_receipt_service import UnifiedReceiptService
        
        combined_service_details = {
            'services': service_details_list,
            'total_services': len(services_list),
            'combined_bill': True,
            'reference_number': reference_number
        }
        
        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=patient,
            amount=amount,
            payment_method=payment_method,
            received_by_user=request.user,
            service_type='combined',
            service_details=combined_service_details,
            notes=notes or f"Combined payment for {len(services_list)} service(s)"
        )
        
        if result and result.get('success'):
            receipt = result['receipt']
            
            # Update transaction reference number if provided
            if reference_number and hasattr(result, 'transaction'):
                result['transaction'].reference_number = reference_number
                result['transaction'].save()
            
            # Process each service payment individually (for accounting sync)
            receipts_created = []
            failed_services = []
            for service in services_list:
                try:
                    service_result = None
                    if service['type'] == 'lab':
                        service_result = LabPaymentService.create_lab_payment_receipt(
                            lab_result=service['obj'],
                            amount=service['price'],
                            payment_method=payment_method,
                            received_by_user=request.user,
                            notes=f"Part of combined bill {receipt.receipt_number}"
                        )
                    elif service['type'] == 'pharmacy':
                        service_result = PharmacyPaymentService.create_pharmacy_payment_receipt(
                            prescription=service['obj'],
                            amount=service['price'],
                            payment_method=payment_method,
                            received_by_user=request.user,
                            notes=f"Part of combined bill {receipt.receipt_number}"
                        )
                    elif service['type'] == 'imaging':
                        service_result = ImagingPaymentService.create_imaging_payment_receipt(
                            imaging_study=service['obj'],
                            amount=service['price'],
                            payment_method=payment_method,
                            received_by_user=request.user,
                            notes=f"Part of combined bill {receipt.receipt_number}"
                        )
                    elif service['type'] == 'consultation':
                        service_result = ConsultationPaymentService.create_consultation_payment_receipt(
                            encounter=service['obj'],
                            amount=service['price'],
                            payment_method=payment_method,
                            received_by_user=request.user,
                            notes=f"Part of combined bill {receipt.receipt_number}"
                        )
                    elif service['type'] == 'bed':
                        service_result = BedPaymentService.create_bed_payment_receipt(
                            admission=service['obj'],
                            amount=service['price'],
                            payment_method=payment_method,
                            received_by_user=request.user,
                            notes=f"Part of combined bill {receipt.receipt_number}"
                        )
                    elif service['type'] == 'pharmacy_walkin':
                        service_result = WalkInPharmacyService.create_payment_receipt(
                            sale=service['obj'],
                            amount=service['price'],
                            payment_method=payment_method,
                            received_by_user=request.user,
                            notes=f"Part of combined bill {receipt.receipt_number}"
                        )
                    
                    if service_result and service_result.get('success'):
                        receipts_created.append(service_result['receipt'])
                        logger.info(f"✅ Created individual receipt for {service['type']}: {service['name']}")
                    else:
                        error_msg = service_result.get('error') if service_result else 'No result returned'
                        failed_services.append({
                            'type': service['type'],
                            'name': service['name'],
                            'error': error_msg
                        })
                        logger.error(f"❌ Failed to create receipt for {service['type']} {service['name']}: {error_msg}")
                except Exception as e:
                    failed_services.append({
                        'type': service['type'],
                        'name': service['name'],
                        'error': str(e)
                    })
                    logger.error(f"❌ Exception processing service {service['type']} {service['id']}: {str(e)}", exc_info=True)
            
            # Show appropriate message based on results
            if failed_services:
                success_count = len(receipts_created)
                fail_count = len(failed_services)
                messages.warning(
                    request,
                    f"⚠️ Combined payment processed with issues! Receipt {receipt.receipt_number}. "
                    f"✅ {success_count} service(s) paid successfully. "
                    f"❌ {fail_count} service(s) failed to link. "
                    f"Total: GHS {amount}. Check logs for details."
                )
                # Show which services failed
                for failed in failed_services:
                    messages.error(request, f"❌ {failed['type']}: {failed['name']} - {failed['error']}")
            else:
                messages.success(
                    request,
                    f"✅ Combined payment processed! Receipt {receipt.receipt_number} for {len(services_list)} service(s). Total: GHS {amount}"
                )
            
            return redirect('hospital:cashier_combined_bill_print', receipt_id=receipt.id)
        else:
            error_msg = result.get('message', result.get('error', 'Unknown error')) if result else 'No result returned'
            messages.error(request, f"❌ Payment failed: {error_msg}")
            logger.error(f"Combined payment failed for patient {patient.id}: {error_msg}")
    
    context = {
        'title': f'Process Combined Payment - {patient.full_name}',
        'patient': patient,
        'services': services_list,
        'total_amount': total_amount,
        'service_count': len(services_list),
        'payment_methods': Transaction.PAYMENT_METHODS,
    }
    return render(request, 'hospital/cashier_combined_payment.html', context)


@login_required
@user_passes_test(is_cashier)
def cashier_combined_bill_print(request, receipt_id):
    """Print/view combined bill receipt"""
    from .models_payment_verification import ReceiptQRCode
    receipt = get_object_or_404(PaymentReceipt, id=receipt_id, is_deleted=False)
    
    # Get QR code if exists
    qr_code = None
    try:
        qr_code = ReceiptQRCode.objects.filter(receipt=receipt).first()
    except:
        pass
    
    # Get service details from QR code or receipt
    services = []
    service_details = None
    
    if qr_code and qr_code.qr_code_data:
        try:
            import json
            if isinstance(qr_code.qr_code_data, str):
                service_details = json.loads(qr_code.qr_code_data)
            elif isinstance(qr_code.qr_code_data, dict):
                service_details = qr_code.qr_code_data
        except:
            pass
    
    if service_details and 'service_details' in service_details:
        if isinstance(service_details['service_details'], dict) and 'services' in service_details['service_details']:
            services = service_details['service_details']['services']
        elif isinstance(service_details['service_details'], list):
            services = service_details['service_details']
    elif service_details and 'services' in service_details:
        services = service_details['services']
    
    context = {
        'receipt': receipt,
        'patient': receipt.patient,
        'services': services,
        'qr_code': qr_code,
    }
    return render(request, 'hospital/cashier_combined_bill_print.html', context)


@login_required
def cashier_revenue_report(request):
    """Revenue report with accounting breakdown"""
    from .services.accounting_sync_service import AccountingSyncService
    
    date_str = request.GET.get('date', timezone.now().date().isoformat())
    try:
        report_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        report_date = timezone.now().date()
    
    summary = AccountingSyncService.get_daily_revenue_summary(report_date)
    
    context = {
        'title': 'Revenue Report',
        'date': report_date,
        'today': timezone.now().date(),
        'summary': summary,
    }
    return render(request, 'hospital/cashier_revenue_report.html', context)


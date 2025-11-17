"""
Views for Hospital Management System frontend
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.db import models, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from datetime import timedelta
from uuid import UUID
import csv
from collections import OrderedDict, Counter
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

DEFAULT_QUICK_ACTIONS = [
    {'title': 'New Patient', 'icon': 'person-plus', 'gradient': 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', 'url_name': 'hospital:patient_create'},
    {'title': 'Accounting', 'icon': 'graph-up-arrow', 'gradient': 'linear-gradient(135deg, #10b981 0%, #059669 100%)', 'url_name': 'hospital:accounting_dashboard'},
    {'title': 'Procurement', 'icon': 'clipboard-check', 'gradient': 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)', 'url_name': 'hospital:admin_approval_list'},
    {'title': 'HOD Scheduling', 'icon': 'calendar-week', 'gradient': 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)', 'url_name': 'hospital:hod_scheduling_dashboard'},
    {'title': 'My Schedule', 'icon': 'clock-history', 'gradient': 'linear-gradient(135deg, #ec4899 0%, #db2777 100%)', 'url_name': 'hospital:staff_schedule_dashboard'},
    {'title': 'Backups', 'icon': 'shield-check', 'gradient': 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)', 'url_name': 'hospital:backup_dashboard'},
    {'title': 'Book Appointment', 'icon': 'calendar-plus', 'gradient': 'linear-gradient(135deg, #10b981 0%, #059669 100%)', 'url_name': 'hospital:frontdesk_appointment_create'},
    {'title': 'Patient Billing', 'icon': 'credit-card', 'gradient': 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)', 'url_name': 'hospital:cashier_patient_bills'},
    {'title': 'Pharmacy', 'icon': 'capsule', 'gradient': 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)', 'url_name': 'hospital:pharmacy_dashboard'},
    {'title': 'Laboratory', 'icon': 'flask', 'gradient': 'linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)', 'url_name': 'hospital:laboratory_dashboard'},
    {'title': 'Imaging', 'icon': 'camera', 'gradient': 'linear-gradient(135deg, #ec4899 0%, #db2777 100%)', 'url_name': 'hospital:imaging_dashboard'},
    {'title': 'Pricing', 'icon': 'tags', 'gradient': 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)', 'url_name': 'hospital:pricing_dashboard'},
    {'title': 'Insurance', 'icon': 'shield-check', 'gradient': 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 'url_name': 'hospital:insurance_management_dashboard'},
    {'title': 'HR Management', 'icon': 'people-fill', 'gradient': 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)', 'url_name': 'hospital:hr_worldclass_dashboard'},
    {'title': 'Beds', 'icon': 'hospital', 'gradient': 'linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)', 'url_name': 'hospital:bed_availability'},
    {'title': 'KPIs', 'icon': 'graph-up-arrow', 'gradient': 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', 'url_name': 'hospital:kpi_dashboard'},
    {'title': 'Search', 'icon': 'search', 'gradient': 'linear-gradient(135deg, #4b5563 0%, #374151 100%)', 'url_name': 'hospital:global_search'},
]

ROLE_SPECIFIC_QUICK_ACTIONS = {
    'accountant': [
        {'title': 'Accounting Hub', 'icon': 'calculator', 'gradient': 'linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%)', 'url_name': 'hospital:accountant_dashboard'},
        {'title': 'Invoices', 'icon': 'receipt', 'gradient': 'linear-gradient(135deg, #10b981 0%, #059669 100%)', 'url_name': 'hospital:invoice_list'},
        {'title': 'Cashier Hub', 'icon': 'cash-stack', 'gradient': 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)', 'url_name': 'hospital:centralized_cashier_dashboard'},
        {'title': 'Revenue Streams', 'icon': 'graph-up-arrow', 'gradient': 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', 'url_name': 'hospital:revenue_streams_dashboard'},
        {'title': 'Accounts Approval', 'icon': 'clipboard-check', 'gradient': 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)', 'url_name': 'hospital:accounts_approval_list'},
        {'title': 'Financial Reports', 'icon': 'bar-chart-line', 'gradient': 'linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)', 'url_name': 'hospital:revenue_report'},
    ]
}


def build_quick_actions(role):
    actions = ROLE_SPECIFIC_QUICK_ACTIONS.get(role, DEFAULT_QUICK_ACTIONS)
    resolved = []
    for action in actions:
        url = action.get('url')
        if not url:
            url_name = action.get('url_name')
            if url_name:
                try:
                    url = reverse(url_name)
                except Exception:
                    url = action.get('fallback_url', '#')
        resolved.append({**action, 'url': url})
    return resolved
from .models import (
    Patient, Encounter, Admission, Invoice, InvoiceLine, Bed,
    Appointment, LabResult, PharmacyStock, VitalSign, Order, Prescription, Staff, Drug, LabTest,
    Department, PatientQRCode
)
from .models_settings import HospitalSettings
from .forms import PatientForm, EncounterForm, TabularLabReportForm
from .utils import get_dashboard_stats, get_patient_demographics, get_encounter_statistics
from .utils_roles import get_user_role, get_user_dashboard_url, user_has_role_access
try:
    from .models_advanced import Queue
except ImportError:
    Queue = None
from .models_workflow import PatientFlowStage
# Reports
from .reports import generate_financial_report


@login_required
def dashboard(request):
    """World-Class Main Dashboard View with Role-Based Routing"""
    from decimal import Decimal
    from .models_accounting import Transaction, PaymentReceipt
    from .models_advanced import ImagingStudy
    
    # Role-based dashboard routing
    user_role = get_user_role(request.user) if request.user.is_authenticated else 'staff'
    if request.user.is_authenticated:
        
        # Redirect to role-specific dashboard
        if user_role == 'hr_manager':
            return redirect('hospital:hr_worldclass_dashboard')
        elif user_role == 'doctor':
            return redirect('hospital:medical_dashboard')
        elif user_role == 'nurse':
            return redirect('hospital:nurse_dashboard')
        elif user_role == 'pharmacist':
            return redirect('hospital:pharmacy_dashboard')
        elif user_role == 'lab_technician':
            return redirect('hospital:lab_technician_dashboard')
        elif user_role == 'receptionist':
            return redirect('hospital:reception_dashboard')
        elif user_role == 'cashier':
            return redirect('hospital:cashier_dashboard')
        elif user_role == 'admin':
            return redirect('hospital:admin_dashboard')
        # Accountants stay on general dashboard with trimmed actions
    
    stats = get_dashboard_stats()
    demographics = get_patient_demographics()
    encounter_stats = get_encounter_statistics()
    
    # Get recent encounters for activity feed
    recent_encounters = Encounter.objects.filter(
        is_deleted=False
    ).defer('current_activity').select_related('patient', 'provider', 'provider__user', 'location').order_by('-started_at')[:10]
    
    # Convert demographics to JSON for Chart.js
    import json
    demographics_json = json.dumps({
        'gender': demographics['gender'],
        'age_groups': demographics['age_groups'],
    })
    encounter_stats_json = json.dumps(encounter_stats)
    
    # Monthly trends data for charts
    monthly_trends_json = json.dumps({
        'labels': stats.get('month_labels', []),
        'patients': stats.get('monthly_patients', []),
        'encounters': stats.get('monthly_encounters', []),
    })
    
    # Additional dashboard data
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    four_hours_ago = timezone.now() - timedelta(hours=4)
    today_date = timezone.now().date()
    
    # Pending appointments
    pending_appointments = Appointment.objects.filter(
        appointment_date__gte=timezone.now(),
        status__in=['scheduled', 'confirmed'],
        is_deleted=False
    ).count()
    
    # Pending lab results
    pending_lab_results = LabResult.objects.filter(
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).count()
    
    # Low stock alerts
    try:
        low_stock_items = PharmacyStock.objects.filter(
            is_deleted=False
        ).extra(where=['quantity_on_hand <= reorder_level']).count()
    except Exception:
        low_stock_items = 0
    
    # Today's queue
    try:
        queue_today = Queue.objects.filter(
            checked_in_at__date=timezone.now().date(),
            status='waiting',
            is_deleted=False
        ).count() if Queue else 0
    except Exception:
        queue_today = 0
    
    # Encounters that need vital signs recorded
    encounters_without_vitals = []
    try:
        encounters_without_vitals = Encounter.objects.filter(
            status='active',
            is_deleted=False,
            started_at__date=timezone.now().date()
        ).exclude(
            pk__in=VitalSign.objects.filter(
                recorded_at__gte=four_hours_ago
            ).values_list('encounter_id', flat=True)
        ).select_related('patient').order_by('-started_at')[:10]
    except Exception:
        pass
    
    # Encounters with critical/abnormal vitals (for nurse dashboard)
    critical_vitals_encounters = []
    try:
        from .services.vital_signs_validator import VitalSignsValidator
        for enc in Encounter.objects.filter(
            status='active',
            is_deleted=False,
            vitals__recorded_at__gte=four_hours_ago
        ).distinct().select_related('patient')[:10]:
            latest_vital = enc.get_latest_vitals()
            if latest_vital and latest_vital.systolic_bp:
                vital_data = {
                    'systolic_bp': latest_vital.systolic_bp,
                    'diastolic_bp': latest_vital.diastolic_bp,
                    'pulse': latest_vital.pulse,
                    'temperature': latest_vital.temperature,
                    'spo2': latest_vital.spo2,
                    'respiratory_rate': latest_vital.respiratory_rate,
                }
                try:
                    validation = VitalSignsValidator.validate_all_vitals(
                        vital_data, enc.patient.age, enc.patient.gender
                    )
                    if validation.get('overall', {}).get('status') in ['critical', 'abnormal']:
                        critical_vitals_encounters.append({
                            'encounter': enc,
                            'vital': latest_vital,
                            'validation': validation
                        })
                except Exception:
                    pass
    except Exception:
        pass
    
    # Upcoming appointments for sidebar
    upcoming_appointments = Appointment.objects.filter(
        appointment_date__gte=timezone.now(),
        status__in=['scheduled', 'confirmed'],
        is_deleted=False
    ).select_related('patient', 'provider__user', 'department').order_by('appointment_date')[:5]
    
    # Additional stats for empty cards
    # Today's prescriptions
    prescriptions_today = Prescription.objects.filter(
        created__date=timezone.now().date(),
        is_deleted=False
    ).count()
    
    # Active orders
    active_orders = Order.objects.filter(
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).count()
    
    # Discharges today
    discharges_today = Admission.objects.filter(
        discharge_date__date=timezone.now().date(),
        status='discharged',
        is_deleted=False
    ).count()
    
    # Staff on duty (simplified)
    staff_on_duty = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).count()
    
    # ========== FINANCIAL STATISTICS (World-Class) ==========
    # Today's revenue from payments
    today_payments = PaymentReceipt.objects.filter(
        receipt_date__date=today_date,
        is_deleted=False
    )
    today_revenue = today_payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0')
    today_payment_count = today_payments.count()
    
    # This month's revenue
    month_start = today_date.replace(day=1)
    month_payments = PaymentReceipt.objects.filter(
        receipt_date__date__gte=month_start,
        receipt_date__date__lte=today_date,
        is_deleted=False
    )
    month_revenue = month_payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0')
    
    # Pending bills (unpaid services)
    pending_bills_count = 0
    try:
        from .models_advanced import ImagingStudy
        pending_lab = LabResult.objects.filter(status='completed', is_deleted=False).count()
        pending_pharmacy = Prescription.objects.filter(is_deleted=False).count()
        pending_imaging = ImagingStudy.objects.filter(status='completed', is_deleted=False).count()
        pending_bills_count = pending_lab + pending_pharmacy + pending_imaging
    except:
        pending_bills_count = 0
    
    # ========== DEPARTMENT STATISTICS (World-Class) ==========
    # Lab pending
    lab_pending = LabResult.objects.filter(
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).count()
    lab_completed_today = LabResult.objects.filter(
        status='completed',
        created__date=today_date,
        is_deleted=False
    ).count()
    
    # Pharmacy pending (prescriptions not yet dispensed)
    pharmacy_pending = Prescription.objects.filter(
        is_deleted=False
    ).exclude(
        id__in=PharmacyDispensing.objects.values_list('prescription_id', flat=True) if 'PharmacyDispensing' in dir() else []
    ).count() if 'PharmacyDispensing' in dir() else Prescription.objects.filter(is_deleted=False).count()
    pharmacy_dispensed_today = 0
    try:
        from .models_advanced import PharmacyDispensing
        pharmacy_dispensed_today = PharmacyDispensing.objects.filter(
            dispensed_at__date=today_date,
            is_deleted=False
        ).count()
    except:
        pass
    
    # Imaging pending and completed
    imaging_pending = 0
    imaging_completed_today = 0
    try:
        imaging_pending = ImagingStudy.objects.filter(
            status__in=['pending', 'in_progress'],
            is_deleted=False
        ).count()
        imaging_completed_today = ImagingStudy.objects.filter(
            status='completed',
            created_at__date=today_date,
            is_deleted=False
        ).count()
    except:
        pass
    
    # ========== ALERTS & NOTIFICATIONS (World-Class) ==========
    alerts = []
    
    # Critical patients (with abnormal vitals)
    if len(critical_vitals_encounters) > 0:
        alerts.append({
            'type': 'danger',
            'icon': 'exclamation-triangle-fill',
            'title': 'Critical Patients',
            'message': f'{len(critical_vitals_encounters)} patient(s) with critical/abnormal vital signs',
            'action_url': '#',
            'action_text': 'View Patients'
        })
    
    # Expiring contracts alert
    try:
        from .models_contracts import Contract
        expiring_contracts = Contract.objects.filter(
            end_date__gte=today_date,
            end_date__lte=today_date + timedelta(days=30),
            is_deleted=False
        ).count()
        if expiring_contracts > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'file-earmark-text-fill',
                'title': 'Contracts Expiring',
                'message': f'{expiring_contracts} contract(s) expiring in the next 30 days',
                'action_url': '/hms/contracts/',
                'action_text': 'View Contracts'
            })
    except:
        pass
    
    # Expiring certificates alert
    try:
        from .models_contracts import Certificate
        expiring_certs = Certificate.objects.filter(
            expiry_date__gte=today_date,
            expiry_date__lte=today_date + timedelta(days=60),
            is_deleted=False
        ).count()
        if expiring_certs > 0:
            alerts.append({
                'type': 'warning',
                'icon': 'award-fill',
                'title': 'Certificates Expiring',
                'message': f'{expiring_certs} certificate(s) expiring in the next 60 days',
                'action_url': '/hms/certificates/list/',
                'action_text': 'View Certificates'
            })
    except:
        pass
    
    # Low stock items
    if low_stock_items > 0:
        alerts.append({
            'type': 'warning',
            'icon': 'box-seam',
            'title': 'Low Stock Alert',
            'message': f'{low_stock_items} medication(s) running low on stock',
            'action_url': '/hms/pharmacy/',
            'action_text': 'Manage Stock'
        })
    
    # Pending lab results
    if lab_pending > 5:
        alerts.append({
            'type': 'info',
            'icon': 'flask',
            'title': 'Pending Lab Tests',
            'message': f'{lab_pending} lab test(s) awaiting processing',
            'action_url': '/hms/lab/',
            'action_text': 'View Lab Queue'
        })
    
    # Patients without vitals
    if len(encounters_without_vitals) > 0:
        alerts.append({
            'type': 'warning',
            'icon': 'heart-pulse',
            'title': 'Missing Vital Signs',
            'message': f'{len(encounters_without_vitals)} patient(s) need vital signs recorded',
            'action_url': '#',
            'action_text': 'Record Vitals'
        })
    
    context = {
        'stats': stats,
        'demographics': demographics,
        'demographics_json': demographics_json,
        'encounter_stats_json': encounter_stats_json,
        'monthly_trends_json': monthly_trends_json,
        'recent_encounters': recent_encounters,
        'pending_appointments': pending_appointments,
        'pending_lab_results': pending_lab_results,
        'low_stock_items': low_stock_items,
        'queue_today': queue_today,
        'upcoming_appointments': upcoming_appointments,
        'encounters_without_vitals': encounters_without_vitals,
        'critical_vitals_encounters': critical_vitals_encounters,
        'prescriptions_today': prescriptions_today,
        'active_orders': active_orders,
        'discharges_today': discharges_today,
        # Financial stats
        'today_revenue': today_revenue,
        'today_payment_count': today_payment_count,
        'month_revenue': month_revenue,
        'pending_bills_count': pending_bills_count,
        # Department stats
        'lab_pending': lab_pending,
        'lab_completed_today': lab_completed_today,
        'pharmacy_pending': pharmacy_pending,
        'pharmacy_dispensed_today': pharmacy_dispensed_today,
        'imaging_pending': imaging_pending,
        'imaging_completed_today': imaging_completed_today,
        # Alerts
        'alerts': alerts,
        'staff_on_duty': staff_on_duty,
        'user_role': user_role,
        'quick_actions': build_quick_actions(user_role),
    }
    
    # Procurement Approval Notifications
    try:
        from .models_procurement import ProcurementRequest
        
        # Check if user has admin approval permission
        if request.user.has_perm('hospital.can_approve_procurement_admin') or request.user.is_superuser:
            pending_admin_approvals = ProcurementRequest.objects.filter(
                status='submitted',
                is_deleted=False
            ).count()
            context['pending_admin_approvals'] = pending_admin_approvals
        
        # Check if user has accounts approval permission
        if request.user.has_perm('hospital.can_approve_procurement_accounts') or request.user.is_superuser:
            pending_accounts_approvals = ProcurementRequest.objects.filter(
                status='admin_approved',
                is_deleted=False
            ).count()
            context['pending_accounts_approvals'] = pending_accounts_approvals
    except Exception:
        # If procurement module not available, skip
        pass
    
    return render(request, 'hospital/dashboard.html', context)


@login_required
def end_session(request):
    """
    Explicit 'End Session' action for any user.
    Logs the user out and ends their active UserSession record via signals.
    """
    # Default to main HMS dashboard (which will enforce login as needed)
    next_url = request.GET.get('next') or '/hms/'
    auth_logout(request)
    return redirect(next_url)


@login_required
def patient_list(request):
    """List all patients - OPTIMIZED for mobile performance"""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from .models_legacy_patients import LegacyPatient
    from datetime import datetime
    from django.core.cache import cache
    
    query = request.GET.get('q', '').strip()
    source_filter = request.GET.get('source', 'all')  # 'all', 'new', 'legacy'
    page_number = request.GET.get('page', 1)
    per_page = 25  # Reduced from 50 for faster mobile loading
    
    # Cache counts for 5 minutes to avoid repeated expensive queries
    cache_key = f'patient_counts_{source_filter}'
    counts = cache.get(cache_key)
    if not counts:
        new_count = Patient.objects.filter(is_deleted=False).count()
        legacy_count = LegacyPatient.objects.count()
        counts = {'new': new_count, 'legacy': legacy_count, 'total': new_count + legacy_count}
        cache.set(cache_key, counts, 300)  # Cache for 5 minutes
    
    new_count = counts['new']
    legacy_count = counts['legacy']
    total_count = counts['total']
    
    all_patients = []
    
    # Filter based on source selection
    if source_filter == 'new':
        # Only new Django patients
        django_patients = Patient.objects.filter(is_deleted=False).only(
            'id', 'first_name', 'last_name', 'middle_name', 'mrn', 'date_of_birth', 
            'gender', 'phone_number', 'created'
        ).order_by('-created')
        
        if query:
            django_patients = django_patients.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(middle_name__icontains=query) |
                Q(mrn__icontains=query) |
                Q(phone_number__icontains=query) |
                Q(national_id__icontains=query)
            )
        
        # Convert to list
        for p in django_patients:
            all_patients.append({
                'id': str(p.id),
                'name': p.full_name,
                'mrn': p.mrn,
                'dob': p.date_of_birth,
                'age': p.age,
                'gender': p.get_gender_display(),
                'phone': p.phone_number,
                'source': 'new',
                'initials': f"{p.first_name[0] if p.first_name else ''}{p.last_name[0] if p.last_name else ''}",
                'view_url': f"/hms/patients/{p.id}/",
                'edit_url': f"/hms/patients/{p.id}/edit/",
            })
    
    elif source_filter == 'legacy':
        # Only legacy patients
        legacy_patients = LegacyPatient.objects.all().only(
            'id', 'pid', 'fname', 'lname', 'mname', 'DOB', 'sex', 'phone_cell', 'pmc_mrn'
        ).order_by('lname', 'fname')
        
        if query:
            legacy_patients = legacy_patients.filter(
                Q(fname__icontains=query) |
                Q(lname__icontains=query) |
                Q(mname__icontains=query) |
                Q(pid__icontains=query) |
                Q(phone_cell__icontains=query) |
                Q(pmc_mrn__icontains=query)
            )
        
        # Convert to list
        for lp in legacy_patients:
            # Calculate age from DOB string
            age_str = ''
            try:
                if lp.DOB:
                    dob = datetime.strptime(lp.DOB, '%Y-%m-%d').date()
                    today = datetime.today().date()
                    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                    age_str = f"{age} years"
            except:
                age_str = 'Unknown'
            
            all_patients.append({
                'id': f"legacy-{lp.id}",
                'name': lp.full_name,
                'mrn': lp.mrn_display,
                'dob': lp.DOB or 'Unknown',
                'age': age_str,
                'gender': lp.sex or 'Unknown',
                'phone': lp.display_phone,
                'source': 'legacy',
                'initials': f"{lp.fname[0] if lp.fname else ''}{lp.lname[0] if lp.lname else ''}",
                'view_url': f"/hms/patients/legacy/{lp.id}/",
                'edit_url': None,  # Legacy patients are read-only
            })
    
    else:  # 'all' - show both (OPTIMIZED: limit initial load)
        # MOBILE OPTIMIZATION: Only load 100 most recent from each source
        # This prevents loading thousands of patients on initial page load
        limit = 100 if not query else 1000  # Search needs more records
        
        # Get new patients (limited)
        django_patients = Patient.objects.filter(is_deleted=False).only(
            'id', 'first_name', 'last_name', 'middle_name', 'mrn', 'date_of_birth', 
            'gender', 'phone_number', 'created'
        ).order_by('-created')[:limit]
        
        if query:
            django_patients = Patient.objects.filter(
                is_deleted=False
            ).filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(middle_name__icontains=query) |
                Q(mrn__icontains=query) |
                Q(phone_number__icontains=query) |
                Q(national_id__icontains=query)
            ).only(
                'id', 'first_name', 'last_name', 'middle_name', 'mrn', 'date_of_birth', 
                'gender', 'phone_number', 'created'
            ).order_by('-created')[:limit]
        
        # Add new patients
        for p in django_patients:
            all_patients.append({
                'id': str(p.id),
                'name': p.full_name,
                'mrn': p.mrn,
                'dob': p.date_of_birth,
                'age': p.age,
                'gender': p.get_gender_display(),
                'phone': p.phone_number,
                'source': 'new',
                'initials': f"{p.first_name[0] if p.first_name else ''}{p.last_name[0] if p.last_name else ''}",
                'view_url': f"/hms/patients/{p.id}/",
                'edit_url': f"/hms/patients/{p.id}/edit/",
            })
        
        # Get legacy patients (limited for performance)
        if query:
            legacy_patients = LegacyPatient.objects.filter(
                Q(fname__icontains=query) |
                Q(lname__icontains=query) |
                Q(mname__icontains=query) |
                Q(pid__icontains=query) |
                Q(phone_cell__icontains=query) |
                Q(pmc_mrn__icontains=query)
            ).only(
                'id', 'pid', 'fname', 'lname', 'mname', 'DOB', 'sex', 'phone_cell', 'pmc_mrn'
            ).order_by('lname', 'fname')[:limit]
        else:
            # No search: only load 100 most recent legacy patients
            legacy_patients = LegacyPatient.objects.all().only(
                'id', 'pid', 'fname', 'lname', 'mname', 'DOB', 'sex', 'phone_cell', 'pmc_mrn'
            ).order_by('-id')[:limit]
        
        # Add legacy patients
        for lp in legacy_patients:
            # Calculate age from DOB string
            age_str = ''
            try:
                if lp.DOB:
                    dob = datetime.strptime(lp.DOB, '%Y-%m-%d').date()
                    today = datetime.today().date()
                    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                    age_str = f"{age} years"
            except:
                age_str = 'Unknown'
            
            all_patients.append({
                'id': f"legacy-{lp.id}",
                'name': lp.full_name,
                'mrn': lp.mrn_display,
                'dob': lp.DOB or 'Unknown',
                'age': age_str,
                'gender': lp.sex or 'Unknown',
                'phone': lp.display_phone,
                'source': 'legacy',
                'initials': f"{lp.fname[0] if lp.fname else ''}{lp.lname[0] if lp.lname else ''}",
                'view_url': f"/hms/patients/legacy/{lp.id}/",
                'edit_url': None,  # Legacy patients are read-only
            })
    
    # PAGINATION - Show 25 patients per page (faster on mobile)
    paginator = Paginator(all_patients, per_page)
    
    try:
        patients_page = paginator.page(page_number)
    except PageNotAnInteger:
        patients_page = paginator.page(1)
    except EmptyPage:
        patients_page = paginator.page(paginator.num_pages)
    
    context = {
        'page_obj': patients_page,
        'patients': patients_page.object_list,  # List of current page patients
        'query': query,
        'source': source_filter,
        'total_count': len(all_patients),
        'new_count': new_count,
        'legacy_count': legacy_count,
        'is_paginated': patients_page.has_other_pages(),
        'page_range': paginator.get_elided_page_range(page_number, on_each_side=2, on_ends=1),
    }
    
    return render(request, 'hospital/patient_list.html', context)


@login_required
def patient_create(request):
    """Create a new patient with insurance enrollment"""
    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = form.save()
            # Ensure MRN is generated
            if not patient.mrn:
                patient.mrn = Patient.generate_mrn()
                patient.save(update_fields=['mrn'])
            
            # Generate QR code credentials for ID card printing
            try:
                patient.ensure_qr_profile()
            except Exception as qr_error:
                logger.warning(f"Failed to provision patient QR card: {qr_error}", exc_info=True)
            
            # Handle insurance enrollment if selected
            selected_insurance_company = form.cleaned_data.get('selected_insurance_company')
            selected_insurance_plan = form.cleaned_data.get('selected_insurance_plan')
            insurance_id = form.cleaned_data.get('insurance_id')
            insurance_member_id = form.cleaned_data.get('insurance_member_id')
            
            if selected_insurance_company and (insurance_id or insurance_member_id):
                try:
                    from .models_insurance_companies import PatientInsurance
                    from .models import Payer
                    
                    # Create patient insurance enrollment
                    enrollment = PatientInsurance.objects.create(
                        patient=patient,
                        insurance_company=selected_insurance_company,
                        insurance_plan=selected_insurance_plan,
                        policy_number=insurance_id or '',
                        member_id=insurance_member_id or insurance_id or '',
                        is_primary_subscriber=True,
                        relationship_to_subscriber='self',
                        effective_date=timezone.now().date(),
                        is_primary=True,
                        status='active',
                    )
                    
                    # Update patient's primary insurance in Payer table
                    payer, _ = Payer.objects.get_or_create(
                        name=selected_insurance_company.name,
                        defaults={
                            'payer_type': 'private',
                            'is_active': True,
                        }
                    )
                    patient.primary_insurance = payer
                    patient.insurance_company = selected_insurance_company.name
                    patient.insurance_member_id = insurance_member_id
                    patient.insurance_id = insurance_id
                    patient.save(update_fields=['primary_insurance', 'insurance_company', 
                                              'insurance_member_id', 'insurance_id'])
                    
                    messages.success(request, f'✅ Patient enrolled in {selected_insurance_company.name}!')
                except Exception as e:
                    messages.warning(request, f'Patient registered, but insurance enrollment failed: {str(e)}')
            
            # Send welcome SMS to new patient
            if patient.phone_number:
                try:
                    from .services.sms_service import sms_service
                    message = (
                        f"Welcome to PrimeCare Hospital, {patient.first_name}!\n\n"
                        f"Your Medical Record Number (MRN): {patient.mrn}\n"
                        f"Please keep this number for future visits.\n\n"
                        f"Thank you for choosing us for your healthcare needs.\n\n"
                        f"PrimeCare Hospital\n"
                        f"Call us: [Hospital Contact]"
                    )
                    sms_service.send_sms(
                        phone_number=patient.phone_number,
                        message=message,
                        message_type='patient_registration',
                        recipient_name=patient.full_name,
                        related_object_id=patient.id,
                        related_object_type='Patient'
                    )
                    messages.success(request, f'Patient registered successfully! Welcome SMS sent to {patient.phone_number}.')
                except Exception as e:
                    messages.warning(request, f'Patient registered successfully, but SMS could not be sent: {str(e)}')
            else:
                messages.success(request, 'Patient registered successfully! No phone number provided for SMS.')
            
            # Auto-create encounter and redirect to vital signs
            from django.utils import timezone
            from .models import Encounter, Department, Staff
            from .models_workflow import PatientFlowStage
            
            # Get or create default department for registration
            default_dept = Department.objects.filter(name__icontains='outpatient').first()
            if not default_dept:
                default_dept = Department.objects.first()
            
            # Get current staff if available
            current_staff = None
            if hasattr(request.user, 'staff'):
                current_staff = request.user.staff
            
            # Create encounter
            encounter = Encounter.objects.create(
                patient=patient,
                encounter_type='outpatient',
                status='active',
                started_at=timezone.now(),
                location=None,
                provider=current_staff,
                chief_complaint='New patient registration',
                notes='Auto-created during registration'
            )
            
            # 🎫 QUEUE SYSTEM: Assign queue number and send SMS
            try:
                from .services.queue_service import queue_service
                from .services.queue_notification_service import queue_notification_service
                
                # Create queue entry (priority: 1=Emergency, 2=Urgent, 3=Normal, 4=Follow-up)
                queue_entry = queue_service.create_queue_entry(
                    patient=patient,
                    encounter=encounter,
                    department=default_dept,
                    assigned_doctor=None,
                    priority=3,  # 3 = Normal priority
                    notes='New patient registration'
                )
                
                # Send queue SMS notification
                queue_notification_service.send_check_in_notification(queue_entry)
                
                logger.info(f"✅ Queue entry created: {queue_entry.queue_number} for {patient.full_name}")
                
            except Exception as e:
                logger.error(f"Error creating queue entry: {str(e)}", exc_info=True)
                # Don't fail patient creation if queue fails
            
            # Create vital signs stage in patient flow
            from .models_workflow import PatientFlowStage
            PatientFlowStage.objects.create(
                encounter=encounter,
                stage_type='vitals',
                status='pending'
            )
            
            # Auto-create invoice with registration fee (50 GHS)
            try:
                from .models import Invoice, InvoiceLine, ServiceCode, Payer
                from .models_pricing import DefaultPrice, PayerPrice
                from decimal import Decimal
                
                # Get patient's payer (default to Cash if not set)
                payer = patient.primary_insurance
                if not payer:
                    # Try to get Cash payer
                    payer = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
                    if not payer:
                        # Try any active payer
                        payer = Payer.objects.filter(is_active=True, is_deleted=False).first()
                        if not payer:
                            # Create a default Cash payer if none exists
                            payer = Payer.objects.create(
                                name='Cash',
                                payer_type='cash',
                                is_active=True
                            )
                
                if payer:
                    # Get registration price (check payer-specific first, then default)
                    registration_price = PayerPrice.get_price(payer, 'registration')
                    if registration_price is None:
                        registration_price = DefaultPrice.get_price('registration', Decimal('50.00'))
                else:
                    # Default 50 GHS if no payer
                    registration_price = DefaultPrice.get_price('registration', Decimal('50.00'))
                
                # Get or create Registration service code
                reg_service, _ = ServiceCode.objects.get_or_create(
                    code='REG001',
                    defaults={
                        'description': 'Patient Registration Fee',
                        'category': 'Administrative',
                        'is_active': True,
                    }
                )
                
                # Only create invoice if payer exists
                if payer:
                    # Set invoice due date (30 days from now)
                    from datetime import timedelta
                    due_date = timezone.now() + timedelta(days=30)
                    
                    # Create invoice
                    invoice = Invoice.objects.create(
                        patient=patient,
                        encounter=encounter,
                        payer=payer,
                        status='draft',
                        due_at=due_date
                    )
                    
                    # Add registration fee line
                    InvoiceLine.objects.create(
                        invoice=invoice,
                        service_code=reg_service,
                        description='Patient Registration Fee',
                        quantity=1,
                        unit_price=registration_price,
                        line_total=registration_price
                    )
                    
                    # Update invoice totals
                    invoice.update_totals()
                
            except Exception as e:
                # Log error but don't break patient registration
                logger.error(f"Error creating registration invoice: {str(e)}")
            
            messages.success(request, f'Patient {patient.full_name} registered successfully with Patient ID: <strong>{patient.mrn}</strong>. Please record vital signs.', extra_tags='html')
            return redirect('hospital:record_vitals', encounter_id=encounter.pk)
    else:
        form = PatientForm()
    
    context = {'form': form, 'title': 'Register New Patient'}
    return render(request, 'hospital/patient_form.html', context)


@login_required
def patient_detail(request, pk):
    """OPTIMIZED patient detail view for fast mobile loading"""
    from .models import Encounter, VitalSign, Order, Invoice, LabResult
    from django.core.cache import cache
    
    # Get patient with optimized query
    patient = get_object_or_404(
        Patient.objects.select_related('primary_insurance'),
        pk=pk, 
        is_deleted=False
    )
    
    # MOBILE OPTIMIZATION: Limit initial data load
    # Use smaller limits for faster page load - users can click "View More" if needed
    ENCOUNTER_LIMIT = 10  # Reduced from 20
    VITALS_LIMIT = 10  # Reduced from 50
    RESULTS_LIMIT = 10  # Reduced from 30
    ORDERS_LIMIT = 10  # Reduced from 30
    INVOICES_LIMIT = 10  # Reduced from 20
    
    # Get encounters with optimized query
    all_encounters = Encounter.objects.filter(
        patient=patient,
        is_deleted=False
    ).select_related('provider__user', 'location').order_by('-started_at')
    
    encounters = all_encounters[:ENCOUNTER_LIMIT]
    active_encounters = all_encounters.filter(status='active')[:5]
    completed_encounters = all_encounters.filter(status='completed')[:5]
    last_encounter = all_encounters.first()
    last_visit_date = last_encounter.started_at if last_encounter else None
    
    # Get vital signs (limited)
    all_vitals = VitalSign.objects.filter(
        encounter__patient=patient,
        is_deleted=False
    ).select_related('encounter').order_by('-recorded_at')[:VITALS_LIMIT]
    
    # Get orders (limited)
    all_orders = Order.objects.filter(
        encounter__patient=patient,
        is_deleted=False
    ).select_related('encounter', 'requested_by__user').order_by('-requested_at')[:ORDERS_LIMIT]
    
    # Get lab results (limited)
    all_lab_results = LabResult.objects.filter(
        order__encounter__patient=patient,
        is_deleted=False
    ).select_related('test', 'order__encounter').order_by('-verified_at')[:RESULTS_LIMIT]
    
    # Get medications (limited)
    try:
        from .models import Prescription
        all_prescriptions = Prescription.objects.filter(
            order__encounter__patient=patient,
            is_deleted=False
        ).select_related('drug', 'order__encounter').order_by('-created')[:ORDERS_LIMIT]
    except:
        all_prescriptions = []
    
    # Get invoices (limited)
    all_invoices = Invoice.objects.filter(
        patient=patient,
        is_deleted=False
    ).order_by('-issued_at')[:INVOICES_LIMIT]
    
    # Cache expensive count queries for 2 minutes
    stats_cache_key = f'patient_stats_{pk}'
    stats = cache.get(stats_cache_key)
    if not stats:
        total_encounters = all_encounters.count()
        total_vitals = VitalSign.objects.filter(encounter__patient=patient, is_deleted=False).count()
        total_orders = Order.objects.filter(encounter__patient=patient, is_deleted=False).count()
        stats = {'encounters': total_encounters, 'vitals': total_vitals, 'orders': total_orders}
        cache.set(stats_cache_key, stats, 120)  # Cache for 2 minutes
    
    total_encounters = stats['encounters']
    total_vitals = stats['vitals']
    total_orders = stats['orders']
    total_lab_tests = LabResult.objects.filter(order__encounter__patient=patient, is_deleted=False).count()
    
    # Get latest vital signs
    latest_vitals = all_vitals.first()
    
    # Calculate total billing
    from decimal import Decimal
    total_billed = sum([invoice.total_amount or Decimal('0.00') for invoice in all_invoices])
    total_paid = sum([invoice.amount_paid or Decimal('0.00') for invoice in all_invoices])
    total_outstanding = total_billed - total_paid
    
    hospital_settings = HospitalSettings.get_settings()
    prepared_by = request.user.get_full_name() or request.user.username
    qr_profile = getattr(patient, 'qr_profile', None)
    
    context = {
        'patient': patient,
        'encounters': encounters,
        'active_encounters': active_encounters,
        'completed_encounters': completed_encounters,
        'all_vitals': all_vitals,
        'latest_vitals': latest_vitals,
        'all_orders': all_orders,
        'all_lab_results': all_lab_results,
        'all_prescriptions': all_prescriptions,
        'invoices': all_invoices,
        # Statistics
        'total_encounters': total_encounters,
        'total_vitals': total_vitals,
        'total_orders': total_orders,
        'total_lab_tests': total_lab_tests,
        'total_billed': total_billed,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
        'now': timezone.now(),
        'last_visit_date': last_visit_date,
        'hospital_settings': hospital_settings,
        'prepared_by': prepared_by,
        'qr_profile': qr_profile,
        'qr_card_url': reverse('hospital:patient_qr_card', args=[patient.pk]) if qr_profile else None,
        'qr_checkin_url': reverse('hospital:patient_qr_checkin'),
    }
    return render(request, 'hospital/patient_medical_record_sheet.html', context)


@login_required
def patient_qr_card(request, patient_pk):
    """Printable patient ID card with QR code"""
    patient = get_object_or_404(Patient, pk=patient_pk, is_deleted=False)
    try:
        qr_profile = patient.ensure_qr_profile()
    except Exception as exc:
        logger.error(f"Failed to refresh QR card for patient {patient_pk}: {exc}", exc_info=True)
        qr_profile = getattr(patient, 'qr_profile', None)
    
    context = {
        'patient': patient,
        'qr_profile': qr_profile,
        'hospital_settings': HospitalSettings.get_settings(),
        'generated_at': timezone.now(),
    }
    return render(request, 'hospital/patient_qr_card.html', context)


@login_required
def patient_qr_checkin(request):
    """Receptionist QR scanning console for instant visit creation"""
    departments = Department.objects.filter(is_deleted=False).order_by('name')
    default_department = departments.filter(name__icontains='outpatient').first() or departments.first()
    
    context = {
        'departments': departments,
        'default_department': default_department,
        'hospital_settings': HospitalSettings.get_settings(),
    }
    return render(request, 'hospital/patient_qr_checkin.html', context)


@login_required
def patient_qr_checkin_api(request):
    """AJAX endpoint triggered by QR scanner to auto-create visits"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
    
    qr_data = request.POST.get('qr_data', '').strip()
    if not qr_data:
        return JsonResponse({'success': False, 'error': 'QR code data is required.'}, status=400)
    
    try:
        patient_uuid, qr_token = PatientQRCode.parse_payload(qr_data)
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)
    
    patient = Patient.objects.filter(pk=patient_uuid, is_deleted=False).select_related('primary_insurance').first()
    if not patient:
        return JsonResponse({'success': False, 'error': 'Patient record not found.'}, status=404)
    
    qr_profile = getattr(patient, 'qr_profile', None)
    if not qr_profile or qr_profile.qr_token != qr_token:
        return JsonResponse({'success': False, 'error': 'QR code does not match this patient.'}, status=400)
    
    encounter_type = request.POST.get('encounter_type', 'outpatient')
    chief_complaint = request.POST.get('chief_complaint', '').strip() or 'QR check-in at reception'
    department_id = request.POST.get('department_id')
    
    department = None
    if department_id:
        try:
            department = Department.objects.get(pk=department_id, is_deleted=False)
        except (Department.DoesNotExist, ValueError):
            department = None
    
    if not department:
        department = Department.objects.filter(name__icontains='outpatient', is_deleted=False).first()
    if not department:
        department = Department.objects.filter(is_deleted=False).first()
    if not department:
        return JsonResponse({'success': False, 'error': 'No active departments configured.'}, status=400)
    
    from .models_queue import QueueEntry
    today = timezone.now().date()
    active_queue = QueueEntry.objects.filter(
        patient=patient,
        queue_date=today,
        status__in=['checked_in', 'called', 'in_progress'],
        is_deleted=False
    ).select_related('department', 'encounter').order_by('-created').first()
    
    if active_queue:
        queue_position = None
        try:
            from .services.queue_service import queue_service
            queue_position = queue_service.get_position_in_queue(active_queue)
        except Exception:
            queue_position = None
        qr_profile.mark_scan(request.user)
        return JsonResponse({
            'success': True,
            'already_checked_in': True,
            'message': f'{patient.full_name} is already in queue {active_queue.queue_number}.',
            'patient': {
                'name': patient.full_name,
                'mrn': patient.mrn,
            },
            'queue': {
                'number': active_queue.queue_number,
                'status': active_queue.get_status_display(),
                'position': queue_position,
                'department': active_queue.department.name if active_queue.department else '',
            },
            'encounter': {
                'id': str(active_queue.encounter_id) if active_queue.encounter_id else None,
                'type': active_queue.encounter.get_encounter_type_display() if active_queue.encounter else encounter_type,
            }
        })
    
    current_staff = getattr(request.user, 'staff', None)
    encounter = None
    encounter_created = False
    
    try:
        with transaction.atomic():
            existing_encounter = Encounter.objects.filter(
                patient=patient,
                status='active',
                is_deleted=False
            ).order_by('-started_at').first()
            
            if existing_encounter and existing_encounter.started_at.date() == today:
                encounter = existing_encounter
            else:
                encounter = Encounter.objects.create(
                    patient=patient,
                    encounter_type=encounter_type,
                    status='active',
                    started_at=timezone.now(),
                    provider=current_staff,
                    chief_complaint=chief_complaint,
                    notes=f'QR check-in by {request.user.get_full_name() or request.user.username}'
                )
                encounter_created = True
                # Initialize patient flow stage
                try:
                    PatientFlowStage.objects.create(
                        encounter=encounter,
                        stage_type='vitals',
                        status='pending'
                    )
                except Exception:
                    pass
            
            from .services.queue_service import queue_service
            from .services.queue_notification_service import queue_notification_service
            
            queue_entry = queue_service.create_queue_entry(
                patient=patient,
                encounter=encounter,
                department=department,
                assigned_doctor=current_staff.user if current_staff else None,
                priority=1 if encounter_type == 'emergency' else 3,
                notes=chief_complaint
            )
            queue_position = queue_service.get_position_in_queue(queue_entry)
            try:
                queue_notification_service.send_check_in_notification(queue_entry)
            except Exception as notify_error:
                logger.warning(f"QR check-in notification failed: {notify_error}")
    except Exception as exc:
        logger.error(f"QR check-in failed for patient {patient.pk}: {exc}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Unable to complete QR check-in. Please process manually.'}, status=500)
    
    qr_profile.mark_scan(request.user)
    
    return JsonResponse({
        'success': True,
        'message': f'{patient.full_name} checked in successfully.',
        'already_checked_in': False,
        'patient': {
            'name': patient.full_name,
            'mrn': patient.mrn,
        },
        'encounter': {
            'id': str(encounter.id),
            'type': encounter.get_encounter_type_display(),
            'created': encounter_created,
            'started_at': timezone.localtime(encounter.started_at).strftime('%Y-%m-%d %H:%M'),
        },
        'queue': {
            'number': queue_entry.queue_number,
            'position': queue_position,
            'status': queue_entry.get_status_display(),
            'estimated_wait': queue_entry.estimated_wait_minutes,
            'department': department.name if department else '',
        }
    })


@login_required
def patient_edit(request, pk):
    """Edit patient"""
    patient = get_object_or_404(Patient, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, f'Patient {patient.full_name} updated successfully.')
            return redirect('hospital:patient_detail', pk=patient.pk)
    else:
        form = PatientForm(instance=patient)
    
    context = {
        'form': form,
        'patient': patient,
    }
    return render(request, 'hospital/patient_form.html', context)


@login_required
def encounter_list(request):
    """List all encounters"""
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    query = request.GET.get('q', '')
    
    encounters = Encounter.objects.filter(is_deleted=False).defer('current_activity').select_related(
        'patient', 'provider__user', 'location'
    ).prefetch_related('provider__department')
    
    if query:
        encounters = encounters.filter(
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(patient__mrn__icontains=query)
        )
    if status_filter:
        encounters = encounters.filter(status=status_filter)
    if type_filter:
        encounters = encounters.filter(encounter_type=type_filter)
    
    encounters = encounters.order_by('-started_at')
    
    # Pagination
    paginator = Paginator(encounters, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'encounters': page_obj,
        'status_filter': status_filter,
        'type_filter': type_filter,
    }
    return render(request, 'hospital/encounter_list.html', context)


@login_required
def encounter_create(request):
    """Create a new encounter"""
    if request.method == 'POST':
        form = EncounterForm(request.POST)
        if form.is_valid():
            encounter = form.save()
            messages.success(request, 'Encounter created successfully.')
            return redirect('hospital:encounter_detail', pk=encounter.pk)
    else:
        form = EncounterForm()
    
    context = {'form': form}
    return render(request, 'hospital/encounter_form.html', context)


@login_required
def patient_quick_visit_create(request, patient_pk):
    """Quick visit/encounter creation for returning patients"""
    patient = get_object_or_404(Patient, pk=patient_pk, is_deleted=False)
    
    if request.method == 'POST':
        encounter_type = request.POST.get('encounter_type', 'outpatient')
        chief_complaint = request.POST.get('chief_complaint', 'Follow-up visit')
        
        # Get current staff if available
        current_staff = None
        if hasattr(request.user, 'staff'):
            current_staff = request.user.staff
        
        # Create encounter/visit
        encounter = Encounter.objects.create(
            patient=patient,
            encounter_type=encounter_type,
            status='active',
            started_at=timezone.now(),
            provider=current_staff,
            chief_complaint=chief_complaint,
            notes=f'Visit created by {request.user.get_full_name() or request.user.username}'
        )
        
        # Create vital signs stage in patient flow
        try:
            from .models_workflow import PatientFlowStage
            PatientFlowStage.objects.create(
                encounter=encounter,
                stage_type='vitals',
                status='pending'
            )
        except:
            pass
        
        # 🎫 QUEUE SYSTEM: Assign queue number and send SMS notification
        queue_number = None
        queue_position = None
        try:
            from .services.queue_service import queue_service
            from .services.queue_notification_service import queue_notification_service
            
            # Get department (try to get from encounter type or use default OPD)
            department = Department.objects.filter(name__icontains='outpatient').first()
            if not department:
                department = Department.objects.first()
            
            # Determine priority based on encounter type
            priority = 1 if encounter_type == 'emergency' else 3  # 1=Emergency, 3=Normal
            
            # Create queue entry
            queue_entry = queue_service.create_queue_entry(
                patient=patient,
                encounter=encounter,
                department=department,
                assigned_doctor=current_staff.user if current_staff else None,
                priority=priority,
                notes=f'Visit: {chief_complaint}'
            )
            
            queue_number = queue_entry.queue_number
            queue_position = queue_service.get_position_in_queue(queue_entry)
            
            # Send queue SMS notification (professional queue message)
            queue_notification_service.send_check_in_notification(queue_entry)
            
            logger.info(
                f"✅ Queue entry created: {queue_number} for {patient.full_name} "
                f"(Position: {queue_position}, Priority: {priority})"
            )
            
            # Add success message to display
            messages.success(
                request,
                f"✅ Visit created! Queue Number: {queue_number}, Position: {queue_position}. SMS sent. Please record vital signs."
            )
            
        except Exception as e:
            logger.error(f"Error creating queue entry: {str(e)}", exc_info=True)
            # Fallback to old SMS if queue fails
            if patient.phone_number:
                try:
                    from .services.sms_service import sms_service
                    visit_date = encounter.started_at.strftime('%d/%m/%Y at %I:%M %p')
                    message = (
                        f"Dear {patient.first_name},\n\n"
                        f"Your visit has been registered at PrimeCare Hospital.\n\n"
                        f"Visit Type: {encounter.get_encounter_type_display()}\n"
                        f"Date/Time: {visit_date}\n"
                        f"MRN: {patient.mrn}\n\n"
                        f"Please proceed to the waiting area.\n\n"
                        f"Thank you,\nPrimeCare Hospital"
                    )
                    sms_service.send_sms(
                        phone_number=patient.phone_number,
                        message=message,
                        message_type='visit_created',
                        recipient_name=patient.full_name,
                        related_object_id=encounter.id,
                        related_object_type='Encounter'
                    )
                    messages.success(request, f'New visit created for {patient.full_name}. SMS confirmation sent. Please record vital signs.')
                except Exception as sms_error:
                    messages.success(request, f'New visit created for {patient.full_name}, but SMS could not be sent. Please record vital signs.')
        else:
            messages.success(request, f'New visit created for {patient.full_name}. Please record vital signs.')
        
        return redirect('hospital:record_vitals', encounter_id=encounter.pk)
    
    # For GET request, show the quick form
    context = {
        'patient': patient,
    }
    return render(request, 'hospital/quick_visit_form.html', context)


@login_required
def encounter_detail(request, pk):
    """Encounter detail view"""
    encounter = get_object_or_404(Encounter, pk=pk, is_deleted=False)
    
    # Get vital signs
    all_vitals = encounter.vitals.filter(is_deleted=False).order_by('-recorded_at')
    vitals = all_vitals[:10]
    latest_vitals = all_vitals.first()
    
    # Get orders
    orders = encounter.orders.filter(is_deleted=False).order_by('-created')[:20]
    
    # Get referrals
    referrals = []
    try:
        from .models_specialists import Referral
        referrals = Referral.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('specialist__staff__user', 'specialty', 'referring_doctor__user').order_by('-referred_date')
    except:
        pass
    
    context = {
        'encounter': encounter,
        'vitals': vitals,
        'latest_vitals': latest_vitals,
        'orders': orders,
        'referrals': referrals,
    }
    return render(request, 'hospital/encounter_detail.html', context)


@login_required
@csrf_exempt
def surgery_control(request, encounter_id):
    """Control surgery start/complete/notes"""
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        logger.info(f"Surgery control request for encounter {encounter_id}, action: {request.POST.get('action')}")
        
        encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
        
        # Verify it's a surgery encounter
        if encounter.encounter_type != 'surgery':
            return JsonResponse({'error': 'This is not a surgery encounter'}, status=400)
        
        action = request.POST.get('action')
    except Exception as e:
        logger.error(f"Error in surgery_control: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)
    
    if action == 'start':
        # Start surgery
        if encounter.status != 'active':
            return JsonResponse({'error': 'Encounter is not active'}, status=400)
        
        # Update encounter start time and add initial note
        encounter.started_at = timezone.now()
        current_notes = encounter.notes or ''
        encounter.notes = f"[SURGERY STARTED: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}]\n\n{current_notes}"
        encounter.save()
        
        messages.success(request, 'Surgery started successfully!')
        return JsonResponse({
            'success': True,
            'message': 'Surgery started',
            'started_at': encounter.started_at.isoformat()
        })
    
    elif action == 'complete':
        # Complete surgery
        if encounter.status != 'active':
            return JsonResponse({'error': 'Encounter is not active'}, status=400)
        
        # Mark as completed
        encounter.status = 'completed'
        encounter.ended_at = timezone.now()
        current_notes = encounter.notes or ''
        duration_minutes = encounter.get_duration_minutes() or 0
        encounter.notes = f"{current_notes}\n\n[SURGERY COMPLETED: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}]\nDuration: {duration_minutes} minutes"
        encounter.save()
        
        messages.success(request, 'Surgery completed successfully!')
        return JsonResponse({
            'success': True,
            'message': 'Surgery completed',
            'ended_at': encounter.ended_at.isoformat(),
            'duration_minutes': duration_minutes
        })
    
    elif action == 'add_note':
        # Add surgical note
        note = request.POST.get('note', '').strip()
        if not note:
            return JsonResponse({'error': 'Note cannot be empty'}, status=400)
        
        current_notes = encounter.notes or ''
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        user_name = request.user.get_full_name() or request.user.username
        encounter.notes = f"{current_notes}\n\n[{timestamp}] {user_name}: {note}"
        encounter.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Note added successfully'
        })
    
    elif action == 'report_issue':
        # Report complication/issue
        issue = request.POST.get('issue', '').strip()
        if not issue:
            return JsonResponse({'error': 'Issue description cannot be empty'}, status=400)
        
        current_notes = encounter.notes or ''
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        user_name = request.user.get_full_name() or request.user.username
        encounter.notes = f"{current_notes}\n\n[⚠️ COMPLICATION - {timestamp}] Reported by {user_name}:\n{issue}"
        encounter.save()
        
        # You could also create an alert or notification here
        messages.warning(request, f'Complication reported: {issue}')
        
        return JsonResponse({
            'success': True,
            'message': 'Issue reported and logged'
        })
    
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)


@login_required
def admission_list(request):
    """List all admissions"""
    status_filter = request.GET.get('status', 'admitted')
    
    admissions = Admission.objects.filter(is_deleted=False).select_related(
        'encounter__patient', 'ward', 'bed', 'admitting_doctor__user'
    ).order_by('-admit_date')
    
    if status_filter:
        admissions = admissions.filter(status=status_filter)
    
    # Calculate statistics
    total_admissions = Admission.objects.filter(is_deleted=False).count()
    current_admissions = Admission.objects.filter(status='admitted', is_deleted=False).count()
    discharged_today = Admission.objects.filter(
        is_deleted=False,
        discharge_date__date=timezone.now().date()
    ).count()
    
    # Bed statistics
    total_beds = Bed.objects.filter(is_deleted=False, is_active=True).count()
    available_beds = Bed.objects.filter(is_deleted=False, is_active=True, status='available').count()
    occupied_beds = Bed.objects.filter(is_deleted=False, is_active=True, status='occupied').count()
    bed_occupancy_rate = round((occupied_beds / total_beds * 100) if total_beds > 0 else 0, 1)
    
    stats = {
        'current_admissions': current_admissions,
        'available_beds': available_beds,
        'total_beds': total_beds,
        'bed_occupancy_rate': bed_occupancy_rate,
        'discharged_today': discharged_today,
    }
    
    paginator = Paginator(admissions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'admissions': page_obj,
        'status_filter': status_filter,
        'total_admissions': total_admissions,
        'current_admissions': current_admissions,
        'stats': stats,
    }
    return render(request, 'hospital/admission_list.html', context)


@login_required
def invoice_list(request):
    """List all invoices"""
    status_filter = request.GET.get('status', '')
    query = request.GET.get('q', '')
    
    invoices = Invoice.objects.filter(is_deleted=False).select_related(
        'patient', 'payer'
    ).order_by('-issued_at')
    
    if query:
        invoices = invoices.filter(
            Q(patient__first_name__icontains=query) |
            Q(patient__last_name__icontains=query) |
            Q(invoice_number__icontains=query)
        )
    if status_filter:
        invoices = invoices.filter(status=status_filter)
    
    # Calculate statistics (all invoices, not just filtered)
    all_invoices = Invoice.objects.filter(is_deleted=False)
    
    total_invoices = all_invoices.count()
    
    paid_invoices = all_invoices.filter(status='paid').count()
    
    total_revenue = all_invoices.filter(
        status='paid'
    ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    outstanding_balance = all_invoices.filter(
        status__in=['issued', 'partially_paid', 'overdue'],
        balance__gt=0
    ).aggregate(Sum('balance'))['balance__sum'] or 0
    
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Create stats dictionary to match template expectations
    stats = {
        'total_invoices': total_invoices,
        'paid_invoices': paid_invoices,
        'total_revenue': total_revenue,
        'outstanding_balance': outstanding_balance,
    }
    
    context = {
        'invoices': page_obj,
        'status_filter': status_filter,
        'stats': stats,  # FIXED: Pass as stats dictionary
    }
    return render(request, 'hospital/invoice_list.html', context)


@login_required
def invoice_detail(request, pk):
    """Invoice detail view"""
    invoice = get_object_or_404(Invoice, pk=pk, is_deleted=False)
    invoice_lines = invoice.lines.filter(is_deleted=False)
    days_overdue = invoice.get_days_overdue() if hasattr(invoice, 'get_days_overdue') else 0
    
    context = {
        'invoice': invoice,
        'lines': invoice_lines,
        'days_overdue': days_overdue,
    }
    return render(request, 'hospital/invoice_detail.html', context)


@login_required
def invoice_print(request, pk):
    """Printable invoice view with detailed services"""
    invoice = get_object_or_404(Invoice, pk=pk, is_deleted=False)
    
    context = {
        'invoice': invoice,
        'now': timezone.now(),
    }
    return render(request, 'hospital/invoice_print.html', context)


@login_required
def bed_availability(request):
    """Bed availability view"""
    ward_filter = request.GET.get('ward', '')
    
    beds = Bed.objects.filter(is_deleted=False).select_related('ward').order_by('ward', 'bed_number')
    
    if ward_filter:
        beds = beds.filter(ward_id=ward_filter)
    
    # Group by ward
    from .models import Ward
    wards = Ward.objects.filter(is_active=True, is_deleted=False)
    
    bed_stats = {}
    for ward in wards:
        ward_beds = beds.filter(ward=ward)
        bed_stats[ward] = {
            'total': ward_beds.count(),
            'available': ward_beds.filter(status='available').count(),
            'occupied': ward_beds.filter(status='occupied').count(),
        }
    
    context = {
        'beds': beds,
        'wards': wards,
        'bed_stats': bed_stats,
        'ward_filter': ward_filter,
    }
    return render(request, 'hospital/bed_availability.html', context)


@login_required
def daily_report(request):
    """Daily activity report"""
    from datetime import date
    report_date = request.GET.get('date')
    
    if report_date:
        try:
            report_date = date.fromisoformat(report_date)
        except ValueError:
            report_date = None
    
    from .utils import generate_daily_report
    report = generate_daily_report(report_date)
    
    context = {
        'report': report,
        'report_date': report_date or date.today(),
    }
    return render(request, 'hospital/daily_report.html', context)


@login_required
def api_stats(request):
    """API endpoint for comprehensive dashboard statistics with real-time updates"""
    from decimal import Decimal
    from .models_accounting import PaymentReceipt
    from .models_advanced import ImagingStudy
    
    stats = get_dashboard_stats()
    today_date = timezone.now().date()
    
    # Financial stats
    today_payments = PaymentReceipt.objects.filter(
        receipt_date__date=today_date,
        is_deleted=False
    )
    today_revenue = today_payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0')
    
    # Department stats
    lab_pending = LabResult.objects.filter(
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).count()
    
    pharmacy_pending = Prescription.objects.filter(
        is_deleted=False
    ).count()
    
    imaging_pending = 0
    try:
        imaging_pending = ImagingStudy.objects.filter(
            status__in=['pending', 'in_progress'],
            is_deleted=False
        ).count()
    except:
        pass
    
    # Add real-time stats
    stats['today_revenue'] = str(today_revenue)
    stats['today_payment_count'] = today_payments.count()
    stats['lab_pending'] = lab_pending
    stats['pharmacy_pending'] = pharmacy_pending
    stats['imaging_pending'] = imaging_pending
    
    return JsonResponse(stats)


@login_required
def export_patients_csv(request):
    """Export patients to CSV"""
    patients = Patient.objects.filter(is_deleted=False)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="patients.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['MRN', 'First Name', 'Last Name', 'Date of Birth', 'Gender', 'Phone', 'Email'])
    
    for patient in patients:
        writer.writerow([
            patient.mrn,
            patient.first_name,
            patient.last_name,
            patient.date_of_birth,
            patient.get_gender_display(),
            patient.phone_number,
            patient.email,
        ])
    
    return response


@login_required
def export_invoices_csv(request):
    """Export invoices to CSV"""
    invoices = Invoice.objects.filter(is_deleted=False).select_related('patient')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Invoice Number', 'Patient', 'Issue Date', 'Status', 'Total', 'Balance'])
    
    for invoice in invoices:
        writer.writerow([
            invoice.invoice_number,
            invoice.patient.full_name,
            invoice.issued_at.date(),
            invoice.get_status_display(),
            invoice.total_amount,
            invoice.balance,
        ])
    
    return response


@login_required
def export_encounters_csv(request):
    """Export encounters to CSV"""
    encounters = Encounter.objects.filter(is_deleted=False).defer('current_activity').select_related('patient')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="encounters.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Patient', 'Type', 'Status', 'Started At', 'Ended At', 'Location'])
    
    for encounter in encounters:
        writer.writerow([
            encounter.patient.full_name,
            encounter.get_encounter_type_display(),
            encounter.get_status_display(),
            encounter.started_at,
            encounter.ended_at or '',
            encounter.location.name if encounter.location else '',
        ])
    
    return response


@login_required
def financial_report_view(request):
    """Interactive financial report with export options"""
    period = request.GET.get('period', 'month') or 'month'
    report = generate_financial_report(period)
    context = {
        'report': report,
        'period': period,
    }
    return render(request, 'hospital/financial_report.html', context)


@login_required
def financial_report_export_excel(request):
    """Export financial report to Excel"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment
    except ImportError:
        return HttpResponse(
            'openpyxl is required for Excel export. Please install it and try again.',
            status=500
        )
    
    period = request.GET.get('period', 'month') or 'month'
    report = generate_financial_report(period)
    
    wb = Workbook()
    ws = wb.active
    ws.title = 'Financial Report'
    
    ws.merge_cells('A1:D1')
    title_cell = ws['A1']
    title_cell.value = f'Financial Report ({period.title()})'
    title_cell.font = Font(size=16, bold=True)
    title_cell.alignment = Alignment(horizontal='center')
    
    current_row = 2
    ws.cell(row=current_row, column=1, value='Metric').font = Font(bold=True)
    ws.cell(row=current_row, column=2, value='Value').font = Font(bold=True)
    current_row += 1
    
    metrics = [
        ('Date Range', f"{report['date_from']} to {report['date_to']}"),
        ('Total Invoiced', float(report['total_invoiced'])),
        ('Total Collected', float(report['total_collected'])),
        ('Outstanding', float(report['outstanding'])),
        ('Collection Rate (%)', float(report['collection_rate'])),
        ('Invoice Count', report['invoice_count']),
    ]
    for label, value in metrics:
        ws.cell(row=current_row, column=1, value=label)
        ws.cell(row=current_row, column=2, value=value)
        current_row += 1
    
    current_row += 1
    ws.cell(row=current_row, column=1, value='Breakdown by Status').font = Font(bold=True)
    current_row += 1
    ws.cell(row=current_row, column=1, value='Status').font = Font(bold=True)
    ws.cell(row=current_row, column=2, value='Count').font = Font(bold=True)
    ws.cell(row=current_row, column=3, value='Total Amount').font = Font(bold=True)
    current_row += 1
    for item in report['by_status']:
        ws.cell(row=current_row, column=1, value=item['status'])
        ws.cell(row=current_row, column=2, value=item['count'])
        ws.cell(row=current_row, column=3, value=float(item['total'] or 0))
        current_row += 1
    
    current_row += 1
    ws.cell(row=current_row, column=1, value='Breakdown by Payer').font = Font(bold=True)
    current_row += 1
    ws.cell(row=current_row, column=1, value='Payer').font = Font(bold=True)
    ws.cell(row=current_row, column=2, value='Count').font = Font(bold=True)
    ws.cell(row=current_row, column=3, value='Total Amount').font = Font(bold=True)
    current_row += 1
    for item in report['by_payer']:
        ws.cell(row=current_row, column=1, value=item['payer__name'] or 'Unknown')
        ws.cell(row=current_row, column=2, value=item['count'])
        ws.cell(row=current_row, column=3, value=float(item['total'] or 0))
        current_row += 1
    
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        column_letter = column_cells[0].column_letter
        ws.column_dimensions[column_letter].width = max(15, length + 2)
    
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="financial_report_{period}.xlsx"'
    return response


@login_required
def financial_report_export_pdf(request):
    """Export financial report to PDF"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import inch
    except ImportError:
        return HttpResponse(
            'ReportLab is required for PDF export. Please install it and try again.',
            status=500
        )
    
    period = request.GET.get('period', 'month') or 'month'
    report = generate_financial_report(period)
    
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawString(1 * inch, height - 1 * inch, f'Financial Report ({period.title()})')
    
    pdf.setFont('Helvetica', 11)
    y = height - 1.5 * inch
    lines = [
        f"Date Range: {report['date_from']} to {report['date_to']}",
        f"Total Invoiced: GHS {report['total_invoiced']}",
        f"Total Collected: GHS {report['total_collected']}",
        f"Outstanding: GHS {report['outstanding']}",
        f"Collection Rate: {report['collection_rate']:.2f}%",
        f"Invoice Count: {report['invoice_count']}",
    ]
    for line in lines:
        pdf.drawString(1 * inch, y, line)
        y -= 0.25 * inch
    
    y -= 0.25 * inch
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(1 * inch, y, 'Breakdown by Status')
    y -= 0.3 * inch
    pdf.setFont('Helvetica', 10)
    pdf.drawString(1 * inch, y, 'Status')
    pdf.drawString(3 * inch, y, 'Count')
    pdf.drawString(4 * inch, y, 'Total (GHS)')
    y -= 0.2 * inch
    for item in report['by_status']:
        pdf.drawString(1 * inch, y, str(item['status']))
        pdf.drawString(3 * inch, y, str(item['count']))
        pdf.drawString(4 * inch, y, f"{item['total'] or 0:.2f}")
        y -= 0.2 * inch
        if y < 1 * inch:
            pdf.showPage()
            y = height - 1 * inch
    
    y -= 0.2 * inch
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(1 * inch, y, 'Breakdown by Payer')
    y -= 0.3 * inch
    pdf.setFont('Helvetica', 10)
    pdf.drawString(1 * inch, y, 'Payer')
    pdf.drawString(3 * inch, y, 'Count')
    pdf.drawString(4 * inch, y, 'Total (GHS)')
    y -= 0.2 * inch
    for item in report['by_payer']:
        payer = item['payer__name'] or 'Unknown'
        pdf.drawString(1 * inch, y, payer[:30])
        pdf.drawString(3 * inch, y, str(item['count']))
        pdf.drawString(4 * inch, y, f"{item['total'] or 0:.2f}")
        y -= 0.2 * inch
        if y < 1 * inch:
            pdf.showPage()
            y = height - 1 * inch
    
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="financial_report_{period}.pdf"'
    return response


@login_required
def patient_statistics_report_view(request):
    """Patient statistics report"""
    from .utils import get_patient_demographics
    report = get_patient_demographics()
    context = {'report': report}
    return render(request, 'hospital/patient_statistics_report.html', context)


@login_required
def encounter_report_view(request):
    """Encounter report view"""
    from .utils import get_encounter_statistics
    report = get_encounter_statistics()
    context = {'report': report}
    return render(request, 'hospital/encounter_report.html', context)


@login_required
def admission_report_view(request):
    """Admission report view"""
    from .models import Admission
    report = {
        'total': Admission.objects.filter(is_deleted=False).count(),
        'current': Admission.objects.filter(status='admitted', is_deleted=False).count(),
        'discharged': Admission.objects.filter(status='discharged', is_deleted=False).count(),
    }
    context = {'report': report}
    return render(request, 'hospital/admission_report.html', context)


@login_required
def department_performance_report_view(request):
    """Department performance report"""
    from .models import Department
    report = {'departments': Department.objects.filter(is_active=True, is_deleted=False)}
    context = {'report': report}
    return render(request, 'hospital/department_performance_report.html', context)


@login_required
def bed_utilization_report_view(request):
    """Bed utilization report"""
    from .models import Bed
    total = Bed.objects.filter(is_deleted=False).count()
    occupied = Bed.objects.filter(status='occupied', is_deleted=False).count()
    report = {
        'total': total,
        'occupied': occupied,
        'available': total - occupied,
        'occupancy_rate': round((occupied / total * 100) if total > 0 else 0, 1),
    }
    context = {'report': report}
    return render(request, 'hospital/bed_utilization_report.html', context)


@login_required
def global_search(request):
    """Enhanced global search across all models with filters"""
    query = request.GET.get('q', '').strip()
    
    # Filter parameters
    category_filter = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    
    # Results per category limit
    limit_per_category = 20
    
    results = {
        'patients': [],
        'encounters': [],
        'invoices': [],
        'appointments': [],
        'staff': [],
        'drugs': [],
        'lab_results': [],
        'prescriptions': [],
        'orders': [],
        'medical_records': [],
        'referrals': [],
        'insurance': [],
        'insurance_companies': [],
        'departments': [],
        'specialties': [],
        'wards': [],
        'beds': [],
    }
    
    result_counts = {
        'patients': 0,
        'encounters': 0,
        'invoices': 0,
        'appointments': 0,
        'staff': 0,
        'drugs': 0,
        'lab_results': 0,
        'prescriptions': 0,
        'orders': 0,
        'medical_records': 0,
        'referrals': 0,
        'insurance': 0,
        'insurance_companies': 0,
        'departments': 0,
        'specialties': 0,
        'wards': 0,
        'beds': 0,
    }
    
    if query and len(query) >= 2:
        # Build date filter if provided
        date_filter = {}
        if date_from:
            try:
                from datetime import datetime
                date_filter['start'] = datetime.strptime(date_from, '%Y-%m-%d')
            except ValueError:
                pass
        if date_to:
            try:
                from datetime import datetime
                date_filter['end'] = datetime.strptime(date_to, '%Y-%m-%d')
            except ValueError:
                pass
        
        # Search patients
        if not category_filter or category_filter == 'patients':
            qs = Patient.objects.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(middle_name__icontains=query) |
                Q(mrn__icontains=query) |
                Q(phone_number__icontains=query) |
                Q(national_id__icontains=query) |
                Q(email__icontains=query),
                is_deleted=False
            ).order_by('-created')[:limit_per_category]
            results['patients'] = list(qs)
            result_counts['patients'] = Patient.objects.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(middle_name__icontains=query) |
                Q(mrn__icontains=query) |
                Q(phone_number__icontains=query) |
                Q(national_id__icontains=query) |
                Q(email__icontains=query),
                is_deleted=False
            ).count()
        
        # Search encounters
        if not category_filter or category_filter == 'encounters':
            qs = Encounter.objects.filter(
                Q(patient__first_name__icontains=query) |
                Q(patient__last_name__icontains=query) |
                Q(patient__mrn__icontains=query) |
                Q(chief_complaint__icontains=query) |
                Q(notes__icontains=query),
                is_deleted=False
            )
            if status_filter:
                qs = qs.filter(status=status_filter)
            if date_from:
                qs = qs.filter(started_at__gte=date_filter.get('start'))
            if date_to:
                qs = qs.filter(started_at__lte=date_filter.get('end'))
            qs = qs.select_related('patient', 'provider__user', 'provider__department', 'location').order_by('-started_at')[:limit_per_category]
            results['encounters'] = list(qs)
            result_counts['encounters'] = Encounter.objects.filter(
                Q(patient__first_name__icontains=query) |
                Q(patient__last_name__icontains=query) |
                Q(patient__mrn__icontains=query) |
                Q(chief_complaint__icontains=query) |
                Q(notes__icontains=query),
                is_deleted=False
            ).count()
        
        # Search invoices
        if not category_filter or category_filter == 'invoices':
            qs = Invoice.objects.filter(
                Q(patient__first_name__icontains=query) |
                Q(patient__last_name__icontains=query) |
                Q(invoice_number__icontains=query),
                is_deleted=False
            )
            if status_filter:
                qs = qs.filter(status=status_filter)
            if date_from:
                qs = qs.filter(issued_at__gte=date_filter.get('start'))
            if date_to:
                qs = qs.filter(issued_at__lte=date_filter.get('end'))
            qs = qs.select_related('patient', 'payer').order_by('-issued_at')[:limit_per_category]
            results['invoices'] = list(qs)
            result_counts['invoices'] = Invoice.objects.filter(
                Q(patient__first_name__icontains=query) |
                Q(patient__last_name__icontains=query) |
                Q(invoice_number__icontains=query),
                is_deleted=False
            ).count()
        
        # Search appointments
        if not category_filter or category_filter == 'appointments':
            from .models import Appointment
            qs = Appointment.objects.filter(
                Q(patient__first_name__icontains=query) |
                Q(patient__last_name__icontains=query) |
                Q(provider__user__first_name__icontains=query) |
                Q(provider__user__last_name__icontains=query) |
                Q(reason__icontains=query),
                is_deleted=False
            )
            if status_filter:
                qs = qs.filter(status=status_filter)
            if date_from:
                qs = qs.filter(appointment_date__gte=date_filter.get('start'))
            if date_to:
                qs = qs.filter(appointment_date__lte=date_filter.get('end'))
            qs = qs.select_related('patient', 'provider__user', 'department').order_by('-appointment_date')[:limit_per_category]
            results['appointments'] = list(qs)
            result_counts['appointments'] = Appointment.objects.filter(
                Q(patient__first_name__icontains=query) |
                Q(patient__last_name__icontains=query) |
                Q(provider__user__first_name__icontains=query) |
                Q(provider__user__last_name__icontains=query) |
                Q(reason__icontains=query),
                is_deleted=False
            ).count()
        
        # Search staff
        if not category_filter or category_filter == 'staff':
            from .models import Staff
            from .models_advanced import LeaveRequest
            from django.utils import timezone
            
            qs = Staff.objects.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__username__icontains=query) |
                Q(user__email__icontains=query) |
                Q(employee_id__icontains=query) |
                Q(registration_number__icontains=query) |
                Q(phone_number__icontains=query),
                is_deleted=False
            )
            if status_filter == 'active':
                qs = qs.filter(is_active=True)
            elif status_filter == 'inactive':
                qs = qs.filter(is_active=False)
            qs = qs.select_related('user', 'department', 'leave_balance').order_by('user__last_name', 'user__first_name')[:limit_per_category]
            
            # Add current leave information to each staff member
            staff_list = list(qs)
            today = timezone.now().date()
            for staff in staff_list:
                # Get current approved leave (if any)
                current_leave = LeaveRequest.objects.filter(
                    staff=staff,
                    status='approved',
                    start_date__lte=today,
                    end_date__gte=today,
                    is_deleted=False
                ).first()
                staff.current_leave = current_leave
            
            results['staff'] = staff_list
            result_counts['staff'] = Staff.objects.filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__username__icontains=query) |
                Q(user__email__icontains=query) |
                Q(employee_id__icontains=query) |
                Q(registration_number__icontains=query) |
                Q(phone_number__icontains=query),
                is_deleted=False
            ).count()
        
        # Search drugs
        if not category_filter or category_filter == 'drugs':
            qs = Drug.objects.filter(
                Q(name__icontains=query) |
                Q(generic_name__icontains=query) |
                Q(atc_code__icontains=query) |
                Q(strength__icontains=query) |
                Q(form__icontains=query) |
                Q(manufacturer__icontains=query),
                is_deleted=False
            )
            if status_filter == 'active':
                qs = qs.filter(is_active=True)
            elif status_filter == 'inactive':
                qs = qs.filter(is_active=False)
            qs = qs.order_by('name')[:limit_per_category]
            results['drugs'] = list(qs)
            result_counts['drugs'] = Drug.objects.filter(
                Q(name__icontains=query) |
                Q(generic_name__icontains=query) |
                Q(atc_code__icontains=query) |
                Q(strength__icontains=query) |
                Q(form__icontains=query) |
                Q(manufacturer__icontains=query),
                is_deleted=False
            ).count()
        
        # Search lab results
        if not category_filter or category_filter == 'lab_results':
            from .models import LabResult, Order
            qs = LabResult.objects.filter(
                Q(order__encounter__patient__first_name__icontains=query) |
                Q(order__encounter__patient__last_name__icontains=query) |
                Q(order__encounter__patient__mrn__icontains=query) |
                Q(test__name__icontains=query) |
                Q(test__code__icontains=query) |
                Q(value__icontains=query),
                is_deleted=False
            )
            if status_filter:
                qs = qs.filter(status=status_filter)
            if date_from:
                qs = qs.filter(created__gte=date_filter.get('start'))
            if date_to:
                qs = qs.filter(created__lte=date_filter.get('end'))
            qs = qs.select_related('order__encounter__patient', 'test', 'order__requested_by__user').order_by('-created')[:limit_per_category]
            results['lab_results'] = list(qs)
            result_counts['lab_results'] = LabResult.objects.filter(
                Q(order__encounter__patient__first_name__icontains=query) |
                Q(order__encounter__patient__last_name__icontains=query) |
                Q(order__encounter__patient__mrn__icontains=query) |
                Q(test__name__icontains=query) |
                Q(test__code__icontains=query) |
                Q(value__icontains=query),
                is_deleted=False
            ).count()
        
        # Search prescriptions
        if not category_filter or category_filter == 'prescriptions':
            from .models import Prescription
            qs = Prescription.objects.filter(
                Q(order__encounter__patient__first_name__icontains=query) |
                Q(order__encounter__patient__last_name__icontains=query) |
                Q(order__encounter__patient__mrn__icontains=query) |
                Q(drug__name__icontains=query) |
                Q(drug__generic_name__icontains=query) |
                Q(instructions__icontains=query),
                is_deleted=False
            )
            # Note: Prescription model doesn't have status field
            if date_from:
                qs = qs.filter(created__gte=date_filter.get('start'))
            if date_to:
                qs = qs.filter(created__lte=date_filter.get('end'))
            qs = qs.select_related('order__encounter__patient', 'drug', 'prescribed_by__user').order_by('-created')[:limit_per_category]
            results['prescriptions'] = list(qs)
            result_counts['prescriptions'] = Prescription.objects.filter(
                Q(order__encounter__patient__first_name__icontains=query) |
                Q(order__encounter__patient__last_name__icontains=query) |
                Q(order__encounter__patient__mrn__icontains=query) |
                Q(drug__name__icontains=query) |
                Q(drug__generic_name__icontains=query) |
                Q(instructions__icontains=query),
                is_deleted=False
            ).count()
        
        # Search orders
        if not category_filter or category_filter == 'orders':
            from .models import Order
            qs = Order.objects.filter(
                Q(encounter__patient__first_name__icontains=query) |
                Q(encounter__patient__last_name__icontains=query) |
                Q(encounter__patient__mrn__icontains=query) |
                Q(notes__icontains=query),
                is_deleted=False
            )
            if status_filter:
                qs = qs.filter(status=status_filter)
            if date_from:
                qs = qs.filter(requested_at__gte=date_filter.get('start'))
            if date_to:
                qs = qs.filter(requested_at__lte=date_filter.get('end'))
            qs = qs.select_related('encounter__patient', 'requested_by__user', 'requested_by__department').order_by('-requested_at')[:limit_per_category]
            results['orders'] = list(qs)
            result_counts['orders'] = Order.objects.filter(
                Q(encounter__patient__first_name__icontains=query) |
                Q(encounter__patient__last_name__icontains=query) |
                Q(encounter__patient__mrn__icontains=query) |
                Q(notes__icontains=query),
                is_deleted=False
            ).count()
        
        # Search medical records
        if not category_filter or category_filter == 'medical_records':
            from .models import MedicalRecord
            qs = MedicalRecord.objects.filter(
                Q(patient__first_name__icontains=query) |
                Q(patient__last_name__icontains=query) |
                Q(patient__mrn__icontains=query) |
                Q(diagnosis__icontains=query) |
                Q(notes__icontains=query),
                is_deleted=False
            )
            if date_from:
                qs = qs.filter(record_date__gte=date_filter.get('start'))
            if date_to:
                qs = qs.filter(record_date__lte=date_filter.get('end'))
            qs = qs.select_related('patient', 'created_by__user').order_by('-record_date')[:limit_per_category]
            results['medical_records'] = list(qs)
            result_counts['medical_records'] = MedicalRecord.objects.filter(
                Q(patient__first_name__icontains=query) |
                Q(patient__last_name__icontains=query) |
                Q(patient__mrn__icontains=query) |
                Q(diagnosis__icontains=query) |
                Q(notes__icontains=query),
                is_deleted=False
            ).count()
        
        # Search insurance
        if not category_filter or category_filter == 'insurance':
            try:
                from .models_insurance import PatientInsurance
                qs = PatientInsurance.objects.filter(
                    Q(patient__first_name__icontains=query) |
                    Q(patient__last_name__icontains=query) |
                    Q(patient__mrn__icontains=query) |
                    Q(insurance_company__name__icontains=query) |
                    Q(policy_number__icontains=query) |
                    Q(member_id__icontains=query),
                    is_deleted=False
                )
                if status_filter == 'active':
                    qs = qs.filter(is_active=True)
                elif status_filter == 'inactive':
                    qs = qs.filter(is_active=False)
                if date_from:
                    qs = qs.filter(effective_date__gte=date_filter.get('start'))
                if date_to:
                    qs = qs.filter(effective_date__lte=date_filter.get('end'))
                qs = qs.select_related('patient', 'insurance_company').order_by('-effective_date')[:limit_per_category]
                results['insurance'] = list(qs)
                result_counts['insurance'] = PatientInsurance.objects.filter(
                    Q(patient__first_name__icontains=query) |
                    Q(patient__last_name__icontains=query) |
                    Q(patient__mrn__icontains=query) |
                    Q(insurance_company__name__icontains=query) |
                    Q(policy_number__icontains=query) |
                    Q(member_id__icontains=query),
                    is_deleted=False
                ).count()
            except ImportError:
                results['insurance'] = []
                result_counts['insurance'] = 0
        
        # Search insurance companies
        if not category_filter or category_filter == 'insurance_companies':
            try:
                from .models_insurance import InsuranceCompany
                qs = InsuranceCompany.objects.filter(
                    Q(name__icontains=query) |
                    Q(code__icontains=query) |
                    Q(contact_phone__icontains=query) |
                    Q(contact_email__icontains=query) |
                    Q(address__icontains=query),
                    is_deleted=False
                )
                if status_filter == 'active':
                    qs = qs.filter(is_active=True)
                elif status_filter == 'inactive':
                    qs = qs.filter(is_active=False)
                qs = qs.order_by('name')[:limit_per_category]
                results['insurance_companies'] = list(qs)
                result_counts['insurance_companies'] = InsuranceCompany.objects.filter(
                    Q(name__icontains=query) |
                    Q(code__icontains=query) |
                    Q(contact_phone__icontains=query) |
                    Q(contact_email__icontains=query) |
                    Q(address__icontains=query),
                    is_deleted=False
                ).count()
            except ImportError:
                results['insurance_companies'] = []
                result_counts['insurance_companies'] = 0
        
        # Search referrals
        if not category_filter or category_filter == 'referrals':
            try:
                from .models_specialists import Referral
                qs = Referral.objects.filter(
                    Q(encounter__patient__first_name__icontains=query) |
                    Q(encounter__patient__last_name__icontains=query) |
                    Q(encounter__patient__mrn__icontains=query) |
                    Q(specialist__staff__user__first_name__icontains=query) |
                    Q(specialist__staff__user__last_name__icontains=query) |
                    Q(specialty__name__icontains=query) |
                    Q(reason__icontains=query) |
                    Q(notes__icontains=query),
                    is_deleted=False
                )
                if status_filter:
                    qs = qs.filter(status=status_filter)
                if date_from:
                    qs = qs.filter(referred_date__gte=date_filter.get('start'))
                if date_to:
                    qs = qs.filter(referred_date__lte=date_filter.get('end'))
                qs = qs.select_related('encounter__patient', 'specialist__staff__user', 'specialty', 'referring_doctor__user').order_by('-referred_date')[:limit_per_category]
                results['referrals'] = list(qs)
                result_counts['referrals'] = Referral.objects.filter(
                    Q(encounter__patient__first_name__icontains=query) |
                    Q(encounter__patient__last_name__icontains=query) |
                    Q(encounter__patient__mrn__icontains=query) |
                    Q(specialist__staff__user__first_name__icontains=query) |
                    Q(specialist__staff__user__last_name__icontains=query) |
                    Q(specialty__name__icontains=query) |
                    Q(reason__icontains=query) |
                    Q(notes__icontains=query),
                    is_deleted=False
                ).count()
            except ImportError:
                results['referrals'] = []
                result_counts['referrals'] = 0
        
        # Search departments
        if not category_filter or category_filter == 'departments':
            from .models import Department
            qs = Department.objects.filter(
                Q(name__icontains=query) |
                Q(code__icontains=query) |
                Q(description__icontains=query),
                is_deleted=False
            )
            if status_filter == 'active':
                qs = qs.filter(is_active=True)
            elif status_filter == 'inactive':
                qs = qs.filter(is_active=False)
            qs = qs.order_by('name')[:limit_per_category]
            results['departments'] = list(qs)
            result_counts['departments'] = Department.objects.filter(
                Q(name__icontains=query) |
                Q(code__icontains=query) |
                Q(description__icontains=query),
                is_deleted=False
            ).count()
        
        # Search specialties
        if not category_filter or category_filter == 'specialties':
            try:
                from .models_specialists import Specialty
                qs = Specialty.objects.filter(
                    Q(name__icontains=query) |
                    Q(code__icontains=query) |
                    Q(description__icontains=query),
                    is_deleted=False
                )
                if status_filter == 'active':
                    qs = qs.filter(is_active=True)
                elif status_filter == 'inactive':
                    qs = qs.filter(is_active=False)
                qs = qs.order_by('name')[:limit_per_category]
                results['specialties'] = list(qs)
                result_counts['specialties'] = Specialty.objects.filter(
                    Q(name__icontains=query) |
                    Q(code__icontains=query) |
                    Q(description__icontains=query),
                    is_deleted=False
                ).count()
            except ImportError:
                results['specialties'] = []
                result_counts['specialties'] = 0
        
        # Search wards
        if not category_filter or category_filter == 'wards':
            from .models import Ward
            qs = Ward.objects.filter(
                Q(name__icontains=query) |
                Q(code__icontains=query) |
                Q(ward_type__icontains=query),
                is_deleted=False
            )
            if status_filter == 'active':
                qs = qs.filter(is_active=True)
            elif status_filter == 'inactive':
                qs = qs.filter(is_active=False)
            qs = qs.select_related('department').order_by('name')[:limit_per_category]
            results['wards'] = list(qs)
            result_counts['wards'] = Ward.objects.filter(
                Q(name__icontains=query) |
                Q(code__icontains=query) |
                Q(ward_type__icontains=query),
                is_deleted=False
            ).count()
        
        # Search beds
        if not category_filter or category_filter == 'beds':
            from .models import Bed
            qs = Bed.objects.filter(
                Q(bed_number__icontains=query) |
                Q(ward__name__icontains=query) |
                Q(ward__code__icontains=query),
                is_deleted=False
            )
            if status_filter == 'available':
                qs = qs.filter(is_occupied=False)
            elif status_filter == 'occupied':
                qs = qs.filter(is_occupied=True)
            qs = qs.select_related('ward', 'ward__department').order_by('ward__name', 'bed_number')[:limit_per_category]
            results['beds'] = list(qs)
            result_counts['beds'] = Bed.objects.filter(
                Q(bed_number__icontains=query) |
                Q(ward__name__icontains=query) |
                Q(ward__code__icontains=query),
                is_deleted=False
            ).count()
    
    # Calculate totals
    total_results = sum(len(v) if isinstance(v, list) else 0 for v in results.values())
    
    context = {
        'query': query,
        'results': results,
        'result_counts': result_counts,
        'has_results': total_results > 0,
        'total_results': total_results,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'hospital/global_search.html', context)


@login_required
def tabular_lab_report(request, result_id):
    """Tabular lab report entry for structured tests (FBC, LFT, RFT, etc.)"""
    lab_result = get_object_or_404(LabResult, pk=result_id, is_deleted=False)
    
    # Get patient and test details
    patient = lab_result.order.encounter.patient
    test = lab_result.test
    
    # Determine test type based on test code/name
    test_type = 'fbc'  # default
    test_name_lower = test.name.lower()
    test_code_lower = test.code.lower()
    
    if any(keyword in test_name_lower or keyword in test_code_lower for keyword in ['fbc', 'cbc', 'complete blood', 'full blood']):
        test_type = 'fbc'
    elif any(keyword in test_name_lower or keyword in test_code_lower for keyword in ['lft', 'liver', 'hepatic']):
        test_type = 'lft'
    elif any(keyword in test_name_lower or keyword in test_code_lower for keyword in ['rft', 'renal', 'kidney', 'urea', 'creatinine']):
        test_type = 'rft'
    elif any(keyword in test_name_lower or keyword in test_code_lower for keyword in ['lipid', 'cholesterol', 'triglyceride']):
        test_type = 'lipid'
    elif any(keyword in test_name_lower or keyword in test_code_lower for keyword in ['tft', 'thyroid', 'tsh', 't3', 't4']):
        test_type = 'tft'
    elif any(keyword in test_name_lower or keyword in test_code_lower for keyword in ['glucose', 'sugar', 'fbs', 'rbs', 'hba1c']):
        test_type = 'glucose'
    elif any(keyword in test_name_lower or keyword in test_code_lower for keyword in ['electrolyte', 'sodium', 'potassium', 'na', 'k']):
        test_type = 'electrolytes'
    
    if request.method == 'POST':
        form = TabularLabReportForm(request.POST)
        if form.is_valid():
            # Extract test type from form
            test_type = form.cleaned_data.get('test_type', test_type)
            
            # Get all parameter values as a dictionary
            details = form.get_details_dict()
            
            # Update lab result
            lab_result.details = details
            lab_result.status = form.cleaned_data.get('status', 'completed')
            lab_result.qualitative_result = form.cleaned_data.get('qualitative_result', '')
            lab_result.notes = form.cleaned_data.get('notes', '')
            
            # Set verified by current user if they are staff
            try:
                staff = Staff.objects.get(user=request.user, is_deleted=False)
                lab_result.verified_by = staff
                lab_result.verified_at = timezone.now()
            except Staff.DoesNotExist:
                pass
            
            lab_result.save()

            # Also update the parent order status so it no longer shows as pending
            try:
                order = lab_result.order
                if order and order.status != 'completed':
                    order.status = 'completed'
                    order.save(update_fields=['status', 'modified'])
            except Exception:
                # Don't break the flow if order update fails; result is still saved
                pass
            
            messages.success(request, f'Lab result for {test.name} saved successfully.')
            return redirect('hospital:laboratory_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-populate form with existing data
        initial_data = {
            'test_type': test_type,
            'status': lab_result.status,
            'qualitative_result': lab_result.qualitative_result or '',
            'notes': lab_result.notes or '',
        }
        
        # Add existing details if any
        if lab_result.details:
            initial_data.update(lab_result.details)
        
        form = TabularLabReportForm(initial=initial_data)
    
    context = {
        'form': form,
        'lab_result': lab_result,
        'lab_result_id': result_id,
        'patient': patient,
        'patient_name': patient.full_name,
        'test': test,
        'test_name': test.name,
        'test_type': test_type,
        'details': lab_result.details or {},
        'notes': lab_result.notes or '',
        'qualitative_result': lab_result.qualitative_result or '',
        'qualitative_options': ['Negative', 'Positive', 'Reactive', 'Non-Reactive', 'Normal', 'Abnormal'],
        'current_user': request.user.get_full_name() or request.user.username,
    }
    
    return render(request, 'hospital/lab_report_tabular.html', context)


@login_required
def print_lab_report(request, result_id):
    """Print-friendly lab report with logo and department info"""
    result = get_object_or_404(LabResult, pk=result_id, is_deleted=False)
    settings = HospitalSettings.get_settings()
    
    context = {
        'result': result,
        'settings': settings,
        'now': timezone.now(),
    }
    
    return render(request, 'hospital/lab_report_print.html', context)


@login_required
def hospital_settings_view(request):
    """Hospital settings configuration page"""
    if not user_has_role_access(request.user, 'admin'):
        messages.error(request, 'You do not have permission to manage hospital settings.')
        return redirect('hospital:dashboard')
    
    settings = HospitalSettings.get_settings()
    
    if request.method == 'POST':
        # Update settings
        settings.hospital_name = request.POST.get('hospital_name', settings.hospital_name)
        settings.hospital_tagline = request.POST.get('hospital_tagline', settings.hospital_tagline)
        settings.address = request.POST.get('address', settings.address)
        settings.city = request.POST.get('city', settings.city)
        settings.state = request.POST.get('state', settings.state)
        settings.postal_code = request.POST.get('postal_code', settings.postal_code)
        settings.country = request.POST.get('country', settings.country)
        settings.phone = request.POST.get('phone', settings.phone)
        settings.email = request.POST.get('email', settings.email)
        settings.website = request.POST.get('website', settings.website)
        
        # Lab settings
        settings.lab_department_name = request.POST.get('lab_department_name', settings.lab_department_name)
        settings.lab_phone = request.POST.get('lab_phone', settings.lab_phone)
        settings.lab_email = request.POST.get('lab_email', settings.lab_email)
        settings.lab_accreditation = request.POST.get('lab_accreditation', settings.lab_accreditation)
        settings.lab_license_number = request.POST.get('lab_license_number', settings.lab_license_number)
        
        # Logo upload
        if 'logo' in request.FILES:
            settings.logo = request.FILES['logo']
        
        settings.logo_width = int(request.POST.get('logo_width', settings.logo_width))
        settings.logo_height = int(request.POST.get('logo_height', settings.logo_height))
        settings.report_header_color = request.POST.get('report_header_color', settings.report_header_color)
        settings.report_footer_text = request.POST.get('report_footer_text', settings.report_footer_text)
        
        settings.updated_by = request.user
        settings.save()
        
        messages.success(request, 'Hospital settings updated successfully.')
        return redirect('hospital:hospital_settings')
    
    context = {
        'settings': settings,
    }
    
    return render(request, 'hospital/hospital_settings.html', context)


# ==================== DRUG FORMULARY MANAGEMENT ====================

@login_required
def drug_formulary_list(request):
    """List all drugs in formulary with search and filtering"""
    drugs = Drug.objects.filter(is_deleted=False).order_by('name')
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        drugs = drugs.filter(
            Q(name__icontains=search_query) |
            Q(generic_name__icontains=search_query) |
            Q(atc_code__icontains=search_query)
        )
    
    # Filter by form
    form_filter = request.GET.get('form', '')
    if form_filter:
        drugs = drugs.filter(form__icontains=form_filter)
    
    # Filter by active status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        drugs = drugs.filter(is_active=True)
    elif status_filter == 'inactive':
        drugs = drugs.filter(is_active=False)
    
    # Filter by controlled
    controlled_filter = request.GET.get('controlled', '')
    if controlled_filter == 'yes':
        drugs = drugs.filter(is_controlled=True)
    elif controlled_filter == 'no':
        drugs = drugs.filter(is_controlled=False)
    
    # Pagination
    paginator = Paginator(drugs, 20)
    page = request.GET.get('page')
    drugs_page = paginator.get_page(page)
    
    # Get unique forms for filter dropdown
    forms = Drug.objects.filter(is_deleted=False).values_list('form', flat=True).distinct().order_by('form')
    
    context = {
        'drugs': drugs_page,
        'forms': forms,
        'search_query': search_query,
        'form_filter': form_filter,
        'status_filter': status_filter,
        'controlled_filter': controlled_filter,
        'total_drugs': drugs.count(),
    }
    return render(request, 'hospital/drug_formulary_list.html', context)


@login_required
def drug_detail(request, pk):
    """View drug details"""
    from datetime import timedelta
    drug = get_object_or_404(Drug, pk=pk, is_deleted=False)
    
    # Get stock information
    stock_entries = PharmacyStock.objects.filter(drug=drug, is_deleted=False).order_by('expiry_date')
    total_stock = stock_entries.aggregate(total=Sum('quantity_on_hand'))['total'] or 0
    
    # Calculate stock value
    stock_value = total_stock * drug.unit_price
    
    # Get recent prescriptions
    recent_prescriptions = Prescription.objects.filter(
        drug=drug,
        is_deleted=False
    ).select_related('order__encounter__patient', 'prescribed_by__user').order_by('-created')[:10]
    
    prescription_count = Prescription.objects.filter(drug=drug, is_deleted=False).count()
    
    # Dates for expiry checking
    today = timezone.now().date()
    expiring_soon = today + timedelta(days=30)
    
    context = {
        'drug': drug,
        'stock_entries': stock_entries,
        'total_stock': total_stock,
        'stock_value': stock_value,
        'recent_prescriptions': recent_prescriptions,
        'prescription_count': prescription_count,
        'today': today,
        'expiring_soon': expiring_soon,
    }
    return render(request, 'hospital/drug_detail.html', context)


@login_required
def drug_create(request):
    """Create a new drug"""
    if request.method == 'POST':
        try:
            drug = Drug.objects.create(
                atc_code=request.POST.get('atc_code', ''),
                name=request.POST['name'],
                generic_name=request.POST.get('generic_name', ''),
                strength=request.POST['strength'],
                form=request.POST['form'],
                pack_size=request.POST.get('pack_size', ''),
                is_controlled=request.POST.get('is_controlled') == 'on',
                is_active=request.POST.get('is_active', 'on') == 'on',
                unit_price=request.POST.get('unit_price', 0) or 0,
                cost_price=request.POST.get('cost_price', 0) or 0,
            )
            messages.success(request, f'Drug "{drug.name}" created successfully.')
            return redirect('hospital:drug_detail', pk=drug.pk)
        except Exception as e:
            messages.error(request, f'Error creating drug: {str(e)}')
    
    return render(request, 'hospital/drug_form.html', {'action': 'Create'})


@login_required
def drug_edit(request, pk):
    """Edit an existing drug"""
    drug = get_object_or_404(Drug, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        try:
            drug.atc_code = request.POST.get('atc_code', '')
            drug.name = request.POST['name']
            drug.generic_name = request.POST.get('generic_name', '')
            drug.strength = request.POST['strength']
            drug.form = request.POST['form']
            drug.pack_size = request.POST.get('pack_size', '')
            drug.is_controlled = request.POST.get('is_controlled') == 'on'
            drug.is_active = request.POST.get('is_active', 'on') == 'on'
            drug.unit_price = request.POST.get('unit_price', 0) or 0
            drug.cost_price = request.POST.get('cost_price', 0) or 0
            drug.save()
            
            messages.success(request, f'Drug "{drug.name}" updated successfully.')
            return redirect('hospital:drug_detail', pk=drug.pk)
        except Exception as e:
            messages.error(request, f'Error updating drug: {str(e)}')
    
    context = {
        'drug': drug,
        'action': 'Edit'
    }
    return render(request, 'hospital/drug_form.html', context)


# ==================== LAB TESTS CATALOG MANAGEMENT ====================

@login_required
def lab_tests_catalog(request):
    """List all lab tests with search and filtering"""
    tests = LabTest.objects.filter(is_deleted=False).order_by('name')
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        tests = tests.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(specimen_type__icontains=search_query)
        )
    
    # Filter by specimen type
    specimen_filter = request.GET.get('specimen', '')
    if specimen_filter:
        tests = tests.filter(specimen_type__icontains=specimen_filter)
    
    # Filter by active status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        tests = tests.filter(is_active=True)
    elif status_filter == 'inactive':
        tests = tests.filter(is_active=False)
    
    # Pagination
    paginator = Paginator(tests, 20)
    page = request.GET.get('page')
    tests_page = paginator.get_page(page)
    
    # Get unique specimen types for filter dropdown
    specimen_types = LabTest.objects.filter(is_deleted=False).values_list('specimen_type', flat=True).distinct().order_by('specimen_type')
    
    context = {
        'tests': tests_page,
        'specimen_types': specimen_types,
        'search_query': search_query,
        'specimen_filter': specimen_filter,
        'status_filter': status_filter,
        'total_tests': tests.count(),
    }
    return render(request, 'hospital/lab_tests_catalog.html', context)


@login_required
def lab_test_detail(request, pk):
    """View lab test details"""
    test = get_object_or_404(LabTest, pk=pk, is_deleted=False)
    
    # Get recent results for this test
    recent_results = LabResult.objects.filter(
        test=test,
        is_deleted=False
    ).select_related('order__encounter__patient').order_by('-created')[:10]
    
    # Get statistics
    total_results = LabResult.objects.filter(test=test, is_deleted=False).count()
    completed_results = LabResult.objects.filter(test=test, status='completed', is_deleted=False).count()
    abnormal_results = LabResult.objects.filter(test=test, is_abnormal=True, is_deleted=False).count()
    
    context = {
        'test': test,
        'recent_results': recent_results,
        'total_results': total_results,
        'completed_results': completed_results,
        'abnormal_results': abnormal_results,
    }
    return render(request, 'hospital/lab_test_detail.html', context)


@login_required
def lab_test_create(request):
    """Create a new lab test"""
    if request.method == 'POST':
        try:
            test = LabTest.objects.create(
                code=request.POST['code'],
                name=request.POST['name'],
                specimen_type=request.POST['specimen_type'],
                tat_minutes=int(request.POST.get('tat_minutes', 60)),
                price=request.POST.get('price', 0) or 0,
                is_active=request.POST.get('is_active', 'on') == 'on',
            )
            messages.success(request, f'Lab test "{test.name}" created successfully.')
            return redirect('hospital:lab_test_detail', pk=test.pk)
        except Exception as e:
            messages.error(request, f'Error creating lab test: {str(e)}')
    
    return render(request, 'hospital/lab_test_form.html', {'action': 'Create'})


@login_required
def lab_test_edit(request, pk):
    """Edit an existing lab test"""
    test = get_object_or_404(LabTest, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        try:
            test.code = request.POST['code']
            test.name = request.POST['name']
            test.specimen_type = request.POST['specimen_type']
            test.tat_minutes = int(request.POST.get('tat_minutes', 60))
            test.price = request.POST.get('price', 0) or 0
            test.is_active = request.POST.get('is_active', 'on') == 'on'
            test.save()
            
            messages.success(request, f'Lab test "{test.name}" updated successfully.')
            return redirect('hospital:lab_test_detail', pk=test.pk)
        except Exception as e:
            messages.error(request, f'Error updating lab test: {str(e)}')
    
    context = {
        'test': test,
        'action': 'Edit'
    }
    return render(request, 'hospital/lab_test_form.html', context)


# ==================== DEPARTMENTS & WARDS MANAGEMENT ====================

from .models import Department, Ward

@login_required
def departments_list(request):
    """List all departments"""
    departments = Department.objects.filter(is_deleted=False).select_related('head_of_department__user').order_by('name')
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        departments = departments.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Filter by active status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        departments = departments.filter(is_active=True)
    elif status_filter == 'inactive':
        departments = departments.filter(is_active=False)
    
    # Add counts
    for dept in departments:
        dept.staff_count = Staff.objects.filter(department=dept, is_active=True, is_deleted=False).count()
        dept.wards_count = Ward.objects.filter(department=dept, is_active=True, is_deleted=False).count()
    
    context = {
        'departments': departments,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_departments': departments.count(),
    }
    return render(request, 'hospital/departments_list.html', context)


@login_required
def department_detail(request, pk):
    """View department details"""
    department = get_object_or_404(Department, pk=pk, is_deleted=False)
    
    # Get staff in this department
    staff = Staff.objects.filter(department=department, is_deleted=False).select_related('user').order_by('user__last_name')
    
    # Get wards in this department
    wards = Ward.objects.filter(department=department, is_deleted=False).order_by('name')
    
    context = {
        'department': department,
        'staff': staff,
        'wards': wards,
    }
    return render(request, 'hospital/department_detail.html', context)


@login_required
def department_create(request):
    """Create a new department"""
    if request.method == 'POST':
        try:
            head_id = request.POST.get('head_of_department')
            head = Staff.objects.get(pk=head_id) if head_id else None
            
            department = Department.objects.create(
                name=request.POST['name'],
                code=request.POST.get('code', ''),
                description=request.POST.get('description', ''),
                head_of_department=head,
                is_active=request.POST.get('is_active', 'on') == 'on',
            )
            messages.success(request, f'Department "{department.name}" created successfully.')
            return redirect('hospital:department_detail', pk=department.pk)
        except Exception as e:
            messages.error(request, f'Error creating department: {str(e)}')
    
    staff_list = Staff.objects.filter(is_active=True, is_deleted=False).select_related('user').order_by('user__last_name')
    return render(request, 'hospital/department_form.html', {'action': 'Create', 'staff_list': staff_list})


@login_required
def department_edit(request, pk):
    """Edit an existing department"""
    department = get_object_or_404(Department, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        try:
            head_id = request.POST.get('head_of_department')
            head = Staff.objects.get(pk=head_id) if head_id else None
            
            department.name = request.POST['name']
            department.code = request.POST.get('code', '')
            department.description = request.POST.get('description', '')
            department.head_of_department = head
            department.is_active = request.POST.get('is_active', 'on') == 'on'
            department.save()
            
            messages.success(request, f'Department "{department.name}" updated successfully.')
            return redirect('hospital:department_detail', pk=department.pk)
        except Exception as e:
            messages.error(request, f'Error updating department: {str(e)}')
    
    staff_list = Staff.objects.filter(is_active=True, is_deleted=False).select_related('user').order_by('user__last_name')
    context = {
        'department': department,
        'action': 'Edit',
        'staff_list': staff_list
    }
    return render(request, 'hospital/department_form.html', context)


@login_required
def wards_list(request):
    """List all wards"""
    wards = Ward.objects.filter(is_deleted=False).select_related('department').order_by('name')
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        wards = wards.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query)
        )
    
    # Filter by department
    dept_filter = request.GET.get('department', '')
    if dept_filter:
        wards = wards.filter(department_id=dept_filter)
    
    # Filter by ward type
    type_filter = request.GET.get('type', '')
    if type_filter:
        wards = wards.filter(ward_type=type_filter)
    
    # Filter by active status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        wards = wards.filter(is_active=True)
    elif status_filter == 'inactive':
        wards = wards.filter(is_active=False)
    
    # Add bed counts
    for ward in wards:
        beds = Bed.objects.filter(ward=ward, is_deleted=False)
        ward.total_beds = beds.count()
        ward.available_beds = beds.filter(status='available').count()
        ward.occupied_beds = beds.filter(status='occupied').count()
    
    departments = Department.objects.filter(is_active=True, is_deleted=False).order_by('name')
    
    context = {
        'wards': wards,
        'departments': departments,
        'search_query': search_query,
        'dept_filter': dept_filter,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'total_wards': wards.count(),
    }
    return render(request, 'hospital/wards_list.html', context)


@login_required
def ward_detail(request, pk):
    """View ward details"""
    ward = get_object_or_404(Ward, pk=pk, is_deleted=False)
    
    # Get beds in this ward
    beds = Bed.objects.filter(ward=ward, is_deleted=False).order_by('bed_number')
    
    # Get current admissions
    admissions = Admission.objects.filter(
        ward=ward,
        status='admitted',
        is_deleted=False
    ).select_related('encounter__patient').order_by('-admit_date')
    
    context = {
        'ward': ward,
        'beds': beds,
        'admissions': admissions,
    }
    return render(request, 'hospital/ward_detail.html', context)


@login_required
def ward_create(request):
    """Create a new ward"""
    if request.method == 'POST':
        try:
            ward = Ward.objects.create(
                name=request.POST['name'],
                code=request.POST.get('code', ''),
                ward_type=request.POST['ward_type'],
                department_id=request.POST['department'],
                capacity=int(request.POST.get('capacity', 1)),
                is_active=request.POST.get('is_active', 'on') == 'on',
            )
            messages.success(request, f'Ward "{ward.name}" created successfully.')
            return redirect('hospital:ward_detail', pk=ward.pk)
        except Exception as e:
            messages.error(request, f'Error creating ward: {str(e)}')
    
    departments = Department.objects.filter(is_active=True, is_deleted=False).order_by('name')
    return render(request, 'hospital/ward_form.html', {'action': 'Create', 'departments': departments})


@login_required
def ward_edit(request, pk):
    """Edit an existing ward"""
    ward = get_object_or_404(Ward, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        try:
            ward.name = request.POST['name']
            ward.code = request.POST.get('code', '')
            ward.ward_type = request.POST['ward_type']
            ward.department_id = request.POST['department']
            ward.capacity = int(request.POST.get('capacity', 1))
            ward.is_active = request.POST.get('is_active', 'on') == 'on'
            ward.save()
            
            messages.success(request, f'Ward "{ward.name}" updated successfully.')
            return redirect('hospital:ward_detail', pk=ward.pk)
        except Exception as e:
            messages.error(request, f'Error updating ward: {str(e)}')
    
    departments = Department.objects.filter(is_active=True, is_deleted=False).order_by('name')
    context = {
        'ward': ward,
        'action': 'Edit',
        'departments': departments
    }
    return render(request, 'hospital/ward_form.html', context)


# ==================== MEDICAL RECORDS MANAGEMENT ====================

from .models import MedicalRecord

@login_required
def medical_records_list(request):
    """List all medical records"""
    # Auto-generate records for encounters that don't have documentation yet
    missing_encounters = Encounter.objects.filter(
        is_deleted=False,
        medical_records__isnull=True
    ).select_related('patient', 'provider').distinct()[:50]  # limit to avoid heavy load
    
    for encounter in missing_encounters:
        if not encounter.patient:
            continue
        
        record_type_map = {
            'lab': 'lab_result',
            'imaging': 'imaging',
            'admission': 'discharge_summary',
            'surgery': 'surgical_report',
            'consultation': 'consultation_note',
        }
        record_type = record_type_map.get(encounter.encounter_type, 'consultation_note')
        title = f"{encounter.patient.full_name} - {encounter.encounter_type.title()} Note" if encounter.encounter_type else f"Encounter Note - {encounter.patient.full_name}"
        content = encounter.diagnosis or encounter.chief_complaint or getattr(encounter, 'summary', '') or ''
        
        try:
            MedicalRecord.objects.create(
                patient=encounter.patient,
                encounter=encounter,
                record_type=record_type,
                title=title,
                content=content,
                created_by=encounter.provider,
            )
        except Exception:
            continue
    
    records = MedicalRecord.objects.filter(is_deleted=False).select_related(
        'patient', 'encounter', 'created_by__user'
    ).order_by('-created')
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        records = records.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(patient__mrn__icontains=search_query)
        )
    
    # Filter by record type
    type_filter = request.GET.get('type', '')
    if type_filter:
        records = records.filter(record_type=type_filter)
    
    # Filter by patient
    patient_filter = request.GET.get('patient', '')
    if patient_filter:
        records = records.filter(patient_id=patient_filter)
    
    # Group records by patient (folder view)
    patient_map = OrderedDict()
    for record in records:
        if not record.patient:
            continue
        pid = record.patient_id
        if pid not in patient_map:
            patient_map[pid] = {
                'patient': record.patient,
                'records': [],
                'record_count': 0,
                'last_created': record.created,
            }
        folder = patient_map[pid]
        folder['record_count'] += 1
        if record.created > folder['last_created']:
            folder['last_created'] = record.created
        folder['records'].append(record)
    patient_records = sorted(
        patient_map.values(),
        key=lambda item: item['last_created'],
        reverse=True
    )
    for folder in patient_records:
        folder['service_counts'] = Counter(r.record_type for r in folder['records']).most_common(3)
    
    context = {
        'patient_records': patient_records,
        'search_query': search_query,
        'type_filter': type_filter,
        'patient_filter': patient_filter,
        'total_records': records.count(),
    }
    return render(request, 'hospital/medical_records_list.html', context)


@login_required
def medical_record_detail(request, pk):
    """View medical record details"""
    record = get_object_or_404(MedicalRecord, pk=pk, is_deleted=False)
    
    context = {
        'record': record,
    }
    return render(request, 'hospital/medical_record_detail.html', context)


@login_required
def medical_record_create(request):
    """Create a new medical record"""
    if request.method == 'POST':
        try:
            staff_profile = getattr(request.user, 'staff_profile', None)
            encounter_id = request.POST.get('encounter')
            encounter = Encounter.objects.get(pk=encounter_id) if encounter_id else None
            
            record = MedicalRecord.objects.create(
                patient_id=request.POST['patient'],
                encounter=encounter,
                record_type=request.POST['record_type'],
                title=request.POST['title'],
                content=request.POST.get('content', ''),
                created_by=staff_profile,
            )
            
            # Handle document upload
            if 'document' in request.FILES:
                record.document = request.FILES['document']
                record.save()
            
            messages.success(request, f'Medical record "{record.title}" created successfully.')
            return redirect('hospital:medical_record_detail', pk=record.pk)
        except Exception as e:
            messages.error(request, f'Error creating medical record: {str(e)}')
    
    patients = Patient.objects.filter(is_deleted=False).order_by('last_name')
    encounters = Encounter.objects.filter(is_deleted=False).select_related('patient').order_by('-started_at')[:50]
    
    return render(request, 'hospital/medical_record_form.html', {
        'action': 'Create',
        'patients': patients,
        'encounters': encounters
    })


# ==================== ORDERS MANAGEMENT ====================

@login_required
def orders_list(request):
    """List all orders"""
    orders = Order.objects.filter(is_deleted=False).select_related(
        'encounter__patient', 'requested_by__user'
    ).order_by('-requested_at')
    
    # Search
    search_query = request.GET.get('q', '')
    if search_query:
        orders = orders.filter(
            Q(encounter__patient__first_name__icontains=search_query) |
            Q(encounter__patient__last_name__icontains=search_query) |
            Q(encounter__patient__mrn__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
    
    # Filter by order type
    type_filter = request.GET.get('type', '')
    if type_filter:
        orders = orders.filter(order_type=type_filter)
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Filter by priority
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        orders = orders.filter(priority=priority_filter)
    
    # Pagination
    paginator = Paginator(orders, 20)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    
    context = {
        'orders': orders_page,
        'search_query': search_query,
        'type_filter': type_filter,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'total_orders': orders.count(),
    }
    return render(request, 'hospital/orders_list.html', context)


@login_required
def order_detail(request, pk):
    """View order details"""
    order = get_object_or_404(Order, pk=pk, is_deleted=False)
    
    # Get related items based on order type
    lab_results = None
    prescriptions = None
    imaging_studies = []
    
    if order.order_type == 'lab':
        lab_results = LabResult.objects.filter(order=order, is_deleted=False)
    elif order.order_type == 'medication':
        prescriptions = Prescription.objects.filter(order=order, is_deleted=False)
    
    try:
        from .models_advanced import ImagingStudy
    except ImportError:
        ImagingStudy = None
    
    if ImagingStudy:
        imaging_queryset = ImagingStudy.objects.filter(
            is_deleted=False
        ).prefetch_related('images')
        
        imaging_studies = imaging_queryset.filter(
            order=order
        ).order_by('-performed_at', '-created')
        
        if not imaging_studies.exists():
            imaging_studies = imaging_queryset.filter(
                encounter=order.encounter
            ).order_by('-performed_at', '-created')
    else:
        imaging_studies = []
    
    context = {
        'order': order,
        'lab_results': lab_results,
        'prescriptions': prescriptions,
        'imaging_studies': imaging_studies,
    }
    return render(request, 'hospital/order_detail.html', context)


@login_required
def order_create(request):
    """Create a new order"""
    if request.method == 'POST':
        try:
            staff_profile = getattr(request.user, 'staff_profile', None)
            
            order = Order.objects.create(
                encounter_id=request.POST['encounter'],
                order_type=request.POST['order_type'],
                status='pending',
                priority=request.POST.get('priority', 'routine'),
                requested_by=staff_profile,
                notes=request.POST.get('notes', ''),
            )
            
            messages.success(request, 'Order created successfully.')
            return redirect('hospital:order_detail', pk=order.pk)
        except Exception as e:
            messages.error(request, f'Error creating order: {str(e)}')
    
    encounters = Encounter.objects.filter(
        status='active',
        is_deleted=False
    ).select_related('patient').order_by('-started_at')
    
    return render(request, 'hospital/order_form.html', {
        'action': 'Create',
        'encounters': encounters
    })

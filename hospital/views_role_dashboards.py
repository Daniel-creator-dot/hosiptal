"""
Role-specific Dashboard Views
Specialized dashboards for different staff roles
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from .models import Patient, Encounter, Staff, Department, Ward, Bed, Admission
from .models_workflow import Bill, PaymentRequest
from .models_accounting import Transaction
from .models import Order, LabResult, Prescription
from .models_advanced import ImagingStudy, MedicationAdministrationRecord
from .models_legacy_patients import LegacyPatient
from .models_legacy_mapping import LegacyIDMapping
from .decorators import role_required


def get_staff_profile(user):
    """Get staff profile for user"""
    try:
        return Staff.objects.get(user=user, is_deleted=False)
    except Staff.DoesNotExist:
        return None


def ensure_staff_profile(request, role_label, expected_profession=None):
    """
    Ensure the requesting user has a Staff profile (and optionally the expected profession).
    Returns tuple (staff, error_response)
    """
    staff = get_staff_profile(request.user)

    if not staff or (expected_profession and staff.profession != expected_profession):
        message = f"Access denied. {role_label} role required."
        response = render(request, 'hospital/access_denied.html', {
            'message': message
        }, status=403)
        return None, response

    return staff, None


@login_required
@role_required('doctor')
def doctor_dashboard(request):
    """Doctor's specialized dashboard with legacy patient support"""
    staff, error_response = ensure_staff_profile(request, 'Doctor', expected_profession='doctor')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    
    # Today's appointments
    today_appointments = Encounter.objects.filter(
        provider=staff,
        started_at__date=today,
        status='active',
        is_deleted=False
    ).select_related('patient').order_by('started_at')
    
    # Pending consultations
    pending_consultations = Encounter.objects.filter(
        provider=staff,
        status='active',
        is_deleted=False
    ).exclude(
        id__in=today_appointments.values_list('id', flat=True)
    ).select_related('patient').order_by('started_at')[:10]
    
    # Recent patients (Django patients)
    recent_patients = Patient.objects.filter(
        encounters__provider=staff,
        encounters__is_deleted=False
    ).distinct().order_by('-encounters__started_at')[:10]
    
    # Lab results pending review
    pending_lab_results = LabResult.objects.filter(
        encounter__provider=staff,
        status='completed',
        reviewed_by__isnull=True,
        is_deleted=False
    ).select_related('encounter', 'patient', 'test').order_by('-created')[:10]
    
    # Legacy patient statistics
    total_legacy_patients = LegacyPatient.objects.count()
    total_django_patients = Patient.objects.filter(is_deleted=False).count()
    
    # Check migration status
    legacy_mrns = set(f'PMC-LEG-{str(lp.pid).zfill(6)}' for lp in LegacyPatient.objects.all()[:1000])  # Sample
    migrated_mrns = set(Patient.objects.filter(mrn__startswith='PMC-LEG-', is_deleted=False).values_list('mrn', flat=True))
    
    unmigrated_count = len(legacy_mrns - migrated_mrns)
    migration_progress = ((len(migrated_mrns) / max(len(legacy_mrns), 1)) * 100) if legacy_mrns else 100
    
    # Recent legacy patients (for awareness)
    recent_legacy_patients = LegacyPatient.objects.all().order_by('-id')[:5]
    
    # Statistics
    stats = {
        'today_appointments': today_appointments.count(),
        'pending_consultations': pending_consultations.count(),
        'total_patients': total_django_patients,
        'pending_lab_results': pending_lab_results.count(),
        'total_legacy_patients': total_legacy_patients,
        'unmigrated_legacy': unmigrated_count,
        'migration_progress': round(migration_progress, 1),
    }
    
    context = {
        'staff': staff,
        'today_appointments': today_appointments,
        'pending_consultations': pending_consultations,
        'recent_patients': recent_patients,
        'pending_lab_results': pending_lab_results,
        'recent_legacy_patients': recent_legacy_patients,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/doctor_dashboard.html', context)


@login_required
@role_required('nurse')
def nurse_dashboard(request):
    """Nurse's specialized dashboard"""
    staff, error_response = ensure_staff_profile(request, 'Nurse', expected_profession='nurse')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    
    # Ward assignments - first try explicit assignments, then fall back to nurse's department, then all active wards
    assigned_wards = Ward.objects.filter(
        staff=staff,
        is_active=True
    ).distinct() if hasattr(Ward, 'staff') else Ward.objects.none()

    if not assigned_wards.exists():
        if staff.department_id:
            assigned_wards = Ward.objects.filter(
                department=staff.department,
                is_active=True
            ).distinct()
        else:
            assigned_wards = Ward.objects.filter(is_active=True).distinct()
    
    # Patients in assigned wards
    ward_patients = Patient.objects.filter(
        encounters__admission__ward__in=assigned_wards,
        encounters__status='active',
        encounters__is_deleted=False
    ).distinct()
    
    # Pending vital signs
    pending_vitals = Encounter.objects.filter(
        admission__ward__in=assigned_wards,
        status='active',
        is_deleted=False
    ).exclude(
        vitals__recorded_at__date=today
    ).select_related('patient', 'admission__ward')[:20]
    
    # Medication administration records
    pending_medications = MedicationAdministrationRecord.objects.filter(
        encounter__admission__ward__in=assigned_wards,
        status__in=['scheduled', 'held'],
        is_deleted=False
    ).select_related('encounter', 'patient', 'prescription')[:20]
    
    # Bed status in assigned wards
    bed_status = Bed.objects.filter(
        ward__in=assigned_wards,
        is_active=True
    ).select_related('ward')
    
    # Statistics
    stats = {
        'assigned_wards': assigned_wards.count(),
        'ward_patients': ward_patients.count(),
        'pending_vitals': pending_vitals.count(),
        'pending_medications': pending_medications.count(),
        'total_beds': bed_status.count(),
        'occupied_beds': bed_status.filter(status='occupied').count(),
    }
    
    context = {
        'staff': staff,
        'assigned_wards': assigned_wards,
        'ward_patients': ward_patients,
        'pending_vitals': pending_vitals,
        'pending_medications': pending_medications,
        'bed_status': bed_status,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/nurse_dashboard.html', context)


@login_required
@role_required('lab_technician')
def lab_technician_dashboard(request):
    """Lab Technician's specialized dashboard"""
    staff, error_response = ensure_staff_profile(request, 'Lab Technician', expected_profession='lab_technician')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    
    # Pending lab orders - only those with no in-progress/completed/cancelled results
    pending_orders = Order.objects.filter(
        order_type='lab',
        status='pending',
        is_deleted=False
    ).exclude(
        lab_results__status__in=['in_progress', 'completed', 'cancelled']
    ).select_related(
        'encounter',
        'encounter__patient'
    ).order_by('-created').distinct()[:20]
    
    # In progress tests
    in_progress_tests = Order.objects.filter(
        order_type='lab',
        status='in_progress',
        is_deleted=False
    ).select_related('encounter', 'encounter__patient').order_by('-modified')[:20]
    
    # Completed results (recent)
    completed_results = LabResult.objects.filter(
        status='completed',
        is_deleted=False
    ).select_related('order__encounter', 'order__encounter__patient', 'test').order_by('-modified')[:20]
    
    # Equipment status (if available)
    equipment_status = []  # Placeholder for equipment monitoring
    
    # Statistics
    stats = {
        'pending_orders': pending_orders.count(),
        'in_progress_tests': in_progress_tests.count(),
        'completed_today': LabResult.objects.filter(
            status='completed',
            modified__date=today,
            is_deleted=False
        ).count(),
        'total_tests_today': Order.objects.filter(
            order_type='lab',
            created__date=today,
            is_deleted=False
        ).count(),
    }
    
    context = {
        'staff': staff,
        'pending_orders': pending_orders,
        'in_progress_tests': in_progress_tests,
        'completed_results': completed_results,
        'equipment_status': equipment_status,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/lab_technician_dashboard.html', context)


@login_required
@role_required('pharmacist')
def pharmacist_dashboard(request):
    """Pharmacists work exclusively inside the dispensing/payment workflow."""
    return redirect('hospital:pharmacy_pending_dispensing')


@login_required
@role_required('radiologist')
def radiologist_dashboard(request):
    """Radiologist's specialized dashboard"""
    staff, error_response = ensure_staff_profile(request, 'Radiologist', expected_profession='radiologist')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    
    # Pending imaging orders
    pending_orders = Order.objects.filter(
        order_type='imaging',
        status='pending',
        is_deleted=False
    ).select_related('encounter', 'patient').order_by('-created')[:20]
    
    # In progress studies
    in_progress_studies = ImagingStudy.objects.filter(
        status='in_progress',
        is_deleted=False
    ).select_related('order', 'patient').order_by('-updated')[:20]
    
    # Completed studies (recent)
    completed_studies = ImagingStudy.objects.filter(
        status='completed',
        is_deleted=False
    ).select_related('order', 'patient').order_by('-completed_at')[:20]
    
    # Equipment status
    equipment_status = []  # Placeholder for imaging equipment monitoring
    
    # Statistics
    stats = {
        'pending_orders': pending_orders.count(),
        'in_progress_studies': in_progress_studies.count(),
        'completed_today': ImagingStudy.objects.filter(
            completed_at__date=today,
            is_deleted=False
        ).count(),
        'total_studies_today': Order.objects.filter(
            order_type='imaging',
            created__date=today,
            is_deleted=False
        ).count(),
    }
    
    context = {
        'staff': staff,
        'pending_orders': pending_orders,
        'in_progress_studies': in_progress_studies,
        'completed_studies': completed_studies,
        'equipment_status': equipment_status,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/radiologist_dashboard.html', context)


@login_required
@role_required('receptionist')
def receptionist_dashboard(request):
    """Receptionist's specialized dashboard"""
    staff, error_response = ensure_staff_profile(request, 'Receptionist', expected_profession='receptionist')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    
    # Today's appointments
    today_appointments = Encounter.objects.filter(
        started_at__date=today,
        is_deleted=False
    ).select_related('patient', 'provider').order_by('started_at')
    
    # Pending registrations
    pending_registrations = Patient.objects.filter(
        created__date=today,
        is_deleted=False
    ).order_by('-created')[:10]
    
    # Walk-in patients
    walk_in_patients = Encounter.objects.filter(
        encounter_type='outpatient',
        started_at__date=today,
        is_deleted=False
    ).select_related('patient').order_by('-started_at')[:10]
    
    # Statistics
    stats = {
        'today_appointments': today_appointments.count(),
        'pending_registrations': pending_registrations.count(),
        'walk_in_patients': walk_in_patients.count(),
        'total_patients_today': Patient.objects.filter(
            created__date=today,
            is_deleted=False
        ).count(),
    }
    
    context = {
        'staff': staff,
        'today_appointments': today_appointments,
        'pending_registrations': pending_registrations,
        'walk_in_patients': walk_in_patients,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/receptionist_dashboard.html', context)


@login_required
@role_required('cashier')
def cashier_dashboard_role(request):
    """Cashier's specialized dashboard (role-based)"""
    staff, error_response = ensure_staff_profile(request, 'Cashier', expected_profession='cashier')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    
    # Pending payments
    pending_payments = PaymentRequest.objects.filter(
        status='pending',
        is_deleted=False
    ).select_related('patient', 'invoice').order_by('-created')[:20]
    
    # Today's transactions
    today_transactions = Transaction.objects.filter(
        processed_by=request.user,
        transaction_date__date=today,
        is_deleted=False
    ).select_related('patient', 'invoice').order_by('-transaction_date')
    
    # Outstanding bills
    outstanding_bills = Bill.objects.filter(
        status__in=['issued', 'partially_paid'],
        patient_portion__gt=0,
        is_deleted=False
    ).select_related('patient', 'invoice').order_by('-issued_at')[:20]
    
    # Statistics
    stats = {
        'pending_payments': pending_payments.count(),
        'today_transactions': today_transactions.count(),
        'outstanding_bills': outstanding_bills.count(),
        'today_revenue': today_transactions.filter(
            transaction_type='payment_received'
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00'),
    }
    
    context = {
        'staff': staff,
        'pending_payments': pending_payments,
        'today_transactions': today_transactions,
        'outstanding_bills': outstanding_bills,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/cashier_dashboard.html', context)


@login_required
@role_required('admin')
def admin_dashboard_role(request):
    """Administrator's specialized dashboard"""
    staff, error_response = ensure_staff_profile(request, 'Administrator', expected_profession='admin')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    
    # System overview - Include both Django and Legacy patients
    django_patients = Patient.objects.filter(is_deleted=False).count()
    try:
        from .models_legacy_patients import LegacyPatient
        legacy_patients = LegacyPatient.objects.count()
    except:
        legacy_patients = 0
    total_patients = django_patients + legacy_patients
    total_staff = Staff.objects.filter(is_deleted=False).count()
    total_departments = Department.objects.filter(is_deleted=False).count()
    total_wards = Ward.objects.filter(is_deleted=False).count()
    
    # Recent activity
    recent_patients = Patient.objects.filter(
        is_deleted=False
    ).order_by('-created')[:10]
    
    recent_staff = Staff.objects.filter(
        is_deleted=False
    ).order_by('-created')[:10]
    
    # System statistics
    stats = {
        'total_patients': total_patients,
        'total_staff': total_staff,
        'total_departments': total_departments,
        'total_wards': total_wards,
        'active_encounters': Encounter.objects.filter(
            status='active',
            is_deleted=False
        ).count(),
        'total_beds': Bed.objects.filter(is_active=True).count(),
        'occupied_beds': Bed.objects.filter(
            status='occupied',
            is_active=True
        ).count(),
    }
    
    context = {
        'staff': staff,
        'recent_patients': recent_patients,
        'recent_staff': recent_staff,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/admin_dashboard.html', context)

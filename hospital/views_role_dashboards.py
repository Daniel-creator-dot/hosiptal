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
from .models import Order, LabResult, Prescription
from .decorators import role_required
from .services.performance_analytics import performance_analytics_service

# Import optional models with safe fallbacks
Bill = None
PaymentRequest = None
try:
    from .models_workflow import Bill, PaymentRequest
except (ImportError, AttributeError, Exception):
    Bill = None
    PaymentRequest = None

Transaction = None
try:
    from .models_accounting import Transaction
except (ImportError, AttributeError, Exception):
    Transaction = None

ImagingStudy = None
MedicationAdministrationRecord = None
try:
    from .models_advanced import ImagingStudy, MedicationAdministrationRecord
except (ImportError, AttributeError, Exception):
    ImagingStudy = None
    MedicationAdministrationRecord = None

LegacyPatient = None
try:
    from .models_legacy_patients import LegacyPatient
except (ImportError, AttributeError, Exception):
    LegacyPatient = None

LegacyIDMapping = None
try:
    from .models_legacy_mapping import LegacyIDMapping
except (ImportError, AttributeError, Exception):
    LegacyIDMapping = None


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


def prescription_avg_minutes(queryset):
    """Helper to calculate average dispense turnaround in minutes for a queryset."""
    if not queryset:
        return 0
    durations = []
    for prescription in queryset:
        if prescription.dispensed_at:
            durations.append((prescription.dispensed_at - prescription.created).total_seconds() / 60)
    if not durations:
        return 0
    return round(sum(durations) / len(durations), 1)


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
    total_legacy_patients = 0
    unmigrated_count = 0
    migration_progress = 100
    recent_legacy_patients = []
    
    if LegacyPatient:
        try:
            total_legacy_patients = LegacyPatient.objects.count()
            # Check migration status
            legacy_mrns = set(f'PMC-LEG-{str(lp.pid).zfill(6)}' for lp in LegacyPatient.objects.all()[:1000])  # Sample
            migrated_mrns = set(Patient.objects.filter(mrn__startswith='PMC-LEG-', is_deleted=False).values_list('mrn', flat=True))
            
            unmigrated_count = len(legacy_mrns - migrated_mrns)
            migration_progress = ((len(migrated_mrns) / max(len(legacy_mrns), 1)) * 100) if legacy_mrns else 100
            
            # Recent legacy patients (for awareness)
            recent_legacy_patients = LegacyPatient.objects.all().order_by('-id')[:5]
        except Exception:
            pass
    
    total_django_patients = Patient.objects.filter(is_deleted=False).count()
    
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
    
    performance_snapshot = performance_analytics_service.generate_snapshot(staff) if staff else None

    context = {
        'staff': staff,
        'today_appointments': today_appointments,
        'pending_consultations': pending_consultations,
        'recent_patients': recent_patients,
        'pending_lab_results': pending_lab_results,
        'recent_legacy_patients': recent_legacy_patients,
        'stats': stats,
        'today': today,
        'performance_snapshot': performance_snapshot,
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
    
    ward_scope_exists = assigned_wards.exists()
    
    patient_filters = {
        'encounters__status': 'active',
        'encounters__is_deleted': False,
    }
    encounter_filters = {
        'status': 'active',
        'is_deleted': False,
    }
    medication_filters = {
        'status__in': ['scheduled', 'held'],
        'is_deleted': False,
    }
    
    if ward_scope_exists:
        patient_filters['encounters__admission__ward__in'] = assigned_wards
        encounter_filters['admission__ward__in'] = assigned_wards
        medication_filters['encounter__admission__ward__in'] = assigned_wards
    else:
        patient_filters['encounters__admission__isnull'] = False
        encounter_filters['admission__isnull'] = False
        medication_filters['encounter__admission__isnull'] = False
    
    # Patients in scope wards (or all admitted if no wards configured)
    ward_patients = Patient.objects.filter(**patient_filters).distinct()
    
    # Pending vital signs
    pending_vitals = Encounter.objects.filter(**encounter_filters).exclude(
        vitals__recorded_at__date=today
    ).select_related('patient', 'admission__ward', 'admission__bed')[:20]
    
    # Medication administration records
    pending_medications = []
    if MedicationAdministrationRecord:
        try:
            pending_medications = MedicationAdministrationRecord.objects.filter(
                **medication_filters
            ).select_related('encounter', 'encounter__patient', 'prescription')[:20]
        except Exception:
            pass
    
    # Bed status in assigned wards
    bed_status_qs = Bed.objects.filter(is_active=True)
    if ward_scope_exists:
        bed_status_qs = bed_status_qs.filter(ward__in=assigned_wards)
    bed_status = bed_status_qs.select_related('ward')
    
    # Statistics
    stats = {
        'assigned_wards': assigned_wards.count(),
        'ward_patients': ward_patients.count(),
        'pending_vitals': pending_vitals.count(),
        'pending_medications': len(pending_medications),
        'total_beds': bed_status.count(),
        'occupied_beds': bed_status.filter(status='occupied').count(),
    }
    
    performance_snapshot = performance_analytics_service.generate_snapshot(staff) if staff else None

    context = {
        'staff': staff,
        'assigned_wards': assigned_wards,
        'ward_patients': ward_patients,
        'pending_vitals': pending_vitals,
        'pending_medications': pending_medications,
        'bed_status': bed_status,
        'stats': stats,
        'today': today,
        'performance_snapshot': performance_snapshot,
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
    
    performance_snapshot = performance_analytics_service.generate_snapshot(staff) if staff else None

    context = {
        'staff': staff,
        'pending_orders': pending_orders,
        'in_progress_tests': in_progress_tests,
        'completed_results': completed_results,
        'equipment_status': equipment_status,
        'stats': stats,
        'today': today,
        'performance_snapshot': performance_snapshot,
    }
    
    return render(request, 'hospital/role_dashboards/lab_technician_dashboard.html', context)


@login_required
@role_required('pharmacist')
def pharmacist_dashboard(request):
    """Pharmacist dashboard with performance summary."""
    staff, error_response = ensure_staff_profile(request, 'Pharmacist', expected_profession='pharmacist')
    if error_response:
        return error_response

    today = timezone.now().date()
    pending_prescriptions = Prescription.objects.filter(
        status='pending',
        is_deleted=False,
    ).select_related('encounter__patient').order_by('-created')[:15]

    dispensed_today_qs = Prescription.objects.filter(
        dispensed_by=staff,
        dispensed_at__date=today,
        status='dispensed',
    ).select_related('encounter__patient')
    dispensed_today = dispensed_today_qs.order_by('-dispensed_at')[:10]

    stats = {
        'pending_queue': Prescription.objects.filter(status='pending', is_deleted=False).count(),
        'dispensed_today': dispensed_today_qs.count(),
        'avg_dispense_minutes': prescription_avg_minutes(dispensed_today_qs),
    }

    performance_snapshot = performance_analytics_service.generate_snapshot(staff)

    context = {
        'staff': staff,
        'pending_prescriptions': pending_prescriptions,
        'dispensed_today': dispensed_today,
        'stats': stats,
        'today': today,
        'performance_snapshot': performance_snapshot,
    }
    return render(request, 'hospital/role_dashboards/pharmacist_dashboard.html', context)


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
    ).select_related('encounter', 'encounter__patient').order_by('-created')[:20]
    
    # In progress studies
    in_progress_studies = []
    if ImagingStudy:
        try:
            in_progress_studies = ImagingStudy.objects.filter(
                status='in_progress',
                is_deleted=False
            ).select_related('order', 'order__encounter__patient').order_by('-updated')[:20]
        except Exception:
            pass
    
    # Completed studies (recent)
    completed_studies = []
    if ImagingStudy:
        try:
            completed_studies = ImagingStudy.objects.filter(
                status='completed',
                is_deleted=False
            ).select_related('order', 'order__encounter__patient').order_by('-completed_at')[:20]
        except Exception:
            pass
    
    # Equipment status
    equipment_status = []  # Placeholder for imaging equipment monitoring
    
    # Statistics
    completed_today = 0
    if ImagingStudy:
        try:
            completed_today = ImagingStudy.objects.filter(
                completed_at__date=today,
                is_deleted=False
            ).count()
        except Exception:
            pass
    
    stats = {
        'pending_orders': pending_orders.count(),
        'in_progress_studies': len(in_progress_studies),
        'completed_today': completed_today,
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
    
    performance_snapshot = performance_analytics_service.generate_snapshot(staff) if staff else None

    context = {
        'staff': staff,
        'today_appointments': today_appointments,
        'pending_registrations': pending_registrations,
        'walk_in_patients': walk_in_patients,
        'stats': stats,
        'today': today,
        'performance_snapshot': performance_snapshot,
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
    pending_payments = []
    if PaymentRequest:
        try:
            pending_payments = PaymentRequest.objects.filter(
                status='pending',
                is_deleted=False
            ).select_related('patient', 'invoice').order_by('-created')[:20]
        except Exception:
            pass
    
    # Today's transactions
    today_transactions = []
    if Transaction:
        try:
            today_transactions = Transaction.objects.filter(
                processed_by=request.user,
                transaction_date__date=today,
                is_deleted=False
            ).select_related('patient', 'invoice').order_by('-transaction_date')
        except Exception:
            pass
    
    # Outstanding bills
    outstanding_bills = []
    if Bill:
        try:
            outstanding_bills = Bill.objects.filter(
                status__in=['issued', 'partially_paid'],
                patient_portion__gt=0,
                is_deleted=False
            ).select_related('patient', 'invoice').order_by('-issued_at')[:20]
        except Exception:
            pass
    
    # Statistics
    today_revenue = Decimal('0.00')
    if Transaction and today_transactions:
        try:
            today_revenue = sum(t.amount for t in today_transactions if hasattr(t, 'transaction_type') and t.transaction_type == 'payment_received') or Decimal('0.00')
        except Exception:
            pass
    
    stats = {
        'pending_payments': len(pending_payments),
        'today_transactions': len(today_transactions),
        'outstanding_bills': len(outstanding_bills),
        'today_revenue': today_revenue,
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
    legacy_patients = 0
    if LegacyPatient:
        try:
            legacy_patients = LegacyPatient.objects.count()
        except Exception:
            pass
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

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
from .models import Order, LabResult, Prescription, MedicalRecord
from .decorators import role_required
from .services.performance_analytics import performance_analytics_service
from .views_hod_shift_monitoring import is_hod

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

def _legacy_table_exists():
    """Check if patient_data table exists"""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'patient_data'
                );
            """)
            return cursor.fetchone()[0]
    except Exception:
        return False

LegacyIDMapping = None
try:
    from .models_legacy_mapping import LegacyIDMapping
except (ImportError, AttributeError, Exception):
    LegacyIDMapping = None


def get_staff_profile(user):
    """Get staff profile for user - handles multiple staff records gracefully"""
    try:
        # Use filter().first() instead of get() to handle multiple staff records
        # This prevents MultipleObjectsReturned errors
        return Staff.objects.filter(user=user, is_deleted=False).order_by('-created').first()
    except Exception:
        return None


def ensure_staff_profile(request, role_label, expected_profession=None):
    """
    Ensure the requesting user has a Staff profile (and optionally the expected profession).
    expected_profession may be a single string or a sequence of allowed professions (e.g. nurse + midwife).
    Returns tuple (staff, error_response)
    """
    staff = get_staff_profile(request.user)

    def _profession_ok():
        if not expected_profession:
            return True
        if isinstance(expected_profession, (list, tuple, set)):
            return staff.profession in expected_profession
        return staff.profession == expected_profession

    if not staff or (expected_profession and not _profession_ok()):
        message = f"Access denied. {role_label} role required."
        try:
            response = render(request, 'hospital/access_denied.html', {
                'message': message,
                'dashboard_url': '/hms/',
                'login_url': '/hms/login/',
            }, status=403)
        except Exception:
            # Fallback if template rendering fails
            from django.http import HttpResponse
            response = HttpResponse(
                f'<html><body><h1>403 - Access Denied</h1>'
                f'<p>{message}</p>'
                f'<p><a href="/hms/">Go to Dashboard</a></p>'
                f'</body></html>',
                status=403
            )
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
    
    # Today's visits (Encounter rows — same patient may also have a separate Appointment record)
    today_encounters = Encounter.objects.filter(
        provider=staff,
        started_at__date=today,
        status='active',
        is_deleted=False
    ).select_related('patient__primary_insurance').order_by('started_at')
    
    # Pending consultations (active only)
    pending_consultations = Encounter.objects.filter(
        provider=staff,
        status='active',
        is_deleted=False
    ).exclude(
        id__in=today_encounters.values_list('id', flat=True)
    ).select_related('patient__primary_insurance').order_by('started_at')[:10]
    
    # Recently completed consultations (re-openable until end of day after completion)
    from datetime import timedelta
    reopenable_consultations = []
    for enc in Encounter.objects.filter(
        provider=staff,
        status='completed',
        ended_at__isnull=False,
        is_deleted=False
    ).select_related('patient__primary_insurance').order_by('-ended_at')[:10]:
        if not enc.consultation_expired():
            reopenable_consultations.append(enc)
    
    # Recent patients (Django patients)
    recent_patients = Patient.objects.filter(
        encounters__provider=staff,
        encounters__is_deleted=False
    ).select_related('primary_insurance').distinct().order_by('-encounters__started_at')[:10]
    
    # Lab results pending review (LabResult links via order->encounter; uses verified_by)
    pending_lab_results = LabResult.objects.filter(
        order__encounter__provider=staff,
        status='completed',
        verified_by__isnull=True,
        is_deleted=False
    ).select_related(
        'order', 'order__encounter', 'order__encounter__patient',
        'order__encounter__patient__primary_insurance', 'test'
    ).order_by('-created')[:10]
    
    # Recent lab orders (pending/in-progress) for this doctor
    recent_lab_orders = Order.objects.filter(
        order_type='lab',
        requested_by=staff,
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).select_related('encounter__patient__primary_insurance').order_by('-requested_at')[:5]
    
    # Legacy patient statistics
    total_legacy_patients = 0
    unmigrated_count = 0
    migration_progress = 100
    recent_legacy_patients = []
    legacy_table_exists = False
    
    if LegacyPatient and _legacy_table_exists():
        try:
            from django.db import ProgrammingError, OperationalError
            legacy_table_exists = True
            total_legacy_patients = LegacyPatient.objects.count()
            # Check migration status
            legacy_mrns = set(f'PMC-LEG-{str(lp.pid).zfill(6)}' for lp in LegacyPatient.objects.all()[:1000])  # Sample
            migrated_mrns = set(Patient.objects.filter(mrn__startswith='PMC-LEG-', is_deleted=False).values_list('mrn', flat=True))
            
            unmigrated_count = len(legacy_mrns - migrated_mrns)
            migration_progress = ((len(migrated_mrns) / max(len(legacy_mrns), 1)) * 100) if legacy_mrns else 100
            
            # Recent legacy patients (for awareness)
            recent_legacy_patients = LegacyPatient.objects.all().order_by('-id')[:5]
        except (ProgrammingError, OperationalError):
            legacy_table_exists = False
        except Exception:
            legacy_table_exists = False
    
    total_django_patients = Patient.objects.filter(is_deleted=False).count()
    
    # Statistics
    stats = {
        'today_appointments': today_encounters.count(),
        'pending_consultations': pending_consultations.count(),
        'total_patients': total_django_patients,
        'pending_lab_results': pending_lab_results.count(),
        'total_legacy_patients': total_legacy_patients,
        'unmigrated_legacy': unmigrated_count,
        'migration_progress': round(migration_progress, 1),
        'legacy_table_exists': legacy_table_exists,
    }
    
    performance_snapshot = performance_analytics_service.generate_snapshot(staff) if staff else None
    
    # Check if user is Medical Director - Enhanced detection
    is_medical_director = False
    if request.user.is_superuser:
        is_medical_director = True
    elif staff:
        try:
            specialization = (staff.specialization or '').lower()
            is_medical_director = (
                'medical director' in specialization or
                (staff.profession == 'doctor' and 'director' in specialization)
            )
        except Exception:
            pass

    context = {
        'staff': staff,
        'today_encounters': today_encounters,
        'pending_consultations': pending_consultations,
        'reopenable_consultations': reopenable_consultations,
        'recent_patients': recent_patients,
        'pending_lab_results': pending_lab_results,
        'recent_lab_orders': recent_lab_orders,
        'recent_legacy_patients': recent_legacy_patients,
        'stats': stats,
        'today': today,
        'performance_snapshot': performance_snapshot,
        'is_medical_director': is_medical_director,
    }
    
    return render(request, 'hospital/role_dashboards/doctor_dashboard.html', context)


@login_required
@role_required('doctor')
def doctor_order_lab_tests(request):
    """Doctor can order lab tests directly from dashboard"""
    staff, error_response = ensure_staff_profile(request, 'Doctor', expected_profession='doctor')
    if error_response:
        return error_response
    
    from .models import LabTest, LabResult
    from .models_lab_management import LabReagent
    
    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        encounter_id = request.POST.get('encounter_id')
        test_ids = request.POST.getlist('test_ids')
        priority = request.POST.get('priority', 'routine')
        notes = request.POST.get('notes', '')
        
        if not patient_id:
            from django.contrib import messages
            messages.error(request, 'Please select a patient.')
            return redirect('hospital:doctor_dashboard')
        
        try:
            patient = Patient.objects.get(pk=patient_id, is_deleted=False)
        except Patient.DoesNotExist:
            from django.contrib import messages
            messages.error(request, 'Patient not found.')
            return redirect('hospital:doctor_dashboard')
        
        # Get or create active encounter
        if encounter_id:
            try:
                encounter = Encounter.objects.get(pk=encounter_id, is_deleted=False, status='active')
            except Encounter.DoesNotExist:
                encounter = None
        else:
            # Get most recent active encounter or create new one
            encounter = Encounter.objects.filter(
                patient=patient,
                provider=staff,
                status='active',
                is_deleted=False
            ).order_by('-started_at').first()
            
            if not encounter:
                # Create new encounter for this lab order
                encounter = Encounter.objects.create(
                    patient=patient,
                    provider=staff,
                    encounter_type='outpatient',
                    status='active',
                )
        
        if not test_ids:
            from django.contrib import messages
            messages.error(request, 'Please select at least one lab test.')
            return redirect('hospital:doctor_order_lab_tests')
        
        try:
            tests = LabTest.objects.filter(pk__in=test_ids, is_active=True, is_deleted=False)
            if tests.exists():
                # Create LAB order
                lab_order = Order.objects.create(
                    encounter=encounter,
                    order_type='lab',
                    status='pending',
                    priority=priority,
                    notes=notes,
                    requested_by=staff
                )
                
                # Create lab results for each test
                reagent_warnings = []
                for test in tests:
                    # Check for duplicate before creating
                    existing_result = LabResult.objects.filter(
                        order=lab_order,
                        test=test,
                        is_deleted=False
                    ).first()
                    
                    if not existing_result:
                        LabResult.objects.create(
                            order=lab_order,
                            test=test,
                            status='pending'
                        )
                    
                    # Check reagent availability
                    required_reagents = test.required_reagents.filter(is_deleted=False)
                    for reagent in required_reagents:
                        if reagent.is_low_stock:
                            reagent_warnings.append(f'{reagent.name} (low stock)')
                        if reagent.is_expired:
                            reagent_warnings.append(f'{reagent.name} (expired)')
                
                from django.contrib import messages
                if reagent_warnings:
                    messages.warning(
                        request,
                        f'Lab order created with {tests.count()} test(s). Reagent warnings: {", ".join(set(reagent_warnings))}'
                    )
                else:
                    messages.success(request, f'Lab order created with {tests.count()} test(s). Order sent to laboratory.')
                
                return redirect('hospital:doctor_dashboard')
            else:
                from django.contrib import messages
                messages.error(request, 'No valid tests selected.')
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'Error creating lab order: {str(e)}')
    
    # GET request - show form
    # Get recent patients for this doctor
    recent_patients = Patient.objects.filter(
        encounters__provider=staff,
        encounters__is_deleted=False
    ).distinct().order_by('-encounters__started_at')[:20]
    
    # Get all active lab tests
    lab_tests = LabTest.objects.filter(is_active=True, is_deleted=False).order_by('name')
    
    # Get reagent availability info
    test_reagent_info = {}
    for test in lab_tests:
        required_reagents = test.required_reagents.filter(is_deleted=False)
        test_reagent_info[str(test.id)] = {
            'reagents': required_reagents,
            'all_available': all(not (r.is_low_stock or r.is_expired) for r in required_reagents),
        }
    
    context = {
        'staff': staff,
        'recent_patients': recent_patients,
        'lab_tests': lab_tests,
        'test_reagent_info': test_reagent_info,
    }
    
    return render(request, 'hospital/role_dashboards/doctor_order_lab_tests.html', context)


@login_required
@role_required('nurse', 'midwife', 'admin')
def nurse_dashboard(request):
    """Nurse's specialized dashboard"""
    staff, error_response = ensure_staff_profile(
        request, 'Nurse', expected_profession=('nurse', 'midwife')
    )
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
    ward_patients = Patient.objects.filter(**patient_filters).select_related(
        'primary_insurance'
    ).distinct()
    
    # Pending vital signs
    pending_vitals = Encounter.objects.filter(**encounter_filters).exclude(
        vitals__recorded_at__date=today
    ).select_related('patient__primary_insurance', 'admission__ward', 'admission__bed')[:20]
    
    # Medication administration records
    pending_medications = []
    if MedicationAdministrationRecord:
        try:
            pending_medications = MedicationAdministrationRecord.objects.filter(
                **medication_filters
            ).select_related(
                'encounter', 'encounter__patient__primary_insurance',
                'patient__primary_insurance', 'prescription'
            )[:20]
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

    # Check if user is HOD
    user_is_hod = False
    if request.user.is_authenticated:
        try:
            user_is_hod = is_hod(request.user)
        except:
            pass
    
    # Get flow board data for nurses
    from .models_workflow import PatientFlowStage
    from collections import defaultdict
    
    # Get active encounters (deduplicated)
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT ON (e.patient_id, DATE(COALESCE(e.started_at, e.created))) e.id
                FROM hospital_encounter e
                WHERE e.is_deleted = false AND e.status = 'active'
                ORDER BY e.patient_id, DATE(COALESCE(e.started_at, e.created)), e.id DESC
                LIMIT 50
            """)
            latest_ids = [row[0] for row in cursor.fetchall()]
        
        active_encounters = Encounter.objects.filter(id__in=latest_ids) if latest_ids else Encounter.objects.none()
        active_encounters = active_encounters.select_related('patient__primary_insurance')
    except:
        active_encounters = Encounter.objects.filter(
            status='active', is_deleted=False
        ).select_related('patient__primary_insurance')[:50]
    
    # Get flow stages for active encounters
    flow_stages = PatientFlowStage.objects.filter(
        encounter__in=active_encounters,
        is_deleted=False
    ).select_related('encounter__patient__primary_insurance', 'completed_by__user')
    
    # Organize by stage type for flow board
    queue_by_stage = {
        'vitals': {
            'name': 'Vital Signs',
            'icon': 'heart-pulse',
            'color': '#EF4444',
            'bg': 'rgba(239, 68, 68, 0.1)',
            'patients': []
        },
        'consultation': {
            'name': 'Consultation',
            'icon': 'clipboard2-pulse',
            'color': '#667eea',
            'bg': 'rgba(102, 126, 234, 0.1)',
            'patients': []
        },
        'laboratory': {
            'name': 'Laboratory',
            'icon': 'flask',
            'color': '#06B6D4',
            'bg': 'rgba(6, 182, 212, 0.1)',
            'patients': []
        },
        'imaging': {
            'name': 'Imaging',
            'icon': 'x-ray',
            'color': '#8B5CF6',
            'bg': 'rgba(139, 92, 246, 0.1)',
            'patients': []
        },
        'pharmacy': {
            'name': 'Pharmacy',
            'icon': 'capsule',
            'color': '#10B981',
            'bg': 'rgba(16, 185, 129, 0.1)',
            'patients': []
        },
        'billing': {
            'name': 'Billing',
            'icon': 'receipt',
            'color': '#F59E0B',
            'bg': 'rgba(245, 158, 11, 0.1)',
            'patients': []
        },
    }
    
    # Populate queue data
    for stage in flow_stages.filter(status__in=['pending', 'in_progress']):
        stage_type = stage.stage_type
        if stage_type in queue_by_stage:
            wait_minutes = 0
            if stage.started_at:
                wait_duration = timezone.now() - stage.started_at
                wait_minutes = int(wait_duration.total_seconds() / 60)
            
            queue_by_stage[stage_type]['patients'].append({
                'encounter_id': stage.encounter.pk,
                'patient_name': stage.encounter.patient.full_name,
                'mrn': stage.encounter.patient.mrn,
                'encounter_type': stage.encounter.get_encounter_type_display(),
                'wait_minutes': wait_minutes,
                'staff': stage.completed_by.user.get_full_name() if stage.completed_by and stage.completed_by.user else None,
                'django_patient': stage.encounter.patient,
                'django_encounter': stage.encounter,
            })
    
    # Flow board statistics
    total_flow_patients = active_encounters.count()
    completed_today = Encounter.objects.filter(
        status='completed',
        is_deleted=False,
        ended_at__date=today
    ).count()
    
    # Calculate average wait time
    in_progress_stages = flow_stages.filter(status='in_progress', started_at__isnull=False)
    total_wait = 0
    wait_count = 0
    for stage in in_progress_stages:
        if stage.started_at:
            wait_duration = timezone.now() - stage.started_at
            total_wait += wait_duration.total_seconds() / 60
            wait_count += 1
    avg_wait_time = int(total_wait / wait_count) if wait_count > 0 else 0
    
    # Count delayed patients (waiting > 60 minutes)
    delayed_count = 0
    for stage in in_progress_stages:
        if stage.started_at:
            wait_duration = timezone.now() - stage.started_at
            if wait_duration.total_seconds() / 60 > 60:
                delayed_count += 1
    
    # Get doctor plans/care plans for patients in assigned wards
    doctor_plans = []
    try:
        from .models_advanced import ClinicalNote
        # Get latest clinical notes with plans for ward patients
        if ward_scope_exists:
            plan_encounters = Encounter.objects.filter(
                admission__ward__in=assigned_wards,
                status='active',
                is_deleted=False
            )
        else:
            plan_encounters = Encounter.objects.filter(
                admission__isnull=False,
                status='active',
                is_deleted=False
            )
        
        # Get clinical notes with plans (SOAP notes, consultation notes, progress notes)
        doctor_plans = ClinicalNote.objects.filter(
            encounter__in=plan_encounters,
            plan__isnull=False,
            plan__gt='',
            is_deleted=False
        ).select_related(
            'encounter__patient__primary_insurance',
            'created_by__user'
        ).order_by('-created')[:20]
    except Exception:
        doctor_plans = []
    
    # Get all active admissions for bed management
    active_admissions = []
    if ward_scope_exists:
        active_admissions = Admission.objects.filter(
            ward__in=assigned_wards,
            status='admitted',
            is_deleted=False
        ).select_related('encounter__patient__primary_insurance', 'ward', 'bed')[:50]
    else:
        active_admissions = Admission.objects.filter(
            status='admitted',
            is_deleted=False
        ).select_related('encounter__patient__primary_insurance', 'ward', 'bed')[:50]
    
    # Get recent clinical notes created by nurses (for reference)
    recent_nurse_notes = []
    try:
        from .models_advanced import ClinicalNote
        recent_nurse_notes = ClinicalNote.objects.filter(
            created_by=staff,
            is_deleted=False
        ).select_related(
            'encounter__patient__primary_insurance'
        ).order_by('-created')[:10]
    except Exception:
        pass
    
    # Get all active encounters for patient care (not just ward patients)
    all_active_encounters = Encounter.objects.filter(
        status='active',
        is_deleted=False
    ).select_related(
        'patient__primary_insurance', 'provider__user', 'admission__ward', 'admission__bed'
    )[:100]
    
    # Get bed utilization stats
    bed_stats = {
        'total': bed_status.count(),
        'occupied': bed_status.filter(status='occupied').count(),
        'available': bed_status.filter(status='available').count(),
        'maintenance': bed_status.filter(status='maintenance').count(),
        'utilization_rate': round((bed_status.filter(status='occupied').count() / bed_status.count() * 100) if bed_status.count() > 0 else 0, 1)
    }

    # Get staff shifts for display on dashboard
    from .models_hr import StaffShift
    from datetime import timedelta
    todays_shifts = StaffShift.objects.filter(
        staff=staff,
        shift_date=today,
        is_deleted=False
    ).select_related('location', 'department', 'assigned_by').order_by('start_time')
    
    # Get upcoming shifts (next 7 days)
    upcoming_shifts = StaffShift.objects.filter(
        staff=staff,
        shift_date__gte=today,
        shift_date__lte=today + timedelta(days=7),
        is_deleted=False
    ).select_related('location', 'department', 'assigned_by').order_by('shift_date', 'start_time')
    
    # Get this week's shifts
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    weekly_shifts = StaffShift.objects.filter(
        staff=staff,
        shift_date__gte=week_start,
        shift_date__lte=week_end,
        is_deleted=False
    ).select_related('location', 'department', 'assigned_by').order_by('shift_date', 'start_time')

    context = {
        'staff': staff,
        'assigned_wards': assigned_wards,
        'ward_patients': ward_patients,
        'pending_vitals': pending_vitals,
        'pending_medications': pending_medications,
        'bed_status': bed_status,
        'bed_stats': bed_stats,
        'active_admissions': active_admissions,
        'all_active_encounters': all_active_encounters,
        'recent_nurse_notes': recent_nurse_notes,
        'stats': stats,
        'today': today,
        'performance_snapshot': performance_snapshot,
        'is_hod': user_is_hod,
        # Flow board data
        'queue_by_stage': queue_by_stage,
        'total_flow_patients': total_flow_patients,
        'completed_today': completed_today,
        'avg_wait_time': avg_wait_time,
        'delayed_count': delayed_count,
        # Doctor plans for nurses
        'doctor_plans': doctor_plans,
        # Staff shifts
        'todays_shifts': todays_shifts,
        'upcoming_shifts': upcoming_shifts,
        'weekly_shifts': weekly_shifts,
        'week_start': week_start,
        'week_end': week_end,
    }
    
    return render(request, 'hospital/role_dashboards/nurse_dashboard.html', context)


@login_required
@role_required('midwife')
def midwife_dashboard(request):
    """Midwife's specialized dashboard for maternity care - Midwife-friendly design"""
    staff, error_response = ensure_staff_profile(request, 'Midwife', expected_profession='midwife')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Get midwife's department (Maternity)
    maternity_dept = staff.department if staff and staff.department else None
    
    # Maternity-related encounters - filter by department if available
    maternity_encounters = Encounter.objects.filter(
        is_deleted=False,
        created__gte=month_ago
    )
    if maternity_dept:
        # Filter by provider's department or location's department
        maternity_encounters = maternity_encounters.filter(
            Q(provider__department=maternity_dept) | Q(location__department=maternity_dept)
        )
    maternity_encounters = maternity_encounters.select_related('patient', 'provider', 'location').order_by('-created')[:20]
    
    # Female patients (maternity focus) with recent encounters
    recent_maternity_patients = Patient.objects.filter(
        gender='F',
        encounters__is_deleted=False,
        encounters__created__gte=week_ago
    )
    if maternity_dept:
        # Filter by provider's department or location's department
        recent_maternity_patients = recent_maternity_patients.filter(
            Q(encounters__provider__department=maternity_dept) | Q(encounters__location__department=maternity_dept)
        )
    recent_maternity_patients = recent_maternity_patients.distinct().select_related()[:15]
    
    # Upcoming appointments for maternity care
    Appointment = None
    try:
        from .models import Appointment
    except:
        pass
    
    upcoming_appointments = []
    if Appointment:
        upcoming_appointments = Appointment.objects.filter(
            appointment_date__gte=today,
            status__in=['scheduled', 'confirmed'],
            is_deleted=False
        )
        if maternity_dept:
            upcoming_appointments = upcoming_appointments.filter(department=maternity_dept)
        upcoming_appointments = upcoming_appointments.select_related('patient', 'provider').order_by('appointment_date')[:10]
    
    # Pending vital signs for maternity patients (and all patients for nursing duties)
    pending_vitals = Encounter.objects.filter(
        status='active',
        is_deleted=False
    )
    if maternity_dept:
        # Filter by provider's department or location's department
        pending_vitals = pending_vitals.filter(
            Q(provider__department=maternity_dept) | Q(location__department=maternity_dept)
        )
    pending_vitals = pending_vitals.exclude(
        vitals__recorded_at__date=today
    ).select_related('patient', 'provider', 'location')[:20]
    
    # Nursing features: Ward assignments and bed status (midwives can act as nurses)
    Ward = None
    Bed = None
    MedicationAdministrationRecord = None
    try:
        from .models import Ward, Bed
        from .models_advanced import MedicationAdministrationRecord
    except:
        pass
    
    # Ward assignments - similar to nurse dashboard
    assigned_wards = []
    ward_patients = []
    bed_status = []
    if Ward:
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
        
        if assigned_wards.exists():
            ward_patients = Patient.objects.filter(
                encounters__status='active',
                encounters__is_deleted=False,
                encounters__admission__ward__in=assigned_wards
            ).distinct()[:20]
        
        if Bed:
            bed_status_qs = Bed.objects.filter(is_active=True)
            if assigned_wards.exists():
                bed_status_qs = bed_status_qs.filter(ward__in=assigned_wards)
            bed_status = bed_status_qs.select_related('ward')[:20]
    
    # Pending medications (nursing duty)
    pending_medications = []
    if MedicationAdministrationRecord:
        try:
            medication_filters = {
                'status__in': ['scheduled', 'held'],
                'is_deleted': False,
            }
            if assigned_wards and assigned_wards.exists():
                medication_filters['encounter__admission__ward__in'] = assigned_wards
            else:
                medication_filters['encounter__admission__isnull'] = False
            
            pending_medications = MedicationAdministrationRecord.objects.filter(
                **medication_filters
            ).select_related('encounter', 'encounter__patient', 'prescription')[:20]
        except Exception:
            pass
    
    # Triage data (midwives can access triage)
    from .models_advanced import Triage
    triage_patients = []
    try:
        triage_patients = Triage.objects.filter(
            is_deleted=False,
            encounter__status='active'
        ).select_related(
            'encounter__patient',
            'triaged_by__user',
            'encounter'
        ).order_by('-triage_time')[:10]
    except:
        pass
    
    # Active encounters needing attention
    active_maternity_encounters = Encounter.objects.filter(
        status='active',
        is_deleted=False
    )
    if maternity_dept:
        # Filter by provider's department or location's department
        active_maternity_encounters = active_maternity_encounters.filter(
            Q(provider__department=maternity_dept) | Q(location__department=maternity_dept)
        )
    active_maternity_encounters = active_maternity_encounters.select_related('patient', 'provider', 'location').order_by('-created')[:10]
    
    # Statistics - Midwife-specific
    antenatal_base = Encounter.objects.filter(is_deleted=False)
    postnatal_base = Encounter.objects.filter(is_deleted=False)
    if maternity_dept:
        # Filter by provider's department or location's department
        antenatal_base = antenatal_base.filter(
            Q(provider__department=maternity_dept) | Q(location__department=maternity_dept)
        )
        postnatal_base = postnatal_base.filter(
            Q(provider__department=maternity_dept) | Q(location__department=maternity_dept)
        )
    
    stats = {
        'antenatal_visits_today': antenatal_base.filter(
            created__date=today,
            encounter_type__icontains='antenatal'
        ).count(),
        'postnatal_visits_today': postnatal_base.filter(
            created__date=today,
            encounter_type__icontains='postnatal'
        ).count(),
        'active_maternity_cases': active_maternity_encounters.count(),
        'pending_vitals': pending_vitals.count(),
        'upcoming_appointments': len(upcoming_appointments),
        'total_maternity_patients': recent_maternity_patients.count(),
        # Nursing features stats
        'assigned_wards': len(assigned_wards) if assigned_wards else 0,
        'ward_patients': len(ward_patients) if ward_patients else 0,
        'pending_medications': len(pending_medications) if pending_medications else 0,
        'total_beds': len(bed_status) if bed_status else 0,
        'occupied_beds': len([b for b in bed_status if hasattr(b, 'status') and b.status == 'occupied']) if bed_status else 0,
        'triage_patients': len(triage_patients) if triage_patients else 0,
    }
    
    # Chart Data - Monthly Trends (Last 6 months)
    import json
    from datetime import datetime
    from collections import defaultdict
    
    chart_months = []
    antenatal_data = []
    postnatal_data = []
    
    for i in range(5, -1, -1):  # Last 6 months
        month_date = today - timedelta(days=30 * i)
        month_start = month_date.replace(day=1)
        if i == 0:
            month_end = today
        else:
            next_month = month_start + timedelta(days=32)
            month_end = next_month.replace(day=1) - timedelta(days=1)
        
        month_label = month_start.strftime('%b %Y')
        chart_months.append(month_label)
        
        antenatal_count = antenatal_base.filter(
            created__date__gte=month_start,
            created__date__lte=month_end,
            encounter_type__icontains='antenatal'
        ).count()
        
        postnatal_count = postnatal_base.filter(
            created__date__gte=month_start,
            created__date__lte=month_end,
            encounter_type__icontains='postnatal'
        ).count()
        
        antenatal_data.append(antenatal_count)
        postnatal_data.append(postnatal_count)
    
    # Visit Types Distribution (Last 30 days)
    visit_types_base = Encounter.objects.filter(
        is_deleted=False,
        created__gte=month_ago
    )
    if maternity_dept:
        # Filter by provider's department or location's department
        visit_types_base = visit_types_base.filter(
            Q(provider__department=maternity_dept) | Q(location__department=maternity_dept)
        )
    
    antenatal_count = visit_types_base.filter(encounter_type__icontains='antenatal').count()
    postnatal_count = visit_types_base.filter(encounter_type__icontains='postnatal').count()
    delivery_count = visit_types_base.filter(encounter_type__icontains='delivery').count()
    general_maternity = visit_types_base.exclude(
        encounter_type__icontains='antenatal'
    ).exclude(
        encounter_type__icontains='postnatal'
    ).exclude(
        encounter_type__icontains='delivery'
    ).count()
    
    visit_types_data = {
        'Antenatal': antenatal_count,
        'Postnatal': postnatal_count,
        'Delivery': delivery_count,
        'General Maternity': general_maternity,
    }
    
    # Weekly Trends (Last 4 weeks)
    weekly_labels = []
    weekly_antenatal = []
    weekly_postnatal = []
    
    for i in range(3, -1, -1):  # Last 4 weeks
        week_start = today - timedelta(days=7 * (i + 1))
        week_end = today - timedelta(days=7 * i)
        
        week_label = f"Week {4-i}"
        weekly_labels.append(week_label)
        
        antenatal_week = antenatal_base.filter(
            created__date__gte=week_start,
            created__date__lt=week_end,
            encounter_type__icontains='antenatal'
        ).count()
        
        postnatal_week = postnatal_base.filter(
            created__date__gte=week_start,
            created__date__lt=week_end,
            encounter_type__icontains='postnatal'
        ).count()
        
        weekly_antenatal.append(antenatal_week)
        weekly_postnatal.append(postnatal_week)
    
    performance_snapshot = performance_analytics_service.generate_snapshot(staff) if staff else None
    
    context = {
        'staff': staff,
        'maternity_encounters': maternity_encounters,
        'recent_maternity_patients': recent_maternity_patients,
        'upcoming_appointments': upcoming_appointments,
        'pending_vitals': pending_vitals,
        'active_maternity_encounters': active_maternity_encounters,
        'stats': stats,
        'today': today,
        'week_ago': week_ago,
        'month_ago': month_ago,
        'maternity_dept': maternity_dept,
        'performance_snapshot': performance_snapshot,
        # Chart data (JSON serialized for JavaScript)
        'chart_months': json.dumps(chart_months),
        'antenatal_data': json.dumps(antenatal_data),
        'postnatal_data': json.dumps(postnatal_data),
        'visit_types_data': visit_types_data,  # Keep as dict for template iteration
        'visit_types_data_json': json.dumps(visit_types_data),  # JSON for chart
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_antenatal': json.dumps(weekly_antenatal),
        'weekly_postnatal': json.dumps(weekly_postnatal),
        # Nursing features (midwives can act as nurses)
        'assigned_wards': assigned_wards if assigned_wards else [],
        'ward_patients': ward_patients if ward_patients else [],
        'bed_status': bed_status if bed_status else [],
        'pending_medications': pending_medications if pending_medications else [],
        'triage_patients': triage_patients if triage_patients else [],
    }
    
    return render(request, 'hospital/role_dashboards/midwife_dashboard.html', context)


@login_required
@role_required('midwife')
def antenatal_care(request):
    """Antenatal care page - list of antenatal visits and patients"""
    staff, error_response = ensure_staff_profile(request, 'Midwife', expected_profession='midwife')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    month_ago = today - timedelta(days=30)
    
    # Get midwife's department (Maternity)
    maternity_dept = staff.department if staff and staff.department else None
    
    # Filter antenatal encounters
    antenatal_encounters = Encounter.objects.filter(
        is_deleted=False,
        encounter_type__icontains='antenatal'
    )
    
    if maternity_dept:
        antenatal_encounters = antenatal_encounters.filter(
            Q(provider__department=maternity_dept) | Q(location__department=maternity_dept)
        )
    
    antenatal_encounters = antenatal_encounters.select_related('patient', 'provider', 'location').order_by('-started_at')
    
    # Get unique antenatal patients
    antenatal_patients = Patient.objects.filter(
        gender='F',
        encounters__is_deleted=False,
        encounters__encounter_type__icontains='antenatal'
    )
    
    if maternity_dept:
        antenatal_patients = antenatal_patients.filter(
            Q(encounters__provider__department=maternity_dept) | Q(encounters__location__department=maternity_dept)
        )
    
    antenatal_patients = antenatal_patients.distinct().select_related()
    
    # Statistics
    stats = {
        'total_antenatal_visits': antenatal_encounters.count(),
        'total_antenatal_patients': antenatal_patients.count(),
        'visits_today': antenatal_encounters.filter(started_at__date=today).count(),
        'visits_this_week': antenatal_encounters.filter(started_at__gte=today - timedelta(days=7)).count(),
        'visits_this_month': antenatal_encounters.filter(started_at__gte=month_ago).count(),
    }
    
    context = {
        'staff': staff,
        'encounters': antenatal_encounters[:50],  # Limit to 50 most recent
        'patients': antenatal_patients[:30],  # Limit to 30 patients
        'stats': stats,
        'care_type': 'Antenatal',
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/maternity_care.html', context)


@login_required
@role_required('midwife')
def postnatal_care(request):
    """Postnatal care page - list of postnatal visits and patients"""
    staff, error_response = ensure_staff_profile(request, 'Midwife', expected_profession='midwife')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    month_ago = today - timedelta(days=30)
    
    # Get midwife's department (Maternity)
    maternity_dept = staff.department if staff and staff.department else None
    
    # Filter postnatal encounters
    postnatal_encounters = Encounter.objects.filter(
        is_deleted=False,
        encounter_type__icontains='postnatal'
    )
    
    if maternity_dept:
        postnatal_encounters = postnatal_encounters.filter(
            Q(provider__department=maternity_dept) | Q(location__department=maternity_dept)
        )
    
    postnatal_encounters = postnatal_encounters.select_related('patient', 'provider', 'location').order_by('-started_at')
    
    # Get unique postnatal patients
    postnatal_patients = Patient.objects.filter(
        gender='F',
        encounters__is_deleted=False,
        encounters__encounter_type__icontains='postnatal'
    )
    
    if maternity_dept:
        postnatal_patients = postnatal_patients.filter(
            Q(encounters__provider__department=maternity_dept) | Q(encounters__location__department=maternity_dept)
        )
    
    postnatal_patients = postnatal_patients.distinct().select_related()
    
    # Statistics
    stats = {
        'total_postnatal_visits': postnatal_encounters.count(),
        'total_postnatal_patients': postnatal_patients.count(),
        'visits_today': postnatal_encounters.filter(started_at__date=today).count(),
        'visits_this_week': postnatal_encounters.filter(started_at__gte=today - timedelta(days=7)).count(),
        'visits_this_month': postnatal_encounters.filter(started_at__gte=month_ago).count(),
    }
    
    context = {
        'staff': staff,
        'encounters': postnatal_encounters[:50],  # Limit to 50 most recent
        'patients': postnatal_patients[:30],  # Limit to 30 patients
        'stats': stats,
        'care_type': 'Postnatal',
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/maternity_care.html', context)


@login_required
@role_required('midwife')
def midwife_records(request):
    """Midwife-specific medical records page - filtered for maternity care"""
    staff, error_response = ensure_staff_profile(request, 'Midwife', expected_profession='midwife')
    if error_response:
        return error_response
    
    from django.db.models import Q, Count
    from collections import OrderedDict, Counter
    from .models import MedicalRecord
    
    today = timezone.now().date()
    month_ago = today - timedelta(days=30)
    
    # Get midwife's department (Maternity)
    maternity_dept = staff.department if staff and staff.department else None
    
    # Filter medical records for maternity patients
    records = MedicalRecord.objects.filter(
        is_deleted=False,
        patient__gender='F'  # Focus on female patients
    ).select_related('patient', 'encounter', 'created_by__user')
    
    # Filter by maternity-related encounter types or department
    if maternity_dept:
        records = records.filter(
            Q(encounter__provider__department=maternity_dept) |
            Q(encounter__location__department=maternity_dept) |
            Q(encounter__encounter_type__icontains='antenatal') |
            Q(encounter__encounter_type__icontains='postnatal') |
            Q(encounter__encounter_type__icontains='maternity')
        )
    else:
        # If no department, filter by encounter type
        records = records.filter(
            Q(encounter__encounter_type__icontains='antenatal') |
            Q(encounter__encounter_type__icontains='postnatal') |
            Q(encounter__encounter_type__icontains='maternity')
        )
    
    # Search functionality
    search_query = request.GET.get('q', '').strip()
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
    
    # Filter by care type (antenatal/postnatal)
    care_type_filter = request.GET.get('care_type', '')
    if care_type_filter == 'antenatal':
        records = records.filter(encounter__encounter_type__icontains='antenatal')
    elif care_type_filter == 'postnatal':
        records = records.filter(encounter__encounter_type__icontains='postnatal')
    
    records = records.order_by('-created')
    
    # Group records by patient (folder view)
    patient_map = OrderedDict()
    for record in records[:200]:  # Limit to 200 records for performance
        if not record.patient:
            continue
        pid = record.patient_id
        if pid not in patient_map:
            patient_map[pid] = {
                'patient': record.patient,
                'records': [],
                'record_count': 0,
                'last_created': record.created,
                'antenatal_count': 0,
                'postnatal_count': 0,
            }
        folder = patient_map[pid]
        folder['record_count'] += 1
        if record.created > folder['last_created']:
            folder['last_created'] = record.created
        
        # Count by care type
        if record.encounter and 'antenatal' in record.encounter.encounter_type.lower():
            folder['antenatal_count'] += 1
        elif record.encounter and 'postnatal' in record.encounter.encounter_type.lower():
            folder['postnatal_count'] += 1
        
        folder['records'].append(record)
    
    patient_records = sorted(
        patient_map.values(),
        key=lambda item: item['last_created'],
        reverse=True
    )
    
    # Add service counts for each patient folder
    for folder in patient_records:
        folder['service_counts'] = Counter(r.record_type for r in folder['records']).most_common(3)
    
    # Statistics
    stats = {
        'total_records': records.count(),
        'total_patients': len(patient_records),
        'records_today': records.filter(created__date=today).count(),
        'records_this_week': records.filter(created__gte=today - timedelta(days=7)).count(),
        'records_this_month': records.filter(created__gte=month_ago).count(),
        'antenatal_records': records.filter(encounter__encounter_type__icontains='antenatal').count(),
        'postnatal_records': records.filter(encounter__encounter_type__icontains='postnatal').count(),
    }
    
    context = {
        'staff': staff,
        'patient_records': patient_records,
        'search_query': search_query,
        'type_filter': type_filter,
        'care_type_filter': care_type_filter,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'hospital/role_dashboards/midwife_records.html', context)


@login_required
def lab_technician_dashboard(request):
    """
    Legacy /hms/lab-dashboard/ URL — canonical lab UI is the Laboratory Control Center.
    """
    from django.shortcuts import redirect
    return redirect('hospital:laboratory_dashboard')


@login_required
@role_required('lab_technician')
def lab_team_summary_dashboard(request):
    """
    Lab Team Summary dashboard for URL /hms/dashboard/lab/
    Shows lab staff in the department and today's shifts.
    """
    # Ensure the user has a staff profile (lab role already enforced by decorator)
    staff, error_response = ensure_staff_profile(request, 'Lab Technician')
    if error_response:
        return error_response

    from .models import Staff as StaffModel, Department
    from .models_hr import StaffShift

    # Resolve the laboratory department (use staff.department as primary)
    lab_department = None
    if getattr(staff, 'department', None):
        lab_department = staff.department
    else:
        lab_department = Department.objects.filter(
            is_deleted=False,
            name__icontains='lab'
        ).order_by('name').first()

    # Lab staff list
    lab_staff = StaffModel.objects.filter(
        is_deleted=False,
        is_active=True,
        department=lab_department
    ).select_related('user').order_by('user__last_name', 'user__first_name') if lab_department else []

    # Today's shifts for lab department
    today = timezone.now().date()
    lab_shifts_today = StaffShift.objects.filter(
        is_deleted=False,
        department=lab_department,
        shift_date=today
    ).select_related('staff__user').order_by('start_time') if lab_department else []

    context = {
        'staff_user': staff,
        'lab_department': lab_department,
        'lab_staff': lab_staff,
        'lab_shifts_today': lab_shifts_today,
        'today': today,
    }
    return render(request, 'hospital/role_dashboards/lab_team_summary.html', context)


@login_required
@role_required('pharmacist')
def pharmacist_dashboard(request):
    """Legacy /dashboard/pharmacy/ URL — canonical pharmacy UI is pharmacy_dashboard (world-class)."""
    from django.shortcuts import redirect

    staff, error_response = ensure_staff_profile(request, 'Pharmacist', expected_profession='pharmacist')
    if error_response:
        return error_response
    return redirect('hospital:pharmacy_dashboard')


@login_required
@role_required('radiologist')
def radiologist_dashboard(request):
    """Outstanding Radiologist's specialized dashboard with comprehensive imaging management"""
    staff, error_response = ensure_staff_profile(request, 'Radiologist', expected_profession='radiologist')
    if error_response:
        return error_response
    
    from django.db.models import Count, Q, Avg
    from datetime import timedelta
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Import ImagingStudy model safely
    try:
        from .models_advanced import ImagingStudy, ImagingImage
        ImagingStudy_available = True
    except ImportError:
        ImagingStudy = None
        ImagingImage = None
        ImagingStudy_available = False
    
    # Pending imaging orders - prioritize by priority level
    priority_order = {'stat': 0, 'urgent': 1, 'routine': 2}
    
    # CRITICAL: Deduplicate orders - keep only most recent per patient per order type per day
    # Use DISTINCT ON approach via raw SQL since UUID fields don't support MAX()
    from django.db import connection
    
    # Get deduplicated order IDs using DISTINCT ON (PostgreSQL)
    try:
        with connection.cursor() as cursor:
            # Use DISTINCT ON to get the latest order per patient per order type per day
            # This prevents showing multiple identical orders for the same patient
            sql_query = """
                SELECT DISTINCT ON (p.id, o.order_type, DATE(COALESCE(o.requested_at, o.created))) o.id::text
                FROM hospital_order o
                INNER JOIN hospital_encounter e ON e.id = o.encounter_id
                INNER JOIN hospital_patient p ON p.id = e.patient_id
                WHERE o.order_type = 'imaging'
                  AND o.status = 'pending'
                  AND o.is_deleted = false
                  AND e.is_deleted = false
                  AND e.patient_id IS NOT NULL
                ORDER BY p.id, o.order_type, DATE(COALESCE(o.requested_at, o.created)), o.created DESC, o.id DESC
                LIMIT 50
            """
            cursor.execute(sql_query)
            latest_order_ids = [row[0] for row in cursor.fetchall()]
        
        if not latest_order_ids:
            pending_orders = []
        else:
            # Create fresh queryset from the deduplicated IDs
            pending_orders_qs = Order.objects.filter(
                pk__in=latest_order_ids
            ).select_related(
                'encounter', 'encounter__patient__primary_insurance',
                'requested_by', 'requested_by__user'
            )
            
            # Sort by priority, then by creation time
            pending_orders = sorted(
                list(pending_orders_qs),
                key=lambda x: (priority_order.get(x.priority or 'routine', 2), x.requested_at or x.created),
                reverse=False
            )[:20]
    except Exception as e:
        # Fallback: return original queryset without deduplication
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error deduplicating orders: {str(e)}")
        pending_orders_qs = Order.objects.filter(
            order_type='imaging',
            status='pending',
            is_deleted=False,
            encounter__isnull=False,
            encounter__patient__isnull=False
        ).select_related(
            'encounter', 'encounter__patient__primary_insurance',
            'requested_by', 'requested_by__user'
        ).order_by('-created')
        
        pending_orders = sorted(
            list(pending_orders_qs[:50]),
            key=lambda x: (priority_order.get(x.priority or 'routine', 2), x.requested_at or x.created),
            reverse=False
        )[:20]
    
    # In progress studies
    in_progress_studies = []
    if ImagingStudy_available:
        try:
            in_progress_studies = ImagingStudy.objects.filter(
                status__in=['in_progress', 'quality_check', 'awaiting_report'],
                is_deleted=False,
                patient__isnull=False
            ).select_related(
                'patient__primary_insurance', 'order', 'order__encounter__patient__primary_insurance',
                'technician', 'assigned_radiologist'
            ).order_by('-started_at')[:20]
        except Exception:
            pass
    
    # Studies awaiting report (completed but not reported)
    awaiting_report = []
    if ImagingStudy_available:
        try:
            awaiting_report = ImagingStudy.objects.filter(
                status='awaiting_report',
                is_deleted=False,
                patient__isnull=False
            ).select_related(
                'patient__primary_insurance', 'order', 'order__encounter__patient__primary_insurance', 'technician'
            ).order_by('-performed_at')[:20]
        except Exception:
            pass
    
    # My assigned studies (if radiologist is assigned)
    my_studies = []
    if ImagingStudy_available and staff:
        try:
            my_studies = ImagingStudy.objects.filter(
                assigned_radiologist=staff,
                status__in=['awaiting_report', 'reporting'],
                is_deleted=False,
                patient__isnull=False
            ).select_related(
                'patient__primary_insurance', 'order', 'order__encounter__patient__primary_insurance', 'technician'
            ).order_by('-performed_at')[:20]
        except Exception:
            pass
    
    # Completed studies today
    completed_today = []
    if ImagingStudy_available:
        try:
            completed_today = ImagingStudy.objects.filter(
                status__in=['reported', 'verified'],
                performed_at__date=today,
                is_deleted=False,
                patient__isnull=False
            ).select_related(
                'patient__primary_insurance', 'order', 'order__encounter__patient__primary_insurance',
                'technician', 'report_dictated_by', 'report_verified_by'
            ).order_by('-performed_at')[:20]
        except Exception:
            pass
    
    # Statistics
    stats = {
        'pending_orders': len(pending_orders),
        'in_progress_studies': len(in_progress_studies),
        'awaiting_report': len(awaiting_report),
        'my_studies': len(my_studies),
        'completed_today': len(completed_today) if ImagingStudy_available else 0,
        'total_studies_today': Order.objects.filter(
            order_type='imaging',
            created__date=today,
            is_deleted=False
        ).count(),
        'critical_findings': 0,
        'avg_turnaround_hours': 0,
    }
    
    # Additional statistics
    if ImagingStudy_available:
        try:
            stats['week_completed'] = ImagingStudy.objects.filter(
                status__in=['reported', 'verified'],
                performed_at__date__gte=week_ago,
                is_deleted=False
            ).count()
            
            stats['month_completed'] = ImagingStudy.objects.filter(
                status__in=['reported', 'verified'],
                performed_at__date__gte=month_ago,
                is_deleted=False
            ).count()
            
            # Critical findings count
            stats['critical_findings'] = ImagingStudy.objects.filter(
                has_critical_findings=True,
                performed_at__date__gte=week_ago,
                is_deleted=False
            ).count()
            
            # Average turnaround time
            avg_tat = ImagingStudy.objects.filter(
                turnaround_time_minutes__isnull=False,
                performed_at__date__gte=week_ago,
                is_deleted=False
            ).aggregate(avg=Avg('turnaround_time_minutes'))
            stats['avg_turnaround_hours'] = round((avg_tat['avg'] or 0) / 60, 1) if avg_tat['avg'] else 0
            
            # Modality breakdown
            modality_stats = ImagingStudy.objects.filter(
                performed_at__date__gte=week_ago,
                is_deleted=False
            ).values('modality').annotate(count=Count('id')).order_by('-count')[:5]
            stats['modality_breakdown'] = list(modality_stats)
            
        except Exception:
            stats['week_completed'] = 0
            stats['month_completed'] = 0
            stats['critical_findings'] = 0
            stats['avg_turnaround_hours'] = 0
            stats['modality_breakdown'] = []
    else:
        stats['week_completed'] = 0
        stats['month_completed'] = 0
        stats['critical_findings'] = 0
        stats['avg_turnaround_hours'] = 0
        stats['modality_breakdown'] = []
    
    # Priority breakdown
    priority_stats = {
        'stat': Order.objects.filter(order_type='imaging', status='pending', priority='stat', is_deleted=False).count(),
        'urgent': Order.objects.filter(order_type='imaging', status='pending', priority='urgent', is_deleted=False).count(),
        'routine': Order.objects.filter(order_type='imaging', status='pending', priority='routine', is_deleted=False).count(),
    }
    
    context = {
        'staff': staff,
        'pending_orders': pending_orders,
        'in_progress_studies': in_progress_studies,
        'awaiting_report': awaiting_report,
        'my_studies': my_studies,
        'completed_today': completed_today,
        'stats': stats,
        'priority_stats': priority_stats,
        'today': today,
        'week_ago': week_ago,
        'month_ago': month_ago,
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
    ).select_related('patient__primary_insurance', 'provider').order_by('started_at')
    
    # Pending registrations
    pending_registrations = Patient.objects.filter(
        created__date=today,
        is_deleted=False
    ).select_related('primary_insurance').order_by('-created')[:10]
    
    # Walk-in patients
    walk_in_patients = Encounter.objects.filter(
        encounter_type='outpatient',
        started_at__date=today,
        is_deleted=False
    ).select_related('patient__primary_insurance').order_by('-started_at')[:10]
    
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

"""
Role-Specific Dashboard Views
Each role gets a tailored dashboard showing only relevant features
"""
import logging

from django.db import DatabaseError, connection
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta, date

from .models import Patient, Encounter, Staff, Appointment, Invoice, Bed, Admission, Order
from .models_advanced import LeaveRequest

# Import Queue model - ensure it's always defined to prevent NameError
# CRITICAL: Queue must be defined at module level before any function uses it
Queue = None  # Initialize to None first to ensure it's always defined
try:
    from .models_advanced import Queue
except (ImportError, AttributeError, Exception):
    # If import fails for any reason, keep it as None
    Queue = None
# Initialize optional models to None first to ensure they're always defined
QueueEntry = None
try:
    from .models_queue import QueueEntry
except (ImportError, AttributeError, Exception):
    QueueEntry = None

from .models_hr import Payroll, StaffContract
from .utils_roles import get_user_role, get_role_display_info
from .decorators import role_required
from .services.performance_analytics import performance_analytics_service

# Import optional models with try/except for robustness
CashierSession = None
PaymentRequest = None
try:
    from .models_workflow import CashierSession, PaymentRequest
except (ImportError, AttributeError, Exception):
    CashierSession = None
    PaymentRequest = None

JournalEntry = None
Account = None
PaymentReceipt = None
try:
    from .models_accounting import JournalEntry, Account, PaymentReceipt
except (ImportError, AttributeError, Exception):
    JournalEntry = None
    Account = None
    PaymentReceipt = None


logger = logging.getLogger(__name__)


def _safe_db_call(default, label, fn):
    """
    Execute a callable that hits the database and gracefully handle failures.
    When the database raises an error (e.g., missing table/column on a remote
    environment), we log the incident, rollback the broken transaction and
    return the provided default so dashboards still load.
    """
    if fn is None:
        return default
    try:
        return fn()
    except DatabaseError as exc:
        logger.warning("Dashboard query '%s' failed: %s", label, exc)
        try:
            connection.rollback()
        except Exception:
            # Best-effort rollback; connection might already be clean or closed
            pass
        return default


@login_required
@role_required('accountant', 'senior_account_officer')
def accountant_dashboard(request):
    """Accounting-focused dashboard for accountants - Redirects to comprehensive dashboard"""
    from django.shortcuts import redirect
    return redirect('hospital:accountant_comprehensive_dashboard')
    
    # Financial Statistics
    # Use PaymentReceipt or PaymentRequest for revenue calculation
    total_revenue_today = 0
    total_revenue_month = 0
    
    if PaymentReceipt:
        total_revenue_today = _safe_db_call(
            0,
            'accountant_dashboard.total_revenue_today',
            lambda: PaymentReceipt.objects.filter(
                receipt_date__date=today,
                is_deleted=False
            ).aggregate(total=Sum('amount_paid'))['total'] or 0
        )
        
        total_revenue_month = _safe_db_call(
            0,
            'accountant_dashboard.total_revenue_month',
            lambda: PaymentReceipt.objects.filter(
                receipt_date__gte=this_month_start,
                is_deleted=False
            ).aggregate(total=Sum('amount_paid'))['total'] or 0
        )
    
    outstanding_invoices = Invoice.objects.filter(
        is_deleted=False,
        status__in=['issued', 'partially_paid', 'overdue']
    ).aggregate(
        total=Sum('balance')
    )['total'] or 0
    
    overdue_count = Invoice.objects.filter(
        is_deleted=False,
        status='overdue'
    ).count()
    
    # Recent transactions
    recent_payments = []
    if PaymentReceipt:
        recent_payments = _safe_db_call(
            PaymentReceipt.objects.none(),
            'accountant_dashboard.recent_payments',
            lambda: PaymentReceipt.objects.filter(
                is_deleted=False
            ).select_related('invoice__patient').order_by('-receipt_date')[:10]
        )
    
    # Active cashier sessions
    active_sessions = []
    if CashierSession:
        active_sessions = _safe_db_call(
            CashierSession.objects.none(),
            'accountant_dashboard.active_sessions',
            lambda: CashierSession.objects.filter(
                is_deleted=False,
                closed_at__isnull=True
            ).select_related('cashier__user')
        )
    
    # Pending invoices
    pending_invoices = Invoice.objects.filter(
        is_deleted=False,
        status='issued'
    ).select_related('patient').order_by('-issued_at')[:10]
    
    context = {
        'title': 'Accounting Dashboard',
        'role_info': get_role_display_info(request.user),
        'total_revenue_today': total_revenue_today,
        'total_revenue_month': total_revenue_month,
        'outstanding_invoices': outstanding_invoices,
        'overdue_count': overdue_count,
        'recent_payments': recent_payments,
        'active_sessions': active_sessions,
        'pending_invoices': pending_invoices,
        'today': today,
    }
    
    return render(request, 'hospital/roles/accountant_dashboard.html', context)


@login_required
@role_required('admin')
def admin_dashboard(request):
    """Comprehensive dashboard for administrators - sees everything"""
    # Explicitly block marketing users from accessing admin dashboard
    from .utils_roles import get_user_role
    user_role = get_user_role(request.user)
    if user_role == 'marketing':
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.error(request, "Access denied. Marketing staff cannot access the admin dashboard.")
        return redirect('hospital:marketing_dashboard')
    
    today = timezone.now().date()
    now = timezone.now()  # For time display
    
    # Overall hospital statistics - Include both Django and Legacy patients
    django_patients = Patient.objects.filter(is_deleted=False).count()
    legacy_patients = 0
    try:
        from .models_legacy_patients import LegacyPatient
    except ImportError:
        LegacyPatient = None
    
    if LegacyPatient:
        legacy_patients = _safe_db_call(
            0,
            'admin_dashboard.legacy_patients',
            lambda: LegacyPatient.objects.count()
        )
    total_patients = django_patients + legacy_patients
    active_encounters = Encounter.objects.filter(
        is_deleted=False,
        status='active'
    ).count()
    
    total_staff = Staff.objects.filter(is_active=True, is_deleted=False).count()
    
    # Financial
    total_revenue_today = 0
    total_revenue_month = 0
    this_month_start = date(today.year, today.month, 1)
    if PaymentReceipt:
        total_revenue_today = _safe_db_call(
            0,
            'admin_dashboard.total_revenue_today',
            lambda: PaymentReceipt.objects.filter(
                receipt_date__date=today,
                is_deleted=False
            ).aggregate(total=Sum('amount_paid'))['total'] or 0
        )
        total_revenue_month = _safe_db_call(
            0,
            'admin_dashboard.total_revenue_month',
            lambda: PaymentReceipt.objects.filter(
                receipt_date__gte=this_month_start,
                is_deleted=False
            ).aggregate(total=Sum('amount_paid'))['total'] or 0
        )
    
    outstanding_invoices = Invoice.objects.filter(
        is_deleted=False,
        status__in=['issued', 'partially_paid', 'overdue']
    ).aggregate(total=Sum('balance'))['total'] or 0
    
    # HR Statistics
    staff_on_leave = _safe_db_call(
        0,
        'admin_dashboard.staff_on_leave',
        lambda: LeaveRequest.objects.filter(
            status='approved',
            start_date__lte=today,
            end_date__gte=today,
            is_deleted=False
        ).values('staff').distinct().count()
    )
    
    pending_leaves = _safe_db_call(
        0,
        'admin_dashboard.pending_leaves',
        lambda: LeaveRequest.objects.filter(
            status='pending',
            is_deleted=False
        ).count()
    )
    
    # Clinical
    appointments_today = _safe_db_call(
        0,
        'admin_dashboard.appointments_today',
        lambda: Appointment.objects.filter(
            appointment_date__date=today,
            is_deleted=False
        ).count()
    )
    
    # Procurement Approvals (for Medical Directors and Admins)
    pending_admin_approvals = 0
    pending_accounts_approvals = 0
    recent_procurement_requests = []
    try:
        from .models_procurement import ProcurementRequest
        
        # Check if user can approve procurement (admin approval)
        if request.user.has_perm('hospital.can_approve_procurement_admin') or request.user.is_superuser:
            pending_admin_approvals = ProcurementRequest.objects.filter(
                status='submitted',
                is_deleted=False
            ).count()
            recent_procurement_requests = ProcurementRequest.objects.filter(
                status='submitted',
                is_deleted=False
            ).select_related('requested_by_store', 'requested_by__user').order_by('-created')[:5]
        
        # Check if user can approve accounts
        if request.user.has_perm('hospital.can_approve_procurement_accounts') or request.user.is_superuser:
            pending_accounts_approvals = ProcurementRequest.objects.filter(
                status='admin_approved',
                is_deleted=False
            ).count()
    except Exception:
        pass
    
    # Chart Data - Revenue Trends (Last 30 days)
    revenue_data = []
    revenue_labels = []
    if PaymentReceipt:
        from datetime import datetime
        for i in range(29, -1, -1):
            date_check = today - timedelta(days=i)
            daily_revenue = _safe_db_call(
                0,
                f'admin_dashboard.revenue_day_{i}',
                lambda d=date_check: PaymentReceipt.objects.filter(
                    receipt_date__date=d,
                    is_deleted=False
                ).aggregate(total=Sum('amount_paid'))['total'] or 0
            )
            revenue_data.append(float(daily_revenue))
            revenue_labels.append(date_check.strftime('%m/%d'))
    else:
        # Provide empty arrays if PaymentReceipt is not available
        revenue_data = [0] * 30
        revenue_labels = [(today - timedelta(days=i)).strftime('%m/%d') for i in range(29, -1, -1)]
    
    # Patient Demographics by Gender
    patient_gender_data = []
    patient_gender_labels = []
    try:
        gender_stats = Patient.objects.filter(is_deleted=False).values('gender').annotate(
            count=Count('id')
        )
        for stat in gender_stats:
            patient_gender_labels.append(stat['gender'] or 'Unknown')
            patient_gender_data.append(stat['count'])
    except Exception:
        patient_gender_data = []
        patient_gender_labels = []
    
    # Department Statistics
    department_stats = []
    try:
        from .models import Department
        dept_stats = Department.objects.annotate(
            staff_count=Count('staff', filter=Q(staff__is_active=True, staff__is_deleted=False)),
            patient_count=Count('encounters__patient', filter=Q(encounters__is_deleted=False), distinct=True)
        ).filter(staff_count__gt=0)[:10]
        for dept in dept_stats:
            department_stats.append({
                'name': dept.name,
                'staff_count': dept.staff_count,
                'patient_count': dept.patient_count or 0,
            })
    except Exception:
        pass
    
    # Monthly Revenue Comparison (Last 6 months)
    monthly_revenue_data = []
    monthly_revenue_labels = []
    if PaymentReceipt:
        from calendar import month_abbr
        for i in range(5, -1, -1):
            month_date = today - timedelta(days=30*i)
            month_start = date(month_date.year, month_date.month, 1)
            if month_date.month == 12:
                month_end = date(month_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                month_end = date(month_date.year, month_date.month + 1, 1) - timedelta(days=1)
            
            monthly_revenue = _safe_db_call(
                0,
                f'admin_dashboard.monthly_revenue_{i}',
                lambda ms=month_start, me=month_end: PaymentReceipt.objects.filter(
                    receipt_date__gte=ms,
                    receipt_date__lte=me,
                    is_deleted=False
                ).aggregate(total=Sum('amount_paid'))['total'] or 0
            )
            monthly_revenue_data.append(float(monthly_revenue))
            monthly_revenue_labels.append(f"{month_abbr[month_date.month]} {month_date.year}")
    else:
        # Provide empty arrays if PaymentReceipt is not available
        from calendar import month_abbr
        for i in range(5, -1, -1):
            month_date = today - timedelta(days=30*i)
            monthly_revenue_data.append(0.0)
            monthly_revenue_labels.append(f"{month_abbr[month_date.month]} {month_date.year}")
    
    # Staff by Profession
    staff_profession_data = []
    staff_profession_labels = []
    try:
        profession_stats = Staff.objects.filter(
            is_active=True, is_deleted=False
        ).values('profession').annotate(count=Count('id'))[:10]
        for stat in profession_stats:
            staff_profession_labels.append(stat['profession'] or 'Unknown')
            staff_profession_data.append(stat['count'])
    except Exception:
        staff_profession_data = []
        staff_profession_labels = []
    
    # Bed Occupancy Stats
    bed_stats = {'total': 0, 'occupied': 0, 'available': 0, 'reserved': 0}
    try:
        from .models import Bed
        bed_stats = {
            'total': Bed.objects.filter(is_active=True, is_deleted=False).count(),
            'occupied': Bed.objects.filter(is_active=True, is_deleted=False, status='occupied').count(),
            'available': Bed.objects.filter(is_active=True, is_deleted=False, status='available').count(),
            'reserved': Bed.objects.filter(is_active=True, is_deleted=False, status='reserved').count(),
        }
    except Exception:
        pass
    
    # Recent Activity (Last 10 encounters) - Only include encounters with valid patients
    recent_encounters = Encounter.objects.filter(
        is_deleted=False,
        patient__isnull=False
    ).select_related('patient', 'provider__user').order_by('-started_at')[:10]
    
    # Top Departments by Revenue (if available)
    top_departments = []
    try:
        if PaymentReceipt and hasattr(PaymentReceipt, 'department'):
            dept_revenue = PaymentReceipt.objects.filter(
                receipt_date__gte=this_month_start,
                is_deleted=False
            ).values('department__name').annotate(
                total=Sum('amount_paid')
            ).order_by('-total')[:5]
            for dept in dept_revenue:
                top_departments.append({
                    'name': dept['department__name'] or 'Unknown',
                    'revenue': float(dept['total'] or 0)
                })
    except Exception:
        pass
    
    # Strategic Objectives Metrics
    try:
        from .views_strategic_objectives import calculate_strategic_objectives_metrics
        strategic_objectives = calculate_strategic_objectives_metrics()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error calculating strategic objectives: {e}")
        strategic_objectives = {
            'objectives': {},
            'overall_progress': 0,
            'last_updated': timezone.now(),
        }
    
    payroll_pending_admin_approval = _safe_db_call(
        0,
        'admin_dashboard.payroll_pending_admin_approval',
        lambda: __import__(
            'hospital.models_accounting_advanced',
            fromlist=['AccountingPayroll'],
        ).AccountingPayroll.objects.filter(
            status='pending_approval',
            is_deleted=False,
        ).count(),
    )

    context = {
        'title': 'Administrator Dashboard',
        'role_info': get_role_display_info(request.user),
        'payroll_pending_admin_approval': payroll_pending_admin_approval,
        'total_patients': total_patients,
        'active_encounters': active_encounters,
        'total_staff': total_staff,
        'total_revenue_today': total_revenue_today,
        'total_revenue_month': total_revenue_month,
        'outstanding_invoices': outstanding_invoices,
        'staff_on_leave': staff_on_leave,
        'pending_leaves': pending_leaves,
        'appointments_today': appointments_today,
        'pending_admin_approvals': pending_admin_approvals,
        'pending_accounts_approvals': pending_accounts_approvals,
        'recent_procurement_requests': recent_procurement_requests,
        'revenue_data': revenue_data,
        'revenue_labels': revenue_labels,
        'patient_gender_data': patient_gender_data,
        'patient_gender_labels': patient_gender_labels,
        'department_stats': department_stats,
        'monthly_revenue_data': monthly_revenue_data,
        'monthly_revenue_labels': monthly_revenue_labels,
        'staff_profession_data': staff_profession_data,
        'staff_profession_labels': staff_profession_labels,
        'bed_stats': bed_stats,
        'recent_encounters': recent_encounters,
        'top_departments': top_departments,
        'strategic_objectives': strategic_objectives,
        'today': today,
        'now': timezone.now(),  # Ensure it's always a datetime object
    }
    
    return render(request, 'hospital/roles/admin_dashboard.html', context)


@login_required
@role_required('doctor')
def medical_dashboard(request):
    """Medical-focused dashboard for doctors"""
    today = timezone.now().date()
    
    # Get doctor's staff record
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        staff = None
    
    # My patients
    my_encounters = Encounter.objects.filter(
        provider=staff,
        is_deleted=False,
        status='active'
    ).select_related('patient__primary_insurance')[:10] if staff else []
    
    # Today's appointments
    today_appointments = Appointment.objects.filter(
        provider=staff,
        appointment_date__date=today,
        is_deleted=False
    ).select_related('patient__primary_insurance').order_by('appointment_date') if staff else []
    
    # Pending lab results - only show orders that still have uncompleted lab results
    pending_labs = []
    if staff:
        pending_labs = Order.objects.filter(
            Q(encounter__provider=staff) | Q(requested_by=staff),
            order_type='lab',
            is_deleted=False,
        ).filter(
            lab_results__status__in=['pending', 'in_progress']
        ).select_related(
            'encounter__patient__primary_insurance'
        ).distinct().order_by('-priority', 'requested_at')[:10]
    
    specialist_links = []
    patient_select_url = reverse('hospital:specialist_patient_select')
    
    def add_specialist_link(label, icon, specialty, description):
        specialist_links.append({
            'label': label,
            'icon': icon,
            'url': f"{patient_select_url}?specialty={specialty}",
            'description': description
        })
    
    if staff and hasattr(staff, 'specialist_profile'):
        specialty_name = staff.specialist_profile.specialty.name.lower()
        if any(keyword in specialty_name for keyword in ['dental', 'dentist', 'oral']):
            add_specialist_link('Dental Chart', 'bi-tooth', 'dental', 'Tooth chart & procedures')
        if any(keyword in specialty_name for keyword in ['ophthalm', 'eye', 'vision']):
            add_specialist_link('Eye Chart', 'bi-eye', 'ophthalmology', 'Retina, lens & acuity records')
        if any(keyword in specialty_name for keyword in ['psychiatric', 'psychiatry', 'mental']):
            add_specialist_link('Psychiatric Chart', 'bi-heart-pulse', 'psychiatric', 'Mental health assessments')
        if any(keyword in specialty_name for keyword in ['gynecology', 'gynec', 'obstetric', 'obgyn']):
            add_specialist_link('Gynecology Chart', 'bi-gender-female', 'gynecology', 'OB/GYN examinations')
    
    # Provide quick access to specialist tools for all doctors even if not tagged
    user_role = get_user_role(request.user)
    if user_role == 'doctor' and not specialist_links:
        add_specialist_link('Dental Chart', 'bi-tooth', 'dental', 'Tooth chart & procedures')
        add_specialist_link('Eye Chart', 'bi-eye', 'ophthalmology', 'Eye examinations & charts')
        add_specialist_link('Psychiatric Chart', 'bi-heart-pulse', 'psychiatric', 'Mental health assessments')
        add_specialist_link('Gynecology Chart', 'bi-gender-female', 'gynecology', 'OB/GYN examinations')
    
    # Bed & admission intelligence
    bed_queryset = Bed.objects.filter(is_active=True, is_deleted=False)
    bed_summary = {
        'total': bed_queryset.count(),
        'occupied': bed_queryset.filter(status='occupied').count(),
        'available': bed_queryset.filter(status='available').count(),
        'reserved': bed_queryset.filter(status='reserved').count(),
        'maintenance': bed_queryset.filter(status='maintenance').count(),
    }
    bed_summary['utilization'] = bed_summary['occupied'] + bed_summary['reserved']
    bed_occupancy_pct = 0
    if bed_summary['total']:
        bed_occupancy_pct = round((bed_summary['utilization'] / bed_summary['total']) * 100)
    
    ward_load = bed_queryset.values(
        'ward__name',
        'ward__ward_type'
    ).annotate(
        total=Count('id'),
        occupied=Count('id', filter=Q(status='occupied')),
        available=Count('id', filter=Q(status='available'))
    ).order_by('-occupied')[:5]
    ward_breakdown = []
    for ward in ward_load:
        total = ward['total'] or 0
        occ = ward['occupied'] or 0
        ward_breakdown.append({
            'ward_name': ward['ward__name'],
            'ward_type': ward['ward__ward_type'],
            'total': total,
            'occupied': occ,
            'available': ward['available'] or 0,
            'utilization_pct': round((occ / total) * 100) if total else 0,
        })
    ward_load = ward_breakdown
    
    bed_alerts = bed_queryset.filter(
        status__in=['reserved', 'maintenance']
    ).select_related('ward').order_by('status', 'ward__name')[:6]
    
    recent_admissions = Admission.objects.filter(
        status='admitted',
        is_deleted=False
    ).select_related('encounter__patient__primary_insurance', 'ward', 'bed').order_by('-admit_date')[:6]
    
    rounds_patients = Encounter.objects.filter(
        provider=staff,
        is_deleted=False,
        status='active',
        encounter_type='inpatient'
    ).select_related('patient__primary_insurance', 'location').order_by('started_at')[:6] if staff else []
    
    high_priority_orders = Order.objects.filter(
        encounter__provider=staff,
        status__in=['pending', 'in_progress'],
        priority__in=['urgent', 'stat'],
        is_deleted=False
    ).select_related('encounter__patient__primary_insurance').order_by('-priority', 'requested_at')[:6] if staff else []
    
    queue_entries = []
    queue_stats = {'waiting': 0, 'in_progress': 0, 'completed': 0}
    if Queue and staff:
        base_queue = Queue.objects.filter(
            encounter__provider=staff,
            is_deleted=False
        ).select_related('encounter__patient__primary_insurance', 'department').order_by('priority', 'queue_number')
        queue_entries = base_queue.filter(status__in=['waiting', 'in_progress'])[:8]
        queue_stats = {
            'waiting': base_queue.filter(status='waiting').count(),
            'in_progress': base_queue.filter(status='in_progress').count(),
            'completed': base_queue.filter(status='completed').count(),
        }
    
    # Enhanced Patient Access for Doctors
    # Recent patients seen by this doctor
    recent_patients = []
    if staff:
        recent_patients = Patient.objects.filter(
            encounters__provider=staff,
            encounters__is_deleted=False
        ).distinct().select_related('primary_insurance').order_by('-encounters__started_at')[:12]
    
    # Patient search quick access
    total_patients_accessible = Patient.objects.filter(is_deleted=False).exclude(id__isnull=True).count()
    
    # Recent prescriptions
    recent_prescriptions = []
    if staff:
        try:
            from .models import Prescription
            recent_prescriptions = Prescription.objects.filter(
                order__encounter__provider=staff,
                is_deleted=False
            ).select_related('drug', 'order__encounter__patient').order_by('-created')[:8]
        except:
            pass
    
    # Statistics
    active_patients = my_encounters.count() if staff else 0
    appointments_count = today_appointments.count() if staff else 0
    pending_labs_count = pending_labs.count() if staff else 0
    total_patients_seen = Patient.objects.filter(
        encounters__provider=staff,
        encounters__is_deleted=False
    ).distinct().count() if staff else 0
    
    # Check if user is HOD
    user_is_hod = False
    if request.user.is_authenticated:
        try:
            from .views_hod_scheduling import is_hod
            user_is_hod = is_hod(request.user)
        except:
            pass
    
    context = {
        'title': 'Medical Dashboard',
        'role_info': get_role_display_info(request.user),
        'staff': staff,
        'my_encounters': my_encounters,
        'today_appointments': today_appointments,
        'pending_labs': pending_labs,
        'active_patients': active_patients,
        'appointments_count': appointments_count,
        'pending_labs_count': pending_labs_count,
        'bed_summary': bed_summary,
        'bed_occupancy_pct': bed_occupancy_pct,
        'ward_load': ward_load,
        'bed_alerts': bed_alerts,
        'recent_admissions': recent_admissions,
        'rounds_patients': rounds_patients,
        'high_priority_orders': high_priority_orders,
        'queue_entries': queue_entries,
        'queue_stats': queue_stats,
        'specialist_links': specialist_links,
        'recent_patients': recent_patients,
        'total_patients_accessible': total_patients_accessible,
        'total_patients_seen': total_patients_seen,
        'recent_prescriptions': recent_prescriptions,
        'today': today,
        'is_hod': user_is_hod,
    }
    
    return render(request, 'hospital/roles/medical_dashboard.html', context)


@login_required
@role_required('receptionist')
def reception_dashboard(request):
    """Reception-focused dashboard"""
    today = timezone.now().date()
    staff = getattr(request.user, 'staff', None)
    
    # Today's appointments
    today_appointments = Appointment.objects.filter(
        appointment_date__date=today,
        is_deleted=False
    ).select_related('patient__primary_insurance', 'provider__user', 'department').order_by('appointment_date')
    
    # Recent patient registrations
    recent_patients = Patient.objects.filter(
        is_deleted=False
    ).select_related('primary_insurance').order_by('-created')[:10]
    
    # Upcoming appointments (next 7 days)
    upcoming_appointments = Appointment.objects.filter(
        appointment_date__date__gt=today,
        appointment_date__date__lte=today + timedelta(days=7),
        is_deleted=False
    ).select_related('patient__primary_insurance', 'provider__user').order_by('appointment_date')[:15]
    
    # Statistics
    total_patients = Patient.objects.filter(is_deleted=False).count()
    appointments_count = today_appointments.count()
    
    queue_waiting = []
    if QueueEntry:
        queue_waiting = QueueEntry.objects.filter(
            queue_date=today,
            status__in=['checked_in', 'called'],
            is_deleted=False
        ).select_related('patient__primary_insurance', 'encounter').order_by('priority', 'sequence_number')[:5]
    
    performance_snapshot = None
    if staff and staff.profession == 'receptionist':
        performance_snapshot = performance_analytics_service.generate_snapshot(staff)

    context = {
        'title': 'Reception Dashboard',
        'role_info': get_role_display_info(request.user),
        'today_appointments': today_appointments,
        'recent_patients': recent_patients,
        'upcoming_appointments': upcoming_appointments,
        'total_patients': total_patients,
        'appointments_count': appointments_count,
        'today': today,
        'queue_waiting': queue_waiting,
        'performance_snapshot': performance_snapshot,
    }
    
    return render(request, 'hospital/roles/reception_dashboard.html', context)


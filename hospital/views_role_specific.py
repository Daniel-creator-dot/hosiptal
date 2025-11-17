"""
Role-Specific Dashboard Views
Each role gets a tailored dashboard showing only relevant features
"""
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta, date

from .models import Patient, Encounter, Staff, Appointment, Invoice, Bed, Admission, Order
from .models_advanced import LeaveRequest
try:
    from .models_advanced import Queue
except ImportError:
    Queue = None
from .models_hr import Payroll, StaffContract
from .utils_roles import get_user_role, get_role_display_info
from .decorators import role_required

# Import optional models with try/except for robustness
try:
    from .models_workflow import CashierSession, PaymentRequest
except ImportError:
    CashierSession = None
    PaymentRequest = None

try:
    from .models_accounting import JournalEntry, Account, PaymentReceipt
except ImportError:
    JournalEntry = None
    Account = None
    PaymentReceipt = None


@login_required
@role_required('accountant')
def accountant_dashboard(request):
    """Accounting-focused dashboard for accountants"""
    today = timezone.now().date()
    this_month_start = date(today.year, today.month, 1)
    
    # Financial Statistics
    # Use PaymentReceipt or PaymentRequest for revenue calculation
    total_revenue_today = 0
    total_revenue_month = 0
    
    if PaymentReceipt:
        total_revenue_today = PaymentReceipt.objects.filter(
            receipt_date=today,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or 0
        
        total_revenue_month = PaymentReceipt.objects.filter(
            receipt_date__gte=this_month_start,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or 0
    
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
        recent_payments = PaymentReceipt.objects.filter(
            is_deleted=False
        ).select_related('invoice__patient').order_by('-receipt_date')[:10]
    
    # Active cashier sessions
    active_sessions = []
    if CashierSession:
        active_sessions = CashierSession.objects.filter(
            is_deleted=False,
            closed_at__isnull=True
        ).select_related('cashier__user')
    
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
    today = timezone.now().date()
    
    # Overall hospital statistics - Include both Django and Legacy patients
    django_patients = Patient.objects.filter(is_deleted=False).count()
    try:
        from .models_legacy_patients import LegacyPatient
        legacy_patients = LegacyPatient.objects.count()
    except:
        legacy_patients = 0
    total_patients = django_patients + legacy_patients
    active_encounters = Encounter.objects.filter(
        is_deleted=False,
        status='active'
    ).count()
    
    total_staff = Staff.objects.filter(is_active=True, is_deleted=False).count()
    
    # Financial
    revenue_today = 0
    if PaymentReceipt:
        revenue_today = PaymentReceipt.objects.filter(
            receipt_date=today,
            is_deleted=False
        ).aggregate(total=Sum('amount_paid'))['total'] or 0
    
    outstanding = Invoice.objects.filter(
        is_deleted=False,
        status__in=['issued', 'partially_paid', 'overdue']
    ).aggregate(total=Sum('balance'))['total'] or 0
    
    # HR Statistics
    staff_on_leave = LeaveRequest.objects.filter(
        status='approved',
        start_date__lte=today,
        end_date__gte=today,
        is_deleted=False
    ).values('staff').distinct().count()
    
    pending_leaves = LeaveRequest.objects.filter(
        status='pending',
        is_deleted=False
    ).count()
    
    # Clinical
    appointments_today = Appointment.objects.filter(
        appointment_date__date=today,
        is_deleted=False
    ).count()
    
    context = {
        'title': 'Administrator Dashboard',
        'role_info': get_role_display_info(request.user),
        'total_patients': total_patients,
        'active_encounters': active_encounters,
        'total_staff': total_staff,
        'revenue_today': revenue_today,
        'outstanding': outstanding,
        'staff_on_leave': staff_on_leave,
        'pending_leaves': pending_leaves,
        'appointments_today': appointments_today,
        'today': today,
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
    ).select_related('patient')[:10] if staff else []
    
    # Today's appointments
    today_appointments = Appointment.objects.filter(
        provider=staff,
        appointment_date__date=today,
        is_deleted=False
    ).select_related('patient').order_by('appointment_date') if staff else []
    
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
            'encounter__patient'
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
    
    # Provide quick access to specialist tools for all doctors even if not tagged
    user_role = get_user_role(request.user)
    if user_role == 'doctor' and not specialist_links:
        add_specialist_link('Dental Chart', 'bi-tooth', 'dental', 'Tooth chart & procedures')
        add_specialist_link('Eye Chart', 'bi-eye', 'ophthalmology', 'Eye examinations & charts')
    
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
    ).select_related('encounter__patient', 'ward', 'bed').order_by('-admit_date')[:6]
    
    rounds_patients = Encounter.objects.filter(
        provider=staff,
        is_deleted=False,
        status='active',
        encounter_type='inpatient'
    ).select_related('patient', 'location').order_by('started_at')[:6] if staff else []
    
    high_priority_orders = Order.objects.filter(
        encounter__provider=staff,
        status__in=['pending', 'in_progress'],
        priority__in=['urgent', 'stat'],
        is_deleted=False
    ).select_related('encounter__patient').order_by('-priority', 'requested_at')[:6] if staff else []
    
    queue_entries = []
    queue_stats = {'waiting': 0, 'in_progress': 0, 'completed': 0}
    if Queue and staff:
        base_queue = Queue.objects.filter(
            encounter__provider=staff,
            is_deleted=False
        ).select_related('encounter__patient', 'department').order_by('priority', 'queue_number')
        queue_entries = base_queue.filter(status__in=['waiting', 'in_progress'])[:8]
        queue_stats = {
            'waiting': base_queue.filter(status='waiting').count(),
            'in_progress': base_queue.filter(status='in_progress').count(),
            'completed': base_queue.filter(status='completed').count(),
        }
    
    # Statistics
    active_patients = my_encounters.count() if staff else 0
    appointments_count = today_appointments.count() if staff else 0
    pending_labs_count = pending_labs.count() if staff else 0
    
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
        'today': today,
    }
    
    return render(request, 'hospital/roles/medical_dashboard.html', context)


@login_required
@role_required('receptionist')
def reception_dashboard(request):
    """Reception-focused dashboard"""
    today = timezone.now().date()
    
    # Today's appointments
    today_appointments = Appointment.objects.filter(
        appointment_date__date=today,
        is_deleted=False
    ).select_related('patient', 'provider__user', 'department').order_by('appointment_date')
    
    # Recent patient registrations
    recent_patients = Patient.objects.filter(
        is_deleted=False
    ).order_by('-created')[:10]
    
    # Upcoming appointments (next 7 days)
    upcoming_appointments = Appointment.objects.filter(
        appointment_date__date__gt=today,
        appointment_date__date__lte=today + timedelta(days=7),
        is_deleted=False
    ).select_related('patient', 'provider__user').order_by('appointment_date')[:15]
    
    # Statistics
    total_patients = Patient.objects.filter(is_deleted=False).count()
    appointments_count = today_appointments.count()
    
    context = {
        'title': 'Reception Dashboard',
        'role_info': get_role_display_info(request.user),
        'today_appointments': today_appointments,
        'recent_patients': recent_patients,
        'upcoming_appointments': upcoming_appointments,
        'total_patients': total_patients,
        'appointments_count': appointments_count,
        'today': today,
    }
    
    return render(request, 'hospital/roles/reception_dashboard.html', context)


"""
Role-Specific Dashboard Views
Each role gets a tailored dashboard showing only relevant features
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Q
from datetime import timedelta, date

from .models import Patient, Encounter, Staff, Appointment, Invoice
from .models_advanced import LeaveRequest
from .models_hr import Payroll, StaffContract
from .utils_roles import get_user_role, get_role_display_info

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
    
    # Pending lab results
    from .models import Order
    pending_labs = Order.objects.filter(
        encounter__provider=staff,
        order_type='lab',
        status='pending',
        is_deleted=False
    ).select_related('encounter__patient')[:10] if staff else []
    
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
        'today': today,
    }
    
    return render(request, 'hospital/roles/medical_dashboard.html', context)


@login_required
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


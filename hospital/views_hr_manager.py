"""
HR Manager Dashboard Views
Comprehensive dashboard for HR managers with all key metrics and quick actions
"""
import logging
from datetime import date, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.db import DatabaseError, connection
from decimal import Decimal

from .models import Staff, Department
from .models_hr import (
    PayrollPeriod, Payroll, StaffContract, LeaveBalance,
    PerformanceReview, TrainingRecord, StaffShift
)
from .models_advanced import LeaveRequest, Attendance
try:
    from .models_hr import StaffMedicalChit
except ImportError:
    StaffMedicalChit = None
from .models_hr_enhanced import AttendanceCalendar, StaffEmploymentContract
from .decorators import role_required
from .utils_roles import get_role_display_info

logger = logging.getLogger(__name__)


def _safe_db_call(default, label, fn):
    """Execute a database call and gracefully handle failures"""
    if fn is None:
        return default
    try:
        return fn()
    except DatabaseError as exc:
        logger.warning("HR Manager Dashboard query '%s' failed: %s", label, exc)
        try:
            connection.rollback()
        except Exception:
            pass
        return default
    except Exception as exc:
        logger.warning("HR Manager Dashboard query '%s' failed: %s", label, exc)
        return default


@login_required
@role_required('hr_manager', 'admin')
def hr_manager_dashboard(request):
    """Comprehensive HR Manager Dashboard"""
    today = timezone.now().date()
    this_month_start = date(today.year, today.month, 1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    
    # ========== STAFF STATISTICS ==========
    total_staff = _safe_db_call(
        0,
        'total_staff',
        lambda: Staff.objects.filter(is_active=True, is_deleted=False).count()
    )
    
    staff_by_department = _safe_db_call(
        [],
        'staff_by_department',
        lambda: list(Staff.objects.filter(
            is_active=True,
            is_deleted=False
        ).values('department__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10])
    )
    
    staff_by_profession = _safe_db_call(
        [],
        'staff_by_profession',
        lambda: list(Staff.objects.filter(
            is_active=True,
            is_deleted=False
        ).values('profession').annotate(
            count=Count('id')
        ).order_by('-count'))
    )
    
    # New hires this month
    new_hires_this_month = _safe_db_call(
        0,
        'new_hires_this_month',
        lambda: Staff.objects.filter(
            is_active=True,
            is_deleted=False,
            date_of_joining__gte=this_month_start,
            date_of_joining__lte=today
        ).count()
    )
    
    # Staff on probation (first 90 days)
    probation_cutoff = today - timedelta(days=90)
    staff_on_probation = _safe_db_call(
        [],
        'staff_on_probation',
        lambda: list(Staff.objects.filter(
            is_active=True,
            is_deleted=False,
            date_of_joining__gte=probation_cutoff
        ).select_related('user', 'department').order_by('date_of_joining')[:10])
    )
    
    # ========== LEAVE MANAGEMENT ==========
    # Staff currently on leave
    staff_on_leave = _safe_db_call(
        0,
        'staff_on_leave',
        lambda: LeaveRequest.objects.filter(
            status='approved',
            start_date__lte=today,
            end_date__gte=today,
            is_deleted=False
        ).values('staff').distinct().count()
    )
    
    # Pending leave requests
    pending_leave_requests = _safe_db_call(
        [],
        'pending_leave_requests',
        lambda: list(LeaveRequest.objects.filter(
            status='pending',
            is_deleted=False
        ).select_related('staff__user', 'staff__department').order_by('start_date')[:10])
    )
    
    pending_leaves_count = len(pending_leave_requests)
    
    # Pending Medical Chits
    pending_medical_chits = []
    pending_medical_chits_count = 0
    if StaffMedicalChit:
        pending_medical_chits = _safe_db_call(
            [],
            'pending_medical_chits',
            lambda: list(StaffMedicalChit.objects.filter(
                status='pending',
                is_deleted=False
            ).select_related('staff', 'staff__user', 'staff__department').order_by('-application_date')[:10])
        )
        pending_medical_chits_count = len(pending_medical_chits)
    
    # Leave requests this month
    leave_requests_this_month = _safe_db_call(
        0,
        'leave_requests_this_month',
        lambda: LeaveRequest.objects.filter(
            created__date__gte=this_month_start,
            is_deleted=False
        ).count()
    )
    
    # Leave balance summary
    leave_balance_summary = _safe_db_call(
        {},
        'leave_balance_summary',
        lambda: LeaveBalance.objects.filter(
            is_deleted=False
        ).aggregate(
            total_available=Sum('available_days'),
            total_used=Sum('used_days'),
            total_pending=Sum('pending_days')
        )
    )
    
    # ========== ATTENDANCE ==========
    # Today's attendance
    present_today = _safe_db_call(
        0,
        'present_today',
        lambda: AttendanceCalendar.objects.filter(
            attendance_date=today,
            status='present',
            is_deleted=False
        ).count()
    )
    
    absent_today = _safe_db_call(
        0,
        'absent_today',
        lambda: AttendanceCalendar.objects.filter(
            attendance_date=today,
            status='absent',
            is_deleted=False
        ).count()
    )
    
    late_today = _safe_db_call(
        0,
        'late_today',
        lambda: AttendanceCalendar.objects.filter(
            attendance_date=today,
            status='late',
            is_deleted=False
        ).count()
    )
    
    # Attendance rate this month
    attendance_rate_this_month = 0
    if total_staff > 0:
        total_attendance_days = _safe_db_call(
            0,
            'total_attendance_days',
            lambda: AttendanceCalendar.objects.filter(
                attendance_date__gte=this_month_start,
                attendance_date__lte=today,
                status__in=['present', 'late'],
                is_deleted=False
            ).count()
        )
        expected_days = total_staff * (today.day if today.day > 0 else 1)
        if expected_days > 0:
            attendance_rate_this_month = round((total_attendance_days / expected_days) * 100, 1)
    
    # ========== PAYROLL ==========
    # Current payroll period
    current_period = _safe_db_call(
        None,
        'current_period',
        lambda: PayrollPeriod.objects.filter(is_processed=False).first()
    )
    
    # Total payroll this month
    total_payroll_this_month = _safe_db_call(
        Decimal('0.00'),
        'total_payroll_this_month',
        lambda: Payroll.objects.filter(
            period__start_date__gte=this_month_start,
            is_deleted=False
        ).aggregate(total=Sum('net_pay'))['total'] or Decimal('0.00')
    )
    
    # Last month payroll for comparison
    total_payroll_last_month = _safe_db_call(
        Decimal('0.00'),
        'total_payroll_last_month',
        lambda: Payroll.objects.filter(
            period__start_date__gte=last_month_start,
            period__start_date__lt=this_month_start,
            is_deleted=False
        ).aggregate(total=Sum('net_pay'))['total'] or Decimal('0.00')
    )
    
    # Pending payroll processing
    pending_payroll_count = _safe_db_call(
        0,
        'pending_payroll_count',
        lambda: StaffContract.objects.filter(
            is_active=True,
            is_deleted=False
        ).exclude(
            id__in=Payroll.objects.filter(
                period=current_period,
                is_deleted=False
            ).values_list('staff_id', flat=True)
        ).count() if current_period else 0
    )
    
    # ========== CONTRACTS ==========
    # Active contracts
    active_contracts = _safe_db_call(
        0,
        'active_contracts',
        lambda: StaffContract.objects.filter(
            is_active=True,
            is_deleted=False
        ).count()
    )
    
    # Contracts expiring soon (within 90 days)
    contracts_expiring_soon = _safe_db_call(
        [],
        'contracts_expiring_soon',
        lambda: list(StaffEmploymentContract.objects.filter(
            is_current=True,
            contract__end_date__gte=today,
            contract__end_date__lte=today + timedelta(days=90),
            is_deleted=False
        ).select_related('staff__user', 'contract').order_by('contract__end_date')[:10])
    )
    
    # ========== PERFORMANCE & TRAINING ==========
    # Performance reviews due (no review in last 12 months)
    one_year_ago = today - timedelta(days=365)
    reviews_due = _safe_db_call(
        0,
        'reviews_due',
        lambda: Staff.objects.filter(
            is_active=True,
            is_deleted=False
        ).exclude(
            id__in=PerformanceReview.objects.filter(
                review_date__gte=one_year_ago,
                is_deleted=False
            ).values_list('staff_id', flat=True)
        ).count()
    )
    
    # Upcoming trainings
    upcoming_trainings = _safe_db_call(
        [],
        'upcoming_trainings',
        lambda: list(TrainingRecord.objects.filter(
            start_date__gte=today,
            start_date__lte=today + timedelta(days=30),
            status='scheduled',
            is_deleted=False
        ).select_related('staff__user').order_by('start_date')[:10])
    )
    
    # ========== SPECIAL EVENTS ==========
    # Birthdays this month
    current_month = today.month
    birthdays_this_month = _safe_db_call(
        [],
        'birthdays_this_month',
        lambda: list(Staff.objects.filter(
            is_active=True,
            is_deleted=False,
            date_of_birth__month=current_month
        ).select_related('user', 'department').order_by('date_of_birth__day')[:10])
    )
    
    # Work anniversaries this month
    work_anniversaries = _safe_db_call(
        [],
        'work_anniversaries',
        lambda: list(Staff.objects.filter(
            is_active=True,
            is_deleted=False,
            date_of_joining__month=current_month
        ).exclude(date_of_joining__year=today.year).select_related('user', 'department').order_by('date_of_joining__day')[:10])
    )
    
    # Note: years_of_service is a read-only property on Staff model
    # It automatically calculates based on date_of_joining
    # No need to set it manually - the template can access staff.years_of_service directly
    
    # ========== RECENT ACTIVITIES ==========
    # Recent payrolls
    recent_payrolls = _safe_db_call(
        [],
        'recent_payrolls',
        lambda: list(Payroll.objects.filter(
            is_deleted=False
        ).select_related('staff__user', 'period').order_by('-created')[:5])
    )
    
    # Recent leave approvals
    recent_leave_approvals = _safe_db_call(
        [],
        'recent_leave_approvals',
        lambda: list(LeaveRequest.objects.filter(
            status='approved',
            is_deleted=False
        ).select_related('staff__user').order_by('-created')[:5])
    )
    
    # ========== ALERTS & NOTIFICATIONS ==========
    alerts = []
    
    if pending_medical_chits_count > 0:
        alerts.append({
            'type': 'danger',
            'url': 'hospital:hr_medical_chit_list',
            'message': f'{pending_medical_chits_count} pending medical chit(s) require approval',
        })
    
    if pending_leaves_count > 0:
        alerts.append({
            'type': 'warning',
            'message': f'{pending_leaves_count} pending leave request(s) require attention',
            'url': 'hospital:leave_request_list'
        })
    
    if contracts_expiring_soon:
        alerts.append({
            'type': 'info',
            'message': f'{len(contracts_expiring_soon)} contract(s) expiring within 90 days',
            'url': 'hospital:contracts_dashboard'
        })
    
    if reviews_due > 0:
        alerts.append({
            'type': 'warning',
            'message': f'{reviews_due} staff member(s) due for performance review',
            'url': 'hospital:hr_reports_dashboard'
        })
    
    if pending_payroll_count > 0:
        alerts.append({
            'type': 'danger',
            'message': f'{pending_payroll_count} staff member(s) pending payroll processing',
            'url': 'hospital:process_payroll'
        })
    
    context = {
        'title': 'HR Manager Dashboard',
        'role_info': get_role_display_info(request.user),
        'today': today,
        'this_month_start': this_month_start,
        
        # Staff Statistics
        'total_staff': total_staff,
        'staff_by_department': staff_by_department,
        'staff_by_profession': staff_by_profession,
        'new_hires_this_month': new_hires_this_month,
        'staff_on_probation': staff_on_probation,
        
        # Leave Management
        'staff_on_leave': staff_on_leave,
        'pending_leave_requests': pending_leave_requests,
        'pending_leaves_count': pending_leaves_count,
        'pending_medical_chits': pending_medical_chits,
        'pending_medical_chits_count': pending_medical_chits_count,
        'leave_requests_this_month': leave_requests_this_month,
        'leave_balance_summary': leave_balance_summary,
        
        # Attendance
        'present_today': present_today,
        'absent_today': absent_today,
        'late_today': late_today,
        'attendance_rate_this_month': attendance_rate_this_month,
        
        # Payroll
        'current_period': current_period,
        'total_payroll_this_month': total_payroll_this_month,
        'total_payroll_last_month': total_payroll_last_month,
        'pending_payroll_count': pending_payroll_count,
        
        # Contracts
        'active_contracts': active_contracts,
        'contracts_expiring_soon': contracts_expiring_soon,
        
        # Performance & Training
        'reviews_due': reviews_due,
        'upcoming_trainings': upcoming_trainings,
        
        # Special Events
        'birthdays_this_month': birthdays_this_month,
        'work_anniversaries': work_anniversaries,
        
        # Recent Activities
        'recent_payrolls': recent_payrolls,
        'recent_leave_approvals': recent_leave_approvals,
        
        # Alerts
        'alerts': alerts,
    }
    
    return render(request, 'hospital/hr_manager/dashboard.html', context)



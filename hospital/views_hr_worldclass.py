"""
World-Class HR Management Views with Calendars
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from datetime import date, timedelta, datetime
import calendar as cal

from .models import Staff, Department
from .models_hr import StaffShift, LeaveBalance, Payroll, StaffContract, PerformanceReview, TrainingRecord
from .models_advanced import LeaveRequest, Attendance
from .models_hr_enhanced import AttendanceCalendar, StaffEmploymentContract, PublicHoliday, StaffPerformanceGoal
from .models_contracts import Contract
from .decorators import role_required


@login_required
@role_required('hr_manager', 'hr')
def hr_worldclass_dashboard(request):
    """World-class HR dashboard with comprehensive features"""
    today = timezone.now().date()
    
    # Staff statistics
    total_staff = Staff.objects.filter(is_active=True, is_deleted=False).count()
    
    # Leave statistics - count unique staff currently on leave
    on_leave_today = 0
    try:
        on_leave_today = LeaveRequest.objects.filter(
            status='approved',
            start_date__lte=today,
            end_date__gte=today,
            is_deleted=False
        ).values('staff').distinct().count()
    except Exception as e:
        print(f"Error calculating on_leave_today: {e}")
        on_leave_today = 0
    
    # Contract expiry alerts
    contracts_expiring = 0
    try:
        contracts_expiring = StaffEmploymentContract.objects.filter(
            is_current=True,
            contract__end_date__gte=today,
            contract__end_date__lte=today + timedelta(days=90),
            is_deleted=False
        ).count()
    except:
        pass
    
    # Leave requests
    pending_leaves = 0
    pending_leave_requests = []
    try:
        pending_leave_requests = LeaveRequest.objects.filter(
            status='pending',
            is_deleted=False
        ).select_related('staff__user').order_by('start_date')[:10]
        pending_leaves = pending_leave_requests.count()
    except:
        pass
    
    # Today's attendance
    present_today = 0
    absent_today = 0
    try:
        attendance_today = AttendanceCalendar.objects.filter(
            attendance_date=today,
            is_deleted=False
        )
        
        if attendance_today.exists():
            # Attendance has been marked - use actual data
            present_today = attendance_today.filter(status='present').count()
            absent_today = attendance_today.filter(status='absent').count()
        else:
            # No attendance marked yet - calculate from staff minus on leave
            present_today = max(0, total_staff - on_leave_today)
            absent_today = 0  # Assume all are present unless marked absent
    except Exception as e:
        print(f"Error calculating attendance: {e}")
        # Fallback: assume all staff present minus those on leave
        present_today = max(0, total_staff - on_leave_today)
        absent_today = 0
    
    # Upcoming trainings
    upcoming_trainings = 0
    upcoming_training_list = []
    try:
        upcoming_training_list = TrainingRecord.objects.filter(
            start_date__gte=today,
            start_date__lte=today + timedelta(days=30),
            status='scheduled',
            is_deleted=False
        ).select_related('staff__user').order_by('start_date')[:5]
        upcoming_trainings = upcoming_training_list.count()
    except:
        pass
    
    # Performance reviews due
    reviews_due = 0
    try:
        # Staff who haven't had a review in 12 months
        one_year_ago = today - timedelta(days=365)
        staff_with_recent_reviews = PerformanceReview.objects.filter(
            review_date__gte=one_year_ago,
            is_deleted=False
        ).values_list('staff_id', flat=True).distinct()
        
        reviews_due = Staff.objects.filter(
            is_active=True,
            is_deleted=False
        ).exclude(id__in=staff_with_recent_reviews).count()
    except:
        pass
    
    # ========== NEW FEATURES ==========
    
    # Birthdays this month
    current_month = today.month
    birthdays_this_month = Staff.objects.filter(
        is_active=True,
        is_deleted=False,
        date_of_birth__month=current_month
    ).distinct().order_by('date_of_birth__day')[:10]
    
    # Work anniversaries this month
    work_anniversaries = Staff.objects.filter(
        is_active=True,
        is_deleted=False,
        date_of_joining__month=current_month
    ).exclude(date_of_joining__year=today.year).distinct().order_by('date_of_joining__day')[:10]
    
    # Note: years_of_service is a read-only property on Staff model
    # It automatically calculates based on date_of_joining
    # No need to set it manually - the template can access staff.years_of_service directly
    
    # Probation period tracking (staff within first 90 days)
    probation_cutoff = today - timedelta(days=90)
    staff_on_probation = Staff.objects.filter(
        is_active=True,
        is_deleted=False,
        date_of_joining__gte=probation_cutoff
    ).select_related('user', 'department').distinct().order_by('date_of_joining')
    
    # Calculate probation progress
    for staff in staff_on_probation:
        if staff.date_of_joining:
            days_since_joining = (today - staff.date_of_joining).days
            staff.probation_days_remaining = max(0, 90 - days_since_joining)
            staff.probation_progress = min(100, int((days_since_joining / 90) * 100))
    
    # Document/Certification expiry alerts (next 60 days)
    from .models_hr import StaffDocument
    thirty_days_from_now = today + timedelta(days=30)
    expiring_documents = StaffDocument.objects.filter(
        is_deleted=False,
        is_active=True,
        expiry_date__gte=today,
        expiry_date__lte=today + timedelta(days=60)
    ).select_related('staff__user').order_by('expiry_date')[:10]
    
    # Mark documents as urgent if expiring within 30 days
    for doc in expiring_documents:
        doc.is_urgent = doc.expiry_date <= thirty_days_from_now
    
    # Staff with missing emergency contacts
    missing_emergency_contacts = Staff.objects.filter(
        is_active=True,
        is_deleted=False
    ).filter(
        Q(emergency_contact_name='') | Q(emergency_contact_phone='')
    ).distinct()[:5]
    
    # Recent activities
    recent_leaves = LeaveRequest.objects.filter(
        is_deleted=False
    ).select_related('staff').order_by('-created')[:5]
    
    expiring_staff_contracts = []
    try:
        expiring_staff_contracts = StaffEmploymentContract.objects.filter(
            is_current=True,
            contract__end_date__gte=today,
            contract__end_date__lte=today + timedelta(days=90),
            is_deleted=False
        ).select_related('staff', 'contract').order_by('contract__end_date')[:10]
        
        # Calculate days until expiry
        for contract in expiring_staff_contracts:
            if contract.contract.end_date:
                contract.days_until_expiry = (contract.contract.end_date - today).days
    except:
        pass
    
    context = {
        'title': 'HR Management Dashboard',
        'total_staff': total_staff,
        'on_leave_today': on_leave_today,
        'contracts_expiring': contracts_expiring,
        'pending_leaves': pending_leaves,
        'pending_leave_requests': pending_leave_requests,
        'present_today': present_today,
        'absent_today': absent_today,
        'upcoming_trainings': upcoming_trainings,
        'upcoming_training_list': upcoming_training_list,
        'reviews_due': reviews_due,
        'recent_leaves': recent_leaves,
        'expiring_staff_contracts': expiring_staff_contracts,
        # New features
        'birthdays_this_month': birthdays_this_month,
        'work_anniversaries': work_anniversaries,
        'staff_on_probation': staff_on_probation,
        'expiring_documents': expiring_documents,
        'missing_emergency_contacts': missing_emergency_contacts,
        'today': today,
        'thirty_days_from_now': thirty_days_from_now,
    }
    
    return render(request, 'hospital/hr/worldclass_dashboard.html', context)


@login_required
@role_required('hr_manager', 'hr')
def hr_services_dashboard(request):
    """Focused HR services dashboard for day-to-day operations"""
    today = timezone.now().date()

    def safe_value(default, func, label):
        try:
            return func()
        except Exception as exc:
            print(f"[hr-services] Failed to compute {label}: {exc}")
            return default

    total_staff = safe_value(
        0,
        lambda: Staff.objects.filter(is_active=True, is_deleted=False).count(),
        'total_staff'
    )

    pending_leaves = safe_value(
        0,
        lambda: LeaveRequest.objects.filter(status='pending', is_deleted=False).count(),
        'pending_leaves'
    )

    approved_leaves_this_month = safe_value(
        0,
        lambda: LeaveRequest.objects.filter(
            status='approved',
            is_deleted=False,
            start_date__month=today.month,
            start_date__year=today.year
        ).count(),
        'approved_leaves_this_month'
    )

    payroll_pending = safe_value(
        0,
        lambda: Payroll.objects.filter(payment_status='pending', is_deleted=False).count(),
        'payroll_pending'
    )

    contracts_expiring_60 = safe_value(
        0,
        lambda: StaffEmploymentContract.objects.filter(
            is_current=True,
            is_deleted=False,
            contract__end_date__gte=today,
            contract__end_date__lte=today + timedelta(days=60)
        ).count(),
        'contracts_expiring_60'
    )

    attendance_present = 0
    attendance_absent = 0
    try:
        today_attendance = AttendanceCalendar.objects.filter(
            attendance_date=today,
            is_deleted=False
        )
        if today_attendance.exists():
            attendance_present = today_attendance.filter(status='present').count()
            attendance_absent = today_attendance.filter(status='absent').count()
        else:
            attendance_present = max(0, total_staff - pending_leaves)
            attendance_absent = 0
    except Exception as exc:
        print(f"[hr-services] Attendance snapshot failed: {exc}")
        attendance_present = max(0, total_staff - pending_leaves)

    last_30_days = today - timedelta(days=30)
    new_hires = safe_value(
        [],
        lambda: list(
            Staff.objects.filter(
                is_active=True,
                is_deleted=False,
                date_of_joining__isnull=False,
                date_of_joining__gte=last_30_days
            ).select_related('user', 'department').distinct().order_by('-date_of_joining')[:6]
        ),
        'new_hires'
    )

    pending_leave_requests = safe_value(
        [],
        lambda: list(
            LeaveRequest.objects.filter(
                status='pending',
                is_deleted=False
            ).select_related('staff__user').order_by('start_date')[:6]
        ),
        'pending_leave_requests'
    )

    upcoming_birthdays = safe_value(
        [],
        lambda: list(
            Staff.objects.filter(
                is_active=True,
                is_deleted=False,
                date_of_birth__month=today.month
            ).select_related('user', 'department').distinct().order_by('date_of_birth__day')[:6]
        ),
        'upcoming_birthdays'
    )

    probation_cutoff = today - timedelta(days=90)
    probation_staff = safe_value(
        [],
        lambda: list(
            Staff.objects.filter(
                is_active=True,
                is_deleted=False,
                date_of_joining__isnull=False,
                date_of_joining__gte=probation_cutoff
            ).select_related('user', 'department').distinct().order_by('date_of_joining')[:6]
        ),
        'probation_staff'
    )
    for staff in probation_staff:
        if staff.date_of_joining:
            days_since_joining = (today - staff.date_of_joining).days
            staff.probation_days_elapsed = max(0, days_since_joining)
            staff.probation_days_remaining = max(0, 90 - days_since_joining)
        else:
            staff.probation_days_elapsed = 0
            staff.probation_days_remaining = 0

    try:
        from .models_hr import StaffDocument
        expiring_documents = list(
            StaffDocument.objects.filter(
                is_deleted=False,
                is_active=True,
                expiry_date__gte=today,
                expiry_date__lte=today + timedelta(days=45)
            ).select_related('staff__user').order_by('expiry_date')[:6]
        )
        for doc in expiring_documents:
            if doc.expiry_date:
                doc.days_remaining = (doc.expiry_date - today).days
                doc.is_overdue = doc.expiry_date < today
            else:
                doc.days_remaining = 0
                doc.is_overdue = False
    except Exception as exc:
        print(f"[hr-services] Could not load expiring documents: {exc}")
        expiring_documents = []

    service_cards = [
        {
            'label': 'Active Staff',
            'value': total_staff,
            'accent': '#8b5cf6',
            'icon': 'people-fill'
        },
        {
            'label': 'Pending Leaves',
            'value': pending_leaves,
            'accent': '#f97316',
            'icon': 'calendar2-event'
        },
        {
            'label': 'Pending Payroll',
            'value': payroll_pending,
            'accent': '#10b981',
            'icon': 'cash-stack'
        },
        {
            'label': 'Expiring Contracts (60d)',
            'value': contracts_expiring_60,
            'accent': '#ef4444',
            'icon': 'file-earmark-excel'
        },
        {
            'label': 'Approved Leave (month)',
            'value': approved_leaves_this_month,
            'accent': '#0ea5e9',
            'icon': 'calendar-check'
        },
        {
            'label': 'Present Today',
            'value': attendance_present,
            'accent': '#22c55e',
            'icon': 'person-check'
        },
    ]

    context = {
        'title': 'HR Service Desk',
        'service_cards': service_cards,
        'pending_leave_requests': pending_leave_requests,
        'new_hires': new_hires,
        'upcoming_birthdays': upcoming_birthdays,
        'probation_staff': probation_staff,
        'expiring_documents': expiring_documents,
        'attendance_snapshot': {
            'present': attendance_present,
            'absent': attendance_absent,
        },
        'today': today,
        'leave_totals': {
            'pending': pending_leaves,
            'approved_this_month': approved_leaves_this_month,
        }
    }

    return render(request, 'hospital/hr/services_dashboard.html', context)


@login_required
@role_required('hr_manager', 'hr')
def leave_calendar(request):
    """Calendar view of all leaves"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Get first and last day of month
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    # Get all approved leaves in this month
    leaves = LeaveRequest.objects.filter(
        status='approved',
        start_date__lte=last_day,
        end_date__gte=first_day,
        is_deleted=False
    ).select_related('staff')
    
    # Build calendar data
    calendar_data = []
    current_date = first_day
    
    while current_date <= last_day:
        day_leaves = []
        for leave in leaves:
            if leave.start_date <= current_date <= leave.end_date:
                day_leaves.append({
                    'staff': leave.staff.user.get_full_name(),
                    'type': leave.get_leave_type_display(),
                    'id': leave.id
                })
        
        calendar_data.append({
            'date': current_date,
            'day': current_date.day,
            'weekday': current_date.strftime('%A'),
            'leaves': day_leaves,
            'is_weekend': current_date.weekday() >= 5,
            'is_today': current_date == timezone.now().date()
        })
        
        current_date += timedelta(days=1)
    
    # Navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    context = {
        'title': 'Leave Calendar',
        'year': year,
        'month': month,
        'month_name': cal.month_name[month],
        'calendar_data': calendar_data,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
    }
    
    return render(request, 'hospital/hr/leave_calendar.html', context)


@login_required
@role_required('hr_manager', 'hr')
def shift_calendar(request):
    """Calendar view of all shifts"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    department_filter = request.GET.get('department')
    
    # Get shifts for the month
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    shifts = StaffShift.objects.filter(
        shift_date__gte=first_day,
        shift_date__lte=last_day,
        is_deleted=False
    ).select_related('staff', 'department')
    
    if department_filter:
        shifts = shifts.filter(department_id=department_filter)
    
    # Build calendar
    calendar_data = []
    current_date = first_day
    
    while current_date <= last_day:
        day_shifts = shifts.filter(shift_date=current_date)
        calendar_data.append({
            'date': current_date,
            'day': current_date.day,
            'weekday': current_date.strftime('%a'),
            'shifts': day_shifts,
            'shift_count': day_shifts.count(),
            'is_weekend': current_date.weekday() >= 5,
            'is_today': current_date == timezone.now().date()
        })
        current_date += timedelta(days=1)
    
    departments = Department.objects.filter(is_deleted=False)
    
    context = {
        'title': 'Shift Calendar',
        'year': year,
        'month': month,
        'month_name': cal.month_name[month],
        'calendar_data': calendar_data,
        'departments': departments,
        'department_filter': department_filter,
    }
    
    return render(request, 'hospital/hr/shift_calendar.html', context)


@login_required
@role_required('hr_manager', 'hr')
def attendance_calendar(request):
    """Attendance calendar view"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Get attendance for the month
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    try:
        attendance_records = AttendanceCalendar.objects.filter(
            attendance_date__gte=first_day,
            attendance_date__lte=last_day,
            is_deleted=False
        ).select_related('staff')
    except:
        attendance_records = []
    
    # Calculate statistics
    stats = {
        'present': 0,
        'absent': 0,
        'late': 0,
        'on_leave': 0
    }
    
    try:
        for record in attendance_records:
            if record.status == 'present':
                stats['present'] += 1
            elif record.status == 'absent':
                stats['absent'] += 1
            elif record.status == 'late':
                stats['late'] += 1
            elif record.status == 'on_leave':
                stats['on_leave'] += 1
    except:
        pass
    
    context = {
        'title': 'Attendance Calendar',
        'year': year,
        'month': month,
        'month_name': cal.month_name[month],
        'attendance_records': attendance_records,
        'stats': stats,
        'first_day': first_day,
        'last_day': last_day,
    }
    
    return render(request, 'hospital/hr/attendance_calendar.html', context)


"""
HR/Admin Department-Wise Shift Management Views
Organized by department for better visibility and management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum, Case, When, IntegerField, F
from django.core.paginator import Paginator
from datetime import datetime, timedelta, date

from .models import Staff, Department
from .models_hr import StaffShift, ShiftTemplate
from .models_auto_attendance import StaffAttendance
from .decorators import role_required


def is_hr_or_admin(user):
    """Check if user is HR Manager or Admin"""
    if user.is_superuser:
        return True
    if user.is_staff:
        if user.groups.filter(name__in=['HR Manager', 'Admin']).exists():
            return True
        try:
            if hasattr(user, 'staff') and user.staff.profession in ['hr_manager', 'admin']:
                return True
        except:
            pass
    return False


@login_required
def hr_shifts_by_department(request):
    """
    Department-wise shift overview for HR/Admin
    Shows all departments with their shift statistics and links to detailed views
    """
    if not is_hr_or_admin(request.user):
        messages.warning(request, 'Access denied. Only HR Managers and Administrators can access this page.')
        return redirect('hospital:dashboard')
    
    # Get date range
    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    try:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except:
        selected_date = timezone.now().date()
    
    # Get date range for week view
    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Get all departments
    departments = Department.objects.filter(
        is_deleted=False
    ).order_by('name')
    
    # Get all shifts for the selected date
    shifts_today = StaffShift.objects.filter(
        shift_date=selected_date,
        is_deleted=False
    ).select_related('staff', 'staff__user', 'department')
    
    # Get attendance for the selected date
    attendance_today = StaffAttendance.objects.filter(
        date=selected_date,
        is_deleted=False
    ).select_related('staff', 'staff__user', 'assigned_shift')
    
    # Build department-wise statistics
    department_stats = []
    for dept in departments:
        dept_shifts = shifts_today.filter(department=dept)
        dept_staff = Staff.objects.filter(
            department=dept,
            is_active=True,
            is_deleted=False
        )
        
        # Count shifts
        total_shifts = dept_shifts.count()
        
        # Count attendance
        dept_attendance = attendance_today.filter(staff__department=dept)
        present_count = dept_attendance.filter(status='present').count()
        absent_count = dept_attendance.filter(status='absent').count()
        late_count = dept_attendance.filter(status='late').count()
        
        # Calculate compliance
        compliance_rate = (present_count / total_shifts * 100) if total_shifts > 0 else 0
        
        # Get upcoming shifts (next 7 days)
        upcoming_shifts = StaffShift.objects.filter(
            department=dept,
            shift_date__gt=selected_date,
            shift_date__lte=selected_date + timedelta(days=7),
            is_deleted=False
        ).count()
        
        # Get HOD if exists
        hod = None
        try:
            from .models_hod_simple import HeadOfDepartment
            hod_obj = HeadOfDepartment.objects.filter(
                department=dept,
                is_active=True
            ).select_related('staff', 'staff__user').first()
            if hod_obj:
                hod = hod_obj.staff
        except:
            pass
        
        department_stats.append({
            'department': dept,
            'hod': hod,
            'total_staff': dept_staff.count(),
            'total_shifts': total_shifts,
            'present_count': present_count,
            'absent_count': absent_count,
            'late_count': late_count,
            'compliance_rate': round(compliance_rate, 1),
            'upcoming_shifts': upcoming_shifts,
            'shifts': dept_shifts[:5],  # Preview of shifts
        })
    
    # Sort by total shifts (descending) or department name
    department_stats.sort(key=lambda x: (x['total_shifts'], x['department'].name), reverse=True)
    
    # Overall statistics
    total_shifts_all = shifts_today.count()
    total_present_all = attendance_today.filter(status='present').count()
    total_absent_all = attendance_today.filter(status='absent').count()
    overall_compliance = (total_present_all / total_shifts_all * 100) if total_shifts_all > 0 else 0
    
    context = {
        'title': 'Shifts by Department',
        'selected_date': selected_date,
        'week_start': week_start,
        'week_end': week_end,
        'department_stats': department_stats,
        'total_shifts_all': total_shifts_all,
        'total_present_all': total_present_all,
        'total_absent_all': total_absent_all,
        'overall_compliance': round(overall_compliance, 1),
        'departments': departments,
    }
    
    return render(request, 'hospital/hr/shifts_by_department.html', context)


@login_required
def hr_department_shifts_detail(request, dept_id):
    """
    Detailed shift view for a specific department
    Shows all shifts, attendance, and monitoring for that department
    """
    if not is_hr_or_admin(request.user):
        messages.warning(request, 'Access denied.')
        return redirect('hospital:dashboard')
    
    department = get_object_or_404(Department, id=dept_id, is_deleted=False)
    
    # Get date range
    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    try:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except:
        selected_date = timezone.now().date()
    
    # Get all shifts for this department on the selected date
    shifts = StaffShift.objects.filter(
        department=department,
        shift_date=selected_date,
        is_deleted=False
    ).select_related('staff', 'staff__user', 'assigned_by').order_by('start_time', 'staff__user__first_name')
    
    # Get attendance for this department
    attendance = StaffAttendance.objects.filter(
        staff__department=department,
        date=selected_date,
        is_deleted=False
    ).select_related('staff', 'staff__user', 'assigned_shift')
    
    # Create mapping of staff to attendance
    attendance_map = {att.staff_id: att for att in attendance}
    
    # Build detailed shift data
    shift_data = []
    for shift in shifts:
        att = attendance_map.get(shift.staff_id)
        
        # Determine status
        if att:
            if att.status == 'present':
                status = 'present'
                status_class = 'success'
            elif att.status == 'late':
                status = 'late'
                status_class = 'warning'
            elif att.status == 'on_leave':
                status = 'on_leave'
                status_class = 'info'
            else:
                status = att.status
                status_class = 'secondary'
        else:
            status = 'absent'
            status_class = 'danger'
        
        # Check if late
        is_late = False
        late_minutes = 0
        if att and att.check_in_time and shift.start_time:
            check_in_dt = datetime.combine(selected_date, att.check_in_time)
            shift_start_dt = datetime.combine(selected_date, shift.start_time)
            if check_in_dt > shift_start_dt:
                is_late = True
                late_minutes = int((check_in_dt - shift_start_dt).total_seconds() / 60)
        
        shift_data.append({
            'shift': shift,
            'staff': shift.staff,
            'attendance': att,
            'status': status,
            'status_class': status_class,
            'is_late': is_late,
            'late_minutes': late_minutes,
            'check_in_time': att.check_in_time if att else None,
        })
    
    # Statistics
    total_shifts = shifts.count()
    present_count = sum(1 for item in shift_data if item['status'] == 'present')
    absent_count = sum(1 for item in shift_data if item['status'] == 'absent')
    late_count = sum(1 for item in shift_data if item['is_late'])
    compliance_rate = (present_count / total_shifts * 100) if total_shifts > 0 else 0
    
    # Get department staff
    dept_staff = Staff.objects.filter(
        department=department,
        is_active=True,
        is_deleted=False
    ).select_related('user').order_by('user__first_name', 'user__last_name')
    
    # Get HOD
    hod = None
    try:
        from .models_hod_simple import HeadOfDepartment
        hod_obj = HeadOfDepartment.objects.filter(
            department=department,
            is_active=True
        ).select_related('staff', 'staff__user').first()
        if hod_obj:
            hod = hod_obj.staff
    except:
        pass
    
    # Get upcoming shifts (next 7 days)
    upcoming_shifts = StaffShift.objects.filter(
        department=department,
        shift_date__gt=selected_date,
        shift_date__lte=selected_date + timedelta(days=7),
        is_deleted=False
    ).select_related('staff', 'staff__user').order_by('shift_date', 'start_time')[:20]
    
    context = {
        'title': f'Shifts - {department.name}',
        'department': department,
        'hod': hod,
        'selected_date': selected_date,
        'shift_data': shift_data,
        'total_shifts': total_shifts,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'compliance_rate': round(compliance_rate, 1),
        'dept_staff': dept_staff,
        'upcoming_shifts': upcoming_shifts,
    }
    
    return render(request, 'hospital/hr/department_shifts_detail.html', context)


@login_required
def hr_department_shifts_calendar(request, dept_id):
    """
    Calendar view of shifts for a specific department
    """
    if not is_hr_or_admin(request.user):
        messages.warning(request, 'Access denied.')
        return redirect('hospital:dashboard')
    
    department = get_object_or_404(Department, id=dept_id, is_deleted=False)
    
    # Get month/year
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    import calendar as cal
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    # Get shifts for the month
    shifts = StaffShift.objects.filter(
        department=department,
        shift_date__gte=first_day,
        shift_date__lte=last_day,
        is_deleted=False
    ).select_related('staff', 'staff__user').order_by('shift_date', 'start_time')
    
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
            'is_today': current_date == timezone.now().date(),
        })
        current_date += timedelta(days=1)
    
    # Navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    context = {
        'title': f'Shift Calendar - {department.name}',
        'department': department,
        'year': year,
        'month': month,
        'month_name': cal.month_name[month],
        'calendar_data': calendar_data,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
    }
    
    return render(request, 'hospital/hr/department_shifts_calendar.html', context)






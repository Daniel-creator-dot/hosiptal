"""
Head of Department Shift Monitoring & Attendance Tracking
Comprehensive system for HODs to monitor shifts vs attendance
Shows shortages, absences, and attendance compliance
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum, Case, When, IntegerField, F, Prefetch
from django.http import JsonResponse
from django.core.paginator import Paginator
from datetime import datetime, timedelta, date, time
from decimal import Decimal

from .models import Staff, Department
from .models_hod_simple import HeadOfDepartment
from .models_hr import StaffShift, ShiftTemplate
from .models_auto_attendance import StaffAttendance
from .models_login_tracking import LoginHistory


def is_hod(user):
    """Check if user is a Head of Department"""
    if user.is_superuser:
        return True
    try:
        return hasattr(user, 'staff') and hasattr(user.staff, 'hod_designation') and user.staff.hod_designation.is_active
    except:
        return False


@login_required
def hod_shift_monitoring_dashboard(request):
    """
    Main monitoring dashboard showing shifts vs attendance
    Highlights shortages, absences, and compliance
    """
    # Check if user is HOD
    if not is_hod(request.user):
        messages.warning(request, 'Access denied. Only Department Heads can access this page.')
        return redirect('hospital:dashboard')
    
    # Get HOD's department
    try:
        hod = request.user.staff.hod_designation
        department = hod.department
    except Exception as e:
        messages.error(request, f'Error accessing HOD designation: {str(e)}')
        return redirect('hospital:dashboard')
    
    # Get date range (default to today, allow selection)
    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    try:
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except:
        selected_date = timezone.now().date()
    
    # Get date range for week view
    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Get all shifts for the selected date
    shifts_today = StaffShift.objects.filter(
        department=department,
        shift_date=selected_date,
        is_deleted=False
    ).select_related('staff', 'staff__user').order_by('start_time', 'staff__user__first_name')
    
    # Get attendance records for the selected date
    attendance_today = StaffAttendance.objects.filter(
        staff__department=department,
        date=selected_date,
        is_deleted=False
    ).select_related('staff', 'staff__user', 'assigned_shift')
    
    # Create a mapping of staff to their attendance
    attendance_map = {att.staff_id: att for att in attendance_today}
    
    # Build monitoring data
    monitoring_data = []
    total_shifts = 0
    present_count = 0
    absent_count = 0
    late_count = 0
    no_shift_but_present = 0
    
    for shift in shifts_today:
        total_shifts += 1
        attendance = attendance_map.get(shift.staff_id)
        
        # Determine status
        if attendance:
            if attendance.status == 'present':
                present_count += 1
                status = 'present'
                status_class = 'success'
            elif attendance.status == 'late':
                late_count += 1
                status = 'late'
                status_class = 'warning'
            elif attendance.status == 'on_leave':
                status = 'on_leave'
                status_class = 'info'
            else:
                status = attendance.status
                status_class = 'secondary'
        else:
            absent_count += 1
            status = 'absent'
            status_class = 'danger'
        
        # Check if late (compare check-in time with shift start time)
        is_late = False
        late_minutes = 0
        if attendance and attendance.check_in_time and shift.start_time:
            check_in_dt = datetime.combine(selected_date, attendance.check_in_time)
            shift_start_dt = datetime.combine(selected_date, shift.start_time)
            if check_in_dt > shift_start_dt:
                is_late = True
                late_minutes = int((check_in_dt - shift_start_dt).total_seconds() / 60)
        
        monitoring_data.append({
            'shift': shift,
            'staff': shift.staff,
            'attendance': attendance,
            'status': status,
            'status_class': status_class,
            'is_late': is_late,
            'late_minutes': late_minutes,
            'check_in_time': attendance.check_in_time if attendance else None,
            'shift_start': shift.start_time,
            'shift_end': shift.end_time,
            'shift_type': shift.get_shift_type_display(),
            'location': shift.assigned_location or 'Not specified',
        })
    
    # Find staff who came to work but had no shift assigned
    staff_with_attendance_no_shift = []
    for attendance in attendance_today:
        if attendance.staff_id not in [s.staff_id for s in shifts_today]:
            no_shift_but_present += 1
            staff_with_attendance_no_shift.append({
                'staff': attendance.staff,
                'attendance': attendance,
                'check_in_time': attendance.check_in_time,
            })
    
    # Calculate statistics
    compliance_rate = (present_count / total_shifts * 100) if total_shifts > 0 else 0
    
    # Get department staff count
    dept_staff_count = Staff.objects.filter(
        department=department,
        is_active=True,
        is_deleted=False
    ).count()
    
    # Get upcoming shifts (next 7 days)
    upcoming_shifts = StaffShift.objects.filter(
        department=department,
        shift_date__gt=selected_date,
        shift_date__lte=selected_date + timedelta(days=7),
        is_deleted=False
    ).select_related('staff', 'staff__user').order_by('shift_date', 'start_time')[:20]
    
    context = {
        'hod': hod,
        'department': department,
        'selected_date': selected_date,
        'week_start': week_start,
        'week_end': week_end,
        'monitoring_data': monitoring_data,
        'staff_with_attendance_no_shift': staff_with_attendance_no_shift,
        'total_shifts': total_shifts,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'no_shift_but_present': no_shift_but_present,
        'compliance_rate': round(compliance_rate, 1),
        'dept_staff_count': dept_staff_count,
        'upcoming_shifts': upcoming_shifts,
    }
    
    return render(request, 'hospital/hod/shift_monitoring_dashboard.html', context)


@login_required
def hod_shift_attendance_report(request):
    """
    Detailed report comparing shifts with attendance over a date range
    Shows patterns, trends, and compliance metrics
    """
    if not is_hod(request.user):
        messages.warning(request, 'Access denied.')
        return redirect('hospital:dashboard')
    
    try:
        hod = request.user.staff.hod_designation
        department = hod.department
    except:
        messages.error(request, 'Error accessing HOD designation')
        return redirect('hospital:dashboard')
    
    # Get date range
    start_date = request.GET.get('start_date', (timezone.now().date() - timedelta(days=7)).isoformat())
    end_date = request.GET.get('end_date', timezone.now().date().isoformat())
    
    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except:
        start_date = timezone.now().date() - timedelta(days=7)
        end_date = timezone.now().date()
    
    # Get all shifts in date range
    shifts = StaffShift.objects.filter(
        department=department,
        shift_date__gte=start_date,
        shift_date__lte=end_date,
        is_deleted=False
    ).select_related('staff', 'staff__user').order_by('shift_date', 'start_time')
    
    # Get all attendance in date range
    attendance_records = StaffAttendance.objects.filter(
        staff__department=department,
        date__gte=start_date,
        date__lte=end_date,
        is_deleted=False
    ).select_related('staff', 'staff__user', 'assigned_shift')
    
    # Build comprehensive report
    report_data = []
    staff_stats = {}
    
    for shift in shifts:
        staff_id = shift.staff_id
        if staff_id not in staff_stats:
            staff_stats[staff_id] = {
                'staff': shift.staff,
                'total_shifts': 0,
                'present': 0,
                'absent': 0,
                'late': 0,
                'on_leave': 0,
            }
        
        staff_stats[staff_id]['total_shifts'] += 1
        
        # Find matching attendance
        attendance = attendance_records.filter(
            staff_id=staff_id,
            date=shift.shift_date
        ).first()
        
        if attendance:
            if attendance.status == 'present':
                staff_stats[staff_id]['present'] += 1
            elif attendance.status == 'late':
                staff_stats[staff_id]['late'] += 1
            elif attendance.status == 'on_leave':
                staff_stats[staff_id]['on_leave'] += 1
            else:
                staff_stats[staff_id]['absent'] += 1
        else:
            staff_stats[staff_id]['absent'] += 1
        
        # Add to report data
        report_data.append({
            'date': shift.shift_date,
            'staff': shift.staff,
            'shift': shift,
            'attendance': attendance,
            'status': attendance.status if attendance else 'absent',
        })
    
    # Calculate compliance for each staff
    for staff_id, stats in staff_stats.items():
        total = stats['total_shifts']
        if total > 0:
            stats['compliance_rate'] = round((stats['present'] / total) * 100, 1)
        else:
            stats['compliance_rate'] = 0
    
    # Sort staff by compliance rate
    staff_stats_list = sorted(
        staff_stats.values(),
        key=lambda x: x['compliance_rate'],
        reverse=True
    )
    
    # Daily summary
    daily_summary = {}
    for shift in shifts:
        date_key = shift.shift_date.isoformat()
        if date_key not in daily_summary:
            daily_summary[date_key] = {
                'date': shift.shift_date,
                'total_shifts': 0,
                'present': 0,
                'absent': 0,
                'late': 0,
            }
        
        daily_summary[date_key]['total_shifts'] += 1
        
        attendance = attendance_records.filter(
            staff_id=shift.staff_id,
            date=shift.shift_date
        ).first()
        
        if attendance:
            if attendance.status == 'present':
                daily_summary[date_key]['present'] += 1
            elif attendance.status == 'late':
                daily_summary[date_key]['late'] += 1
            else:
                daily_summary[date_key]['absent'] += 1
        else:
            daily_summary[date_key]['absent'] += 1
    
    context = {
        'hod': hod,
        'department': department,
        'start_date': start_date,
        'end_date': end_date,
        'report_data': report_data,
        'staff_stats': staff_stats_list,
        'daily_summary': sorted(daily_summary.values(), key=lambda x: x['date']),
        'total_shifts': len(shifts),
    }
    
    return render(request, 'hospital/hod/shift_attendance_report.html', context)


@login_required
def hod_create_shift_enhanced(request):
    """
    Enhanced shift creation with bulk assignment and template support
    """
    if not is_hod(request.user):
        messages.warning(request, 'Access denied.')
        return redirect('hospital:dashboard')
    
    try:
        hod = request.user.staff.hod_designation
        department = hod.department
    except:
        messages.error(request, 'Error accessing HOD designation')
        return redirect('hospital:dashboard')
    
    if request.method == 'POST':
        try:
            action = request.POST.get('action', 'single')
            
            if action == 'single':
                # Single shift assignment
                staff_id = request.POST.get('staff')
                shift_date = request.POST.get('shift_date')
                shift_type = request.POST.get('shift_type')
                start_time = request.POST.get('start_time')
                end_time = request.POST.get('end_time')
                assigned_location = request.POST.get('assigned_location', '')
                assigned_duties = request.POST.get('assigned_duties', '')
                
                # Get default times if not provided
                if not start_time or not end_time:
                    shift_times = {
                        'day': ('08:00', '17:00'),
                        'evening': ('14:00', '22:00'),
                        'night': ('22:00', '06:00'),
                        'on_call': ('00:00', '23:59'),
                        'weekend': ('08:00', '17:00'),
                    }
                    start_time, end_time = shift_times.get(shift_type, ('08:00', '17:00'))
                
                shift = StaffShift.objects.create(
                    staff_id=staff_id,
                    department=department,
                    shift_date=shift_date,
                    shift_type=shift_type,
                    start_time=start_time,
                    end_time=end_time,
                    assigned_by=request.user,
                    assigned_location=assigned_location,
                    assigned_duties=assigned_duties,
                    is_confirmed=True,
                    confirmed_at=timezone.now(),
                )
                
                messages.success(request, f'Shift assigned to {shift.staff.user.get_full_name() or shift.staff.user.username}')
            
            elif action == 'bulk':
                # Bulk assignment with day-of-week selection
                staff_ids = request.POST.getlist('staff')
                start_date_str = request.POST.get('start_date')
                end_date_str = request.POST.get('end_date')
                shift_type = request.POST.get('shift_type')
                start_time = request.POST.get('start_time')
                end_time = request.POST.get('end_time')
                assigned_location = request.POST.get('assigned_location', '')
                assigned_duties = request.POST.get('assigned_duties', '')
                days_of_week = request.POST.getlist('days_of_week')  # Selected days (0-6)
                
                # Parse dates
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                
                # Convert days_of_week strings to integers, default to all days if not selected
                if days_of_week:
                    selected_days = [int(day) for day in days_of_week]
                else:
                    # Default to all weekdays (Monday-Friday) if no selection
                    selected_days = [0, 1, 2, 3, 4]
                
                # Generate shifts for each staff for selected days only
                created_count = 0
                skipped_count = 0
                current_date = start_date
                
                while current_date <= end_date:
                    # weekday() returns 0=Monday, 6=Sunday
                    if current_date.weekday() in selected_days:
                        for staff_id in staff_ids:
                            # Skip if shift already exists
                            if not StaffShift.objects.filter(
                                staff_id=staff_id,
                                shift_date=current_date,
                                is_deleted=False
                            ).exists():
                                StaffShift.objects.create(
                                    staff_id=staff_id,
                                    department=department,
                                    shift_date=current_date,
                                    shift_type=shift_type,
                                    start_time=start_time,
                                    end_time=end_time,
                                    assigned_by=request.user,
                                    assigned_location=assigned_location,
                                    assigned_duties=assigned_duties,
                                    is_confirmed=True,
                                    confirmed_at=timezone.now(),
                                )
                                created_count += 1
                            else:
                                skipped_count += 1
                    current_date += timedelta(days=1)
                
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                selected_day_names = [day_names[day] for day in selected_days]
                
                if skipped_count > 0:
                    messages.success(
                        request, 
                        f'✅ {created_count} shift(s) created for selected staff on {", ".join(selected_day_names)}. '
                        f'{skipped_count} shift(s) skipped (already exist).'
                    )
                else:
                    messages.success(
                        request, 
                        f'✅ {created_count} shift(s) created for selected staff on {", ".join(selected_day_names)}.'
                    )
            
            elif action == 'template':
                # Use template with day-of-week selection
                template_id = request.POST.get('template_id')
                staff_ids = request.POST.getlist('staff')
                start_date_str = request.POST.get('start_date')
                end_date_str = request.POST.get('end_date')
                days_of_week = request.POST.getlist('days_of_week')  # Selected days (0-6)
                
                template = get_object_or_404(ShiftTemplate, id=template_id, department=department)
                
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                
                # Convert days_of_week strings to integers, default to all weekdays if not selected
                if days_of_week:
                    selected_days = [int(day) for day in days_of_week]
                else:
                    # Default to all weekdays (Monday-Friday) if no selection
                    selected_days = [0, 1, 2, 3, 4]
                
                created_count = 0
                skipped_count = 0
                current_date = start_date
                
                while current_date <= end_date:
                    # weekday() returns 0=Monday, 6=Sunday
                    if current_date.weekday() in selected_days:
                        for staff_id in staff_ids:
                            if not StaffShift.objects.filter(
                                staff_id=staff_id,
                                shift_date=current_date,
                                is_deleted=False
                            ).exists():
                                StaffShift.objects.create(
                                    staff_id=staff_id,
                                    department=department,
                                    shift_date=current_date,
                                    shift_type=template.shift_type,
                                    start_time=template.start_time,
                                    end_time=template.end_time,
                                    assigned_by=request.user,
                                    is_confirmed=True,
                                    confirmed_at=timezone.now(),
                                )
                                created_count += 1
                            else:
                                skipped_count += 1
                    current_date += timedelta(days=1)
                
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                selected_day_names = [day_names[day] for day in selected_days]
                
                if skipped_count > 0:
                    messages.success(
                        request, 
                        f'✅ {created_count} shift(s) created from template on {", ".join(selected_day_names)}. '
                        f'{skipped_count} shift(s) skipped (already exist).'
                    )
                else:
                    messages.success(
                        request, 
                        f'✅ {created_count} shift(s) created from template on {", ".join(selected_day_names)}.'
                    )
            
            return redirect('hospital:hod_shift_monitoring_dashboard')
        
        except Exception as e:
            messages.error(request, f'Error creating shift: {str(e)}')
    
    # Get department staff
    dept_staff = Staff.objects.filter(
        department=department,
        is_active=True,
        is_deleted=False
    ).select_related('user').order_by('user__first_name', 'user__last_name')
    
    # Get shift templates
    shift_templates = ShiftTemplate.objects.filter(
        department=department,
        is_active=True,
        is_deleted=False
    )
    
    today = timezone.now().date()
    
    context = {
        'hod': hod,
        'department': department,
        'dept_staff': dept_staff,
        'shift_templates': shift_templates,
        'today': today,
    }
    
    return render(request, 'hospital/hod/create_shift_enhanced.html', context)


@login_required
def hod_shortages_alert(request):
    """
    Real-time alert showing current shortages (staff scheduled but not present)
    """
    if not is_hod(request.user):
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    try:
        hod = request.user.staff.hod_designation
        department = hod.department
    except:
        return JsonResponse({'error': 'HOD designation not found'}, status=404)
    
    today = timezone.now().date()
    current_time = timezone.now().time()
    
    # Get shifts that should be active now
    active_shifts = StaffShift.objects.filter(
        department=department,
        shift_date=today,
        is_deleted=False,
        start_time__lte=current_time,
        end_time__gte=current_time,
    ).select_related('staff', 'staff__user')
    
    shortages = []
    for shift in active_shifts:
        # Check if staff is present
        attendance = StaffAttendance.objects.filter(
            staff=shift.staff,
            date=today,
            is_deleted=False
        ).first()
        
        if not attendance or attendance.status != 'present':
            shortages.append({
                'staff_name': shift.staff.user.get_full_name() or shift.staff.user.username,
                'shift_type': shift.get_shift_type_display(),
                'start_time': shift.start_time.strftime('%H:%M'),
                'end_time': shift.end_time.strftime('%H:%M'),
                'location': shift.assigned_location or 'Not specified',
            })
    
    return JsonResponse({
        'shortages': shortages,
        'count': len(shortages),
        'timestamp': timezone.now().isoformat(),
    })


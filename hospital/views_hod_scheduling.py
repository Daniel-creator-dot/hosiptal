"""
Head of Department Scheduling Views
Allow HODs to manage timetables and shifts
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count
from django.http import JsonResponse
from django.utils.dateparse import parse_date
from datetime import datetime, timedelta, date, time

from .models import Staff, Department
from .models_hod_simple import HeadOfDepartment
from .models_hr import StaffShift, ShiftTemplate
from .models_advanced import DutyRoster

SHIFT_TYPE_COLORS = {
    'morning': '#3b82f6',
    'afternoon': '#f59e0b',
    'night': '#6366f1',
    'day': '#10b981',
    'custom': '#0ea5e9',
}


def is_hod(user):
    """Check if user is a Head of Department"""
    if user.is_superuser:
        return True
    try:
        return hasattr(user, 'staff') and hasattr(user.staff, 'hod_designation') and user.staff.hod_designation.is_active
    except:
        return False


@login_required
def hod_scheduling_dashboard(request):
    """
    Main dashboard for HOD scheduling
    Shows timetables, shifts, and staff overview
    """
    # Check if user has staff record
    try:
        staff = request.user.staff
    except:
        messages.error(request, 'No staff profile found. Please contact administrator.')
        return redirect('hospital:dashboard')
    
    # Check if user is HOD
    if not is_hod(request.user):
        messages.warning(request, 'Access denied. Only Department Heads can access this page. Please contact your administrator to be designated as HOD.')
        return redirect('hospital:dashboard')
    
    # Get HOD's department
    try:
        hod = request.user.staff.hod_designation
        department = hod.department
    except Exception as e:
        messages.error(request, f'Error accessing HOD designation: {str(e)}')
        return redirect('hospital:dashboard')
    
    # Get department staff
    dept_staff = Staff.objects.filter(
        department=department,
        is_active=True,
        is_deleted=False
    )
    
    # Get this week's shifts
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    this_week_shifts = StaffShift.objects.filter(
        department=department,
        shift_date__gte=week_start,
        shift_date__lte=week_end,
        is_deleted=False
    ).select_related('staff').order_by('shift_date', 'start_time')
    
    # Get shift templates
    shift_templates = ShiftTemplate.objects.filter(
        department=department,
        is_active=True,
        is_deleted=False
    )
    
    context = {
        'hod': hod,
        'department': department,
        'dept_staff': dept_staff,
        'staff_count': dept_staff.count(),
        'this_week_shifts': this_week_shifts,
        'shifts_this_week': this_week_shifts.count(),
        'shift_templates': shift_templates,
        'timetable_count': 0,
        'week_start': week_start,
        'week_end': week_end,
        'active_timetables': [],
    }
    
    return render(request, 'hospital/hod/scheduling_dashboard.html', context)


@login_required
def hod_create_timetable_simple(request):
    """
    Create timetable/schedule for department staff
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
    
    # Get department staff
    dept_staff = Staff.objects.filter(
        department=department,
        is_active=True,
        is_deleted=False
    ).select_related('user')
    
    # Get shift templates
    shift_templates = ShiftTemplate.objects.filter(
        department=department,
        is_active=True,
        is_deleted=False
    )
    
    context = {
        'hod': hod,
        'department': department,
        'dept_staff': dept_staff,
        'shift_templates': shift_templates,
    }
    
    return render(request, 'hospital/hod/create_timetable.html', context)


@login_required
def hod_create_shift(request):
    """
    Create new shift assignment
    """
    if not is_hod(request.user):
        messages.error(request, 'Access denied.')
        return redirect('hospital:dashboard')
    
    hod = request.user.staff.hod_designation
    department = hod.department
    
    if request.method == 'POST':
        try:
            staff_id = request.POST.get('staff')
            multi_day_mode = request.POST.get('multi_day_mode') == 'on'
            
            # Get default times based on shift type
            shift_type = request.POST.get('shift_type')
            shift_times = {
                'morning': ('06:00', '14:00'),
                'afternoon': ('14:00', '22:00'),
                'night': ('22:00', '06:00'),
                'day': ('08:00', '17:00'),
                'custom': (request.POST.get('start_time'), request.POST.get('end_time')),
            }
            
            start_time, end_time = shift_times.get(shift_type, ('08:00', '17:00'))
            
            # Check if multi-day mode (recurring shifts)
            if multi_day_mode:
                from datetime import datetime, timedelta
                
                start_date_str = request.POST.get('start_date')
                end_date_str = request.POST.get('end_date')
                days_of_week = request.POST.getlist('days_of_week')  # List of selected days (0-6)
                
                if not start_date_str or not end_date_str:
                    messages.error(request, 'Start date and end date are required for recurring shifts.')
                    return redirect('hospital:hod_create_shift')
                
                if not days_of_week:
                    messages.error(request, 'Please select at least one day of the week.')
                    return redirect('hospital:hod_create_shift')
                
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                
                if start_date > end_date:
                    messages.error(request, 'Start date must be before or equal to end date.')
                    return redirect('hospital:hod_create_shift')
                
                # Convert days_of_week strings to integers
                selected_days = [int(day) for day in days_of_week]
                
                # Create shifts for each selected day in the date range
                created_count = 0
                current_date = start_date
                staff = Staff.objects.get(id=staff_id)
                
                while current_date <= end_date:
                    # weekday() returns 0=Monday, 6=Sunday
                    if current_date.weekday() in selected_days:
                        # Check if shift already exists for this date
                        existing = StaffShift.objects.filter(
                            staff_id=staff_id,
                            shift_date=current_date,
                            is_deleted=False
                        ).first()
                        
                        if not existing:
                            StaffShift.objects.create(
                                staff=staff,
                                department=department,
                                shift_date=current_date,
                                shift_type=shift_type,
                                start_time=start_time,
                                end_time=end_time,
                                assigned_by=request.user,
                                assigned_location=request.POST.get('location', ''),
                                assigned_duties=request.POST.get('duties', ''),
                            )
                            created_count += 1
                    
                    current_date += timedelta(days=1)
                
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                selected_day_names = [day_names[day] for day in selected_days]
                
                messages.success(
                    request, 
                    f'✅ {created_count} shift(s) created for {staff.user.get_full_name() or staff.user.username} '
                    f'on {", ".join(selected_day_names)} from {start_date_str} to {end_date_str}'
                )
            else:
                # Single shift creation (original behavior)
                shift_date = request.POST.get('shift_date')
                
                # Check if shift already exists
                existing = StaffShift.objects.filter(
                    staff_id=staff_id,
                    shift_date=shift_date,
                    is_deleted=False
                ).first()
                
                if existing:
                    messages.warning(request, f'Shift already exists for {shift_date}. Please edit the existing shift or choose a different date.')
                    return redirect('hospital:hod_create_shift')
                
                # Create shift
                shift = StaffShift.objects.create(
                    staff_id=staff_id,
                    department=department,
                    shift_date=shift_date,
                    shift_type=shift_type,
                    start_time=start_time,
                    end_time=end_time,
                    assigned_by=request.user,
                    assigned_location=request.POST.get('location', ''),
                    assigned_duties=request.POST.get('duties', ''),
                )
                
                messages.success(request, f'Shift assigned to {shift.staff.user.get_full_name() or shift.staff.user.username} for {shift_date}')
            
            return redirect('hospital:hod_scheduling_dashboard')
        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating shift: {e}", exc_info=True)
            messages.error(request, f'Error creating shift: {str(e)}')
    
    # Get department staff
    dept_staff = Staff.objects.filter(
        department=department,
        is_active=True,
        is_deleted=False
    )
    
    context = {
        'hod': hod,
        'department': department,
        'dept_staff': dept_staff,
    }
    
    return render(request, 'hospital/hod/create_shift.html', context)


@login_required
def hod_bulk_assign_shifts(request):
    """
    Bulk assign shifts using a template
    """
    if not is_hod(request.user):
        messages.error(request, 'Access denied.')
        return redirect('hospital:dashboard')
    
    hod = request.user.staff.hod_designation
    department = hod.department
    
    if request.method == 'POST':
        try:
            template_id = request.POST.get('template')
            staff_ids = request.POST.getlist('staff')
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
            
            template = ShiftTemplate.objects.get(id=template_id)
            
            total_created = 0
            for staff_id in staff_ids:
                staff = Staff.objects.get(id=staff_id)
                shifts = template.apply_to_staff(staff, start_date, end_date)
                total_created += len(shifts)
            
            messages.success(request, f'{total_created} shifts created for {len(staff_ids)} staff members')
            return redirect('hospital:hod_scheduling_dashboard')
        
        except Exception as e:
            messages.error(request, f'Error creating shifts: {e}')
    
    # Get templates and staff
    templates = ShiftTemplate.objects.filter(is_active=True)
    dept_staff = Staff.objects.filter(department=department, is_active=True, is_deleted=False)
    
    context = {
        'hod': hod,
        'department': department,
        'templates': templates,
        'dept_staff': dept_staff,
    }
    
    return render(request, 'hospital/hod/bulk_assign_shifts.html', context)


@login_required
def hod_upload_roster(request):
    """
    Upload monthly duty roster file
    """
    if not is_hod(request.user):
        messages.error(request, 'Access denied.')
        return redirect('hospital:dashboard')
    
    hod = request.user.staff.hod_designation
    department = hod.department
    
    if request.method == 'POST':
        try:
            month = int(request.POST.get('month'))
            year = int(request.POST.get('year'))
            roster_file = request.FILES.get('roster_file')
            
            # Note: DutyRoster model needs month, year, created_by, roster_file, and is_published fields
            # For now, just save the notes without using fields that don't exist
            # TODO: Create a separate MonthlyRoster model or update DutyRoster model
            
            # Temporary fix - this section needs model updates
            messages.warning(request, 'Roster upload feature requires model updates. Please contact administrator.')
            return redirect('hospital:hod_scheduling_dashboard')
            
            # roster, created = DutyRoster.objects.update_or_create(
            #     department=department,
            #     month=month,
            #     year=year,
            #     defaults={
            #         'created_by': request.user,
            #         'roster_file': roster_file,
            #         'notes': request.POST.get('notes', ''),
            #         'is_published': request.POST.get('publish') == 'on',
            #     }
            # )
            # 
            # if created:
            #     messages.success(request, f'Roster uploaded for {roster.get_month_name()} {year}')
            # else:
            #     messages.success(request, f'Roster updated for {roster.get_month_name()} {year}')
            
            return redirect('hospital:hod_scheduling_dashboard')
        
        except Exception as e:
            messages.error(request, f'Error uploading roster: {e}')
    
    context = {
        'hod': hod,
        'department': department,
    }
    
    return render(request, 'hospital/hod/upload_roster.html', context)


@login_required
def staff_dashboard_with_schedule(request):
    """
    Enhanced staff dashboard showing their timetable and shifts
    """
    if not hasattr(request.user, 'staff'):
        messages.error(request, 'Staff profile not found')
        return redirect('hospital:dashboard')
    
    staff = request.user.staff
    
    # Get today's shifts
    today = timezone.now().date()
    todays_shifts = StaffShift.objects.filter(
        staff=staff,
        shift_date=today,
        is_deleted=False
    ).order_by('start_time')
    
    # Get this week's shifts
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    weekly_shifts = StaffShift.objects.filter(
        staff=staff,
        shift_date__gte=week_start,
        shift_date__lte=week_end,
        is_deleted=False
    ).order_by('shift_date', 'start_time')
    
    # Timetable from shifts
    todays_timetable = []
    
    # Get current month's roster
    current_month = today.month
    current_year = today.year
    
    roster = DutyRoster.objects.filter(
        department=staff.department,
        shift_date__month=current_month,
        shift_date__year=current_year,
        is_deleted=False
    ).first()
    
    context = {
        'staff': staff,
        'todays_shifts': todays_shifts,
        'weekly_shifts': weekly_shifts,
        'todays_timetable': todays_timetable,
        'roster': roster,
        'today': today,
        'week_start': week_start,
        'week_end': week_end,
    }
    
    return render(request, 'hospital/staff/dashboard_schedule.html', context)


@login_required
def hod_schedule_events(request):
    """
    Return JSON events for the HOD scheduling calendar (shifts, optionally timetables)
    """
    if not is_hod(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        hod = request.user.staff.hod_designation
        department = hod.department
    except Exception:
        return JsonResponse([], safe=False)
    
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')
    staff_id = request.GET.get('staff')
    
    start_date = parse_date(start_str) if start_str else None
    end_date = parse_date(end_str) if end_str else None
    
    # If parsing fails, default to current month
    today = timezone.now().date()
    if not start_date:
        start_date = today.replace(day=1)
    if not end_date:
        # extend to end of month
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)
    
    shifts = StaffShift.objects.filter(
        department=department,
        shift_date__gte=start_date,
        shift_date__lte=end_date,
        is_deleted=False
    ).select_related('staff__user')
    
    if staff_id:
        shifts = shifts.filter(staff_id=staff_id)
    
    events = []
    for shift in shifts:
        start_time = shift.start_time or time(8, 0)
        end_time = shift.end_time or (datetime.combine(date.today(), start_time) + timedelta(hours=8)).time()
        
        start_dt = datetime.combine(shift.shift_date, start_time)
        end_dt = datetime.combine(shift.shift_date, end_time)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        
        staff_name = shift.staff.user.get_full_name() or shift.staff.user.username
        shift_label = getattr(shift, 'get_shift_type_display', lambda: shift.shift_type)()
        color = SHIFT_TYPE_COLORS.get(shift.shift_type, '#6366f1')
        
        events.append({
            'id': str(shift.id),
            'title': f"{staff_name} • {shift_label}",
            'start': start_dt.isoformat(),
            'end': end_dt.isoformat(),
            'backgroundColor': color,
            'borderColor': color,
            'textColor': '#ffffff',
            'extendedProps': {
                'staff': staff_name,
                'shiftType': shift_label,
                'location': shift.assigned_location or '',
                'duties': shift.assigned_duties or '',
            }
        })
    
    return JsonResponse(events, safe=False)


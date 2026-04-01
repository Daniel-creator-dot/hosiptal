"""
Staff Dashboard Views
Leave countdown, activities calendar, and notifications
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
import calendar as cal

from .models import Staff
from .models_hr_activities import StaffActivity, LeaveBalanceAlert, StaffLeaveCounter
from .models_advanced import LeaveRequest
from .models_hr import StaffShift


@login_required
def staff_dashboard(request):
    """
    Staff personal dashboard with:
    - Leave balance countdown
    - Upcoming activities calendar
    - Alerts and notifications
    """
    # Check if user is IT staff - redirect to IT Operations dashboard
    from .utils_roles import get_user_role
    user_role = get_user_role(request.user)
    if user_role in ['it', 'it_staff']:
        from django.shortcuts import redirect
        return redirect('hospital:it_operations_dashboard')

    # Lab staff: personal HR page is not their work queue — send them to Laboratory Control Center
    if user_role == 'lab_technician':
        from django.shortcuts import redirect
        return redirect('hospital:laboratory_dashboard')
    
    # Get staff record for current user
    try:
        staff = Staff.objects.select_related('user', 'department').get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        # User is not a staff member
        return render(request, 'hospital/staff/not_staff.html')
    
    today = timezone.now().date()
    
    # Get or create leave counter
    leave_counter, created = StaffLeaveCounter.objects.get_or_create(
        staff=staff,
        defaults={
            'days_until_next_leave': 0,
        }
    )
    
    # Update leave counter with next approved leave
    from .models_advanced import LeaveRequest
    next_leave = LeaveRequest.objects.filter(
        staff=staff,
        status='approved',
        start_date__gt=today,
        is_deleted=False
    ).order_by('start_date').first()
    
    if next_leave:
        leave_counter.next_leave_date = next_leave.start_date
        leave_counter.next_leave_type = next_leave.get_leave_type_display()
        leave_counter.days_until_next_leave = (next_leave.start_date - today).days
        leave_counter.save()
    
    # Get upcoming activities (next 30 days) - personal activities
    upcoming_activities = StaffActivity.objects.filter(
        staff=staff,
        activity_date__gte=today,
        activity_date__lte=today + timedelta(days=30),
        is_deleted=False
    ).order_by('activity_date', 'activity_time')[:10]
    
    # Get today's activities
    today_activities = StaffActivity.objects.filter(
        staff=staff,
        activity_date=today,
        is_deleted=False
    ).order_by('activity_time')
    
    # Get unacknowledged leave balance alerts
    leave_alerts = LeaveBalanceAlert.objects.filter(
        staff=staff,
        is_acknowledged=False,
        is_deleted=False
    ).order_by('-created')[:5]
    
    # Get today's shifts (most important - show prominently)
    # Use select_related to optimize queries
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
    
    # Get this week's shifts (for weekly view)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    weekly_shifts = StaffShift.objects.filter(
        staff=staff,
        shift_date__gte=week_start,
        shift_date__lte=week_end,
        is_deleted=False
    ).select_related('location', 'department', 'assigned_by').order_by('shift_date', 'start_time')
    
    # Debug: Log shift counts for troubleshooting
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Staff {staff.user.username} - Today's shifts: {todays_shifts.count()}, Upcoming: {upcoming_shifts.count()}, Weekly: {weekly_shifts.count()}")
    
    # Get pending leave requests
    pending_leaves = LeaveRequest.objects.filter(
        staff=staff,
        status='pending',
        is_deleted=False
    ).order_by('-created')
    
    # Get leave balance from LeaveBalance model
    leave_balance = None
    annual_percentage = 0
    sick_percentage = 0
    casual_percentage = 0
    
    try:
        from .models_hr import LeaveBalance
        leave_balance = LeaveBalance.objects.get(staff=staff)
        
        # Calculate leave percentages (assuming 21 annual, 14 sick, 7 casual as defaults)
        annual_total = 21
        sick_total = 14
        casual_total = 7
        
        annual_percentage = int((float(leave_balance.annual_leave) / annual_total) * 100) if annual_total > 0 else 0
        sick_percentage = int((float(leave_balance.sick_leave) / sick_total) * 100) if sick_total > 0 else 0
        casual_percentage = int((float(leave_balance.casual_leave) / casual_total) * 100) if casual_total > 0 else 0
        
    except (ImportError, AttributeError, Exception):
        pass
    
    # ========== WORLD-CLASS ENHANCEMENTS ==========
    
    # Get important hospital-wide announcements/messages
    important_messages = []
    mandatory_events = []
    upcoming_hospital_activities = []
    
    try:
        from .models_hr_activities import HospitalActivity
        
        # Urgent/important messages (high priority announcements for next 7 days)
        activity_q = Q(all_staff=True) | Q(specific_staff=staff)
        if staff.department_id:
            activity_q |= Q(departments=staff.department)
        important_messages = HospitalActivity.objects.filter(
            activity_q,
            activity_type__in=['announcement', 'drill', 'maintenance'],
            priority__in=['urgent', 'high'],
            start_date__lte=today + timedelta(days=7),
            end_date__gte=today,
            is_deleted=False,
            is_published=True
        ).order_by('-priority', 'start_date')[:5]
        
        # Mandatory upcoming events
        mandatory_events = HospitalActivity.objects.filter(
            activity_q,
            is_mandatory=True,
            start_date__gte=today,
            start_date__lte=today + timedelta(days=30),
            is_deleted=False,
            is_published=True
        ).order_by('start_date')[:5]
        
        # Get all hospital activities for this staff (next 30 days) - prominent reminders
        upcoming_hospital_activities = HospitalActivity.objects.filter(
            activity_q,
            start_date__gte=today,
            start_date__lte=today + timedelta(days=30),
            is_deleted=False,
            is_published=True
        ).order_by('start_date', 'start_time')[:15]
    except (ImportError, AttributeError, Exception):
        pass
    
    # Count unread/important items
    unread_count = {
        'messages': len(important_messages),
        'mandatory': len(mandatory_events),
        'alerts': leave_alerts.count(),
        'activities': len(upcoming_hospital_activities),
    }
    
    # Next activity for countdown (first upcoming)
    next_activity = upcoming_hospital_activities[0] if upcoming_hospital_activities else None
    
    # Quick stats for staff
    last_review = None
    try:
        from .models_hr import PerformanceReview
        last_review = PerformanceReview.objects.filter(
            staff=staff,
            is_deleted=False
        ).order_by('-review_date').first()
    except (ImportError, AttributeError, Exception):
        pass
    
    # Days since joining
    days_employed = 0
    if staff.date_of_joining:
        days_employed = (today - staff.date_of_joining).days
    
    context = {
        'staff': staff,
        'leave_counter': leave_counter,
        'leave_balance': leave_balance,
        'annual_percentage': annual_percentage,
        'sick_percentage': sick_percentage,
        'casual_percentage': casual_percentage,
        'upcoming_activities': upcoming_activities,
        'today_activities': today_activities,
        'leave_alerts': leave_alerts,
        'todays_shifts': todays_shifts,
        'upcoming_shifts': upcoming_shifts,
        'weekly_shifts': weekly_shifts,
        'week_start': week_start,
        'week_end': week_end,
        'pending_leaves': pending_leaves,
        'today': today,
        # New world-class features
        'important_messages': important_messages,
        'mandatory_events': mandatory_events,
        'upcoming_hospital_activities': upcoming_hospital_activities,
        'unread_count': unread_count,
        'next_activity': next_activity,
        'last_review': last_review,
        'days_employed': days_employed,
    }
    
    return render(request, 'hospital/staff/dashboard.html', context)


@login_required
def staff_activities_calendar(request):
    """
    Monthly calendar view of staff activities
    """
    # Get staff record
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        return render(request, 'hospital/staff/not_staff.html')
    
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    # Get first and last day of month
    from datetime import date
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    # Get all hospital-wide activities and personal activities in this month
    from .models_hr_activities import HospitalActivity
    
    hospital_activities = HospitalActivity.objects.filter(
        Q(all_staff=True) | Q(departments=staff.department) | Q(specific_staff=staff),
        start_date__lte=last_day,
        end_date__gte=first_day,
        is_deleted=False,
        is_published=True
    ).distinct().order_by('start_date', 'start_time')
    
    personal_activities = StaffActivity.objects.filter(
        staff=staff,
        activity_date__gte=first_day,
        activity_date__lte=last_day,
        is_deleted=False
    ).order_by('activity_date', 'activity_time')
    
    # Build calendar data
    calendar_data = []
    current_date = first_day
    
    while current_date <= last_day:
        day_activities = []
        
        # Add hospital activities
        for activity in hospital_activities:
            if activity.start_date <= current_date <= activity.end_date:
                day_activities.append({
                    'title': activity.title,
                    'type': activity.get_activity_type_display(),
                    'type_code': activity.activity_type,
                    'time': activity.start_time.strftime('%H:%M') if activity.start_time else 'All Day',
                    'location': activity.location or '',
                    'priority': activity.priority,
                    'is_mandatory': activity.is_mandatory,
                })
        
        # Add personal activities
        for activity in personal_activities:
            if activity.activity_date == current_date:
                day_activities.append({
                    'title': activity.title,
                    'type': 'Personal Task',
                    'type_code': 'personal',
                    'time': activity.activity_time.strftime('%H:%M') if activity.activity_time else '',
                    'location': '',
                    'priority': 'normal',
                    'is_mandatory': False,
                })
        
        calendar_data.append({
            'date': current_date,
            'day': current_date.day,
            'weekday': current_date.strftime('%a'),
            'activities': day_activities,
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
        'staff': staff,
        'year': year,
        'month': month,
        'month_name': cal.month_name[month],
        'calendar_data': calendar_data,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
    }
    
    return render(request, 'hospital/staff/activities_calendar.html', context)


@login_required
def acknowledge_leave_alert(request, alert_id):
    """Acknowledge a leave balance alert"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        alert = get_object_or_404(LeaveBalanceAlert, id=alert_id, staff=staff)
        
        alert.is_acknowledged = True
        alert.acknowledged_at = timezone.now()
        alert.save()
        
        return JsonResponse({'success': True, 'message': 'Alert acknowledged'})
    except:
        return JsonResponse({'success': False, 'message': 'Error acknowledging alert'}, status=400)


@login_required
def staff_leave_counter_api(request):
    """API endpoint to get current leave balance"""
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        leave_counter = StaffLeaveCounter.objects.get(staff=staff)
        leave_counter.update_from_leave_balance()
        
        data = {
            'annual_leave': {
                'total': float(leave_counter.annual_leave_total),
                'used': float(leave_counter.annual_leave_used),
                'pending': float(leave_counter.annual_leave_pending),
                'remaining': float(leave_counter.annual_leave_remaining),
                'percentage': int((leave_counter.annual_leave_remaining / leave_counter.annual_leave_total) * 100) if leave_counter.annual_leave_total > 0 else 0
            },
            'sick_leave': {
                'total': float(leave_counter.sick_leave_total),
                'used': float(leave_counter.sick_leave_used),
                'pending': float(leave_counter.sick_leave_pending),
                'remaining': float(leave_counter.sick_leave_remaining),
                'percentage': int((leave_counter.sick_leave_remaining / leave_counter.sick_leave_total) * 100) if leave_counter.sick_leave_total > 0 else 0
            },
            'casual_leave': {
                'total': float(leave_counter.casual_leave_total),
                'used': float(leave_counter.casual_leave_used),
                'pending': float(leave_counter.casual_leave_pending),
                'remaining': float(leave_counter.casual_leave_remaining),
                'percentage': int((leave_counter.casual_leave_remaining / leave_counter.casual_leave_total) * 100) if leave_counter.casual_leave_total > 0 else 0
            },
            'days_until_reset': leave_counter.days_until_reset
        }
        
        return JsonResponse(data)
    except:
        return JsonResponse({'error': 'Unable to fetch leave balance'}, status=400)


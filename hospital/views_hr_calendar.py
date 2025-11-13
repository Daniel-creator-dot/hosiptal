"""
HR Activity Calendar and Events Management Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from datetime import date, timedelta, datetime
import calendar as cal
import json

from .models import Staff, Department
from .models_hr_activities import (
    HospitalActivity, ActivityRSVP, StaffRecognition, 
    RecruitmentPosition, Candidate, WellnessProgram, 
    WellnessParticipation, StaffSurvey, SurveyResponse
)


@login_required
def activity_calendar(request):
    """Hospital-wide activity calendar"""
    today = timezone.now().date()
    
    # Get date parameters
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    
    # Calendar boundaries
    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    
    # Get activities for the month
    activities = HospitalActivity.objects.filter(
        is_deleted=False,
        is_published=True,
        start_date__lte=last_day,
        end_date__gte=first_day
    ).select_related('organizer__user').order_by('start_date', 'start_time')
    
    # Build calendar data
    calendar_data = []
    current_date = first_day
    
    while current_date <= last_day:
        day_activities = []
        for activity in activities:
            if activity.start_date <= current_date <= activity.end_date:
                day_activities.append(activity)
        
        calendar_data.append({
            'date': current_date,
            'day': current_date.day,
            'weekday': current_date.strftime('%A'),
            'activities': day_activities,
            'is_weekend': current_date.weekday() >= 5,
            'is_today': current_date == today
        })
        
        current_date += timedelta(days=1)
    
    # Upcoming activities (next 30 days)
    upcoming_activities_qs = HospitalActivity.objects.filter(
        is_deleted=False,
        is_published=True,
        start_date__gte=today,
        start_date__lte=today + timedelta(days=30)
    ).select_related('organizer__user').order_by('start_date', 'start_time')
    
    # Calculate mandatory count before slicing
    mandatory_upcoming = upcoming_activities_qs.filter(is_mandatory=True).count()
    
    # Now slice for display
    upcoming_activities = upcoming_activities_qs[:10]
    
    # Navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    # Statistics
    total_activities = HospitalActivity.objects.filter(
        is_deleted=False,
        is_published=True
    ).count()
    
    this_month_count = activities.count()
    
    context = {
        'title': 'Activity Calendar',
        'calendar_data': calendar_data,
        'upcoming_activities': upcoming_activities,
        'year': year,
        'month': month,
        'month_name': cal.month_name[month],
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': today,
        'total_activities': total_activities,
        'this_month_count': this_month_count,
        'mandatory_upcoming': mandatory_upcoming,
    }
    
    return render(request, 'hospital/hr/activity_calendar.html', context)


@login_required
def activity_detail(request, activity_id):
    """View activity details and RSVP"""
    activity = get_object_or_404(HospitalActivity, id=activity_id, is_deleted=False)
    
    # Get current user's staff profile
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        staff = None
    
    # Get RSVP status
    user_rsvp = None
    if staff and activity.requires_rsvp:
        try:
            user_rsvp = ActivityRSVP.objects.get(activity=activity, staff=staff)
        except ActivityRSVP.DoesNotExist:
            pass
    
    # Get all RSVPs
    rsvps = activity.rsvps.select_related('staff__user').all()
    rsvp_stats = {
        'yes': rsvps.filter(response='yes').count(),
        'no': rsvps.filter(response='no').count(),
        'maybe': rsvps.filter(response='maybe').count(),
    }
    
    context = {
        'title': activity.title,
        'activity': activity,
        'user_rsvp': user_rsvp,
        'rsvps': rsvps,
        'rsvp_stats': rsvp_stats,
        'staff': staff,
    }
    
    return render(request, 'hospital/hr/activity_detail.html', context)


@login_required
def staff_recognition_board(request):
    """Public recognition board"""
    today = timezone.now().date()
    
    # Recent recognitions (last 6 months)
    six_months_ago = today - timedelta(days=180)
    recent_recognitions = StaffRecognition.objects.filter(
        is_deleted=False,
        is_public=True,
        awarded_date__gte=six_months_ago
    ).select_related('staff__user', 'awarded_by').order_by('-awarded_date')
    
    # Recognition statistics
    total_recognitions = StaffRecognition.objects.filter(
        is_deleted=False,
        is_public=True
    ).count()
    
    this_year_count = StaffRecognition.objects.filter(
        is_deleted=False,
        is_public=True,
        awarded_date__year=today.year
    ).count()
    
    # Top recognized staff (all time)
    top_staff = Staff.objects.filter(
        is_deleted=False,
        recognitions__is_deleted=False,
        recognitions__is_public=True
    ).annotate(
        recognition_count=Count('recognitions')
    ).order_by('-recognition_count')[:10]
    
    context = {
        'title': 'Staff Recognition Board',
        'recent_recognitions': recent_recognitions,
        'total_recognitions': total_recognitions,
        'this_year_count': this_year_count,
        'top_staff': top_staff,
    }
    
    return render(request, 'hospital/hr/recognition_board.html', context)


@login_required
def recruitment_pipeline(request):
    """Recruitment pipeline dashboard"""
    
    # Active positions
    open_positions = RecruitmentPosition.objects.filter(
        is_deleted=False,
        status__in=['open', 'draft']
    ).select_related('department', 'hiring_manager__user').annotate(
        applicant_count=Count('candidates')
    ).order_by('-posted_date')
    
    # Recent candidates
    recent_candidates = Candidate.objects.filter(
        is_deleted=False
    ).select_related('position__department').order_by('-application_date')[:20]
    
    # Statistics
    total_positions = RecruitmentPosition.objects.filter(is_deleted=False).count()
    open_count = open_positions.filter(status='open').count()
    filled_count = RecruitmentPosition.objects.filter(is_deleted=False, status='filled').count()
    
    total_candidates = Candidate.objects.filter(is_deleted=False).count()
    interviewed_count = Candidate.objects.filter(
        is_deleted=False,
        status__in=['interviewed', 'offered', 'accepted']
    ).count()
    
    # Pipeline stages
    pipeline_stats = {
        'applied': Candidate.objects.filter(is_deleted=False, status='applied').count(),
        'screening': Candidate.objects.filter(is_deleted=False, status='screening').count(),
        'shortlisted': Candidate.objects.filter(is_deleted=False, status='shortlisted').count(),
        'interviewed': Candidate.objects.filter(is_deleted=False, status='interviewed').count(),
        'offered': Candidate.objects.filter(is_deleted=False, status='offered').count(),
    }
    
    context = {
        'title': 'Recruitment Pipeline',
        'open_positions': open_positions,
        'recent_candidates': recent_candidates,
        'total_positions': total_positions,
        'open_count': open_count,
        'filled_count': filled_count,
        'total_candidates': total_candidates,
        'interviewed_count': interviewed_count,
        'pipeline_stats': pipeline_stats,
    }
    
    return render(request, 'hospital/hr/recruitment_pipeline.html', context)


@login_required
def wellness_dashboard(request):
    """Staff wellness programs dashboard"""
    today = timezone.now().date()
    
    # Active wellness programs
    active_programs = WellnessProgram.objects.filter(
        is_deleted=False,
        is_active=True,
        start_date__lte=today
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).annotate(
        participant_count=Count('participants')
    ).order_by('-start_date')
    
    # Upcoming programs
    upcoming_programs = WellnessProgram.objects.filter(
        is_deleted=False,
        is_active=True,
        start_date__gt=today
    ).annotate(
        participant_count=Count('participants')
    ).order_by('start_date')[:5]
    
    # Get current user's participation
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        my_programs = WellnessParticipation.objects.filter(
            staff=staff,
            is_deleted=False
        ).select_related('program').order_by('-enrolled_date')
    except Staff.DoesNotExist:
        my_programs = []
    
    # Statistics
    total_programs = WellnessProgram.objects.filter(is_deleted=False).count()
    active_count = active_programs.count()
    
    total_participations = WellnessParticipation.objects.filter(is_deleted=False).count()
    completed_count = WellnessParticipation.objects.filter(
        is_deleted=False,
        is_completed=True
    ).count()
    
    context = {
        'title': 'Wellness Programs',
        'active_programs': active_programs,
        'upcoming_programs': upcoming_programs,
        'my_programs': my_programs,
        'total_programs': total_programs,
        'active_count': active_count,
        'total_participations': total_participations,
        'completed_count': completed_count,
    }
    
    return render(request, 'hospital/hr/wellness_dashboard.html', context)


@login_required
def survey_dashboard(request):
    """Staff surveys dashboard"""
    today = timezone.now().date()
    
    # Active surveys
    active_surveys = StaffSurvey.objects.filter(
        is_deleted=False,
        is_active=True,
        start_date__lte=today,
        end_date__gte=today
    ).annotate(
        response_count=Count('responses')
    ).order_by('-start_date')
    
    # Get user's responses
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
        my_responses = SurveyResponse.objects.filter(
            staff=staff,
            is_deleted=False
        ).values_list('survey_id', flat=True)
    except Staff.DoesNotExist:
        my_responses = []
    
    # Statistics
    total_surveys = StaffSurvey.objects.filter(is_deleted=False).count()
    active_count = active_surveys.count()
    
    total_responses = SurveyResponse.objects.filter(is_deleted=False).count()
    
    context = {
        'title': 'Staff Surveys',
        'active_surveys': active_surveys,
        'my_responses': my_responses,
        'total_surveys': total_surveys,
        'active_count': active_count,
        'total_responses': total_responses,
    }
    
    return render(request, 'hospital/hr/survey_dashboard.html', context)


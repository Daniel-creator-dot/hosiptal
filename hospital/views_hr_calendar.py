"""
HR Activity Calendar and Events Management Views
"""
from decimal import Decimal
from datetime import date, timedelta, datetime
import calendar as cal
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .forms_hr import RecruitmentPositionForm, CandidateForm
from .models import Staff, Department
from .models_hr_activities import (
    HospitalActivity,
    ActivityRSVP,
    StaffRecognition,
    RecruitmentPosition,
    Candidate,
    WellnessProgram,
    WellnessParticipation,
    StaffSurvey,
    SurveyResponse,
)


def seed_recruitment_demo_data():
    """
    Auto-populate recruitment tables with showcase data when a fresh database has
    no requisitions. This keeps the UI from feeling empty and provides a
    reference pipeline that users can customize or delete.
    """

    if RecruitmentPosition.objects.filter(is_deleted=False).exists():
        return

    today = timezone.now().date()
    departments = list(Department.objects.filter(is_deleted=False).order_by('name'))
    staff_pool = list(
        Staff.objects.filter(is_deleted=False)
        .select_related('user')
        .order_by('user__first_name', 'user__last_name')
    )

    def pick_department(keyword: str):
        keyword_lower = (keyword or '').lower()
        for dept in departments:
            if keyword_lower and keyword_lower in (dept.name or '').lower():
                return dept
        return departments[0] if departments else None

    def pick_manager(full_name_hint: str):
        hint = (full_name_hint or '').lower()
        for staff in staff_pool:
            if hint and hint in staff.user.get_full_name().lower():
                return staff
        return staff_pool[0] if staff_pool else None

    positions_seed = [
        {
            'title': 'Senior Registered Nurse',
            'department_hint': 'Nursing',
            'employment_type': 'full_time',
            'slots': 3,
            'description': 'Lead ward-based nursing care, supervise junior nurses, and coordinate interdisciplinary rounds.',
            'requirements': 'Active RN license, 5+ years acute care experience, leadership exposure.',
            'qualifications': 'BSN or higher, BCLS/ACLS certifications.',
            'salary_min': Decimal('4200.00'),
            'salary_max': Decimal('5200.00'),
            'posted_days': 10,
            'closing_days': 14,
            'status': 'open',
            'urgent': True,
            'manager_hint': 'Nurse',
        },
        {
            'title': 'Radiology Technologist',
            'department_hint': 'Imaging',
            'employment_type': 'full_time',
            'slots': 2,
            'description': 'Operate diagnostic imaging equipment (CT/MRI), ensure patient comfort, and liaise with radiologists.',
            'requirements': '3+ years radiology experience, familiarity with PACS workflows.',
            'qualifications': 'Diploma/degree in Radiologic Technology, ARRT certification preferred.',
            'salary_min': Decimal('3800.00'),
            'salary_max': Decimal('4500.00'),
            'posted_days': 5,
            'closing_days': 20,
            'status': 'open',
            'urgent': False,
            'manager_hint': 'Imaging',
        },
        {
            'title': 'Pharmacy Procurement Lead',
            'department_hint': 'Pharmacy',
            'employment_type': 'full_time',
            'slots': 1,
            'description': 'Own formulary sourcing, monitor stock-outs, and negotiate with vendors.',
            'requirements': 'Experience with hospital pharmacy supply chains and ERP systems.',
            'qualifications': 'B.Pharm or related degree, membership with professional council.',
            'salary_min': Decimal('5000.00'),
            'salary_max': Decimal('6000.00'),
            'posted_days': 2,
            'closing_days': 28,
            'status': 'draft',
            'urgent': False,
            'manager_hint': 'Pharmacy',
        },
        {
            'title': 'Human Resource Business Partner',
            'department_hint': 'Human Resource',
            'employment_type': 'full_time',
            'slots': 1,
            'description': 'Support departmental heads with workforce planning, engagement programs, and policy rollouts.',
            'requirements': '7+ years HR generalist/HRBP experience, healthcare exposure preferred.',
            'qualifications': 'BA in HRM or related field, SHRM/CHRM certification advantageous.',
            'salary_min': Decimal('5500.00'),
            'salary_max': Decimal('6800.00'),
            'posted_days': 12,
            'closing_days': 18,
            'status': 'open',
            'urgent': False,
            'manager_hint': 'HR',
        },
    ]

    candidate_seed = [
        {
            'position_title': 'Senior Registered Nurse',
            'first_name': 'Anthony',
            'last_name': 'Amissah',
            'email': 'anthony.amissah@example.com',
            'phone': '+233501234567',
            'status': 'shortlisted',
            'applied_days': 6,
            'interview_in_days': 1,
            'interview_notes': 'Excellent leadership stories; needs salary alignment.',
        },
        {
            'position_title': 'Senior Registered Nurse',
            'first_name': 'Miriam',
            'last_name': 'Boateng',
            'email': 'miriam.boateng@example.com',
            'phone': '+233542221199',
            'status': 'screening',
            'applied_days': 3,
        },
        {
            'position_title': 'Radiology Technologist',
            'first_name': 'Samuel',
            'last_name': 'Owusu',
            'email': 'samuel.owusu@example.com',
            'phone': '+233240987654',
            'status': 'interviewed',
            'applied_days': 9,
            'interview_in_days': None,
            'interview_notes': 'Awaiting second-round review from Dr. Mensah.',
        },
        {
            'position_title': 'Human Resource Business Partner',
            'first_name': 'Linda',
            'last_name': 'Yeboah',
            'email': 'linda.yeboah@example.com',
            'phone': '+233208889990',
            'status': 'offered',
            'applied_days': 15,
            'offer_in_days': -1,
            'offer_salary': Decimal('6200.00'),
        },
    ]

    with transaction.atomic():
        created_positions = []
        for row in positions_seed:
            department = pick_department(row['department_hint'])
            manager = pick_manager(row.get('manager_hint'))
            position = RecruitmentPosition.objects.create(
                position_title=row['title'],
                department=department,
                employment_type=row['employment_type'],
                number_of_positions=row['slots'],
                job_description=row['description'],
                requirements=row['requirements'],
                qualifications=row['qualifications'],
                salary_range_min=row['salary_min'],
                salary_range_max=row['salary_max'],
                posted_date=today - timedelta(days=row['posted_days']),
                closing_date=today + timedelta(days=row['closing_days']),
                status=row['status'],
                hiring_manager=manager,
                is_urgent=row['urgent'],
            )
            created_positions.append(position)

        for row in candidate_seed:
            position = next((p for p in created_positions if p.position_title == row['position_title']), None)
            if not position:
                continue

            candidate_kwargs = {
                'position': position,
                'first_name': row['first_name'],
                'last_name': row['last_name'],
                'email': row['email'],
                'phone': row['phone'],
                'application_date': today - timedelta(days=row.get('applied_days', 0)),
                'status': row.get('status', 'applied'),
                'interview_notes': row.get('interview_notes', ''),
                'notes': row.get('notes', ''),
                'offer_salary': row.get('offer_salary'),
            }

            interview_in_days = row.get('interview_in_days')
            if interview_in_days is not None:
                candidate_kwargs['interview_date'] = timezone.now() + timedelta(days=interview_in_days)

            offer_in_days = row.get('offer_in_days')
            if offer_in_days is not None:
                candidate_kwargs['offer_date'] = today + timedelta(days=offer_in_days)

            Candidate.objects.create(**candidate_kwargs)


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
def activity_detail(request, pk):
    """View activity details and RSVP"""
    activity = get_object_or_404(HospitalActivity, id=pk, is_deleted=False)
    
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
    today = timezone.now().date()
    seed_recruitment_demo_data()
    action = request.POST.get('action') if request.method == 'POST' else None
    candidate_status_filter = request.GET.get('candidate_status')
    position_filter = request.GET.get('position')
    
    # Forms default
    position_form = RecruitmentPositionForm()
    candidate_form_initial = {}
    if position_filter:
        candidate_form_initial['position'] = position_filter
    candidate_form = CandidateForm(initial=candidate_form_initial)
    
    if request.method == 'POST':
        if action == 'create_position':
            position_form = RecruitmentPositionForm(request.POST)
            if position_form.is_valid():
                position = position_form.save()
                messages.success(request, f"{position.position_title} has been added to the requisition list.")
                return redirect('hospital:recruitment_pipeline')
            else:
                messages.error(request, "Please correct the errors in the position form.")
        elif action == 'create_candidate':
            candidate_form = CandidateForm(request.POST, request.FILES)
            if candidate_form.is_valid():
                candidate = candidate_form.save()
                messages.success(request, f"{candidate.first_name} {candidate.last_name} has been added to {candidate.position.position_title}.")
                return redirect('hospital:recruitment_pipeline')
            else:
                messages.error(request, "Please correct the errors in the candidate form.")
        elif action == 'update_candidate_status':
            candidate_id = request.POST.get('candidate_id')
            new_status = request.POST.get('status')
            valid_statuses = dict(Candidate.STATUS_CHOICES)
            if new_status not in valid_statuses:
                messages.error(request, "Select a valid status before updating.")
            else:
                try:
                    candidate = Candidate.objects.get(id=candidate_id, is_deleted=False)
                    candidate.status = new_status
                    candidate.save(update_fields=['status', 'modified'])
                    messages.success(request, f"{candidate.first_name} {candidate.last_name} moved to {candidate.get_status_display()}.")
                    return redirect('hospital:recruitment_pipeline')
                except Candidate.DoesNotExist:
                    messages.error(request, "Candidate could not be found.")
        else:
            messages.error(request, "Unknown action requested.")
    
    # Positions (annotated with applicant counts)
    positions_qs = RecruitmentPosition.objects.filter(
        is_deleted=False
    ).select_related('department', 'hiring_manager__user').annotate(
        applicant_count=Count('candidates', distinct=True)
    )
    open_positions = positions_qs.filter(status__in=['open', 'draft']).order_by('closing_date', '-posted_date')
    
    # Candidate list with filters
    candidate_qs = Candidate.objects.filter(is_deleted=False).select_related('position__department')
    if candidate_status_filter in dict(Candidate.STATUS_CHOICES):
        candidate_qs = candidate_qs.filter(status=candidate_status_filter)
    if position_filter:
        candidate_qs = candidate_qs.filter(position_id=position_filter)
    recent_candidates = candidate_qs.order_by('-application_date')[:20]
    
    # Statistics
    total_positions = positions_qs.count()
    open_count = open_positions.filter(status='open').count()
    filled_count = positions_qs.filter(status='filled').count()
    
    total_candidates = Candidate.objects.filter(is_deleted=False).count()
    interviewed_count = Candidate.objects.filter(
        is_deleted=False,
        status__in=['interviewed', 'offered', 'accepted']
    ).count()
    
    # Pipeline breakdown for visual display
    pipeline_raw = {
        'applied': Candidate.objects.filter(is_deleted=False, status='applied').count(),
        'screening': Candidate.objects.filter(is_deleted=False, status='screening').count(),
        'shortlisted': Candidate.objects.filter(is_deleted=False, status='shortlisted').count(),
        'interviewed': Candidate.objects.filter(is_deleted=False, status='interviewed').count(),
        'offered': Candidate.objects.filter(is_deleted=False, status='offered').count(),
        'accepted': Candidate.objects.filter(is_deleted=False, status='accepted').count(),
    }
    pipeline_order = [
        ('applied', 'Applied', 'primary'),
        ('screening', 'Screening', 'info'),
        ('shortlisted', 'Shortlisted', 'warning'),
        ('interviewed', 'Interviewed', 'secondary'),
        ('offered', 'Offered', 'success'),
        ('accepted', 'Accepted', 'dark'),
    ]
    pipeline_stats = []
    for key, label, color in pipeline_order:
        count = pipeline_raw.get(key, 0)
        percent = round((count / total_candidates) * 100, 1) if total_candidates else 0
        pipeline_stats.append({
            'key': key,
            'label': label,
            'count': count,
            'percent': percent,
            'color': color,
        })
    
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
        'position_form': position_form,
        'candidate_form': candidate_form,
        'candidate_status_choices': Candidate.STATUS_CHOICES,
        'candidate_status_filter': candidate_status_filter,
        'candidate_position_filter': position_filter,
        'positions_all': positions_qs.order_by('position_title'),
        'today': today,
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


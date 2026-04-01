"""
World-Class Triage System Views
Efficient patient flow management with comprehensive reporting
OPTIMIZED FOR HIGH PERFORMANCE
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from datetime import timedelta, datetime
from decimal import Decimal

from .models import Patient, Encounter, Staff
from .models_advanced import Triage
from .models_workflow import PatientFlowStage


from .decorators import role_required

@login_required
@role_required('nurse', 'midwife', 'admin', message='Access denied. Only nurses and midwives can access triage.')
def triage_dashboard_enhanced(request):
    """
    World-class triage dashboard with patient flow tracking
    OPTIMIZED: Uses select_related, prefetch_related, and efficient queries
    REALISTIC: Connected to real patient data and ambulance system
    """
    now = timezone.now()
    today = now.date()
    
    # Get filter parameters
    level_filter = request.GET.get('level', '')
    status_filter = request.GET.get('status', '')
    
    # OPTIMIZATION: Use select_related to reduce queries
    triage_records = Triage.objects.filter(
        is_deleted=False,
        encounter__status='active'
    ).select_related(
        'encounter__patient',
        'triaged_by__user',
        'encounter'
    ).order_by('triage_time')
    
    # Apply filters
    if level_filter:
        triage_records = triage_records.filter(triage_level=level_filter)
    
    # Calculate wait times
    for record in triage_records:
        time_diff = now - record.triage_time
        record.wait_time_minutes = int(time_diff.total_seconds() / 60)
    
    # Group by triage level
    critical_patients = [r for r in triage_records if r.triage_level in ['esi_1', 'mts_red']]
    emergency_patients = [r for r in triage_records if r.triage_level in ['esi_2', 'mts_orange']]
    urgent_patients = [r for r in triage_records if r.triage_level in ['esi_3', 'mts_yellow']]
    standard_patients = [r for r in triage_records if r.triage_level in ['esi_4', 'mts_green']]
    non_urgent_patients = [r for r in triage_records if r.triage_level in ['esi_5', 'mts_blue']]
    
    # Calculate statistics
    critical_count = len(critical_patients)
    emergency_count = len(emergency_patients)
    urgent_count = len(urgent_patients)
    standard_count = len(standard_patients)
    non_urgent_count = len(non_urgent_patients)
    
    # Average wait time
    wait_times = [r.wait_time_minutes for r in triage_records if hasattr(r, 'wait_time_minutes')]
    avg_wait_time = int(sum(wait_times) / len(wait_times)) if wait_times else 0
    
    # ========== AMBULANCE SYSTEM DATA ==========
    try:
        from .models_ambulance import AmbulanceUnit, AmbulanceDispatch, AmbulanceServiceType
        
        # Get active ambulance units
        ambulance_units = AmbulanceUnit.objects.filter(
            is_deleted=False
        ).select_related('primary_paramedic__user', 'primary_emt__user')
        
        # Get recent dispatches (last 24 hours)
        recent_dispatches = AmbulanceDispatch.objects.filter(
            is_deleted=False,
            call_received_at__gte=now - timedelta(hours=24)
        ).select_related(
            'ambulance_unit',
            'patient',
            'encounter__patient'
        ).order_by('-call_received_at')[:10]
        
        # Get incoming ambulances (en route to hospital)
        incoming_ambulances = recent_dispatches.filter(
            ambulance_unit__status__in=['transporting', 'returning']
        ).select_related('patient', 'encounter__patient')
        
        # Calculate ETA for incoming (mock for now, can be enhanced with actual GPS)
        for dispatch in incoming_ambulances:
            if dispatch.hospital_arrival_time:
                eta_delta = dispatch.hospital_arrival_time - now
                dispatch.eta_minutes = max(0, int(eta_delta.total_seconds() / 60))
            else:
                # Estimate based on dispatch time
                dispatch.eta_minutes = 5  # Default estimate
        
        # Get service types for pricing
        service_types = AmbulanceServiceType.objects.filter(
            is_deleted=False,
            is_active=True
        ).order_by('base_charge')
        
        # Fleet statistics
        fleet_stats = {
            'total_units': ambulance_units.count(),
            'available': ambulance_units.filter(status='available').count(),
            'en_route': ambulance_units.filter(status__in=['en_route', 'transporting']).count(),
            'on_scene': ambulance_units.filter(status='on_scene').count(),
        }
        
        # Calculate average response time (last 30 days)
        thirty_days_ago = now - timedelta(days=30)
        completed_dispatches = AmbulanceDispatch.objects.filter(
            call_received_at__gte=thirty_days_ago,
            arrival_time__isnull=False
        )
        
        response_times = []
        for dispatch in completed_dispatches:
            if dispatch.response_time_minutes:
                response_times.append(dispatch.response_time_minutes)
        
        avg_response_time = round(sum(response_times) / len(response_times), 1) if response_times else 0
        
    except Exception as e:
        print(f"Ambulance data not available: {e}")
        ambulance_units = []
        recent_dispatches = []
        incoming_ambulances = []
        service_types = []
        fleet_stats = {
            'total_units': 0,
            'available': 0,
            'en_route': 0,
            'on_scene': 0,
        }
        avg_response_time = 0
    
    context = {
        'now': now,
        'triage_records': list(triage_records),
        'critical_patients': critical_patients,
        'emergency_patients': emergency_patients,
        'urgent_patients': urgent_patients,
        'standard_patients': standard_patients,
        'non_urgent_patients': non_urgent_patients,
        'critical_count': critical_count,
        'emergency_count': emergency_count,
        'urgent_count': urgent_count,
        'standard_count': standard_count,
        'non_urgent_count': non_urgent_count,
        'avg_wait_time': avg_wait_time,
        'level_filter': level_filter,
        'status_filter': status_filter,
        # Ambulance system data
        'ambulance_units': ambulance_units,
        'recent_dispatches': recent_dispatches,
        'incoming_ambulances': incoming_ambulances,
        'ambulance_service_types': service_types,
        'fleet_stats': fleet_stats,
        'avg_response_time': avg_response_time,
    }
    
    return render(request, 'hospital/triage_dashboard_worldclass.html', context)


@login_required
@role_required('nurse', 'midwife', 'admin', message='Access denied. Only nurses and midwives can move patients.')
def move_patient_to_department(request, encounter_id):
    """
    Move patient to next department in workflow
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    if request.method == 'POST':
        department_type = request.POST.get('department_type')
        
        # Get or create staff
        try:
            staff = Staff.objects.get(user=request.user, is_deleted=False)
        except Staff.DoesNotExist:
            staff = None
        
        # Create or update flow stage
        stage, created = PatientFlowStage.objects.get_or_create(
            encounter=encounter,
            stage_type=department_type,
            defaults={
                'status': 'pending',
                'priority': 'routine'
            }
        )
        
        # Update encounter current activity
        if department_type == 'consultation':
            activity = 'Consulting'
        elif department_type == 'laboratory':
            activity = 'Lab'
        elif department_type == 'imaging':
            activity = 'Imaging'
        elif department_type == 'pharmacy':
            activity = 'Pharmacy'
        else:
            activity = department_type.capitalize()
        
        # Update or append activity
        if encounter.current_activity:
            activities = encounter.current_activity.split(',')
            if activity not in activities:
                activities.append(activity)
                encounter.current_activity = ','.join(activities)
        else:
            encounter.current_activity = activity
        
        encounter.save()
        
        # Start the stage
        stage.start(staff=staff)
        
        messages.success(request, f'Patient moved to {department_type.title()}')
        return redirect('hospital:triage_dashboard_enhanced')
    
    return redirect('hospital:encounter_detail', pk=encounter_id)


@login_required
@role_required('nurse', 'midwife', 'admin', message='Access denied. Only nurses and midwives can access triage reports.')
def triage_reports(request):
    """
    Comprehensive triage reporting dashboard
    """
    # Date range
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    today = timezone.now().date()
    
    if not start_date:
        start_date = today - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    if not end_date:
        end_date = today
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Get triage records in date range
    triage_records = Triage.objects.filter(
        triage_time__date__gte=start_date,
        triage_time__date__lte=end_date,
        is_deleted=False
    ).select_related('encounter__patient', 'triaged_by__user')
    
    # Statistics by triage level
    by_level = triage_records.values('triage_level').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Daily volume
    daily_volume = triage_records.extra(
        select={'day': 'DATE(triage_time)'}
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    # Average wait times by level
    wait_times_by_level = {}
    for level_code, level_name in Triage.TRIAGE_SCALES:
        level_records = triage_records.filter(triage_level=level_code)
        if level_records.exists():
            wait_times = []
            for record in level_records:
                # Calculate wait time (triage to encounter start)
                if record.encounter.started_at:
                    wait = (record.encounter.started_at - record.triage_time).total_seconds() / 60
                    wait_times.append(wait)
            
            if wait_times:
                wait_times_by_level[level_name] = {
                    'avg': round(sum(wait_times) / len(wait_times), 1),
                    'max': round(max(wait_times), 1),
                    'min': round(min(wait_times), 1),
                    'count': len(wait_times)
                }
    
    # Peak hours analysis
    hourly_distribution = {}
    for record in triage_records:
        hour = record.triage_time.hour
        hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
    
    peak_hours = sorted(hourly_distribution.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Staff performance
    staff_performance = triage_records.values(
        'triaged_by__user__first_name',
        'triaged_by__user__last_name'
    ).annotate(
        total_triaged=Count('id')
    ).order_by('-total_triaged')[:10]
    
    # Outcome tracking
    completed_encounters = Encounter.objects.filter(
        triage__triage_time__date__gte=start_date,
        triage__triage_time__date__lte=end_date,
        status='completed'
    ).count()
    
    still_active = Encounter.objects.filter(
        triage__triage_time__date__gte=start_date,
        triage__triage_time__date__lte=end_date,
        status='active'
    ).count()
    
    # Patient flow statistics
    flow_stages = PatientFlowStage.objects.filter(
        encounter__triage__triage_time__date__gte=start_date,
        encounter__triage__triage_time__date__lte=end_date
    )
    
    avg_time_per_stage = {}
    for stage_type, stage_name in PatientFlowStage.STAGE_TYPES:
        stage_records = flow_stages.filter(
            stage_type=stage_type,
            status='completed',
            started_at__isnull=False,
            completed_at__isnull=False
        )
        
        if stage_records.exists():
            durations = []
            for stage in stage_records:
                duration = (stage.completed_at - stage.started_at).total_seconds() / 60
                durations.append(duration)
            
            if durations:
                avg_time_per_stage[stage_name] = round(sum(durations) / len(durations), 1)
    
    # Chart data for JavaScript
    import json
    
    # Triage level distribution
    level_labels = [item['triage_level'] for item in by_level]
    level_counts = [item['count'] for item in by_level]
    
    # Daily volume chart
    daily_labels = [str(item['day']) for item in daily_volume]
    daily_counts = [item['count'] for item in daily_volume]
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_triaged': triage_records.count(),
        'by_level': by_level,
        'wait_times_by_level': wait_times_by_level,
        'peak_hours': peak_hours,
        'staff_performance': staff_performance,
        'completed_encounters': completed_encounters,
        'still_active': still_active,
        'avg_time_per_stage': avg_time_per_stage,
        'level_labels_json': json.dumps(level_labels),
        'level_counts_json': json.dumps(level_counts),
        'daily_labels_json': json.dumps(daily_labels),
        'daily_counts_json': json.dumps(daily_counts),
    }
    
    return render(request, 'hospital/triage_reports.html', context)


@login_required
@role_required('nurse', 'midwife', 'admin', message='Access denied. Only nurses and midwives can complete stages.')
def complete_and_move(request, encounter_id, current_stage):
    """
    Complete current stage and move to next
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    try:
        staff = Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        staff = None
    
    # Complete current stage
    try:
        stage = PatientFlowStage.objects.get(
            encounter=encounter,
            stage_type=current_stage,
            is_deleted=False
        )
        stage.complete(staff=staff)
        
        # Determine next stage
        stage_order = [
            'registration', 'triage', 'vitals', 'consultation',
            'laboratory', 'imaging', 'pharmacy', 'treatment',
            'billing', 'payment', 'discharge'
        ]
        
        current_index = stage_order.index(current_stage)
        if current_index < len(stage_order) - 1:
            next_stage = stage_order[current_index + 1]
            
            # Create next stage if it doesn't exist
            next_flow, created = PatientFlowStage.objects.get_or_create(
                encounter=encounter,
                stage_type=next_stage,
                defaults={
                    'status': 'pending',
                    'priority': stage.priority
                }
            )
            
            messages.success(request, f'Completed {current_stage.title()}. Patient moved to {next_stage.title()}.')
        else:
            messages.success(request, f'Completed {current_stage.title()}.')
        
    except PatientFlowStage.DoesNotExist:
        messages.error(request, 'Stage not found.')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('hospital:patient_flow', encounter_id=encounter_id)















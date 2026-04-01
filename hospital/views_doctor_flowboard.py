"""
Doctor Patient Flowboard
Shows patients in consultation queue and workflow for doctors
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta, datetime, date
from django.http import JsonResponse

from .models import Encounter, Patient, Order, LabResult, Staff
from .models_workflow import PatientFlowStage
from .utils_roles import is_doctor, ensure_staff_profile


@login_required
def doctor_patient_flowboard(request):
    """
    Doctor-specific patient flowboard showing:
    - Patients waiting for consultation
    - Patients in consultation
    - Patients waiting for results/next steps
    - Lab/imaging results pending review
    
    Features:
    - Date filtering (defaults to today)
    - Auto-archives consultations older than 24 hours
    - Historical view for previous encounters
    """
    # Ensure user is a doctor
    if not is_doctor(request.user):
        return render(request, 'hospital/access_denied.html', {'message': 'Access denied. Only doctors can view this flowboard.'})
    
    staff, error_response = ensure_staff_profile(request, 'Doctor', expected_profession='doctor')
    if error_response:
        return error_response
    
    today = timezone.now().date()
    now = timezone.now()
    
    # Get selected date from request (default to today)
    selected_date_str = request.GET.get('date', None)
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            selected_date = today
    else:
        selected_date = today
    
    # CRITICAL FIX: Calculate proper date filtering
    # For today: only show encounters/stages from last 24 hours
    # For past dates: show all from that date
    if selected_date == today:
        # Today: 24-hour auto-archive threshold
        archive_threshold = now - timedelta(hours=24)
        # Get encounters from last 24 hours only
        active_encounters = Encounter.objects.filter(
            provider=staff,
            status='active',
            is_deleted=False
        ).filter(
            Q(started_at__gte=archive_threshold) | 
            Q(started_at__isnull=True, created__gte=archive_threshold)
        ).select_related('patient__primary_insurance', 'provider__user').order_by('-started_at', '-created')
    else:
        # Past date: show all encounters from that specific date
        date_start = timezone.make_aware(datetime.combine(selected_date, datetime.min.time()))
        date_end = timezone.make_aware(datetime.combine(selected_date, datetime.max.time()))
        archive_threshold = None
        active_encounters = Encounter.objects.filter(
            provider=staff,
            status='active',
            is_deleted=False
        ).filter(
            Q(started_at__gte=date_start, started_at__lte=date_end) |
            Q(started_at__isnull=True, created__gte=date_start, created__lte=date_end)
        ).select_related('patient__primary_insurance', 'provider__user').order_by('-started_at', '-created')
    
    # Get consultation flow stages for these encounters
    consultation_stages = PatientFlowStage.objects.filter(
        encounter__in=active_encounters,
        stage_type='consultation',
        is_deleted=False
    ).select_related('encounter__patient__primary_insurance', 'completed_by__user')
    
    # Apply additional date filtering to consultation stages - STRICT FILTERING
    if selected_date == today:
        # For today: STRICTLY exclude consultation stages older than 24 hours
        consultation_stages = consultation_stages.filter(
            Q(started_at__gte=archive_threshold) | Q(started_at__isnull=True, created__gte=archive_threshold)
        ).exclude(
            Q(started_at__lt=archive_threshold) | Q(started_at__isnull=True, created__lt=archive_threshold)
        )
    else:
        # For past dates: filter consultation stages by date - STRICT
        date_start_aware = timezone.make_aware(datetime.combine(selected_date, datetime.min.time()))
        date_end_aware = timezone.make_aware(datetime.combine(selected_date, datetime.max.time()))
        consultation_stages = consultation_stages.filter(
            Q(started_at__gte=date_start_aware, started_at__lte=date_end_aware) | 
            Q(started_at__isnull=True, created__gte=date_start_aware, created__lte=date_end_aware)
        )
    
    # Organize patients by status
    queue_by_status = {
        'waiting_consultation': {
            'name': 'Waiting for Consultation',
            'icon': 'clock-history',
            'color': '#F59E0B',
            'bg': 'rgba(245, 158, 11, 0.1)',
            'patients': []
        },
        'in_consultation': {
            'name': 'In Consultation',
            'icon': 'clipboard2-pulse',
            'color': '#667eea',
            'bg': 'rgba(102, 126, 234, 0.1)',
            'patients': []
        },
        'waiting_results': {
            'name': 'Waiting for Results',
            'icon': 'hourglass-split',
            'color': '#06B6D4',
            'bg': 'rgba(6, 182, 212, 0.1)',
            'patients': []
        },
        'results_ready': {
            'name': 'Results Ready for Review',
            'icon': 'flask-vial',
            'color': '#10B981',
            'bg': 'rgba(16, 185, 129, 0.1)',
            'patients': []
        },
        'ready_for_discharge': {
            'name': 'Ready for Discharge',
            'icon': 'check-circle',
            'color': '#14B8A6',
            'bg': 'rgba(20, 184, 166, 0.1)',
            'patients': []
        },
    }
    
    # Process consultation stages - deduplicate by encounter_id (UUID)
    seen_encounter_ids = set()  # Store str(id) for consistent comparison
    for stage in consultation_stages:
        enc_key = str(stage.encounter_id)
        if enc_key in seen_encounter_ids:
            continue
        seen_encounter_ids.add(enc_key)
        
        encounter = stage.encounter
        patient = encounter.patient
        
        # Calculate wait time - CRITICAL FIX: Cap at 24 hours max
        wait_start = stage.started_at or stage.created
        
        # For today: only calculate wait time if within last 24 hours
        if selected_date == today:
            if wait_start < archive_threshold:
                continue  # Skip old stages completely
        
        wait_minutes = int((now - wait_start).total_seconds() / 60)
        
        # HARD CAP: Never show wait times > 24 hours (1440 minutes)
        if wait_minutes > 1440:
            continue  # Skip this patient - data is too old
        
        patient_data = {
            'encounter_id': str(encounter.id),
            'patient_id': str(patient.id),
            'patient_name': patient.full_name,
            'mrn': patient.mrn,
            'encounter_type': encounter.get_encounter_type_display(),
            'chief_complaint': encounter.chief_complaint or 'No complaint recorded',
            'wait_minutes': min(wait_minutes, 1440),  # Cap at 24 hours
            'wait_start': wait_start,
            'flow_stage': stage,
            'status': stage.status,
            'django_patient': patient,
            'django_encounter': encounter,
        }
        
        if stage.status == 'pending':
            queue_by_status['waiting_consultation']['patients'].append(patient_data)
        elif stage.status == 'in_progress':
            queue_by_status['in_consultation']['patients'].append(patient_data)
        elif stage.status == 'completed':
            # Check if patient has pending lab/imaging orders
            has_pending_orders = Order.objects.filter(
                encounter=encounter,
                order_type__in=['lab', 'imaging'],
                status__in=['pending', 'in_progress'],
                is_deleted=False
            ).exists()
            
            if has_pending_orders:
                queue_by_status['waiting_results']['patients'].append(patient_data)
    
    # Add active encounters without consultation stage to waiting list
    # Skip encounters already added from consultation_stages
    for encounter in active_encounters:
        if str(encounter.id) in seen_encounter_ids:
            continue
        # Double-check date filter (encounters are already filtered, but verify)
        encounter_time = encounter.started_at or encounter.created
        if selected_date == today:
            if encounter_time < archive_threshold:
                continue  # Skip encounters older than 24 hours
        
        has_consultation_stage = consultation_stages.filter(encounter=encounter).exists()
        if not has_consultation_stage:
            # Check if consultation stage exists but was filtered out
            consultation_stage = PatientFlowStage.objects.filter(
                encounter=encounter,
                stage_type='consultation',
                is_deleted=False
            ).first()
            
            if consultation_stage:
                # Stage exists but was filtered out - check if we should show encounter
                stage_time = consultation_stage.started_at or consultation_stage.created
                if selected_date == today:
                    if stage_time < archive_threshold:
                        continue  # Skip if stage is too old
                else:
                    stage_date = (consultation_stage.started_at or consultation_stage.created).date()
                    if stage_date != selected_date:
                        continue  # Skip if stage doesn't match selected date
            
            # Calculate wait time - CRITICAL FIX: Cap at 24 hours max
            wait_minutes = int((now - encounter_time).total_seconds() / 60)
            
            # HARD FILTER: Skip any wait time > 24 hours (1440 minutes)
            if wait_minutes > 1440:
                continue  # Skip old encounters completely
            
            # For today: double-check against archive threshold
            if selected_date == today:
                if encounter_time < archive_threshold:
                    continue  # Skip encounters older than 24 hours
            
            seen_encounter_ids.add(str(encounter.id))
            queue_by_status['waiting_consultation']['patients'].append({
                'encounter_id': str(encounter.id),
                'patient_id': str(encounter.patient.id),
                'patient_name': encounter.patient.full_name,
                'mrn': encounter.patient.mrn,
                'encounter_type': encounter.get_encounter_type_display(),
                'chief_complaint': encounter.chief_complaint or 'No complaint recorded',
                'wait_minutes': min(wait_minutes, 1440),  # Cap at 24 hours
                'wait_start': encounter_time,
                'flow_stage': None,
                'status': 'pending',
                'django_patient': encounter.patient,
                'django_encounter': encounter,
            })
    
    # Get lab results ready for review (only for filtered encounters)
    pending_lab_results = LabResult.objects.filter(
        order__encounter__in=active_encounters,
        status='completed',
        verified_at__isnull=False,
        is_deleted=False
    ).select_related(
        'order__encounter__patient__primary_insurance',
        'test',
        'verified_by__user'
    ).order_by('-verified_at')[:20]
    
    # Organize by encounter
    results_by_encounter = {}
    for result in pending_lab_results:
        encounter_id = str(result.order.encounter.id)
        if encounter_id not in results_by_encounter:
            enc = result.order.encounter
            results_by_encounter[encounter_id] = {
                'encounter_id': encounter_id,
                'patient_name': enc.patient.full_name,
                'patient_id': str(enc.patient.id),
                'mrn': enc.patient.mrn,
                'encounter_type': enc.get_encounter_type_display(),
                'results': [],
                'results_count': 0,
                'has_abnormal': False,
                'django_patient': enc.patient,
                'django_encounter': enc,
            }
        
        results_by_encounter[encounter_id]['results'].append(result)
        results_by_encounter[encounter_id]['results_count'] += 1
        if result.is_abnormal:
            results_by_encounter[encounter_id]['has_abnormal'] = True
    
    # Add to results ready queue - skip if already in main consultation queues
    for encounter_id, data in results_by_encounter.items():
        if encounter_id in seen_encounter_ids:
            continue
        seen_encounter_ids.add(encounter_id)
        queue_by_status['results_ready']['patients'].append(data)
    
    # Get imaging results (if ImagingStudy model exists)
    try:
        from .models_advanced import ImagingStudy
        
        pending_imaging = ImagingStudy.objects.filter(
            encounter__in=active_encounters,
            status='completed',
            is_deleted=False
        ).select_related(
            'encounter__patient__primary_insurance'
        ).order_by('-report_verified_at', '-performed_at')[:20]
        
        # Add to results ready - skip if already in any queue
        for study in pending_imaging:
            encounter_id = str(study.encounter.id)
            if encounter_id in seen_encounter_ids:
                continue
            if encounter_id not in results_by_encounter:
                seen_encounter_ids.add(encounter_id)
                queue_by_status['results_ready']['patients'].append({
                    'encounter_id': encounter_id,
                    'patient_name': study.patient.full_name,
                    'patient_id': str(study.patient.id),
                    'mrn': study.patient.mrn,
                    'encounter_type': study.encounter.get_encounter_type_display(),
                    'imaging_study': study,
                    'results_count': 1,
                    'has_abnormal': False,
                    'django_patient': study.patient,
                    'django_encounter': study.encounter,
                })
    except ImportError:
        pass
    
    # Check for encounters ready for discharge (consultation done, no pending orders/results)
    # Skip if already in any queue to prevent duplicates
    for encounter in active_encounters:
        if str(encounter.id) in seen_encounter_ids:
            continue
        consultation_done = consultation_stages.filter(
            encounter=encounter,
            status='completed'
        ).exists()
        
        if consultation_done:
            # Check for pending orders
            has_pending = Order.objects.filter(
                encounter=encounter,
                status__in=['pending', 'in_progress'],
                is_deleted=False
            ).exists()
            
            # Check for pending flow stages
            has_pending_stages = PatientFlowStage.objects.filter(
                encounter=encounter,
                status__in=['pending', 'in_progress'],
                stage_type__in=['laboratory', 'imaging', 'pharmacy'],
                is_deleted=False
            ).exists()
            
            if not has_pending and not has_pending_stages:
                # Ready for discharge
                queue_by_status['ready_for_discharge']['patients'].append({
                    'encounter_id': str(encounter.id),
                    'patient_name': encounter.patient.full_name,
                    'patient_id': str(encounter.patient.id),
                    'mrn': encounter.patient.mrn,
                    'encounter_type': encounter.get_encounter_type_display(),
                    'chief_complaint': encounter.chief_complaint or 'No complaint recorded',
                    'wait_minutes': 0,
                    'wait_start': encounter.started_at or encounter.created,
                    'django_patient': encounter.patient,
                    'django_encounter': encounter,
                })
    
    # Sort by wait time (longest first)
    for status_key in ['waiting_consultation', 'in_consultation', 'waiting_results']:
        if status_key in queue_by_status:
            queue_by_status[status_key]['patients'].sort(key=lambda x: x['wait_minutes'], reverse=True)
    
    # Sort results ready by abnormal first, then by time
    if 'results_ready' in queue_by_status:
        queue_by_status['results_ready']['patients'].sort(
            key=lambda x: (not x.get('has_abnormal', False), x.get('wait_start', now)),
            reverse=True
        )
    
    # Statistics
    total_waiting = len(queue_by_status['waiting_consultation']['patients'])
    total_in_consultation = len(queue_by_status['in_consultation']['patients'])
    total_waiting_results = len(queue_by_status['waiting_results']['patients'])
    total_results_ready = len(queue_by_status['results_ready']['patients'])
    total_ready_discharge = len(queue_by_status['ready_for_discharge']['patients'])
    
    total_patients = (
        total_waiting + total_in_consultation + total_waiting_results + 
        total_results_ready + total_ready_discharge
    )
    
    # Calculate average wait time - FIXED: Only include reasonable wait times
    all_wait_times = []
    for status_key in ['waiting_consultation', 'in_consultation', 'waiting_results']:
        for patient in queue_by_status[status_key]['patients']:
            wait_time = patient.get('wait_minutes', 0)
            # Only include wait times <= 24 hours (1440 minutes)
            if wait_time <= 1440:
                all_wait_times.append(wait_time)
    
    avg_wait_time = int(sum(all_wait_times) / len(all_wait_times)) if all_wait_times else 0
    
    delayed_count = sum(
        1 for status_key in ['waiting_consultation', 'in_consultation']
        for p in queue_by_status[status_key]['patients']
        if 30 < p.get('wait_minutes', 0) <= 1440  # Only count delays between 30 min and 24 hours
    )
    
    # Abnormal results count
    abnormal_count = sum(
        1 for p in queue_by_status['results_ready']['patients']
        if p.get('has_abnormal', False)
    )
    
    # Get available dates for calendar (last 30 days + today)
    all_doctor_encounters = Encounter.objects.filter(
        provider=staff,
        is_deleted=False
    )
    
    available_dates = []
    for i in range(30):
        check_date = today - timedelta(days=i)
        has_encounters = all_doctor_encounters.filter(
            started_at__date=check_date
        ).exists()
        if has_encounters or check_date == today:
            available_dates.append(check_date)
    
    context = {
        'title': 'Doctor Patient Flowboard',
        'queue_by_status': queue_by_status,
        'total_patients': total_patients,
        'total_waiting': total_waiting,
        'total_in_consultation': total_in_consultation,
        'total_waiting_results': total_waiting_results,
        'total_results_ready': total_results_ready,
        'total_ready_discharge': total_ready_discharge,
        'avg_wait_time': avg_wait_time,
        'delayed_count': delayed_count,
        'abnormal_count': abnormal_count,
        'now': now,
        'today': today,
        'selected_date': selected_date,
        'available_dates': available_dates,
        'is_today': selected_date == today,
        'doctor_name': staff.user.get_full_name() or staff.user.username,
    }
    
    return render(request, 'hospital/doctor_patient_flowboard.html', context)

"""
Nurse Patient Flowboard
Shows all patients who visited the facility
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Count
from datetime import timedelta

from .models import Encounter, Patient
from .models_workflow import PatientFlowStage


@login_required
def nurse_patient_flowboard(request):
    """
    Nurse flowboard showing all patients who visited the facility
    Comprehensive view of all patient activity
    """
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Get all encounters (active and recent completed)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # Base queryset for active encounters
    active_encounters = Encounter.objects.filter(
        status='active',
        is_deleted=False
    ).select_related('patient__primary_insurance', 'provider__user')
    
    # Base queryset for recent completed encounters
    recent_completed = Encounter.objects.filter(
        status='completed',
        is_deleted=False,
        ended_at__date__gte=week_ago
    ).select_related('patient__primary_insurance', 'provider__user')
    
    # Apply search filter if provided
    if search_query:
        search_filter = (
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(patient__middle_name__icontains=search_query) |
            Q(patient__mrn__icontains=search_query) |
            Q(patient__phone_number__icontains=search_query)
        )
        active_encounters = active_encounters.filter(search_filter)
        recent_completed = recent_completed.filter(search_filter)
    
    # Order and limit
    active_encounters = active_encounters.order_by('-started_at')
    recent_completed = recent_completed.order_by('-ended_at')[:100]
    
    # Get flow stages for active encounters
    flow_stages = PatientFlowStage.objects.filter(
        encounter__in=active_encounters,
        is_deleted=False
    ).select_related('encounter__patient__primary_insurance', 'completed_by__user')
    
    # Organize by stage type
    queue_by_stage = {
        'registration': {
            'name': 'Registration',
            'icon': 'person-plus',
            'color': '#6366F1',
            'bg': 'rgba(99, 102, 241, 0.1)',
            'patients': []
        },
        'triage': {
            'name': 'Triage',
            'icon': 'shield-check',
            'color': '#EF4444',
            'bg': 'rgba(239, 68, 68, 0.1)',
            'patients': []
        },
        'vitals': {
            'name': 'Vital Signs',
            'icon': 'heart-pulse',
            'color': '#F59E0B',
            'bg': 'rgba(245, 158, 11, 0.1)',
            'patients': []
        },
        'consultation': {
            'name': 'Consultation',
            'icon': 'clipboard2-pulse',
            'color': '#667eea',
            'bg': 'rgba(102, 126, 234, 0.1)',
            'patients': []
        },
        'laboratory': {
            'name': 'Laboratory',
            'icon': 'flask',
            'color': '#06B6D4',
            'bg': 'rgba(6, 182, 212, 0.1)',
            'patients': []
        },
        'imaging': {
            'name': 'Imaging',
            'icon': 'x-ray',
            'color': '#8B5CF6',
            'bg': 'rgba(139, 92, 246, 0.1)',
            'patients': []
        },
        'pharmacy': {
            'name': 'Pharmacy',
            'icon': 'capsule',
            'color': '#10B981',
            'bg': 'rgba(16, 185, 129, 0.1)',
            'patients': []
        },
        'billing': {
            'name': 'Billing',
            'icon': 'receipt',
            'color': '#F59E0B',
            'bg': 'rgba(245, 158, 11, 0.1)',
            'patients': []
        },
        'payment': {
            'name': 'Payment',
            'icon': 'credit-card',
            'color': '#14B8A6',
            'bg': 'rgba(20, 184, 166, 0.1)',
            'patients': []
        },
    }
    
    now = timezone.now()
    
    # Stage order - each encounter appears in ONLY the leftmost (current) stage
    STAGE_ORDER = [
        'registration', 'triage', 'vitals', 'consultation',
        'laboratory', 'imaging', 'pharmacy', 'treatment',
        'admission', 'billing', 'payment', 'discharge'
    ]
    
    # Build encounter -> current stage mapping (leftmost pending/in_progress)
    encounter_current_stage = {}
    for stage in flow_stages.filter(status__in=['pending', 'in_progress']):
        enc_id = str(stage.encounter_id)
        stage_order_idx = STAGE_ORDER.index(stage.stage_type) if stage.stage_type in STAGE_ORDER else 999
        if enc_id not in encounter_current_stage or stage_order_idx < encounter_current_stage[enc_id][0]:
            encounter_current_stage[enc_id] = (stage_order_idx, stage)
    
    # Populate queue - each encounter in only ONE stage
    for enc_id, (_, stage) in encounter_current_stage.items():
        stage_type = stage.stage_type
        if stage_type in queue_by_stage:
            wait_minutes = 0
            if stage.started_at:
                wait_duration = now - stage.started_at
                wait_minutes = int(wait_duration.total_seconds() / 60)
            
            queue_by_stage[stage_type]['patients'].append({
                'encounter_id': str(stage.encounter.pk),
                'patient_name': stage.encounter.patient.full_name,
                'mrn': stage.encounter.patient.mrn,
                'encounter_type': stage.encounter.get_encounter_type_display(),
                'wait_minutes': wait_minutes,
                'wait_start': stage.started_at or stage.created,
                'staff': stage.completed_by.user.get_full_name() if stage.completed_by and stage.completed_by.user else None,
                'django_patient': stage.encounter.patient,
                'django_encounter': stage.encounter,
            })
    
    # Add active encounters without flow stages to registration
    for encounter in active_encounters:
        has_stage = any(s['encounter_id'] == str(encounter.id) for stage_list in queue_by_stage.values() for s in stage_list['patients'])
        if not has_stage:
            queue_by_stage['registration']['patients'].append({
                'encounter_id': str(encounter.pk),
                'patient_name': encounter.patient.full_name,
                'mrn': encounter.patient.mrn,
                'encounter_type': encounter.get_encounter_type_display(),
                'wait_minutes': int((now - (encounter.started_at or encounter.created)).total_seconds() / 60),
                'wait_start': encounter.started_at or encounter.created,
                'staff': None,
                'django_patient': encounter.patient,
                'django_encounter': encounter,
            })
    
    # Sort by wait time (longest first)
    for stage in queue_by_stage.values():
        stage['patients'].sort(key=lambda x: x['wait_minutes'], reverse=True)
    
    # Statistics
    total_active = active_encounters.count()
    total_recent = recent_completed.count()
    total_patients = total_active + total_recent
    
    # Calculate average wait time
    all_wait_times = []
    for stage in queue_by_stage.values():
        for patient in stage['patients']:
            all_wait_times.append(patient['wait_minutes'])
    avg_wait_time = int(sum(all_wait_times) / len(all_wait_times)) if all_wait_times else 0
    
    delayed_count = sum(1 for stage in queue_by_stage.values() for p in stage['patients'] if p['wait_minutes'] > 60)
    
    context = {
        'title': 'Nurse Patient Flowboard - All Facility Visitors',
        'queue_by_stage': queue_by_stage,
        'total_patients': total_patients,
        'total_active': total_active,
        'total_recent': total_recent,
        'avg_wait_time': avg_wait_time,
        'delayed_count': delayed_count,
        'recent_completed': recent_completed[:20],
        'now': now,
        'search_query': search_query,
    }
    
    return render(request, 'hospital/nurse_patient_flowboard.html', context)

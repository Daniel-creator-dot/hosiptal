"""
Queue management views for doctor console and public feeds.
"""
import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Department
from .models_advanced import Queue
from .models_queue import QueueEntry, HealthTip
from .services.queue_service import queue_service


def _get_request_data(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body.decode() or '{}')
        except ValueError:
            return {}
    return request.POST


def _resolve_department(request, user, *, allow_fallback=True, data=None):
    """
    Determine which department context to use for queue operations.
    """
    payload = data or {}
    department_id = payload.get('department') or request.POST.get('department') or request.GET.get('department')
    if department_id:
        return get_object_or_404(Department, pk=department_id, is_deleted=False)

    staff_profile = getattr(user, 'staff', None) if user else None
    if staff_profile and staff_profile.department:
        return staff_profile.department

    if allow_fallback:
        return Department.objects.filter(is_active=True, is_deleted=False).order_by('name').first()

    raise ValueError("Department context required")


def _serialize_entry(entry):
    if not entry:
        return None
    
    # Get patient - QueueEntry has both patient and encounter relationships
    patient = getattr(entry, 'patient', None)
    if not patient and hasattr(entry, 'encounter') and entry.encounter:
        patient = entry.encounter.patient
    
    # Handle queue_number - QueueEntry has CharField, Queue has IntegerField
    queue_number = str(getattr(entry, 'queue_number', ''))
    
    # Handle priority - QueueEntry has IntegerField with get_priority_display(), Queue has CharField
    if hasattr(entry, 'get_priority_display'):
        priority = entry.get_priority_display()
    else:
        priority = getattr(entry, 'priority', 'normal')
        if isinstance(priority, str):
            # For Queue model, capitalize the priority
            priority = priority.replace('_', ' ').title()
    
    # Handle room_number - only QueueEntry has this
    room_number = getattr(entry, 'room_number', None) or ''
    
    # Handle assigned_doctor - only QueueEntry has this
    assigned_doctor = ''
    if hasattr(entry, 'assigned_doctor') and entry.assigned_doctor:
        assigned_doctor = entry.assigned_doctor.get_full_name()
    
    # Handle timestamps - different field names for different models
    # QueueEntry: check_in_time, called_time, started_time
    # Queue: checked_in_at, called_at, completed_at
    check_in_time = None
    called_time = None
    started_time = None
    
    if hasattr(entry, 'check_in_time'):
        # QueueEntry model
        check_in_time = entry.check_in_time.isoformat() if entry.check_in_time else None
        called_time = entry.called_time.isoformat() if entry.called_time else None
        started_time = entry.started_time.isoformat() if entry.started_time else None
    elif hasattr(entry, 'checked_in_at'):
        # Queue model
        check_in_time = entry.checked_in_at.isoformat() if entry.checked_in_at else None
        called_time = entry.called_at.isoformat() if entry.called_at else None
        started_time = entry.completed_at.isoformat() if entry.completed_at else None
    
    return {
        'id': str(entry.id),
        'queue_number': queue_number,
        'patient': patient.full_name if patient else 'Unknown',
        'mrn': patient.mrn if patient else '',
        'status': entry.status,
        'priority': priority,
        'room_number': room_number,
        'assigned_doctor': assigned_doctor,
        'called_time': called_time,
        'started_time': started_time,
        'check_in_time': check_in_time,
    }


@login_required
def doctor_queue_console(request):
    department = _resolve_department(request, request.user)
    today = timezone.now().date()

    assigned_entries = QueueEntry.objects.filter(
        queue_date=today,
        department=department,
        is_deleted=False,
        assigned_doctor=request.user,
        status__in=['checked_in', 'called', 'in_progress'],
    ).order_by('status', 'priority', 'sequence_number')

    unassigned_entries = QueueEntry.objects.filter(
        queue_date=today,
        department=department,
        is_deleted=False,
        assigned_doctor__isnull=True,
        status='checked_in',
    ).order_by('priority', 'sequence_number')[:15]

    context = {
        'department': department,
        'assigned_entries': assigned_entries,
        'unassigned_entries': unassigned_entries,
        'departments': Department.objects.filter(is_active=True, is_deleted=False),
    }
    return render(request, 'hospital/queue_doctor_console.html', context)


def _lock_next_entry(department, doctor):
    """
    Atomically fetch the next waiting entry for a department.
    """
    today = timezone.now().date()
    with transaction.atomic():
        entry = (
            QueueEntry.objects.select_for_update(skip_locked=True)
            .filter(
                queue_date=today,
                department=department,
                status='checked_in',
                is_deleted=False,
            )
            .order_by('priority', 'sequence_number')
            .first()
        )
        if not entry:
            return None
        if not entry.assigned_doctor:
            entry.assigned_doctor = doctor if getattr(doctor, 'staff', None) else entry.assigned_doctor
            entry.save(update_fields=['assigned_doctor', 'modified'])
        return entry


@login_required
@require_POST
def queue_call_next(request):
    payload = _get_request_data(request)
    department = _resolve_department(request, request.user, data=payload)
    room_number = (payload.get('room_number') or '').strip()

    entry = _lock_next_entry(department, request.user)
    if not entry:
        return JsonResponse({'error': 'queue_empty'}, status=404)

    queue_service.call_next_patient(entry, room_number=room_number)
    return JsonResponse({'entry': _serialize_entry(entry)})


def _has_entries_ahead(entry):
    """
    Returns True if there are entries ahead that should be handled first.
    """
    return QueueEntry.objects.filter(
        queue_date=entry.queue_date,
        department=entry.department,
        status='checked_in',
        is_deleted=False,
    ).filter(
        Q(priority__lt=entry.priority)
        | Q(priority=entry.priority, sequence_number__lt=entry.sequence_number)
    ).exists()


@login_required
@require_POST
def queue_call_specific(request, queue_id):
    payload = _get_request_data(request)
    department = _resolve_department(request, request.user, data=payload)
    room_number = (payload.get('room_number') or '').strip()
    entry = get_object_or_404(
        QueueEntry,
        pk=queue_id,
        department=department,
        is_deleted=False,
    )

    if entry.status not in ['checked_in', 'called']:
        return JsonResponse({'error': 'invalid_status'}, status=400)

    if _has_entries_ahead(entry) and entry.priority > 1:
        return JsonResponse({'error': 'ahead_entries'}, status=409)

    if not entry.assigned_doctor:
        entry.assigned_doctor = request.user if getattr(request.user, 'staff', None) else entry.assigned_doctor
        entry.save(update_fields=['assigned_doctor', 'modified'])

    queue_service.call_next_patient(entry, room_number=room_number)
    return JsonResponse({'entry': _serialize_entry(entry)})


def _get_entry_or_404(queue_id, user):
    entry = get_object_or_404(QueueEntry, pk=queue_id, is_deleted=False)
    staff_profile = getattr(user, 'staff', None)
    if staff_profile and entry.department != staff_profile.department:
        raise PermissionDenied("You cannot manage queues for another department.")
    return entry


@login_required
@require_POST
def queue_start_entry(request, queue_id):
    entry = _get_entry_or_404(queue_id, request.user)
    queue_service.start_consultation(entry)
    return JsonResponse({'entry': _serialize_entry(entry)})


@login_required
@require_POST
def queue_complete_entry(request, queue_id):
    entry = _get_entry_or_404(queue_id, request.user)
    queue_service.complete_consultation(entry)
    return JsonResponse({'entry': _serialize_entry(entry)})


@login_required
@require_POST
def queue_mark_no_show(request, queue_id):
    entry = _get_entry_or_404(queue_id, request.user)
    queue_service.mark_no_show(entry)
    return JsonResponse({'entry': _serialize_entry(entry)})


def _serialize_tip(tip):
    if not tip:
        return None
    try:
        return {
            'title': getattr(tip, 'title', ''),
            'message': getattr(tip, 'message', ''),
            'category': getattr(tip, 'category', ''),
            'audience': getattr(tip, 'audience', ''),
            'icon': getattr(tip, 'icon', '💡'),
            'accent_color': getattr(tip, 'accent_color', '#3B82F6'),
        }
    except Exception:
        return None


def queue_status_feed(request):
    """
    JSON endpoint consumed by the public queue display.
    """
    today = timezone.now().date()
    
    # Match queue_display behavior: only scope to a department if explicitly requested.
    department = None
    department_id = request.GET.get('department')
    if department_id:
        try:
            department = Department.objects.get(pk=department_id, is_deleted=False)
        except (Department.DoesNotExist, ValueError):
            department = None

    # Build query filters
    waiting_filters = {
        'queue_date': today,
        'status__in': ['checked_in', 'called', 'in_progress'],
        'is_deleted': False,
    }
    in_progress_filters = {
        'queue_date': today,
        'status': 'in_progress',
        'is_deleted': False,
    }
    completed_filters = {
        'queue_date': today,
        'status': 'completed',
        'is_deleted': False,
    }
    
    if department:
        waiting_filters['department'] = department
        in_progress_filters['department'] = department
        completed_filters['department'] = department

    use_queue_entry = QueueEntry.objects.filter(queue_date=today, is_deleted=False).exists()
    
    if use_queue_entry:
        waiting_qs = QueueEntry.objects.filter(**waiting_filters).order_by('priority', 'sequence_number')
        in_progress_qs = QueueEntry.objects.filter(**in_progress_filters).order_by('called_time', 'priority')
        completed_qs = QueueEntry.objects.filter(**completed_filters)
        
        now_serving = in_progress_qs.first()
        upcoming = list(waiting_qs)
        
        completed_today = completed_qs.count()
        
        from django.db.models import Avg
        avg_wait = completed_qs.filter(actual_wait_minutes__isnull=False).aggregate(avg=Avg('actual_wait_minutes'))
        avg_wait_minutes = int(avg_wait['avg'] or 0) if avg_wait['avg'] else None
        
        waiting_count = waiting_qs.count()
        in_progress_count = in_progress_qs.count()
    else:
        queue_filters = {
            'is_deleted': False,
            'checked_in_at__date': today,
        }
        if department:
            queue_filters['department'] = department
        
        all_queue = Queue.objects.filter(**queue_filters).select_related('encounter__patient').order_by('priority', 'queue_number')
        
        waiting_qs = all_queue.filter(status='waiting')
        in_progress_qs = all_queue.filter(status='in_progress')
        completed_qs = all_queue.filter(status='completed')
        
        now_serving = in_progress_qs.order_by('called_at').first()
        if not now_serving:
            now_serving = waiting_qs.first()
        upcoming = list(waiting_qs.order_by('queue_number')[:5])
        
        completed_today = completed_qs.count()
        
        avg_wait_minutes = None
        completed_with_times = completed_qs.exclude(checked_in_at__isnull=True).exclude(completed_at__isnull=True)
        if completed_with_times.exists():
            total_wait = 0
            count = 0
            for entry in completed_with_times:
                wait_seconds = (entry.completed_at - entry.checked_in_at).total_seconds()
                total_wait += wait_seconds / 60
                count += 1
            if count > 0:
                avg_wait_minutes = int(total_wait / count)
        
        # Include in-progress entries in waiting count to keep badge stable
        waiting_count = waiting_qs.count() + in_progress_qs.count()
        in_progress_count = in_progress_qs.count()
    
    # Get health tips with error handling
    tips = []
    try:
        if HealthTip and hasattr(HealthTip, 'objects'):
            tips = [
                _serialize_tip(tip)
                for tip in HealthTip.objects.filter(is_active=True).order_by('display_order')[:10]
                if hasattr(tip, 'is_visible') and tip.is_visible(today)
            ]
    except Exception as e:
        # If HealthTip model doesn't exist or has issues, just use empty list
        tips = []
    
    # Serialize entries with error handling
    try:
        now_serving_data = _serialize_entry(now_serving)
    except Exception as e:
        now_serving_data = None
    
    try:
        up_next_data = [_serialize_entry(entry) for entry in upcoming]
    except Exception as e:
        up_next_data = []
    
    response = {
        'now_serving': now_serving_data,
        'up_next': up_next_data,
        'health_tips': tips,
        'waiting_count': int(waiting_count or 0),
        'in_progress_count': int(in_progress_count or 0),
        'completed_today': int(completed_today or 0),
        'avg_wait_minutes': avg_wait_minutes,
        'timestamp': timezone.now().isoformat(),
    }
    return JsonResponse(response)




"""
Queue management views for doctor console and public feeds.
"""
import json
from datetime import timedelta

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
    department_id = payload.get('department') or (request.POST.get('department') if hasattr(request, 'POST') else None) or (request.GET.get('department') if hasattr(request, 'GET') else None)
    if department_id:
        try:
            return Department.objects.get(pk=department_id, is_deleted=False)
        except (Department.DoesNotExist, ValueError):
            pass  # Fall through to other methods

    staff_profile = getattr(user, 'staff', None) if user else None
    if staff_profile and staff_profile.department:
        return staff_profile.department

    if allow_fallback:
        dept = Department.objects.filter(is_active=True, is_deleted=False).order_by('name').first()
        if dept:
            return dept

    raise ValueError("Department context required")


def _serialize_entry(entry):
    if not entry:
        return None
    
    try:
        # Get patient - QueueEntry has both patient and encounter relationships
        patient = None
        try:
            patient = getattr(entry, 'patient', None)
        except Exception:
            pass
        
        if not patient and hasattr(entry, 'encounter'):
            try:
                if entry.encounter:
                    patient = entry.encounter.patient
            except Exception:
                pass
        
        # Handle queue_number for public feed:
        # QueueEntry -> display_ticket_number (no ACC prefix), Queue -> original number
        try:
            if isinstance(entry, QueueEntry):
                queue_number = str(getattr(entry, 'display_ticket_number', '') or '')
            else:
                queue_number = str(getattr(entry, 'queue_number', ''))
        except Exception:
            queue_number = ''
        
        # Handle priority - QueueEntry has IntegerField with get_priority_display(), Queue has CharField
        priority = 'Normal'
        try:
            if hasattr(entry, 'get_priority_display'):
                priority = entry.get_priority_display()
            else:
                priority_val = getattr(entry, 'priority', 'normal')
                if isinstance(priority_val, str):
                    priority = priority_val.replace('_', ' ').title()
                else:
                    priority = str(priority_val)
        except Exception:
            pass
        
        # Handle room_number - only QueueEntry has this
        room_number = ''
        try:
            room_number = getattr(entry, 'room_number', None) or ''
        except Exception:
            pass
        
        # Clinician name for boards (QueueEntry: assigned doctor or encounter provider)
        assigned_doctor = ''
        try:
            if isinstance(entry, QueueEntry):
                assigned_doctor = entry.get_display_clinician_name()
        except Exception:
            pass
        if not assigned_doctor:
            try:
                if hasattr(entry, 'assigned_doctor') and entry.assigned_doctor:
                    u = entry.assigned_doctor
                    assigned_doctor = (u.get_full_name() or u.username or '').strip() if hasattr(u, 'get_full_name') else str(u)
            except Exception:
                pass
        if not assigned_doctor:
            try:
                enc = getattr(entry, 'encounter', None)
                if enc and getattr(enc, 'provider', None):
                    prov = enc.provider
                    u = getattr(prov, 'user', None)
                    if u:
                        assigned_doctor = (u.get_full_name() or u.username or '').strip()
            except Exception:
                pass
        
        # Handle timestamps - different field names for different models
        check_in_time = None
        called_time = None
        started_time = None
        
        try:
            if hasattr(entry, 'check_in_time'):
                check_in_time = entry.check_in_time.isoformat() if entry.check_in_time else None
                called_time = entry.called_time.isoformat() if entry.called_time else None
                started_time = entry.started_time.isoformat() if entry.started_time else None
            elif hasattr(entry, 'checked_in_at'):
                check_in_time = entry.checked_in_at.isoformat() if entry.checked_in_at else None
                called_time = entry.called_at.isoformat() if entry.called_at else None
                started_time = entry.completed_at.isoformat() if entry.completed_at else None
        except Exception:
            pass
        
        patient_name = ''
        patient_mrn = ''
        try:
            if patient:
                patient_name = patient.full_name if hasattr(patient, 'full_name') else (f"{patient.first_name} {patient.last_name}".strip() if hasattr(patient, 'first_name') else str(patient))
                patient_mrn = getattr(patient, 'mrn', '') or ''
        except Exception:
            pass
        
        status = ''
        try:
            status = getattr(entry, 'status', '')
        except Exception:
            pass
        
        entry_id = ''
        try:
            entry_id = str(entry.id)
        except Exception:
            pass
        
        return {
            'id': entry_id,
            'queue_number': queue_number,
            'patient': patient_name,
            'mrn': patient_mrn,
            'status': status,
            'priority': priority,
            'room_number': room_number,
            'assigned_doctor': assigned_doctor,
            'called_time': called_time,
            'started_time': started_time,
            'check_in_time': check_in_time,
        }
    except Exception as e:
        # If serialization fails, return minimal data
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error serializing queue entry: {str(e)}", exc_info=True)
        try:
            return {
                'id': str(entry.id) if hasattr(entry, 'id') else '',
                'queue_number': str(getattr(entry, 'display_ticket_number', getattr(entry, 'queue_number', ''))),
                'patient': '',
                'mrn': '',
                'status': getattr(entry, 'status', ''),
                'priority': 'Normal',
                'room_number': '',
                'assigned_doctor': '',
                'called_time': None,
                'started_time': None,
                'check_in_time': None,
            }
        except Exception:
            return None
    except Exception as e:
        # If serialization fails, return minimal data
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error serializing queue entry: {str(e)}", exc_info=True)
        try:
            return {
                'id': str(entry.id) if hasattr(entry, 'id') else '',
                'queue_number': str(getattr(entry, 'display_ticket_number', getattr(entry, 'queue_number', ''))),
                'patient': '',
                'mrn': '',
                'status': getattr(entry, 'status', ''),
                'priority': 'Normal',
                'room_number': '',
                'assigned_doctor': '',
                'called_time': None,
                'started_time': None,
                'check_in_time': None,
            }
        except Exception:
            return None


@login_required
def doctor_queue_console(request):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        department = _resolve_department(request, request.user)
        today = timezone.now().date()
        
        logger.debug(f"Doctor queue console - User: {request.user.username}, Department: {department.name if department else 'None'}, Date: {today}")

        # Get entries assigned to this doctor - show ALL assigned patients regardless of department
        # This ensures doctors see all their assigned patients even if they work across departments
        assigned_entries = QueueEntry.objects.filter(
            queue_date=today,
            is_deleted=False,
            assigned_doctor=request.user,
            status__in=['checked_in', 'called', 'vitals_completed', 'in_progress'],
        ).select_related('patient', 'department', 'assigned_doctor', 'encounter', 'encounter__patient').order_by('department__name', 'status', 'priority', 'sequence_number')
        
        assigned_count = assigned_entries.count()
        logger.debug(f"Found {assigned_count} assigned entries for doctor {request.user.username}")

        # Get unassigned entries in the current department
        # These are patients waiting without a specific doctor assignment
        unassigned_filter = {
            'queue_date': today,
            'is_deleted': False,
            'assigned_doctor__isnull': True,
            'status': 'checked_in',
        }
        if department:
            unassigned_filter['department'] = department
        
        unassigned_entries = QueueEntry.objects.filter(
            **unassigned_filter
        ).select_related('patient', 'department', 'encounter', 'encounter__patient').order_by('priority', 'sequence_number')[:15]
        
        unassigned_count = unassigned_entries.count()
        logger.debug(f"Found {unassigned_count} unassigned entries in department {department.name if department else 'All'}")
        
        # Debug: Check all today's entries for this doctor to see what's happening
        all_today_entries = QueueEntry.objects.filter(
            queue_date=today,
            is_deleted=False
        ).select_related('patient', 'department', 'assigned_doctor')
        
        logger.debug(f"Total queue entries today: {all_today_entries.count()}")
        if assigned_count == 0:
            # Log why no entries found
            entries_with_doctor = all_today_entries.filter(assigned_doctor__isnull=False)
            logger.debug(f"Total entries with assigned doctor today: {entries_with_doctor.count()}")
            for entry in entries_with_doctor[:5]:  # Log first 5 for debugging
                logger.debug(f"Entry {entry.queue_number}: assigned_doctor={entry.assigned_doctor}, department={entry.department}, status={entry.status}")
    except Exception as e:
        logger.error(f"Error in doctor_queue_console: {str(e)}", exc_info=True)
        # Fallback to basic query
        today = timezone.now().date()
        department = None
        try:
            department = _resolve_department(request, request.user)
        except:
            pass
        
        assigned_entries = QueueEntry.objects.filter(
            queue_date=today,
            is_deleted=False,
            assigned_doctor=request.user,
            status__in=['checked_in', 'called', 'vitals_completed', 'in_progress'],
        ).select_related('patient', 'department', 'assigned_doctor', 'encounter', 'encounter__patient').order_by('status', 'priority', 'sequence_number')
        
        unassigned_entries = QueueEntry.objects.filter(
            queue_date=today,
            is_deleted=False,
            assigned_doctor__isnull=True,
            status='checked_in',
        ).select_related('patient', 'department', 'encounter', 'encounter__patient').order_by('priority', 'sequence_number')[:15]
        
        if department:
            unassigned_entries = unassigned_entries.filter(department=department)
    
    # Get current room assignment for this doctor
    current_room_assignment = None
    try:
        from .models_consulting_rooms import DoctorRoomAssignment
        current_room_assignment = DoctorRoomAssignment.objects.filter(
            doctor=request.user,
            assignment_date=today,
            is_active=True,
            is_deleted=False
        ).select_related('room').first()
    except Exception:
        pass
    
    # Get available rooms for room selection
    available_rooms = []
    try:
        from .models_consulting_rooms import ConsultingRoom
        available_rooms = ConsultingRoom.objects.filter(
            is_active=True,
            status='available',
            is_deleted=False
        ).order_by('room_number')
    except ImportError:
        pass

    context = {
        'department': department,
        'assigned_entries': assigned_entries,
        'unassigned_entries': unassigned_entries,
        'departments': Department.objects.filter(is_active=True, is_deleted=False),
        'current_room_assignment': current_room_assignment,
        'available_rooms': available_rooms,
    }
    return render(request, 'hospital/queue_doctor_console.html', context)


def _lock_next_entry(department, doctor):
    """
    Atomically fetch the next waiting entry for a department.
    Tries the selected department first, then entries with no department set (common
    when check-in did not attach a department) so Call next still works.
    """
    today = timezone.now().date()
    base = dict(
        queue_date=today,
        status='checked_in',
        is_deleted=False,
    )
    staff = getattr(doctor, 'staff', None) if doctor else None
    assign_doctor = bool(
        staff and getattr(staff, 'profession', None) == 'doctor'
    )
    # Prefer this department, then rows with no department, then any department
    # (patients often check in under Lab/OPD while the doctor has Medicine selected).
    dept_filters = []
    if department is not None:
        dept_filters.append({'department': department})
    dept_filters.append({'department__isnull': True})
    dept_filters.append({})  # any department, same day

    with transaction.atomic():
        for extra in dept_filters:
            entry = (
                QueueEntry.objects.select_for_update(skip_locked=True)
                .filter(**base, **extra)
                .order_by('priority', 'sequence_number')
                .first()
            )
            if not entry:
                continue
            if assign_doctor:
                entry.assigned_doctor = doctor
                entry.save(update_fields=['assigned_doctor', 'modified'])
            return entry
    return None


@login_required
@require_POST
def queue_call_next(request):
    """
    API endpoint to call the next patient in queue.
    Accepts POST requests with JSON payload containing optional 'department' and 'room_number'.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        today = timezone.now().date()
        # Log the request for debugging
        logger.info(f"queue_call_next called by user: {request.user.username}, method: {request.method}")
        
        payload = _get_request_data(request)
        logger.debug(f"Payload received: {payload}")
        
        try:
            department = _resolve_department(request, request.user, data=payload)
            logger.debug(f"Resolved department: {department.name if department else None}")
        except (ValueError, Department.DoesNotExist) as e:
            logger.warning(f"Department resolution failed: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'department_required',
                'message': 'Department is required. Please select a department or ensure you are assigned to one.'
            }, status=400)
        
        room_number = (payload.get('room_number') or '').strip()
        logger.debug(f"Room number: {room_number or 'None'}")

        entry = _lock_next_entry(department, request.user)
        if not entry:
            logger.info(f"No patients found in queue for department: {department.name}")
            checked_in_total = QueueEntry.objects.filter(
                queue_date=today,
                status='checked_in',
                is_deleted=False,
            ).count()
            called_or_busy = QueueEntry.objects.filter(
                queue_date=today,
                status__in=['called', 'in_progress'],
                is_deleted=False,
            ).count()
            msg = (
                'No one is waiting in "Checked in" status for call next. '
                'Patients already shown as Called or In consultation must use the megaphone on their row, not Call next.'
            )
            if checked_in_total == 0 and called_or_busy > 0:
                msg += f' Today there are {called_or_busy} ticket(s) already called or in consultation.'
            elif checked_in_total == 0:
                msg += ' There are no checked-in tickets left in the queue for today.'
            return JsonResponse({
                'success': False,
                'error': 'queue_empty',
                'message': msg,
                'checked_in_waiting_count': checked_in_total,
                'called_or_in_progress_count': called_or_busy,
            }, status=200)  # Changed to 200 so it doesn't trigger generic error handler

        logger.info(f"Calling next patient: {entry.queue_number}")

        # Check if user is a doctor (safely)
        doctor_user = None
        if hasattr(request.user, 'staff') and request.user.staff:
            try:
                if getattr(request.user.staff, 'profession', None) == 'doctor':
                    doctor_user = request.user
                    logger.debug(f"Doctor user identified: {doctor_user.username}")
            except Exception as e:
                logger.warning(f"Error checking doctor status: {str(e)}")
                pass  # If there's any error accessing staff.profession, just use None
        
        # Call the next patient
        queue_service.call_next_patient(entry, room_number=room_number, doctor=doctor_user)
        try:
            entry.refresh_from_db()
        except Exception:
            pass

        serialized_entry = _serialize_entry(entry)
        logger.info(f"Successfully called patient: {entry.queue_number}")

        return JsonResponse({
            'success': True,
            'entry': serialized_entry or {},
            'message': f'Called patient #{entry.queue_number}'
        })
    except Exception as e:
        logger.error(f"Error in queue_call_next: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Unable to perform action: {str(e)}'
        }, status=500)


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


def _queue_specific_call_may_skip_ahead(entry, user):
    """
    Allow calling a specific ticket from My Consultations / doctor console even when
    others are waiting, if this user is the assigned clinician or the encounter provider.
    Strict FIFO still applies to generic 'call next' and uninvolved staff.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    try:
        if getattr(entry, 'assigned_doctor_id', None) == user.id:
            return True
        enc = getattr(entry, 'encounter', None)
        if enc and getattr(enc, 'provider_id', None):
            prov = enc.provider
            if prov and getattr(prov, 'user_id', None) == user.id:
                return True
    except Exception:
        pass
    return False


@login_required
@require_POST
def queue_call_specific(request, queue_id):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        payload = _get_request_data(request)
        room_number = (payload.get('room_number') or '').strip()
        
        # Try to get the entry - don't filter by department since doctors can work across departments
        try:
            entry = (
                QueueEntry.objects.select_related(
                    'encounter',
                    'encounter__provider',
                    'encounter__provider__user',
                    'assigned_doctor',
                )
                .get(pk=queue_id, is_deleted=False)
            )
        except QueueEntry.DoesNotExist:
            logger.warning(f"QueueEntry {queue_id} not found for user {request.user.username}")
            return JsonResponse({
                'success': False,
                'error': 'not_found',
                'message': 'Queue entry not found. It may have been deleted or does not exist.'
            }, status=404)
        
        logger.debug(f"Found queue entry {entry.queue_number} for action by {request.user.username}")

        if entry.status not in ['checked_in', 'called']:
            return JsonResponse({
                'success': False,
                'error': 'invalid_status',
                'message': 'Patient status is not valid for calling'
            }, status=400)

        if (
            _has_entries_ahead(entry)
            and entry.priority > 1
            and not _queue_specific_call_may_skip_ahead(entry, request.user)
        ):
            return JsonResponse({
                'success': False,
                'error': 'ahead_entries',
                'message': 'There are patients ahead in the queue'
            }, status=409)

        # Check if user is a doctor (safely)
        doctor_user = None
        staff = getattr(request.user, 'staff', None)
        if staff:
            try:
                if getattr(staff, 'profession', None) == 'doctor':
                    doctor_user = request.user
                elif entry.encounter_id and getattr(entry.encounter, 'provider_id', None) == staff.id:
                    doctor_user = request.user
            except Exception:
                pass

        if doctor_user:
            entry.assigned_doctor = doctor_user
            entry.save(update_fields=['assigned_doctor', 'modified'])

        # Use request.user as doctor for room detection
        if not doctor_user and entry.assigned_doctor:
            doctor_user = entry.assigned_doctor
        
        queue_service.call_next_patient(entry, room_number=room_number, doctor=doctor_user)
        return JsonResponse({
            'success': True,
            'entry': _serialize_entry(entry),
            'message': f'Called patient #{entry.queue_number}'
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in queue_call_specific: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Unable to perform action: {str(e)}'
        }, status=500)


def _get_entry_or_404(queue_id, user):
    """
    Get a queue entry by ID, with permission checks.
    Allows doctors to manage entries they're assigned to, regardless of department.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        entry = QueueEntry.objects.get(pk=queue_id, is_deleted=False)
    except QueueEntry.DoesNotExist:
        logger.warning(f"QueueEntry {queue_id} not found for user {user.username}")
        from django.http import Http404
        raise Http404("Queue entry not found")
    
    staff_profile = getattr(user, 'staff', None)
    
    # Allow if:
    # 1. User is assigned to this entry as the doctor
    # 2. Entry is unassigned and user is a doctor in the same department
    # 3. User is admin
    if entry.assigned_doctor == user:
        # User is the assigned doctor - always allow
        return entry
    
    if user.is_staff or user.is_superuser:
        # Admins can manage all entries
        return entry
    
    # Check department permission for unassigned entries
    if staff_profile and entry.department:
        if entry.department == staff_profile.department:
            # Same department - allow if user is a doctor
            if staff_profile.profession == 'doctor':
                return entry
    
    # Otherwise, check if entry has no assigned doctor and user is in the same department
    if not entry.assigned_doctor and staff_profile and entry.department:
        if entry.department == staff_profile.department and staff_profile.profession == 'doctor':
            return entry
    
    # Permission denied
    from django.core.exceptions import PermissionDenied
    raise PermissionDenied("You do not have permission to manage this queue entry.")


@login_required
@require_POST
def queue_start_entry(request, queue_id):
    entry = _get_entry_or_404(queue_id, request.user)
    queue_service.start_consultation(entry)
    return JsonResponse({'entry': _serialize_entry(entry)})


@login_required
@require_POST
def queue_complete_entry(request, queue_id):
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        entry = _get_entry_or_404(queue_id, request.user)
        queue_service.complete_consultation(entry)
        return JsonResponse({
            'success': True,
            'entry': _serialize_entry(entry),
            'message': f'Completed consultation for patient #{entry.queue_number}'
        })
    except QueueEntry.DoesNotExist:
        logger.warning(f"QueueEntry {queue_id} not found for user {request.user.username}")
        return JsonResponse({
            'success': False,
            'error': 'not_found',
            'message': 'Queue entry not found. It may have been deleted or does not exist.'
        }, status=404)
    except PermissionDenied as e:
        logger.warning(f"Permission denied for user {request.user.username} on queue entry {queue_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'permission_denied',
            'message': 'You do not have permission to manage this queue entry.'
        }, status=403)
    except Exception as e:
        logger.error(f"Error in queue_complete_entry: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'server_error',
            'message': f'Unable to complete consultation: {str(e)}'
        }, status=500)


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
    now = timezone.now()
    today = now.date()
    stale_cutoff = now - timedelta(minutes=20)
    
    # Match queue_display behavior: only scope to a department if explicitly requested.
    department = None
    department_id = request.GET.get('department')
    if department_id:
        try:
            department = Department.objects.get(pk=department_id, is_deleted=False)
        except (Department.DoesNotExist, ValueError):
            department = None

    in_progress_filters = {
        'queue_date': today,
        'status': 'in_progress',
        'is_deleted': False,
    }
    waiting_only_filters = {
        'queue_date': today,
        'status__in': ['checked_in', 'called'],
        'is_deleted': False,
    }
    completed_filters = {
        'queue_date': today,
        'status': 'completed',
        'is_deleted': False,
    }
    
    if department:
        waiting_only_filters['department'] = department
        in_progress_filters['department'] = department
        completed_filters['department'] = department

    use_queue_entry = QueueEntry.objects.filter(queue_date=today, is_deleted=False).exists()
    
    _qe_related = (
        'patient', 'department', 'assigned_doctor',
        'encounter', 'encounter__provider', 'encounter__provider__user',
    )
    if use_queue_entry:
        def _dedupe_entries(entries):
            """
            Keep first entry per patient (or encounter fallback) preserving input order.
            This stabilizes public board tickets when historical duplicate active rows exist.
            """
            seen = set()
            result = []
            for item in entries:
                key = getattr(item, 'patient_id', None) or getattr(item, 'encounter_id', None) or getattr(item, 'id', None)
                if key in seen:
                    continue
                seen.add(key)
                result.append(item)
            return result

        waiting_qs = (
            QueueEntry.objects.filter(**waiting_only_filters)
            .select_related(*_qe_related)
            .order_by('priority', 'sequence_number')
        )
        in_progress_qs = (
            QueueEntry.objects.filter(**in_progress_filters)
            .select_related(*_qe_related)
            .order_by('-called_time', 'priority', 'sequence_number')
        )
        called_qs = (
            QueueEntry.objects.filter(
                queue_date=today,
                status='called',
                is_deleted=False,
                **({'department': department} if department else {})
            )
            .select_related(*_qe_related)
            .order_by('-called_time', 'priority', 'sequence_number')
        )
        completed_qs = QueueEntry.objects.filter(**completed_filters)

        waiting_entries = _dedupe_entries(list(waiting_qs))
        in_progress_entries = _dedupe_entries(list(in_progress_qs))
        called_entries = _dedupe_entries(list(called_qs))

        in_progress_count = len(in_progress_entries)
        latest_in_progress = in_progress_entries[0] if in_progress_entries else None
        latest_called = called_entries[0] if called_entries else None
        # Prevent stale "001 stuck": pick the most recently called/active entry across both states.
        if latest_in_progress and latest_called:
            in_progress_mark = getattr(latest_in_progress, 'called_time', None) or getattr(latest_in_progress, 'started_time', None)
            called_mark = getattr(latest_called, 'called_time', None) or getattr(latest_called, 'started_time', None)
            if called_mark and (not in_progress_mark or called_mark >= in_progress_mark):
                now_serving = latest_called
            else:
                now_serving = latest_in_progress
        else:
            now_serving = latest_in_progress or latest_called or waiting_qs.first()
        # Safeguard: if active consultation is stale and patients are still waiting,
        # advance board display so "Now Serving" doesn't appear frozen.
        if now_serving and getattr(now_serving, 'status', '') == 'in_progress':
            active_mark = getattr(now_serving, 'started_time', None) or getattr(now_serving, 'called_time', None)
            if active_mark and active_mark < stale_cutoff and waiting_entries:
                now_serving = latest_called or waiting_entries[0]
        upcoming = list(waiting_entries)
        if now_serving and getattr(now_serving, 'status', '') in ('checked_in', 'called'):
            upcoming = [e for e in upcoming if str(e.id) != str(now_serving.id)]
        
        completed_today = completed_qs.count()
        
        from django.db.models import Avg
        avg_wait = completed_qs.filter(actual_wait_minutes__isnull=False).aggregate(avg=Avg('actual_wait_minutes'))
        avg_wait_minutes = int(avg_wait['avg'] or 0) if avg_wait['avg'] else None
        
        waiting_count = len(waiting_entries)
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
        
        latest_in_progress = in_progress_qs.order_by('-called_at').first()
        latest_called = waiting_qs.filter(status='called').order_by('-called_at', 'queue_number').first()
        if latest_in_progress and latest_called:
            in_progress_mark = getattr(latest_in_progress, 'called_at', None)
            called_mark = getattr(latest_called, 'called_at', None)
            if called_mark and (not in_progress_mark or called_mark >= in_progress_mark):
                now_serving = latest_called
            else:
                now_serving = latest_in_progress
        else:
            now_serving = latest_in_progress or latest_called or waiting_qs.first()
        if now_serving and getattr(now_serving, 'status', '') == 'in_progress':
            active_mark = getattr(now_serving, 'called_at', None)
            if active_mark and active_mark < stale_cutoff and waiting_qs.exists():
                now_serving = latest_called or waiting_qs.first()
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




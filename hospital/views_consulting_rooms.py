"""
Views for Consulting Room Management and Doctor Room Assignment
"""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError

from .models import Staff
from .models_consulting_rooms import ConsultingRoom, DoctorRoomAssignment
from .models_queue import QueueEntry


@login_required
def doctor_room_selection(request):
    """
    Allow doctors to select their consulting room when they arrive
    """
    user = request.user
    
    # Check if user is a doctor
    try:
        staff = user.staff
        if staff.profession != 'doctor':
            messages.error(request, "Only doctors can select consulting rooms.")
            return redirect('hospital:dashboard')
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:dashboard')
    
    today = timezone.now().date()
    now = timezone.now()
    
    # Get current assignment if exists
    current_assignment = DoctorRoomAssignment.objects.filter(
        doctor=user,
        assignment_date=today,
        is_active=True,
        is_deleted=False
    ).select_related('room').first()
    
    # Get all available rooms
    available_rooms = ConsultingRoom.objects.filter(
        is_active=True,
        status='available',
        is_deleted=False
    ).order_by('room_number')
    
    # Get all rooms (including occupied ones) for display
    all_rooms = ConsultingRoom.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('room_number')
    
    # Get today's assignments for all rooms
    today_assignments = {}
    for room in all_rooms:
        assignments = DoctorRoomAssignment.objects.filter(
            room=room,
            assignment_date=today,
            is_active=True,
            is_deleted=False
        ).select_related('doctor')
        today_assignments[str(room.id)] = list(assignments)
    
    context = {
        'current_assignment': current_assignment,
        'available_rooms': available_rooms,
        'all_rooms': all_rooms,
        'today_assignments': today_assignments,
        'today': today,
    }
    
    return render(request, 'hospital/doctor_room_selection.html', context)


@login_required
@require_POST
def assign_doctor_to_room(request):
    """
    Assign doctor to a consulting room
    """
    user = request.user
    
    # Check if user is a doctor
    try:
        staff = user.staff
        if staff.profession != 'doctor':
            return JsonResponse({'success': False, 'error': 'Only doctors can select rooms.'}, status=403)
    except Staff.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Staff profile not found.'}, status=404)
    
    # Ensure user is in Doctor group (required by ForeignKey limit_choices_to)
    doctor_group, _ = Group.objects.get_or_create(name='Doctor')
    if not user.groups.filter(name='Doctor').exists():
        user.groups.add(doctor_group)
        user.save()
    
    room_id = request.POST.get('room_id')
    if not room_id:
        return JsonResponse({'success': False, 'error': 'Room ID is required.'}, status=400)
    
    try:
        room = ConsultingRoom.objects.get(pk=room_id, is_active=True, is_deleted=False)
    except ConsultingRoom.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Room not found.'}, status=404)
    
    today = timezone.now().date()
    
    with transaction.atomic():
        # End any existing active assignment
        existing_assignment = DoctorRoomAssignment.objects.filter(
            doctor=user,
            assignment_date=today,
            is_active=True,
            is_deleted=False
        ).first()
        
        if existing_assignment:
            existing_assignment.end_assignment()
        
        # Create new assignment
        try:
            # Validate user exists and is a doctor
            if not User.objects.filter(pk=user.pk).exists():
                return JsonResponse({'success': False, 'error': 'User not found.'}, status=404)
            
            assignment = DoctorRoomAssignment.objects.create(
                doctor=user,
                room=room,
                assignment_date=today,
                start_time=timezone.now().time(),
                is_active=True
            )
            
            # Update queue entries assigned to this doctor to use the room
            QueueEntry.objects.filter(
                assigned_doctor=user,
                queue_date=today,
                status__in=['checked_in', 'called', 'vitals_completed', 'in_progress'],
                is_deleted=False
            ).update(room_number=room.room_number)
            
            return JsonResponse({
                'success': True,
                'message': f'Assigned to {room.room_number}',
                'assignment': {
                    'id': str(assignment.id),
                    'room_number': room.room_number,
                    'room_name': room.room_name or '',
                }
            })
            
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def end_room_assignment(request):
    """
    End current room assignment for doctor
    """
    user = request.user
    today = timezone.now().date()
    
    assignment = DoctorRoomAssignment.objects.filter(
        doctor=user,
        assignment_date=today,
        is_active=True,
        is_deleted=False
    ).first()
    
    if not assignment:
        return JsonResponse({'success': False, 'error': 'No active assignment found.'}, status=404)
    
    assignment.end_assignment()
    
    return JsonResponse({
        'success': True,
        'message': 'Room assignment ended successfully.'
    })


@login_required
def consulting_rooms_dashboard(request):
    """
    Dashboard showing all consulting rooms and their current status
    """
    # Check permissions - allow admin, frontdesk, nurses, and doctors
    try:
        staff = request.user.staff
        allowed_roles = ['receptionist', 'nurse', 'admin', 'doctor']
        if staff.profession not in allowed_roles:
            messages.error(request, "You don't have permission to view this page.")
            return redirect('hospital:dashboard')
    except Staff.DoesNotExist:
        # Allow if user is in allowed groups (fallback)
        user_groups = request.user.groups.values_list('name', flat=True)
        allowed_groups = ['Admin', 'Front Desk', 'Doctor', 'Receptionist', 'Nurse']
        if not any(group in allowed_groups for group in user_groups):
            messages.error(request, "You don't have permission to view this page.")
            return redirect('hospital:dashboard')
    
    today = timezone.now().date()
    
    # Get all consulting rooms
    rooms = ConsultingRoom.objects.filter(
        is_deleted=False
    ).order_by('room_number')
    
    # Get today's assignments for each room
    room_assignments = {}
    room_queue_entries = {}  # Separate dict for queue entries for easier template access
    for room in rooms:
        assignments = DoctorRoomAssignment.objects.filter(
            room=room,
            assignment_date=today,
            is_active=True,
            is_deleted=False
        ).select_related('doctor').order_by('start_time')
        room_assignments[str(room.id)] = list(assignments)
        
        # Get current queue entries for this room (both by room_number and by assigned doctors in this room)
        assigned_doctor_ids = [a.doctor.id for a in assignments]
        raw_entries = QueueEntry.objects.filter(
            Q(room_number=room.room_number) | Q(assigned_doctor_id__in=assigned_doctor_ids),
            queue_date=today,
            status__in=['checked_in', 'called', 'vitals_completed', 'in_progress'],
            is_deleted=False
        ).select_related('patient', 'assigned_doctor').order_by('priority', 'sequence_number')
        # Deduplicate by encounter (or patient) so the same patient does not appear twice in the list
        seen_keys = set()
        queue_entries = []
        for entry in raw_entries:
            key = (entry.encounter_id if entry.encounter_id else entry.patient_id)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            queue_entries.append(entry)
        room_queue_entries[str(room.id)] = queue_entries
    
    context = {
        'rooms': rooms,
        'room_assignments': room_assignments,
        'room_queue_entries': room_queue_entries,
        'today': today,
    }
    
    try:
        return render(request, 'hospital/consulting_rooms_dashboard.html', context)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error rendering consulting_rooms_dashboard: {str(e)}", exc_info=True)
        messages.error(request, f"Error loading consulting rooms dashboard: {str(e)}")
        return redirect('hospital:reception_dashboard')


@login_required
def doctor_appointment_calendar(request):
    """
    Calendar view showing doctor's appointments and queue
    """
    user = request.user
    
    # Check if user is a doctor
    try:
        staff = user.staff
        if staff.profession != 'doctor':
            messages.error(request, "Only doctors can view appointment calendar.")
            return redirect('hospital:dashboard')
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:dashboard')
    
    from .models import Appointment
    from datetime import datetime, timedelta
    
    # Get date range (current week)
    today = timezone.now().date()
    start_date = request.GET.get('start_date')
    if start_date:
        try:
            today = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Get week start (Monday)
    days_since_monday = today.weekday()
    week_start = today - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    
    # Get appointments for this week
    appointments = Appointment.objects.filter(
        provider=staff,
        appointment_date__date__gte=week_start,
        appointment_date__date__lte=week_end,
        is_deleted=False
    ).select_related('patient', 'department').order_by('appointment_date')
    
    # Get current room assignment
    current_assignment = DoctorRoomAssignment.objects.filter(
        doctor=user,
        assignment_date=today,
        is_active=True,
        is_deleted=False
    ).select_related('room').first()
    
    # Get today's queue entries
    today_queue = QueueEntry.objects.filter(
        assigned_doctor=user,
        queue_date=today,
        is_deleted=False
    ).select_related('patient', 'department').order_by('priority', 'sequence_number')
    
    # Organize appointments by date (as string keys for template)
    appointments_by_date = {}
    for appointment in appointments:
        date_key = str(appointment.appointment_date.date())
        if date_key not in appointments_by_date:
            appointments_by_date[date_key] = []
        appointments_by_date[date_key].append(appointment)
    
    context = {
        'doctor': staff,
        'current_assignment': current_assignment,
        'appointments': appointments,
        'appointments_by_date': appointments_by_date,
        'today_queue': today_queue,
        'week_start': week_start,
        'week_end': week_end,
        'today': today,
        'date_range': [week_start + timedelta(days=x) for x in range(7)],
    }
    
    return render(request, 'hospital/doctor_appointment_calendar.html', context)


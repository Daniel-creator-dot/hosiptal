"""
Front Desk Queue Management Views
Allow front desk staff to create queue entries and assign patients to doctors/rooms
"""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Staff, Patient, Encounter, Department
from .models_queue import QueueEntry
from .models_consulting_rooms import ConsultingRoom, DoctorRoomAssignment
from .forms_advanced import QueueEntryForm
from .services.queue_service import queue_service


@login_required
def frontdesk_queue_create(request):
    """
    Front desk view to create queue entry with doctor/room assignment
    """
    user = request.user
    
    # Check if user is front desk staff or nurse
    try:
        staff = user.staff
        allowed_roles = ['receptionist', 'admin', 'nurse', 'midwife']
        if staff.profession not in allowed_roles:
            messages.error(request, "Only front desk staff and nurses can create queue entries.")
            return redirect('hospital:dashboard')
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:dashboard')
    
    if request.method == 'POST':
        form = QueueEntryForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    patient = form.cleaned_data['patient']
                    department = form.cleaned_data['department']
                    encounter = form.cleaned_data.get('encounter')
                    assigned_doctor = form.cleaned_data.get('assigned_doctor')
                    priority = form.cleaned_data.get('priority', 3)
                    notes = form.cleaned_data.get('notes', '')
                    consulting_room = form.cleaned_data.get('consulting_room')
                    
                    # Create encounter if not provided
                    if not encounter:
                        current_staff = getattr(user, 'staff', None)
                        today = timezone.now().date()
                        
                        # Check for existing encounter today to prevent duplicates
                        existing_encounter = Encounter.objects.filter(
                            patient=patient,
                            status='active',
                            is_deleted=False,
                            started_at__date=today
                        ).select_for_update().order_by('-started_at', '-id').first()
                        
                        if existing_encounter:
                            encounter = existing_encounter
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.info(f"Front desk queue: Reusing existing encounter {encounter.id} for patient {patient.mrn}")
                        else:
                            # Do not set provider to front desk staff - leave unassigned until doctor is set
                            encounter = Encounter.objects.create(
                                patient=patient,
                                encounter_type='outpatient',
                                status='active',
                                started_at=timezone.now(),
                                provider=None,
                                chief_complaint='Walk-in visit',
                                notes='Created during queue entry'
                            )
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.info(f"Front desk queue: Created new encounter {encounter.id} for patient {patient.mrn}")
                    
                    # Create queue entry using queue service
                    queue_entry = queue_service.create_queue_entry(
                        patient=patient,
                        encounter=encounter,
                        department=department,
                        assigned_doctor=assigned_doctor,
                        priority=priority,
                        notes=notes,
                        consulting_room=consulting_room
                    )
                    
                    # Send check-in SMS notification
                    try:
                        from .services.queue_notification_service import queue_notification_service
                        queue_notification_service.send_check_in_notification(queue_entry)
                    except Exception as sms_error:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to send check-in SMS: {str(sms_error)}")
                    
                    messages.success(
                        request,
                        f'Patient {patient.full_name} added to queue (ticket {queue_entry.display_ticket_number}). '
                        f'{"Assigned to " + assigned_doctor.get_full_name() if assigned_doctor else ""} '
                        f'{"in " + consulting_room.room_number if consulting_room else ""}'
                    )
                    return redirect('hospital:consulting_rooms_dashboard')
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error creating queue entry: {str(e)}", exc_info=True)
                messages.error(request, f'Error creating queue entry: {str(e)}')
    else:
        form = QueueEntryForm()
        
        # Pre-fill patient if provided in query params
        patient_id = request.GET.get('patient')
        if patient_id:
            try:
                patient = Patient.objects.get(pk=patient_id, is_deleted=False)
                form.fields['patient'].initial = patient
            except Patient.DoesNotExist:
                pass
        
        # Pre-fill department based on staff
        try:
            staff = user.staff
            if staff.department:
                form.fields['department'].initial = staff.department
        except Staff.DoesNotExist:
            pass
    
    # Get active doctors and rooms for context
    doctor_group, _ = Group.objects.get_or_create(name='Doctor')
    active_doctors = User.objects.filter(
        groups=doctor_group,
        is_active=True
    ).select_related('staff').order_by('first_name', 'last_name')
    
    active_rooms = ConsultingRoom.objects.filter(
        is_active=True,
        is_deleted=False,
        status='available'
    ).order_by('room_number')
    
    # Get today's doctor-room assignments for display
    today = timezone.now().date()
    today_assignments = DoctorRoomAssignment.objects.filter(
        assignment_date=today,
        is_active=True,
        is_deleted=False
    ).select_related('doctor', 'room').order_by('room__room_number')
    
    context = {
        'form': form,
        'title': 'Add Patient to Queue',
        'active_doctors': active_doctors,
        'active_rooms': active_rooms,
        'today_assignments': today_assignments,
    }
    
    return render(request, 'hospital/frontdesk_queue_create.html', context)


@login_required
@require_GET
def get_doctor_current_room_api(request, doctor_id):
    """
    API endpoint to get doctor's current room assignment
    Used by front desk queue form to auto-populate room when doctor is selected
    """
    try:
        doctor = User.objects.get(pk=doctor_id, is_active=True)
        today = timezone.now().date()
        
        assignment = DoctorRoomAssignment.objects.filter(
            doctor=doctor,
            assignment_date=today,
            is_active=True,
            is_deleted=False
        ).select_related('room').first()
        
        if assignment and assignment.room:
            return JsonResponse({
                'success': True,
                'room_id': str(assignment.room.id),
                'room_number': assignment.room.room_number,
                'room_name': assignment.room.room_name or ''
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Doctor has no room assignment today'
            })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Doctor not found'}, status=404)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching doctor room: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

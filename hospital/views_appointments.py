"""
Front Desk Appointment Management Views
Enhanced appointment creation with SMS notifications
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Count
import logging

from .models import Appointment, Patient, Staff, Department, Encounter
from .forms_advanced import AppointmentForm
from .services.sms_service import sms_service

logger = logging.getLogger(__name__)

try:
    from .models_queue import QueueEntry
except ImportError:
    QueueEntry = None


def _enqueue_appointment_into_queue(appointment, *, request_user=None, allow_future=False):
    """
    Ensure an appointment has a queue ticket (and encounter) for today's queue.
    Returns dict with keys: status, entry (QueueEntry or None), message (optional).
    """
    if not QueueEntry:
        return {'status': 'queue_disabled', 'entry': None}

    try:
        from .services.queue_service import queue_service
        from .services.queue_notification_service import queue_notification_service
    except Exception as service_error:
        logger.error("Queue services unavailable while enqueueing appointment %s: %s",
                     appointment.pk, service_error, exc_info=True)
        return {'status': 'service_error', 'entry': None, 'message': str(service_error)}

    today = timezone.now().date()
    appointment_day = appointment.appointment_date.date()
    if not allow_future and appointment_day != today:
        return {'status': 'not_today', 'entry': None}

    existing_entry = QueueEntry.objects.filter(
        is_deleted=False,
        queue_date=today,
        patient=appointment.patient,
        department=appointment.department,
        status__in=['checked_in', 'called', 'in_progress']
    ).order_by('sequence_number').first()
    if existing_entry:
        return {'status': 'already', 'entry': existing_entry}

    encounter = Encounter.objects.filter(
        patient=appointment.patient,
        status='active',
        is_deleted=False
    ).order_by('-started_at').first()

    if not encounter or encounter.started_at.date() != today:
        encounter = Encounter.objects.create(
            patient=appointment.patient,
            encounter_type='outpatient',
            status='active',
            started_at=timezone.now(),
            provider=appointment.provider,
            chief_complaint=appointment.reason or 'Scheduled appointment',
            notes=f'Auto check-in from appointment #{appointment.pk}'
        )

    assigned_doctor = getattr(appointment.provider, 'user', None)
    priority = 2 if appointment.status == 'confirmed' else 3

    queue_entry = queue_service.create_queue_entry(
        patient=appointment.patient,
        encounter=encounter,
        department=appointment.department,
        assigned_doctor=assigned_doctor,
        priority=priority,
        notes=f'Appointment {appointment.appointment_date.strftime("%Y-%m-%d %H:%M")}'
    )

    try:
        queue_notification_service.send_check_in_notification(queue_entry)
    except Exception as notify_error:
        logger.warning("Queue notification failed for appointment %s: %s",
                       appointment.pk, notify_error, exc_info=True)

    if appointment.status == 'scheduled':
        appointment.status = 'confirmed'
        appointment.save(update_fields=['status', 'modified'])

    return {
        'status': 'created',
        'entry': queue_entry,
        'message': f'Ticket {queue_entry.queue_number} (position {queue_service.get_position_in_queue(queue_entry)})'
    }


@login_required
def frontdesk_appointment_dashboard(request):
    """
    Front desk appointment dashboard showing today's appointments and quick actions
    """
    today = timezone.now().date()
    
    # Get today's appointments
    todays_appointments = Appointment.objects.filter(
        is_deleted=False,
        appointment_date__date=today
    ).select_related(
        'patient', 'provider__user', 'department'
    ).order_by('appointment_date')
    
    # Get upcoming appointments (next 7 days)
    upcoming_appointments = Appointment.objects.filter(
        is_deleted=False,
        appointment_date__date__gt=today,
        appointment_date__date__lte=today + timezone.timedelta(days=7),
        status__in=['scheduled', 'confirmed']
    ).select_related(
        'patient', 'provider__user', 'department'
    ).order_by('appointment_date')[:10]
    
    # Statistics for TODAY
    stats = {
        'today_total': todays_appointments.count(),
        'today_scheduled': todays_appointments.filter(status='scheduled').count(),
        'today_confirmed': todays_appointments.filter(status='confirmed').count(),
        'today_completed': todays_appointments.filter(status='completed').count(),
        'today_cancelled': todays_appointments.filter(status='cancelled').count(),
        'today_no_show': todays_appointments.filter(status='no_show').count(),
        'upcoming_count': upcoming_appointments.count(),
    }
    
    # Add ALL appointments statistics (for better visibility)
    all_upcoming = Appointment.objects.filter(
        is_deleted=False,
        appointment_date__date__gte=today,
        status__in=['scheduled', 'confirmed']
    )
    
    stats['all_scheduled'] = all_upcoming.filter(status='scheduled').count()
    stats['all_confirmed'] = all_upcoming.filter(status='confirmed').count()
    stats['total_upcoming'] = all_upcoming.count()
    
    # Get status filter from request
    status_filter = request.GET.get('status', '')
    if status_filter:
        todays_appointments = todays_appointments.filter(status=status_filter)
    
    context = {
        'title': 'Front Desk - Appointment Management',
        'todays_appointments': todays_appointments,
        'upcoming_appointments': upcoming_appointments,
        'stats': stats,
        'today': today,
        'status_filter': status_filter,
    }
    return render(request, 'hospital/frontdesk_appointment_dashboard.html', context)


@login_required
def frontdesk_appointment_create(request):
    """
    Create a new appointment from front desk with SMS notification
    """
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save()

            auto_queue_feedback = None
            if appointment.appointment_date.date() == timezone.now().date():
                auto_queue_feedback = _enqueue_appointment_into_queue(
                    appointment,
                    request_user=request.user,
                    allow_future=False
                )
                if auto_queue_feedback and auto_queue_feedback['status'] == 'created':
                    messages.info(
                        request,
                        f"Patient queued immediately: {auto_queue_feedback['message']}."
                    )
                elif auto_queue_feedback and auto_queue_feedback['status'] == 'queue_disabled':
                    messages.warning(
                        request,
                        'Queue system is disabled, so the visit was not placed in the queue automatically.'
                    )
            
            # Send SMS notification to patient with confirmation link
            try:
                from .views_appointment_confirmation import send_appointment_notification_with_confirmation
                
                patient = appointment.patient
                if patient.phone_number and patient.phone_number.strip():
                    # Send SMS with confirmation link (pass request for proper URL)
                    sms_sent = send_appointment_notification_with_confirmation(appointment, request=request)
                    
                    if sms_sent:
                        messages.success(
                            request, 
                            f'Appointment created successfully for {patient.full_name}! '
                            f'SMS with confirmation link sent to {patient.phone_number}.'
                        )
                    else:
                        messages.warning(
                            request,
                            f'Appointment created for {patient.full_name}, but SMS failed to send.'
                        )
                else:
                    messages.success(
                        request,
                        f'Appointment created successfully for {patient.full_name}. '
                        f'No phone number on file - SMS not sent.'
                    )
            except Exception as e:
                logger.error(f"Error sending appointment SMS: {str(e)}")
                messages.warning(
                    request,
                    f'Appointment created, but SMS notification failed: {str(e)}'
                )
            
            return redirect('hospital:frontdesk_appointment_dashboard')
    else:
        form = AppointmentForm()
        
        # Pre-fill patient if provided in query params
        patient_id = request.GET.get('patient')
        if patient_id:
            try:
                patient = Patient.objects.get(pk=patient_id, is_deleted=False)
                form.fields['patient'].initial = patient
            except Patient.DoesNotExist:
                pass
    
    context = {
        'form': form,
        'title': 'Create New Appointment',
        'breadcrumb': 'Create Appointment',
    }
    return render(request, 'hospital/frontdesk_appointment_form.html', context)


@login_required
def frontdesk_appointment_list(request):
    """
    List all appointments with filtering and search
    """
    appointments = Appointment.objects.filter(
        is_deleted=False
    ).select_related(
        'patient', 'provider__user', 'department'
    ).order_by('-appointment_date')
    
    # Search functionality
    search_query = request.GET.get('search', '').strip()
    if search_query:
        appointments = appointments.filter(
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(patient__mrn__icontains=search_query) |
            Q(provider__user__first_name__icontains=search_query) |
            Q(provider__user__last_name__icontains=search_query) |
            Q(reason__icontains=search_query)
        )
    
    # Filters
    status_filter = request.GET.get('status', '')
    department_filter = request.GET.get('department', '')
    provider_filter = request.GET.get('provider', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    if department_filter:
        appointments = appointments.filter(department_id=department_filter)
    if provider_filter:
        appointments = appointments.filter(provider_id=provider_filter)
    if date_from:
        appointments = appointments.filter(appointment_date__date__gte=date_from)
    if date_to:
        appointments = appointments.filter(appointment_date__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(appointments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    departments = Department.objects.filter(is_active=True, is_deleted=False).order_by('name')
    providers = Staff.objects.filter(is_active=True, is_deleted=False).order_by('user__first_name')
    
    context = {
        'title': 'All Appointments',
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'department_filter': department_filter,
        'provider_filter': provider_filter,
        'date_from': date_from,
        'date_to': date_to,
        'departments': departments,
        'providers': providers,
        'status_choices': Appointment.STATUS_CHOICES,
    }
    return render(request, 'hospital/frontdesk_appointment_list.html', context)


@login_required
def frontdesk_appointment_detail(request, pk):
    """
    View appointment details and update status
    """
    appointment = get_object_or_404(
        Appointment.objects.select_related('patient', 'provider__user', 'department'),
        pk=pk,
        is_deleted=False
    )
    
    # Handle status updates
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'confirm':
            appointment.status = 'confirmed'
            appointment.save()
            messages.success(request, f'Appointment confirmed for {appointment.patient.full_name}.')
            
            # Send detailed schedule SMS with preparation instructions
            try:
                from .views_appointment_confirmation import send_appointment_schedule_sms
                
                if appointment.patient.phone_number:
                    sms_sent = send_appointment_schedule_sms(appointment)
                    if sms_sent:
                        messages.info(request, 'Appointment schedule SMS with preparation instructions sent to patient.')
            except Exception as e:
                logger.error(f"Error sending schedule SMS: {str(e)}")
        
        elif action == 'complete':
            appointment.status = 'completed'
            appointment.save()
            messages.success(request, f'Appointment marked as completed.')
        
        elif action == 'cancel':
            appointment.status = 'cancelled'
            appointment.save()
            messages.success(request, f'Appointment cancelled.')
            
            # Send cancellation SMS
            try:
                if appointment.patient.phone_number:
                    message = (
                        f"Dear {appointment.patient.first_name},\n\n"
                        f"Your appointment on {appointment.appointment_date.strftime('%d/%m/%Y at %I:%M %p')} "
                        f"has been cancelled.\n\n"
                        f"Please contact us to reschedule.\n\n"
                        f"PrimeCare Medical Center"
                    )
                    sms_service.send_sms(
                        phone_number=appointment.patient.phone_number,
                        message=message,
                        message_type='appointment_cancellation',
                        recipient_name=appointment.patient.full_name,
                        related_object_id=appointment.id,
                        related_object_type='Appointment'
                    )
                    messages.info(request, 'Cancellation SMS sent to patient.')
            except Exception as e:
                logger.error(f"Error sending cancellation SMS: {str(e)}")
        
        elif action == 'no_show':
            appointment.status = 'no_show'
            appointment.save()
            messages.warning(request, f'Appointment marked as no-show.')
        
        elif action == 'resend_sms':
            # Resend booking confirmation SMS with link
            try:
                from .views_appointment_confirmation import send_booking_confirmation_sms
                
                if appointment.patient.phone_number:
                    sms_sent = send_booking_confirmation_sms(appointment, request=request)
                    if sms_sent:
                        messages.success(request, 'Booking confirmation SMS with link sent successfully.')
                    else:
                        messages.error(request, 'Failed to send SMS. Please check SMS logs.')
                else:
                    messages.error(request, 'Patient has no phone number on file.')
            except Exception as e:
                logger.error(f"Error resending SMS: {str(e)}")
                messages.error(request, f'Error sending SMS: {str(e)}')
        
        elif action == 'send_reminder':
            # Send detailed appointment reminder/schedule
            try:
                from .views_appointment_confirmation import send_appointment_schedule_sms
                
                if appointment.patient.phone_number:
                    sms_sent = send_appointment_schedule_sms(appointment)
                    if sms_sent:
                        messages.success(request, 'Appointment reminder with schedule details sent successfully.')
                    else:
                        messages.error(request, 'Failed to send reminder SMS.')
                else:
                    messages.error(request, 'Patient has no phone number on file.')
            except Exception as e:
                logger.error(f"Error sending reminder SMS: {str(e)}")
                messages.error(request, f'Error sending SMS: {str(e)}')

        elif action == 'check_in':
            queue_feedback = _enqueue_appointment_into_queue(
                appointment,
                request_user=request.user,
                allow_future=True
            )

            if queue_feedback['status'] == 'queue_disabled':
                messages.error(request, 'Queue system is not enabled on this deployment.')
            elif queue_feedback['status'] == 'service_error':
                messages.error(request, 'Unable to access queue services. Please try again later.')
            elif queue_feedback['status'] == 'already' and queue_feedback['entry']:
                messages.info(
                    request,
                    f'Patient is already in the queue with ticket {queue_feedback["entry"].queue_number}.'
                )
            elif queue_feedback['status'] == 'created':
                messages.success(
                    request,
                    f'Patient queued successfully! {queue_feedback["message"]}'
                )
            elif queue_feedback['status'] == 'not_today':
                messages.warning(
                    request,
                    'This appointment is scheduled for another day; open the queue on the day of the visit.'
                )
        
        return redirect('hospital:frontdesk_appointment_detail', pk=pk)
    
    today = timezone.now().date()
    can_check_in = (
        QueueEntry is not None
        and appointment.status in ['scheduled', 'confirmed']
        and appointment.appointment_date.date() <= today
    )

    context = {
        'title': f'Appointment Details - {appointment.patient.full_name}',
        'appointment': appointment,
        'can_check_in': can_check_in,
    }
    return render(request, 'hospital/frontdesk_appointment_detail.html', context)


@login_required
def frontdesk_appointment_edit(request, pk):
    """
    Edit an existing appointment
    """
    appointment = get_object_or_404(Appointment, pk=pk, is_deleted=False)
    
    if request.method == 'POST':
        form = AppointmentForm(request.POST, instance=appointment)
        if form.is_valid():
            updated_appointment = form.save()
            
            # Send SMS notification about the update
            try:
                patient = updated_appointment.patient
                if patient.phone_number and patient.phone_number.strip():
                    message = (
                        f"Dear {patient.first_name},\n\n"
                        f"Your appointment has been updated:\n"
                        f"Date: {updated_appointment.appointment_date.strftime('%d/%m/%Y at %I:%M %p')}\n"
                        f"Provider: Dr. {updated_appointment.provider.user.get_full_name()}\n"
                        f"Department: {updated_appointment.department.name}\n\n"
                        f"Please arrive 15 minutes early.\n\n"
                        f"PrimeCare Medical Center"
                    )
                    sms_log = sms_service.send_sms(
                        phone_number=patient.phone_number,
                        message=message,
                        message_type='appointment_update',
                        recipient_name=patient.full_name,
                        related_object_id=updated_appointment.id,
                        related_object_type='Appointment'
                    )
                    
                    if sms_log.status == 'sent':
                        messages.success(
                            request,
                            f'Appointment updated successfully! SMS notification sent to {patient.phone_number}.'
                        )
                    else:
                        messages.warning(
                            request,
                            f'Appointment updated, but SMS failed to send: {sms_log.error_message}'
                        )
                else:
                    messages.success(request, 'Appointment updated successfully.')
            except Exception as e:
                logger.error(f"Error sending appointment update SMS: {str(e)}")
                messages.warning(request, f'Appointment updated, but SMS notification failed.')
            
            return redirect('hospital:frontdesk_appointment_detail', pk=pk)
    else:
        form = AppointmentForm(instance=appointment)
    
    context = {
        'form': form,
        'title': f'Edit Appointment - {appointment.patient.full_name}',
        'appointment': appointment,
        'breadcrumb': 'Edit Appointment',
    }
    return render(request, 'hospital/frontdesk_appointment_form.html', context)


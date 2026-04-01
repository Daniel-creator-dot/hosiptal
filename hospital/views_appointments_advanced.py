"""
State-of-the-Art Appointment Management Views
Calendar view, smart scheduling, waiting lists, analytics
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from datetime import timedelta, datetime
import json
import logging

from .models import Appointment, Patient, Staff, Department
from .models_advanced import ProviderSchedule, Queue
from .services.sms_service import sms_service

logger = logging.getLogger(__name__)


@login_required
def appointment_calendar_view(request):
    """
    Calendar view showing all appointments with drag-and-drop capability
    """
    # Get filter parameters
    department_id = request.GET.get('department')
    provider_id = request.GET.get('provider')
    view_type = request.GET.get('view', 'week')  # day, week, month
    date_str = request.GET.get('date')
    
    if date_str:
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            current_date = timezone.now().date()
    else:
        current_date = timezone.now().date()
    
    # Get appointments
    appointments = Appointment.objects.filter(
        is_deleted=False,
        status__in=['scheduled', 'confirmed', 'completed']
    ).select_related('patient', 'provider__user', 'department')
    
    if department_id:
        appointments = appointments.filter(department_id=department_id)
    if provider_id:
        appointments = appointments.filter(provider_id=provider_id)
    
    # Filter by date range based on view type
    if view_type == 'day':
        appointments = appointments.filter(appointment_date__date=current_date)
    elif view_type == 'week':
        week_start = current_date - timedelta(days=current_date.weekday())
        week_end = week_start + timedelta(days=6)
        appointments = appointments.filter(
            appointment_date__date__gte=week_start,
            appointment_date__date__lte=week_end
        )
    elif view_type == 'month':
        month_start = current_date.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        appointments = appointments.filter(
            appointment_date__date__gte=month_start,
            appointment_date__date__lte=month_end
        )
    
    # Convert to calendar format
    calendar_events = []
    for appt in appointments:
        calendar_events.append({
            'id': str(appt.id),
            'title': f"{appt.patient.full_name} - {appt.reason[:30]}",
            'start': appt.appointment_date.isoformat(),
            'end': (appt.appointment_date + timedelta(minutes=appt.duration_minutes)).isoformat(),
            'color': _get_status_color(appt.status),
            'extendedProps': {
                'patient': appt.patient.full_name,
                'provider': appt.provider.user.get_full_name(),
                'department': appt.department.name,
                'status': appt.get_status_display(),
                'phone': appt.patient.phone_number,
            }
        })
    
    # Get filter options
    departments = Department.objects.filter(is_active=True, is_deleted=False)
    providers = Staff.objects.filter(is_active=True, is_deleted=False)
    
    context = {
        'title': 'Appointment Calendar',
        'calendar_events': json.dumps(calendar_events),
        'departments': departments,
        'providers': providers,
        'current_date': current_date,
        'view_type': view_type,
        'selected_department': department_id,
        'selected_provider': provider_id,
    }
    return render(request, 'hospital/appointment_calendar.html', context)


@login_required
def smart_appointment_booking(request):
    """
    Smart appointment booking with availability checking
    """
    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        department_id = request.POST.get('department')
        provider_id = request.POST.get('provider')
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')
        reason = request.POST.get('reason')
        duration_minutes = int(request.POST.get('duration_minutes', 30))
        
        try:
            patient = Patient.objects.get(pk=patient_id)
            department = Department.objects.get(pk=department_id)
            provider = Staff.objects.get(pk=provider_id)
            
            # Combine date and time
            date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
            time = datetime.strptime(appointment_time, '%H:%M').time()
            appointment_datetime = datetime.combine(date, time)
            appointment_datetime = timezone.make_aware(appointment_datetime)
            
            # Check for conflicts
            conflicts = Appointment.objects.filter(
                provider=provider,
                appointment_date__date=date,
                status__in=['scheduled', 'confirmed'],
                is_deleted=False
            )
            
            has_conflict = False
            for appt in conflicts:
                appt_end = appt.appointment_date + timedelta(minutes=appt.duration_minutes)
                new_appt_end = appointment_datetime + timedelta(minutes=duration_minutes)
                if appointment_datetime < appt_end and new_appt_end > appt.appointment_date:
                    has_conflict = True
                    break
            
            if has_conflict:
                messages.error(request, 'Time slot conflicts with existing appointment. Please choose another time.')
            else:
                # Create appointment
                appointment = Appointment.objects.create(
                    patient=patient,
                    provider=provider,
                    department=department,
                    appointment_date=appointment_datetime,
                    duration_minutes=duration_minutes,
                    reason=reason,
                    status='scheduled'
                )
                
                # Send SMS with booking confirmation to patient
                patient_sms_sent = False
                try:
                    if patient.phone_number:
                        from .views_appointment_confirmation import send_booking_confirmation_sms
                        patient_sms_sent = send_booking_confirmation_sms(appointment, request=request)
                        if patient_sms_sent:
                            messages.success(request, f'Appointment created successfully! SMS confirmation with link sent to patient.')
                        else:
                            messages.warning(request, f'Appointment created, but patient SMS failed to send. Please check SMS logs.')
                    else:
                        messages.success(request, 'Appointment created successfully.')
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error sending patient appointment SMS: {str(e)}")
                    messages.success(request, 'Appointment created successfully.')
                
                # Send SMS notification to doctor
                try:
                    from .views_appointment_confirmation import send_appointment_notification_to_doctor
                    doctor_sms_sent = send_appointment_notification_to_doctor(appointment)
                    if doctor_sms_sent:
                        logger.info(f"Doctor SMS sent successfully for appointment {appointment.id}")
                    else:
                        logger.warning(f"Doctor SMS failed to send for appointment {appointment.id}")
                except Exception as e:
                    logger.error(f"Error sending doctor appointment SMS: {str(e)}", exc_info=True)
                
                return redirect('hospital:appointment_calendar_view')
        
        except Exception as e:
            logger.error(f"Error in smart booking: {str(e)}")
            messages.error(request, f"Error creating appointment: {str(e)}")
    
    context = {
        'title': 'Smart Appointment Booking',
        'patients': Patient.objects.filter(is_deleted=False).order_by('first_name'),
        'departments': Department.objects.filter(is_active=True, is_deleted=False),
        'providers': Staff.objects.filter(is_active=True, is_deleted=False),
    }
    return render(request, 'hospital/smart_appointment_booking.html', context)


@login_required
def check_availability_api(request):
    """
    API endpoint to check provider availability for a specific date
    Simple version checking existing appointments
    """
    provider_id = request.GET.get('provider')
    date_str = request.GET.get('date')
    duration = int(request.GET.get('duration', 30))
    
    if not provider_id or not date_str:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        provider = Staff.objects.get(pk=provider_id)
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get existing appointments for this provider on this date
        existing_appointments = Appointment.objects.filter(
            provider=provider,
            appointment_date__date=date,
            status__in=['scheduled', 'confirmed'],
            is_deleted=False
        ).order_by('appointment_date')
        
        # Generate time slots from 9 AM to 5 PM
        slots_data = []
        start_hour = 9
        end_hour = 17
        
        for hour in range(start_hour, end_hour):
            for minute in [0, 30]:
                time_slot = f"{hour:02d}:{minute:02d}"
                slot_datetime = datetime.combine(date, datetime.strptime(time_slot, '%H:%M').time())
                slot_datetime = timezone.make_aware(slot_datetime)
                
                # Check if slot conflicts with existing appointment
                available = True
                for appt in existing_appointments:
                    appt_end = appt.appointment_date + timedelta(minutes=appt.duration_minutes)
                    slot_end = slot_datetime + timedelta(minutes=duration)
                    if slot_datetime < appt_end and slot_end > appt.appointment_date:
                        available = False
                        break
                
                # Skip past slots
                if slot_datetime < timezone.now():
                    continue
                    
                slots_data.append({
                    'start_time': time_slot,
                    'end_time': (datetime.strptime(time_slot, '%H:%M') + timedelta(minutes=duration)).strftime('%H:%M'),
                    'available': available,
                    'available_count': 1 if available else 0,
                    'department': provider.department.name if provider.department else 'N/A',
                })
        
        return JsonResponse({'slots': slots_data})
    
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def waiting_list_dashboard(request):
    """
    Waiting list management dashboard - using Queue model
    """
    # Use existing Queue model as waiting list
    queues = Queue.objects.filter(
        is_deleted=False,
        status='waiting'
    ).select_related('encounter__patient', 'department').order_by('-priority', 'created')
    
    # Filters
    department_filter = request.GET.get('department')
    
    if department_filter:
        queues = queues.filter(department_id=department_filter)
    
    # Pagination
    paginator = Paginator(queues, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'total_waiting': Queue.objects.filter(status='waiting', is_deleted=False).count(),
        'total_in_progress': Queue.objects.filter(status='in_progress', is_deleted=False).count(),
        'total_completed': Queue.objects.filter(status='completed', is_deleted=False).count(),
        'high_priority': Queue.objects.filter(status='waiting', priority='high', is_deleted=False).count(),
    }
    
    context = {
        'title': 'Waiting List / Queue Management',
        'page_obj': page_obj,
        'stats': stats,
        'departments': Department.objects.filter(is_active=True, is_deleted=False),
        'department_filter': department_filter,
    }
    return render(request, 'hospital/waiting_list_dashboard.html', context)


@login_required
def add_to_waiting_list(request):
    """
    Add patient to waiting list - redirects to queue
    """
    messages.info(request, 'Use the Queue system to manage waiting patients.')
    return redirect('hospital:queue_display')


@login_required
def appointment_analytics_dashboard(request):
    """
    Advanced analytics dashboard for appointments
    """
    # Date range
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    # Get all appointments in range
    appointments = Appointment.objects.filter(
        appointment_date__date__gte=start_date,
        appointment_date__date__lte=end_date,
        is_deleted=False
    )
    
    # Statistics
    total_appointments = appointments.count()
    completed = appointments.filter(status='completed').count()
    no_shows = appointments.filter(status='no_show').count()
    cancelled = appointments.filter(status='cancelled').count()
    
    stats = {
        'total_appointments': total_appointments,
        'completed': completed,
        'no_shows': no_shows,
        'cancelled': cancelled,
        'scheduled': appointments.filter(status='scheduled').count(),
        'confirmed': appointments.filter(status='confirmed').count(),
    }
    
    if total_appointments > 0:
        stats['completion_rate'] = round((completed / total_appointments) * 100, 1)
        stats['no_show_rate'] = round((no_shows / total_appointments) * 100, 1)
        stats['cancellation_rate'] = round((cancelled / total_appointments) * 100, 1)
    else:
        stats['completion_rate'] = 0
        stats['no_show_rate'] = 0
        stats['cancellation_rate'] = 0
    
    # Department breakdown
    dept_stats = appointments.values('department__name').annotate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        no_shows=Count('id', filter=Q(status='no_show'))
    ).order_by('-total')[:10]
    
    # Provider performance
    provider_stats = appointments.values(
        'provider__user__first_name',
        'provider__user__last_name'
    ).annotate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        no_shows=Count('id', filter=Q(status='no_show'))
    ).order_by('-total')[:10]
    
    # Daily trend (last 30 days)
    daily_data = []
    for i in range(30):
        date = end_date - timedelta(days=29-i)
        count = appointments.filter(appointment_date__date=date).count()
        daily_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    context = {
        'title': 'Appointment Analytics',
        'stats': stats,
        'dept_stats': list(dept_stats),
        'provider_stats': list(provider_stats),
        'daily_data': json.dumps(daily_data),
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'hospital/appointment_analytics.html', context)


# Helper functions

def _get_status_color(status):
    """Get color code for appointment status"""
    colors = {
        'scheduled': '#6c757d',
        'confirmed': '#17a2b8',
        'completed': '#28a745',
        'cancelled': '#dc3545',
        'no_show': '#ffc107',
    }
    return colors.get(status, '#007bff')


"""
Advanced frontend views for Hospital Management System
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta, date
from .models import Patient, Encounter, Staff, Department, Ward
from .models_advanced import (
    Queue, Triage, ImagingStudy, TheatreSchedule,
    MedicationAdministrationRecord, HandoverSheet,
    TheatreSchedule, ProviderSchedule
)
# Also import QueueEntry from models_queue (they might be different models)
try:
    from .models_queue import QueueEntry
    # Use QueueEntry if it exists, otherwise fall back to Queue
    QueueModel = QueueEntry
except ImportError:
    QueueModel = Queue
from .reports_advanced import get_comprehensive_report


@login_required
def queue_display(request):
    """Display queue for a department or location"""
    department_id = request.GET.get('department', '').strip()
    location = request.GET.get('location', '').strip()
    
    # Use QueueEntry model (not Queue from models_advanced)
    queues = QueueModel.objects.filter(
        is_deleted=False,
        status__in=['checked_in', 'waiting', 'in_consultation']  # QueueEntry statuses
    ).select_related(
        'encounter__patient', 'department'
    ).order_by('priority', 'sequence_number')
    
    # Filter by department - only if valid and not 'None'/'null'/empty
    selected_department_id = None
    if department_id and department_id.lower() not in ['none', 'null', '']:
        try:
            department = Department.objects.get(pk=department_id, is_deleted=False)
            queues = queues.filter(department=department)
            selected_department_id = str(department.pk)  # Store as string for template comparison
        except (Department.DoesNotExist, ValueError):
            selected_department_id = None
    
    # Filter by location - only if valid and not 'None'/'null'/empty
    selected_location = None
    if location and location.lower() not in ['none', 'null', '']:
        queues = queues.filter(location=location)
        selected_location = location
    
    # Group by status and priority for proper ordering
    # Priority ordering: 1=Emergency, 2=Urgent, 3=Normal, 4=Follow-up (lower number = higher priority)
    
    # QueueEntry uses different status names: checked_in, waiting, in_consultation, completed
    waiting = list(queues.filter(status__in=['checked_in', 'waiting']).order_by('priority', 'sequence_number'))
    in_progress = list(queues.filter(status='in_consultation').order_by('priority', 'sequence_number'))
    
    context = {
        'waiting': waiting,
        'in_progress': in_progress,
        'departments': Department.objects.filter(is_active=True, is_deleted=False),
        'selected_department': selected_department_id,  # None or string ID
        'selected_location': selected_location,  # None or valid location
    }
    return render(request, 'hospital/queue_display_worldclass.html', context)


@login_required
def triage_queue(request):
    """ER Triage queue management"""
    triage_records = Triage.objects.filter(
        is_deleted=False
    ).select_related(
        'encounter__patient', 'triaged_by__user'
    ).order_by('triage_time')[:50]
    
    # Group by triage level
    by_level = {}
    for record in triage_records:
        level = record.get_triage_level_display()
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(record)
    
    context = {
        'triage_records': triage_records,
        'by_level': by_level,
    }
    return render(request, 'hospital/triage_queue.html', context)


@login_required
def theatre_schedule(request):
    """Theatre/OR scheduling view"""
    today = timezone.now().date()
    start_date = request.GET.get('start_date', today.strftime('%Y-%m-%d'))
    end_date = request.GET.get('end_date', (today + timedelta(days=7)).strftime('%Y-%m-%d'))
    
    try:
        start_date = date.fromisoformat(start_date)
        end_date = date.fromisoformat(end_date)
    except ValueError:
        start_date = today
        end_date = today + timedelta(days=7)
    
    schedules = TheatreSchedule.objects.filter(
        scheduled_start__date__gte=start_date,
        scheduled_start__date__lte=end_date,
        is_deleted=False
    ).select_related(
        'patient', 'surgeon__user', 'anaesthetist__user'
    ).order_by('scheduled_start')
    
    # Group by theatre
    by_theatre = {}
    for schedule in schedules:
        theatre = schedule.theatre_name
        if theatre not in by_theatre:
            by_theatre[theatre] = []
        by_theatre[theatre].append(schedule)
    
    context = {
        'schedules': schedules,
        'by_theatre': by_theatre,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'hospital/theatre_schedule.html', context)


@login_required
def mar_admin(request):
    """Medication Administration Record view"""
    patient_query = request.GET.get('patient', '').strip()
    encounter_id = request.GET.get('encounter')
    date_filter = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
    
    try:
        filter_date = date.fromisoformat(date_filter)
    except ValueError:
        filter_date = timezone.now().date()
    
    mar_entries = MedicationAdministrationRecord.objects.filter(
        is_deleted=False,
        scheduled_time__date=filter_date
    ).select_related(
        'patient', 'prescription__drug', 'administered_by__user'
    ).order_by('scheduled_time')
    
    # Handle patient search - can be UUID, MRN, or name
    if patient_query:
        try:
            # Try as UUID first
            import uuid
            patient_uuid = uuid.UUID(patient_query)
            mar_entries = mar_entries.filter(patient_id=patient_uuid)
        except (ValueError, AttributeError):
            # Not a UUID, search by name or MRN
            mar_entries = mar_entries.filter(
                Q(patient__first_name__icontains=patient_query) |
                Q(patient__last_name__icontains=patient_query) |
                Q(patient__mrn__icontains=patient_query)
            )
    
    if encounter_id:
        try:
            import uuid
            encounter_uuid = uuid.UUID(encounter_id)
            mar_entries = mar_entries.filter(encounter_id=encounter_uuid)
        except (ValueError, AttributeError):
            pass  # Invalid UUID, ignore
    
    # Group by status
    scheduled = mar_entries.filter(status='scheduled')
    given = mar_entries.filter(status='given')
    missed = mar_entries.filter(status='missed')
    
    context = {
        'scheduled': scheduled,
        'given': given,
        'missed': missed,
        'filter_date': filter_date,
        'patient_query': patient_query,
    }
    return render(request, 'hospital/mar_worldclass.html', context)


@login_required
def kpi_dashboard(request):
    """Comprehensive KPI dashboard"""
    # Get date range from request or default to last 30 days
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = None
    
    if end_date:
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = None
    
    # Get comprehensive report
    report = get_comprehensive_report(start_date, end_date)
    
    # Additional real-time metrics
    from .utils import get_dashboard_stats
    current_stats = get_dashboard_stats()
    
    # Extract AR aging values for easier template access
    ar_aging = report.get('financial', {}).get('ar_aging', {})
    ar_0_30 = ar_aging.get('0-30', 0)
    ar_90_plus = ar_aging.get('90+', 0)
    
    context = {
        'report': report,
        'current_stats': current_stats,
        'start_date': start_date or (timezone.now().date() - timedelta(days=30)),
        'end_date': end_date or timezone.now().date(),
        'ar_0_30': ar_0_30,
        'ar_90_plus': ar_90_plus,
    }
    
    return render(request, 'hospital/kpi_dashboard.html', context)


@login_required
def provider_calendar(request, provider_id=None):
    """Provider schedule calendar view"""
    if provider_id:
        provider = get_object_or_404(Staff, pk=provider_id, is_deleted=False)
    else:
        # Get current user's staff profile
        if hasattr(request.user, 'staff_profile'):
            provider = request.user.staff
        else:
            messages.error(request, 'You do not have a staff profile.')
            return redirect('hospital:dashboard')
    
    # Get schedules for next 2 weeks
    start_date = timezone.now().date()
    end_date = start_date + timedelta(days=14)
    
    schedules = ProviderSchedule.objects.filter(
        provider=provider,
        date__gte=start_date,
        date__lte=end_date,
        is_deleted=False
    ).select_related('department').order_by('date', 'start_time')
    
    # Get appointments
    from .models import Appointment
    appointments = Appointment.objects.filter(
        provider=provider,
        appointment_date__date__gte=start_date,
        appointment_date__date__lte=end_date,
        is_deleted=False
    ).select_related('patient').order_by('appointment_date')
    
    # Generate calendar days (2 weeks)
    from calendar import monthcalendar
    days = []
    current_date = start_date
    while current_date <= end_date:
        days.append(current_date)
        current_date += timedelta(days=1)
    
    context = {
        'provider': provider,
        'schedules': schedules,
        'appointments': appointments,
        'start_date': start_date,
        'end_date': end_date,
        'days': days,
        'today': timezone.now().date(),
    }
    return render(request, 'hospital/provider_calendar.html', context)


@login_required
def handover_sheet_list(request):
    """List handover sheets"""
    ward_id = request.GET.get('ward')
    shift_type = request.GET.get('shift_type')
    
    handovers = HandoverSheet.objects.filter(
        is_deleted=False
    ).select_related('ward', 'created_by__user').order_by('-date', '-shift_start')
    
    if ward_id:
        handovers = handovers.filter(ward_id=ward_id)
    if shift_type:
        handovers = handovers.filter(shift_type=shift_type)
    
    paginator = Paginator(handovers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'handovers': page_obj,
        'wards': Ward.objects.filter(is_active=True, is_deleted=False),
    }
    return render(request, 'hospital/handover_sheet_list.html', context)


@login_required
def equipment_list(request):
    """Medical equipment list with maintenance status"""
    from .models_advanced import MedicalEquipment, MaintenanceLog
    
    equipment = MedicalEquipment.objects.filter(
        is_deleted=False
    ).prefetch_related('maintenance_logs').order_by('name')
    
    location_filter = request.GET.get('location')
    status_filter = request.GET.get('status')
    maintenance_due = request.GET.get('maintenance_due') == '1'
    
    if location_filter:
        equipment = equipment.filter(location=location_filter)
    if status_filter:
        equipment = equipment.filter(status=status_filter)
    if maintenance_due:
        from datetime import date
        equipment = equipment.filter(
            next_maintenance_due__lte=date.today()
        )
    
    paginator = Paginator(equipment, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'equipment': page_obj,
        'locations': MedicalEquipment.objects.values_list('location', flat=True).distinct(),
    }
    return render(request, 'hospital/equipment_list.html', context)


@login_required
def consumables_list(request):
    """Consumables inventory list"""
    from .models_advanced import ConsumablesInventory
    
    consumables = ConsumablesInventory.objects.filter(
        is_deleted=False
    ).order_by('item_name')
    
    category_filter = request.GET.get('category')
    location_filter = request.GET.get('location')
    low_stock_only = request.GET.get('low_stock') == '1'
    
    if category_filter:
        consumables = consumables.filter(category=category_filter)
    if location_filter:
        consumables = consumables.filter(location=location_filter)
    if low_stock_only:
        from django.db.models import F
        consumables = consumables.filter(quantity_on_hand__lte=F('reorder_level'))
    
    paginator = Paginator(consumables, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'consumables': page_obj,
        'categories': ConsumablesInventory.objects.values_list('category', flat=True).distinct(),
        'locations': ConsumablesInventory.objects.values_list('location', flat=True).distinct(),
    }
    return render(request, 'hospital/consumables_list.html', context)


@login_required
def queue_create(request):
    """Create a new queue entry"""
    from .forms_advanced import QueueForm
    from .models import Encounter
    
    if request.method == 'POST':
        form = QueueForm(request.POST)
        if form.is_valid():
            queue = form.save(commit=False)
            # Auto-assign queue number if not provided
            if not queue.queue_number:
                last_queue = Queue.objects.filter(
                    department=queue.department,
                    location=queue.location
                ).order_by('-queue_number').first()
                queue.queue_number = (last_queue.queue_number + 1) if last_queue else 1
            
            queue.checked_in_at = timezone.now()
            queue.status = 'waiting'
            queue.save()
            messages.success(request, 'Patient added to queue successfully.')
            return redirect('hospital:queue_display')
    else:
        form = QueueForm()
        # Pre-select encounter if provided
        encounter_id = request.GET.get('encounter')
        if encounter_id:
            try:
                encounter = Encounter.objects.get(pk=encounter_id, is_deleted=False)
                form.fields['encounter'].initial = encounter
            except Encounter.DoesNotExist:
                pass
    
    context = {
        'form': form,
        'title': 'Add Patient to Queue',
    }
    return render(request, 'hospital/queue_form.html', context)


@login_required
def queue_action(request, queue_id, action):
    """Perform actions on queue items: call, complete, skip"""
    queue = get_object_or_404(QueueModel, pk=queue_id, is_deleted=False)
    
    if action == 'call':
        # Call next patient - move to in_consultation
        if queue.status in ['checked_in', 'waiting']:
            queue.status = 'in_consultation'
            # QueueEntry uses: called_time and started_time
            if hasattr(queue, 'called_time'):
                queue.called_time = timezone.now()
            if hasattr(queue, 'started_time'):
                queue.started_time = timezone.now()
            queue.save()
            messages.success(request, f'Called patient #{queue.queue_number} - {queue.encounter.patient.full_name}')
        else:
            messages.warning(request, 'Patient is already in consultation.')
    
    elif action == 'complete':
        # Complete - move to completed
        queue.status = 'completed'
        # QueueEntry uses: completed_time
        if hasattr(queue, 'completed_time'):
            queue.completed_time = timezone.now()
        # Calculate actual wait time
        if hasattr(queue, 'check_in_time') and hasattr(queue, 'started_time'):
            if queue.check_in_time and queue.started_time:
                wait_seconds = (queue.started_time - queue.check_in_time).total_seconds()
                queue.actual_wait_minutes = int(wait_seconds / 60)
        queue.save()
        messages.success(request, f'Completed queue entry #{queue.queue_number}')
    
    elif action == 'skip':
        # Skip patient - move to skipped
        queue.status = 'skipped'
        queue.save()
        messages.info(request, f'Skipped queue entry #{queue.queue_number}')
    
    elif action == 'recall':
        # Put back to waiting
        if queue.status in ['skipped', 'completed']:
            queue.status = 'checked_in'
            queue.called_at = None
            queue.completed_at = None
            queue.save(update_fields=['status', 'called_at', 'completed_at', 'modified'])
            messages.success(request, f'Patient #{queue.queue_number} returned to waiting queue')
        else:
            messages.warning(request, 'Can only recall completed or skipped patients.')
    
    else:
        messages.error(request, 'Invalid action.')
    
    # Redirect back with same filters
    from django.urls import reverse
    from urllib.parse import urlencode
    
    params = {}
    department = request.GET.get('department', '').strip()
    location = request.GET.get('location', '').strip()
    
    # Only add params if they have valid values (not None, not empty, not the string 'None')
    if department and department.lower() not in ['none', 'null', '']:
        params['department'] = department
    if location and location.lower() not in ['none', 'null', '']:
        params['location'] = location
    
    # Build redirect URL
    try:
        redirect_url = reverse('hospital:queue_display')
        if params:
            redirect_url += '?' + urlencode(params)
        return redirect(redirect_url)
    except Exception as e:
        # Fallback to queue_display without parameters
        return redirect('hospital:queue_display')


@login_required
def queue_call_next(request):
    """AJAX endpoint to call next patient in queue"""
    department_id = request.GET.get('department') or request.POST.get('department')
    location = request.GET.get('location', '') or request.POST.get('location', '')
    
    # Find next patient in waiting queue - use QueueEntry model
    queues = QueueModel.objects.filter(
        is_deleted=False,
        status__in=['checked_in', 'waiting']
    ).order_by('priority', 'sequence_number')
    
    if department_id and department_id != 'None':
        queues = queues.filter(department_id=department_id)
    if location and location != 'None' and location != '':
        queues = queues.filter(location=location)
    
    # Get first patient (already ordered by priority and sequence)
    next_queue = queues.first()
    
    if next_queue:
        next_queue.status = 'in_consultation'
        # QueueEntry uses: called_time and started_time
        if hasattr(next_queue, 'called_time'):
            next_queue.called_time = timezone.now()
        if hasattr(next_queue, 'started_time'):
            next_queue.started_time = timezone.now()
        next_queue.save()
        
        # Send SMS notification to patient
        sms_sent = False
        sms_message = ''
        try:
            patient = next_queue.encounter.patient
            department_name = next_queue.department.name if next_queue.department else 'clinic'
            location_display = 'clinic'  # Simplified - QueueEntry may not have location
            
            if patient and patient.phone_number:
                from .services.sms_service import sms_service
                
                sms_message = (
                    f"Dear {patient.first_name},\n\n"
                    f"You are next in queue! Queue #{next_queue.queue_number}.\n"
                    f"Please proceed to {department_name} - {location_display}.\n\n"
                    f"Thank you.\nPrimeCare Medical"
                )
                
                sms_log = sms_service.send_sms(
                    phone_number=patient.phone_number,
                    message=sms_message,
                    message_type='queue_notification',
                    recipient_name=patient.full_name,
                    related_object_id=next_queue.id,
                    related_object_type='Queue'
                )
                sms_sent = (sms_log.status == 'sent')
        except Exception as e:
            # Log error but don't fail the queue action
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send SMS for queue {next_queue.id}: {str(e)}")
        
        # For POST requests (form submission), redirect
        if request.method == 'POST':
            messages.success(request, f'✅ Called patient #{next_queue.queue_number} - {next_queue.encounter.patient.full_name}')
            return redirect('hospital:queue_display')
        
        # For GET/AJAX requests, return JSON
        response_data = {
            'success': True,
            'queue_number': next_queue.queue_number,
            'patient_name': next_queue.encounter.patient.full_name if next_queue.encounter and next_queue.encounter.patient else 'Unknown',
            'mrn': next_queue.encounter.patient.mrn if next_queue.encounter and next_queue.encounter.patient else '',
            'message': f'Called #{next_queue.queue_number}',
            'sms_sent': sms_sent
        }
        
        return JsonResponse(response_data)
    else:
        # No patients in queue
        if request.method == 'POST':
            messages.warning(request, 'No patients in waiting queue')
            return redirect('hospital:queue_display')
        
        return JsonResponse({
            'success': False,
            'message': 'No patients in waiting queue'
        })


@login_required
def queue_data_api(request):
    """AJAX API endpoint to get current queue data"""
    department_id = request.GET.get('department')
    location = request.GET.get('location', '')
    
    # Use QueueEntry model
    queues = QueueModel.objects.filter(
        is_deleted=False,
        status__in=['checked_in', 'waiting', 'in_consultation']
    ).select_related(
        'encounter__patient', 'department'
    )
    
    if department_id and department_id != 'None':
        queues = queues.filter(department_id=department_id)
    if location and location != 'None' and location != '':
        queues = queues.filter(location=location)
    
    # Order by priority (1=highest) and sequence_number
    waiting = list(queues.filter(status__in=['checked_in', 'waiting']).order_by('priority', 'sequence_number'))
    in_progress = list(queues.filter(status='in_consultation').order_by('priority', 'sequence_number'))
    
    # Serialize queue data
    def serialize_queue(q):
        # QueueEntry uses: check_in_time, called_time, started_time, completed_time
        checked_in = getattr(q, 'check_in_time', None)
        called = getattr(q, 'called_time', None) or getattr(q, 'started_time', None)
        wait_time = getattr(q, 'estimated_wait_minutes', 0)
        
        return {
            'id': str(q.id),
            'queue_number': q.queue_number,
            'patient_name': q.encounter.patient.full_name if q.encounter and q.encounter.patient else 'Unknown',
            'mrn': q.encounter.patient.mrn if q.encounter and q.encounter.patient else '',
            'priority': q.priority,
            'priority_display': q.get_priority_display(),
            'department': q.department.name if q.department else '',
            'checked_in_at': checked_in.isoformat() if checked_in else timezone.now().isoformat(),
            'called_at': called.isoformat() if called else None,
            'estimated_wait_time': wait_time,
        }
    
    return JsonResponse({
        'success': True,
        'waiting': [serialize_queue(q) for q in waiting],
        'in_progress': [serialize_queue(q) for q in in_progress],
        'waiting_count': len(waiting),
        'in_progress_count': len(in_progress),
        'timestamp': timezone.now().isoformat()
    })


@login_required
def triage_create(request):
    """Create a new triage record"""
    from .forms_advanced import TriageForm
    
    if request.method == 'POST':
        form = TriageForm(request.POST)
        if form.is_valid():
            triage = form.save(commit=False)
            triage.triage_time = timezone.now()
            # Get current user's staff profile
            if hasattr(request.user, 'staff_profile'):
                triage.triaged_by = request.user.staff
            triage.save()
            messages.success(request, 'Triage record created successfully.')
            return redirect('hospital:triage_queue')
    else:
        form = TriageForm()
        # Pre-select encounter if provided
        encounter_id = request.GET.get('encounter')
        if encounter_id:
            try:
                from .models import Encounter
                encounter = Encounter.objects.get(pk=encounter_id, is_deleted=False)
                form.fields['encounter'].initial = encounter
                form.fields['chief_complaint'].initial = encounter.chief_complaint
            except Encounter.DoesNotExist:
                pass
    
    context = {
        'form': form,
        'title': 'Create Triage Record',
    }
    return render(request, 'hospital/triage_form.html', context)


@login_required
def appointment_create(request):
    """Create a new appointment"""
    from .forms_advanced import AppointmentForm
    
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save()
            messages.success(request, 'Appointment created successfully.')
            return redirect('hospital:frontdesk_appointment_dashboard')
    else:
        form = AppointmentForm()
        # Pre-select provider if user has staff profile
        if hasattr(request.user, 'staff_profile'):
            form.fields['provider'].initial = request.user.staff
            if request.user.staff.department:
                form.fields['department'].initial = request.user.staff.department
    
    context = {
        'form': form,
        'title': 'Create Appointment',
    }
    return render(request, 'hospital/appointment_form.html', context)


@login_required
def incident_list_view(request):
    """Incident log list"""
    from .models_advanced import IncidentLog
    
    incidents = IncidentLog.objects.filter(
        is_deleted=False
    ).select_related(
        'patient', 'staff', 'reported_by__user'
    ).order_by('-incident_date')
    
    type_filter = request.GET.get('type')
    severity_filter = request.GET.get('severity')
    status_filter = request.GET.get('status')
    
    if type_filter:
        incidents = incidents.filter(incident_type=type_filter)
    if severity_filter:
        incidents = incidents.filter(severity=severity_filter)
    if status_filter:
        incidents = incidents.filter(status=status_filter)
    
    paginator = Paginator(incidents, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'incidents': page_obj,
    }
    return render(request, 'hospital/incident_list.html', context)


@login_required
def mar_administer(request, mar_id):
    """Administer medication via AJAX"""
    from .models_advanced import MedicationAdministrationRecord
    from django.http import JsonResponse
    
    mar = get_object_or_404(MedicationAdministrationRecord, pk=mar_id, is_deleted=False)
    
    if request.method == 'POST':
        dose_given = request.POST.get('dose_given', mar.prescription.dosage)
        notes = request.POST.get('notes', '')
        
        # Get current user's staff profile
        staff = None
        if hasattr(request.user, 'staff_profile'):
            staff = request.user.staff
        
        mar.status = 'given'
        mar.dose_given = dose_given
        mar.notes = notes
        mar.administered_time = timezone.now()
        mar.administered_by = staff
        mar.save()
        
        return JsonResponse({'status': 'success', 'message': 'Medication administered successfully'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


@login_required
def api_kpi_stats(request):
    """API endpoint for KPI statistics (AJAX)"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            start_date = date.fromisoformat(start_date)
        except ValueError:
            start_date = None
    
    if end_date:
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = None
    
    report = get_comprehensive_report(start_date, end_date)
    
    # Convert Decimal to float for JSON serialization
    import json
    from decimal import Decimal
    
    def default(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError
    
    return JsonResponse(report, safe=False, json_dumps_params={'default': default})


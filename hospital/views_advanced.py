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
from pathlib import Path
import os
from django.conf import settings
from .models import Patient, Encounter, Staff, Department, Ward
from .models_advanced import (
    Queue, Triage, ImagingStudy, TheatreSchedule,
    MedicationAdministrationRecord, HandoverSheet,
    TheatreSchedule, ProviderSchedule
)
# Also import QueueEntry from models_queue (they might be different models)
# Support both Queue (old) and QueueEntry (new) models
try:
    from .models_queue import QueueEntry, HealthTip
    HAS_QUEUE_ENTRY = True
except ImportError:
    QueueEntry = None
    HealthTip = None
    HAS_QUEUE_ENTRY = False
from .reports_advanced import get_comprehensive_report


def queue_display(request):
    """
    Public waiting-area queue board (TV / kiosk). Must stay accessible without login
    so the live feed and voice can run on shared displays.
    Staff-only actions (call next) are gated in the template/JS when not authenticated.
    """
    department_id = request.GET.get('department', '').strip()
    location = request.GET.get('location', '').strip()
    
    today = timezone.now().date()
    
    # Use QueueEntry if available and has data, otherwise fall back to Queue
    if HAS_QUEUE_ENTRY and QueueEntry.objects.filter(is_deleted=False, queue_date=today).exists():
        # Use new QueueEntry model
        queues = QueueEntry.objects.filter(
            is_deleted=False,
            queue_date=today
        ).select_related(
            'patient', 'encounter__patient', 'encounter__provider', 'encounter__provider__user',
            'department', 'assigned_doctor',
        ).order_by('priority', 'sequence_number')
        use_queue_entry = True
    elif Queue.objects.filter(is_deleted=False, checked_in_at__date=today).exists():
        # Use old Queue model (has data)
        queues = Queue.objects.filter(
            is_deleted=False,
            checked_in_at__date=today
        ).select_related(
            'encounter__patient', 'encounter__provider', 'encounter__provider__user', 'department',
        ).order_by('queue_number')
        use_queue_entry = False
    elif HAS_QUEUE_ENTRY:
        # No data yet, but use QueueEntry for new entries
        queues = QueueEntry.objects.filter(
            is_deleted=False,
            queue_date=today
        ).select_related(
            'patient', 'encounter__patient', 'encounter__provider', 'encounter__provider__user',
            'department', 'assigned_doctor',
        ).order_by('priority', 'sequence_number')
        use_queue_entry = True
    else:
        # Fallback to Queue
        queues = Queue.objects.filter(
            is_deleted=False,
            checked_in_at__date=today
        ).select_related(
            'encounter__patient', 'encounter__provider', 'encounter__provider__user', 'department',
        ).order_by('queue_number')
        use_queue_entry = False
    
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
    # Note: QueueEntry doesn't have a location field, only Queue (old model) does
    selected_location = None
    if location and location.lower() not in ['none', 'null', '']:
        if not use_queue_entry:
            # Only filter by location for old Queue model
            queues = queues.filter(location=location)
        # For QueueEntry, location filtering is not available
        selected_location = location
    
    # Group by status and priority for proper ordering
    stale_cutoff = timezone.now() - timedelta(minutes=20)
    if use_queue_entry:
        # QueueEntry statuses: 'checked_in', 'called', 'in_progress', 'completed', 'no_show', 'cancelled'
        waiting_statuses = ['checked_in', 'called']
        waiting = list(queues.filter(status__in=waiting_statuses).order_by('priority', 'sequence_number'))
        in_progress = list(queues.filter(status='in_progress').order_by('called_time', 'priority'))
        # Get completed entries for today
        completed_queues = QueueEntry.objects.filter(
            is_deleted=False,
            queue_date=today,
            status='completed'
        )
        if department_id and department_id.lower() not in ['none', 'null', '']:
            try:
                department = Department.objects.get(pk=department_id, is_deleted=False)
                completed_queues = completed_queues.filter(department=department)
            except (Department.DoesNotExist, ValueError):
                pass
        # Note: QueueEntry doesn't have a location field, so we skip location filtering here
        # Location filtering is only available for the old Queue model
        completed_today = completed_queues.count()
    else:
        # Queue statuses: 'waiting', 'in_progress', 'completed', 'skipped'
        waiting_statuses = ['waiting']
        waiting = list(queues.filter(status__in=waiting_statuses).order_by('queue_number'))
        in_progress = list(queues.filter(status='in_progress').order_by('called_at', 'queue_number'))
        # Get completed entries for today
        completed_queues = Queue.objects.filter(
            is_deleted=False,
            checked_in_at__date=today,
            status='completed'
        )
        if department_id and department_id.lower() not in ['none', 'null', '']:
            try:
                department = Department.objects.get(pk=department_id, is_deleted=False)
                completed_queues = completed_queues.filter(department=department)
            except (Department.DoesNotExist, ValueError):
                pass
        if location and location.lower() not in ['none', 'null', '']:
            completed_queues = completed_queues.filter(location=location)
        completed_today = completed_queues.count()
    
    # Pick a true "now serving" candidate:
    # 1) active consultation (in_progress) by latest call time
    # 2) latest called ticket
    # 3) first waiting fallback
    if use_queue_entry:
        called_waiting = [q for q in waiting if getattr(q, 'status', '') == 'called']
        latest_called = None
        if called_waiting:
            called_waiting.sort(
                key=lambda q: (
                    getattr(q, 'called_time', None) or timezone.now() - timedelta(days=36500),
                    int(getattr(q, 'priority', 99) or 99),
                    int(getattr(q, 'sequence_number', 0) or 0),
                ),
                reverse=True,
            )
            latest_called = called_waiting[0]
        latest_in_progress = in_progress[0] if in_progress else None
        if latest_in_progress and latest_called:
            in_progress_mark = getattr(latest_in_progress, 'called_time', None) or getattr(latest_in_progress, 'started_time', None)
            called_mark = getattr(latest_called, 'called_time', None) or getattr(latest_called, 'started_time', None)
            now_serving = latest_called if called_mark and (not in_progress_mark or called_mark >= in_progress_mark) else latest_in_progress
        else:
            now_serving = latest_in_progress or latest_called or (waiting[0] if waiting else None)
        if now_serving and getattr(now_serving, 'status', '') == 'in_progress':
            active_mark = getattr(now_serving, 'started_time', None) or getattr(now_serving, 'called_time', None)
            if active_mark and active_mark < stale_cutoff and waiting:
                now_serving = latest_called or waiting[0]
    else:
        called_waiting = [q for q in waiting if getattr(q, 'status', '') == 'called']
        latest_called = None
        if called_waiting:
            called_waiting.sort(
                key=lambda q: (
                    getattr(q, 'called_at', None) or timezone.now() - timedelta(days=36500),
                    int(getattr(q, 'queue_number', 0) or 0),
                ),
                reverse=True,
            )
            latest_called = called_waiting[0]
        latest_in_progress = in_progress[0] if in_progress else None
        if latest_in_progress and latest_called:
            in_progress_mark = getattr(latest_in_progress, 'called_at', None)
            called_mark = getattr(latest_called, 'called_at', None)
            now_serving = latest_called if called_mark and (not in_progress_mark or called_mark >= in_progress_mark) else latest_in_progress
        else:
            now_serving = latest_in_progress or latest_called or (waiting[0] if waiting else None)
        if now_serving and getattr(now_serving, 'status', '') == 'in_progress':
            active_mark = getattr(now_serving, 'called_at', None)
            if active_mark and active_mark < stale_cutoff and waiting:
                now_serving = latest_called or waiting[0]
    
    health_tips = []
    try:
        tips_qs = HealthTip.objects.filter(is_active=True).order_by('display_order')[:8]
        today_date = timezone.now().date()
        health_tips = [tip for tip in tips_qs if tip.is_visible(today_date)]
    except (NameError, AttributeError, Exception) as e:
        # HealthTip model not available or table doesn't exist
        health_tips = []
    
    # Calculate average wait time
    avg_wait_minutes = 0
    if use_queue_entry:
        completed_with_wait = QueueEntry.objects.filter(
            is_deleted=False,
            queue_date=today,
            status='completed',
            actual_wait_minutes__isnull=False
        )
        if completed_with_wait.exists():
            from django.db.models import Avg
            avg_wait = completed_with_wait.aggregate(avg=Avg('actual_wait_minutes'))
            avg_wait_minutes = int(avg_wait['avg'] or 0)
    else:
        # For Queue model, calculate from checked_in_at to completed_at
        completed_with_times = Queue.objects.filter(
            is_deleted=False,
            checked_in_at__date=today,
            status='completed',
            checked_in_at__isnull=False,
            completed_at__isnull=False
        )
        if completed_with_times.exists():
            total_wait = 0
            count = 0
            for q in completed_with_times:
                if q.checked_in_at and q.completed_at:
                    wait_seconds = (q.completed_at - q.checked_in_at).total_seconds()
                    total_wait += wait_seconds / 60  # Convert to minutes
                    count += 1
            if count > 0:
                avg_wait_minutes = int(total_wait / count)
    
    # Ensure completed_today is always a number, never None
    if completed_today is None:
        completed_today = 0
    else:
        completed_today = int(completed_today)
    
    # Ensure avg_wait_minutes is a number
    if avg_wait_minutes is None:
        avg_wait_minutes = 0
    
    # Collect slideshow images — only from explicit waiting-room folders.
    # Never pull from imaging/radiology paths (patient scans may live there).
    slideshow_images = []
    allowed_ext = ('.jpg', '.jpeg', '.png', '.webp', '.gif')
    media_root = Path(settings.MEDIA_ROOT)
    media_url = settings.MEDIA_URL.rstrip('/') + '/'

    def _slide_path_allowed(rel_posix: str) -> bool:
        p = rel_posix.replace('\\', '/').lower()
        for frag in (
            'imaging_studies',
            '/dicom',
            'dicom/',
            '/radiology',
            'radiology/',
            'xray_',
            '_xray',
            '/mri',
            'mri/',
            '/ct_',
            '/ultrasound',
            'patient_documents',
            'lab_results',
        ):
            if frag in p:
                return False
        return True

    # Priority folders (clinical media such as imaging_studies is intentionally excluded)
    priority_folders = [
        'queue_display',
        'waiting_room_slides',
        'reception_slides',
        'slideshow',
    ]

    for folder_name in priority_folders:
        folder_path = media_root / folder_name
        if folder_path.exists() and folder_path.is_dir():
            try:
                for img_file in folder_path.rglob('*'):
                    if img_file.is_file() and img_file.suffix.lower() in allowed_ext:
                        try:
                            rel_path = img_file.relative_to(media_root).as_posix()
                            if not _slide_path_allowed(rel_path):
                                continue
                            image_url = f"{media_url}{rel_path}"
                            slideshow_images.append({
                                'url': image_url,
                                'caption': img_file.stem.replace('_', ' ').replace('-', ' ').title(),
                                'mtime': img_file.stat().st_mtime,
                            })
                        except Exception:
                            continue
            except Exception:
                continue

    # Do not scan arbitrary media root — avoids accidentally showing uploads or scans
    
    # Sort by modification time and limit to 20
    slideshow_images.sort(key=lambda x: x.get('mtime', 0), reverse=True)
    slideshow_images = slideshow_images[:20]
    
    # Debug: Print results to console (for immediate debugging)
    print(f"\n{'='*60}")
    print(f"SLIDESHOW IMAGES DEBUG")
    print(f"{'='*60}")
    print(f"MEDIA_ROOT: {media_root}")
    print(f"MEDIA_ROOT exists: {media_root.exists()}")
    print(f"MEDIA_URL: {media_url}")
    print(f"Images found: {len(slideshow_images)}")
    if slideshow_images:
        print(f"First 3 image URLs:")
        for i, img in enumerate(slideshow_images[:3], 1):
            print(f"  {i}. {img['url']}")
    else:
        print("⚠️ NO IMAGES FOUND!")
        print("Searched in:")
        for folder_name in priority_folders:
            search_dir = media_root / folder_name
            exists = search_dir.exists()
            is_dir = search_dir.is_dir() if exists else False
            print(f"  - {folder_name}: exists={exists}, is_dir={is_dir}")
    print(f"{'='*60}\n")
    
    # Also log to logger
    import logging
    logger = logging.getLogger(__name__)
    if slideshow_images:
        logger.info(f"✅ Found {len(slideshow_images)} slideshow images")
        if slideshow_images:
            logger.info(f"First image URL: {slideshow_images[0]['url']}")
    else:
        logger.warning(f"⚠️ No slideshow images found")
        logger.warning(f"MEDIA_ROOT: {media_root}, exists: {media_root.exists()}")

    context = {
        'waiting': waiting,
        'in_progress': in_progress,
        'now_serving': now_serving,
        'completed_today': completed_today,
        'avg_wait_minutes': avg_wait_minutes,
        'departments': Department.objects.filter(is_active=True, is_deleted=False),
        'selected_department': selected_department_id,  # None or string ID
        'selected_location': selected_location,  # None or valid location
        'health_tips': health_tips,
        'use_queue_entry': use_queue_entry,  # Flag to indicate which model is being used
        'slideshow_images': slideshow_images,
        'today': timezone.now(),  # Add today for calendar widget
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
    # Try to find in QueueEntry first, then Queue
    queue = None
    use_queue_entry = False
    
    if HAS_QUEUE_ENTRY:
        try:
            queue = QueueEntry.objects.get(pk=queue_id, is_deleted=False)
            use_queue_entry = True
        except QueueEntry.DoesNotExist:
            pass
    
    if not queue:
        try:
            queue = Queue.objects.get(pk=queue_id, is_deleted=False)
            use_queue_entry = False
        except Queue.DoesNotExist:
            from django.http import Http404
            raise Http404("Queue entry not found")
    
    if action == 'call':
        # Call next patient - move to in_progress
        if use_queue_entry:
            # QueueEntry statuses: 'checked_in', 'called', 'in_progress'
            if queue.status in ['checked_in', 'called']:
                queue.status = 'in_progress'
                if hasattr(queue, 'called_time'):
                    queue.called_time = timezone.now()
                if hasattr(queue, 'started_time'):
                    queue.started_time = timezone.now()
                queue.save()
                patient_name = queue.patient.full_name if hasattr(queue, 'patient') else queue.encounter.patient.full_name
                messages.success(request, f'Called patient #{queue.queue_number} - {patient_name}')
            else:
                messages.warning(request, 'Patient is already in consultation.')
        else:
            # Queue statuses: 'waiting', 'in_progress'
            if queue.status == 'waiting':
                queue.status = 'in_progress'
                queue.called_at = timezone.now()
                queue.save()
                messages.success(request, f'Called patient #{queue.queue_number} - {queue.encounter.patient.full_name}')
            else:
                messages.warning(request, 'Patient is already in consultation.')
    
    elif action == 'complete':
        # Complete - move to completed
        queue.status = 'completed'
        if use_queue_entry:
            # QueueEntry uses: completed_time
            if hasattr(queue, 'completed_time'):
                queue.completed_time = timezone.now()
            # Calculate actual wait time
            if hasattr(queue, 'check_in_time') and hasattr(queue, 'started_time'):
                if queue.check_in_time and queue.started_time:
                    wait_seconds = (queue.started_time - queue.check_in_time).total_seconds()
                    if hasattr(queue, 'actual_wait_minutes'):
                        queue.actual_wait_minutes = int(wait_seconds / 60)
        else:
            # Queue uses: completed_at
            queue.completed_at = timezone.now()
        queue.save()
        messages.success(request, f'Completed queue entry #{queue.queue_number}')
    
    elif action == 'skip':
        # Skip patient
        if use_queue_entry:
            queue.status = 'no_show'
        else:
            queue.status = 'skipped'
        queue.save()
        messages.info(request, f'Skipped queue entry #{queue.queue_number}')
    
    elif action == 'recall':
        # Put back to waiting
        if use_queue_entry:
            if queue.status in ['no_show', 'completed', 'cancelled']:
                queue.status = 'checked_in'
                if hasattr(queue, 'called_time'):
                    queue.called_time = None
                if hasattr(queue, 'completed_time'):
                    queue.completed_time = None
                queue.save()
                messages.success(request, f'Patient #{queue.queue_number} returned to waiting queue')
            else:
                messages.warning(request, 'Can only recall completed, no-show, or cancelled patients.')
        else:
            if queue.status in ['skipped', 'completed']:
                queue.status = 'waiting'
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
    # Use QueueEntry if available, otherwise Queue
    if HAS_QUEUE_ENTRY and QueueEntry.objects.filter(is_deleted=False).exists():
        queues = QueueEntry.objects.filter(
            is_deleted=False,
            status__in=['checked_in', 'called']
        ).order_by('priority', 'sequence_number')
    else:
        queues = Queue.objects.filter(
            is_deleted=False,
            status='waiting'
        ).order_by('queue_number')
    
    if department_id and department_id != 'None':
        queues = queues.filter(department_id=department_id)
    if location and location != 'None' and location != '':
        queues = queues.filter(location=location)
    
    # Get first patient (already ordered by priority and sequence)
    next_queue = queues.first()
    
    if next_queue:
        # Update status based on model type
        if HAS_QUEUE_ENTRY and isinstance(next_queue, QueueEntry):
            next_queue.status = 'in_progress'
            if hasattr(next_queue, 'called_time'):
                next_queue.called_time = timezone.now()
            if hasattr(next_queue, 'started_time'):
                next_queue.started_time = timezone.now()
        else:
            next_queue.status = 'in_progress'
            if hasattr(next_queue, 'called_at'):
                next_queue.called_at = timezone.now()
        next_queue.save()
        
        # Send SMS notification to patient
        sms_sent = False
        sms_message = ''
        try:
            # Get patient - QueueEntry has patient directly, Queue has it through encounter
            if hasattr(next_queue, 'patient'):
                patient = next_queue.patient
            else:
                patient = next_queue.encounter.patient if next_queue.encounter else None
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
        
        # Check if this is an AJAX request (based on Accept header or content type)
        is_ajax = (
            request.headers.get('Accept', '').find('application/json') != -1 or
            request.content_type == 'application/json' or
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        )
        
        # For POST requests that are NOT AJAX (form submission), redirect
        if request.method == 'POST' and not is_ajax:
            messages.success(request, f'✅ Called patient #{next_queue.queue_number} - {next_queue.encounter.patient.full_name if next_queue.encounter else "Unknown"}')
            return redirect('hospital:queue_display')
        
        # For AJAX/JSON requests, always return JSON
        try:
            patient_name = 'Unknown'
            mrn = ''
            if hasattr(next_queue, 'patient') and next_queue.patient:
                patient_name = next_queue.patient.full_name
                mrn = next_queue.patient.mrn or ''
            elif next_queue.encounter and next_queue.encounter.patient:
                patient_name = next_queue.encounter.patient.full_name
                mrn = next_queue.encounter.patient.mrn or ''
        except Exception:
            pass  # Use defaults if error accessing patient
        
        response_data = {
            'success': True,
            'queue_number': str(next_queue.queue_number) if next_queue.queue_number else '',
            'patient_name': patient_name,
            'mrn': mrn,
            'message': f'Called #{next_queue.queue_number}' if next_queue.queue_number else 'Called patient',
            'sms_sent': sms_sent
        }
        
        return JsonResponse(response_data)
    else:
        # No patients in queue
        is_ajax = (
            request.headers.get('Accept', '').find('application/json') != -1 or
            request.content_type == 'application/json' or
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        )
        
        if request.method == 'POST' and not is_ajax:
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
    # Use QueueEntry if available, otherwise Queue
    if HAS_QUEUE_ENTRY and QueueEntry.objects.filter(is_deleted=False).exists():
        queues = QueueEntry.objects.filter(
            is_deleted=False,
            status__in=['checked_in', 'called', 'in_progress']
        ).select_related(
            'patient', 'encounter__patient', 'department', 'assigned_doctor'
        )
    else:
        queues = Queue.objects.filter(
            is_deleted=False,
            status__in=['waiting', 'in_progress']
        ).select_related(
            'encounter__patient', 'department'
        )
    
    if department_id and department_id != 'None':
        queues = queues.filter(department_id=department_id)
    if location and location != 'None' and location != '':
        queues = queues.filter(location=location)
    
    # Order by priority (1=highest) and sequence_number
    if HAS_QUEUE_ENTRY and QueueEntry.objects.filter(is_deleted=False).exists():
        waiting = list(queues.filter(status__in=['checked_in', 'called']).order_by('priority', 'sequence_number'))
        in_progress = list(queues.filter(status='in_progress').order_by('priority', 'sequence_number'))
        # Get completed count for today
        completed_queues = QueueEntry.objects.filter(
            is_deleted=False,
            queue_date=timezone.now().date(),
            status='completed'
        )
        if department_id and department_id != 'None':
            completed_queues = completed_queues.filter(department_id=department_id)
        if location and location != 'None' and location != '':
            completed_queues = completed_queues.filter(location=location)
        completed_today = completed_queues.count()
        # Calculate average wait time
        from django.db.models import Avg
        avg_wait = completed_queues.filter(actual_wait_minutes__isnull=False).aggregate(avg=Avg('actual_wait_minutes'))
        avg_wait_minutes = int(avg_wait['avg'] or 0) if avg_wait['avg'] else 0
    else:
        waiting = list(queues.filter(status='waiting').order_by('queue_number'))
        in_progress = list(queues.filter(status='in_progress').order_by('queue_number'))
        # Get completed count for today
        completed_queues = Queue.objects.filter(
            is_deleted=False,
            checked_in_at__date=timezone.now().date(),
            status='completed'
        )
        if department_id and department_id != 'None':
            completed_queues = completed_queues.filter(department_id=department_id)
        if location and location != 'None' and location != '':
            completed_queues = completed_queues.filter(location=location)
        completed_today = completed_queues.count()
        # Calculate average wait time
        total_wait = 0
        count = 0
        for q in completed_queues.filter(checked_in_at__isnull=False, completed_at__isnull=False):
            if q.checked_in_at and q.completed_at:
                wait_seconds = (q.completed_at - q.checked_in_at).total_seconds()
                total_wait += wait_seconds / 60
                count += 1
        avg_wait_minutes = int(total_wait / count) if count > 0 else 0
    
    # Serialize queue data
    def serialize_queue(q):
        # Handle both QueueEntry and Queue models
        if HAS_QUEUE_ENTRY and isinstance(q, QueueEntry):
            # QueueEntry uses: check_in_time, called_time, started_time, completed_time
            checked_in = getattr(q, 'check_in_time', None) or getattr(q, 'created', None)
            called = getattr(q, 'called_time', None) or getattr(q, 'started_time', None)
            wait_time = getattr(q, 'estimated_wait_minutes', 0)
            patient = q.patient if hasattr(q, 'patient') else (q.encounter.patient if q.encounter else None)
        else:
            # Queue uses: checked_in_at, called_at, completed_at
            checked_in = getattr(q, 'checked_in_at', None)
            called = getattr(q, 'called_at', None)
            wait_time = getattr(q, 'estimated_wait_time', 0)
            patient = q.encounter.patient if q.encounter else None
        
        if HAS_QUEUE_ENTRY and isinstance(q, QueueEntry):
            ticket = str(getattr(q, 'display_ticket_number', '') or getattr(q, 'queue_number', '') or '')
        else:
            ticket = q.queue_number
        return {
            'id': str(q.id),
            'queue_number': ticket,
            'patient_name': patient.full_name if patient else 'Unknown',
            'mrn': patient.mrn if patient else '',
            'priority': getattr(q, 'priority', 'normal'),
            'priority_display': q.get_priority_display() if hasattr(q, 'get_priority_display') else str(getattr(q, 'priority', 'normal')),
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
        'completed_today': completed_today,
        'avg_wait_minutes': avg_wait_minutes,
        'timestamp': timezone.now().isoformat()
    })


from .decorators import role_required

@login_required
@role_required('nurse', 'midwife', 'admin', message='Access denied. Only nurses and midwives can create triage records.')
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
            
            # Send SMS notification to patient
            try:
                from .views_appointment_confirmation import send_appointment_notification_with_confirmation
                patient = appointment.patient
                if patient.phone_number and patient.phone_number.strip():
                    send_appointment_notification_with_confirmation(appointment, request=request)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error sending patient appointment SMS: {str(e)}")
            
            # Send SMS notification to doctor
            try:
                from .views_appointment_confirmation import send_appointment_notification_to_doctor
                send_appointment_notification_to_doctor(appointment)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error sending doctor appointment SMS: {str(e)}")
            
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
    """Administer medication via AJAX - with inventory accountability"""
    from .models_advanced import MedicationAdministrationRecord
    from .models_drug_accountability import DrugAdministrationInventory
    from django.http import JsonResponse
    import logging
    
    logger = logging.getLogger(__name__)
    
    mar = get_object_or_404(MedicationAdministrationRecord, pk=mar_id, is_deleted=False)
    
    if request.method == 'POST':
        dose_given = request.POST.get('dose_given', mar.prescription.dosage)
        notes = request.POST.get('notes', '')
        quantity = request.POST.get('quantity', None)
        
        # Get current user's staff profile
        staff = None
        if hasattr(request.user, 'staff_profile'):
            staff = request.user.staff
        
        if not staff:
            return JsonResponse({
                'status': 'error',
                'message': 'Staff profile not found. Please ensure you have a staff profile.'
            }, status=400)
        
        try:
            # Parse quantity if provided
            qty = None
            if quantity:
                try:
                    qty = int(quantity)
                except ValueError:
                    pass
            
            # Update MAR record
            mar.status = 'given'
            mar.dose_given = dose_given
            mar.notes = notes
            mar.administered_time = timezone.now()
            mar.administered_by = staff
            mar.save()
            
            # Create inventory tracking record (reduces inventory)
            try:
                admin_inv = DrugAdministrationInventory.create_from_mar(mar, staff, quantity=qty)
                logger.info(
                    f"✅ Drug administered: {mar.prescription.drug.name} to {mar.patient.full_name}. "
                    f"Inventory reduced by {admin_inv.quantity_administered} units. "
                    f"Transaction: {admin_inv.inventory_transaction.transaction_number if admin_inv.inventory_transaction else 'N/A'}"
                )
            except Exception as e:
                # Log error but don't fail the MAR record
                logger.error(f"⚠️ Error creating inventory tracking for MAR {mar_id}: {str(e)}")
                # Still return success for MAR, but note the inventory issue
                return JsonResponse({
                    'status': 'partial_success',
                    'message': f'Medication administered successfully, but inventory tracking failed: {str(e)}'
                })
            
            return JsonResponse({
                'status': 'success',
                'message': 'Medication administered successfully. Inventory updated.'
            })
        
        except Exception as e:
            logger.error(f"Error administering medication: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'Error: {str(e)}'
            }, status=400)
    
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


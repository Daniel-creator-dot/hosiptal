"""
Theatre/Surgery Management Views
User-friendly interface for scheduling surgeries
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Patient, Encounter, Staff
from .models_advanced import TheatreSchedule


@login_required
def theatre_dashboard(request):
    """Theatre dashboard with schedule and booking"""
    today = timezone.now().date()
    
    # Get today's schedules
    today_schedules = TheatreSchedule.objects.filter(
        scheduled_start__date=today,
        is_deleted=False
    ).select_related(
        'patient', 'surgeon__user', 'anaesthetist__user', 'scrub_nurse__user'
    ).order_by('scheduled_start')
    
    # Get upcoming schedules (next 7 days)
    upcoming_schedules = TheatreSchedule.objects.filter(
        scheduled_start__date__gt=today,
        scheduled_start__date__lte=today + timedelta(days=7),
        is_deleted=False
    ).select_related(
        'patient', 'surgeon__user'
    ).order_by('scheduled_start')[:10]
    
    # Statistics
    stats = {
        'today_surgeries': today_schedules.count(),
        'in_progress': today_schedules.filter(status='in_progress').count(),
        'completed_today': today_schedules.filter(status='completed').count(),
        'scheduled': TheatreSchedule.objects.filter(
            scheduled_start__gte=timezone.now(),
            status='scheduled',
            is_deleted=False
        ).count(),
    }
    
    context = {
        'title': 'Theatre Management',
        'today_schedules': today_schedules,
        'upcoming_schedules': upcoming_schedules,
        'stats': stats,
        'today': today,
    }
    
    return render(request, 'hospital/theatre/dashboard.html', context)


@login_required
def theatre_schedule_create(request):
    """Create new theatre schedule"""
    if request.method == 'POST':
        try:
            patient_id = request.POST.get('patient')
            encounter_id = request.POST.get('encounter')
            theatre_name = request.POST.get('theatre_name')
            procedure = request.POST.get('procedure')
            scheduled_start = request.POST.get('scheduled_start')
            scheduled_end = request.POST.get('scheduled_end')
            surgeon_id = request.POST.get('surgeon')
            anaesthetist_id = request.POST.get('anaesthetist')
            scrub_nurse_id = request.POST.get('scrub_nurse')
            notes = request.POST.get('notes', '')
            
            patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
            
            # Get encounter (optional, can be None)
            encounter = None
            if encounter_id:
                encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
            
            surgeon = get_object_or_404(Staff, pk=surgeon_id, is_deleted=False)
            
            # Convert datetime strings
            scheduled_start_dt = datetime.fromisoformat(scheduled_start.replace('Z', '+00:00'))
            scheduled_end_dt = datetime.fromisoformat(scheduled_end.replace('Z', '+00:00'))
            
            # Make timezone aware
            scheduled_start_dt = timezone.make_aware(scheduled_start_dt) if timezone.is_naive(scheduled_start_dt) else scheduled_start_dt
            scheduled_end_dt = timezone.make_aware(scheduled_end_dt) if timezone.is_naive(scheduled_end_dt) else scheduled_end_dt
            
            # Create theatre schedule
            schedule = TheatreSchedule.objects.create(
                patient=patient,
                encounter=encounter,
                theatre_name=theatre_name,
                procedure=procedure,
                scheduled_start=scheduled_start_dt,
                scheduled_end=scheduled_end_dt,
                surgeon=surgeon,
                status='scheduled',
                notes=notes,
            )
            
            # Add anaesthetist if provided
            if anaesthetist_id:
                schedule.anaesthetist_id = anaesthetist_id
                schedule.save(update_fields=['anaesthetist'])
            
            # Add scrub nurse if provided
            if scrub_nurse_id:
                schedule.scrub_nurse_id = scrub_nurse_id
                schedule.save(update_fields=['scrub_nurse'])
            
            messages.success(request, f'✅ Surgery scheduled for {patient.full_name} - {procedure} on {scheduled_start_dt.strftime("%B %d, %Y at %I:%M %p")}')
            return redirect('hospital:theatre_dashboard')
        
        except Exception as e:
            messages.error(request, f'❌ Error scheduling surgery: {str(e)}')
    
    # Get data for form
    patients = Patient.objects.filter(is_deleted=False).order_by('last_name', 'first_name')
    surgeons = Staff.objects.filter(is_active=True, is_deleted=False).order_by('user__last_name')
    
    context = {
        'title': 'Schedule Surgery',
        'patients': patients,
        'surgeons': surgeons,
    }
    
    return render(request, 'hospital/theatre/schedule_form.html', context)


@login_required
def get_patient_encounters_api(request, patient_id):
    """API endpoint to get encounters for a patient"""
    from django.http import JsonResponse
    
    encounters = Encounter.objects.filter(
        patient_id=patient_id,
        is_deleted=False
    ).values('id', 'encounter_type', 'started_at', 'status').order_by('-started_at')[:10]
    
    return JsonResponse({'encounters': list(encounters)})
























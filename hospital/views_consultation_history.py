"""
Consultation History & Patient Records Views
Allows doctors to review past consultations and patient visit history
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Encounter, Patient, Staff, Prescription, Order
from .models import LabResult

logger = logging.getLogger(__name__)


@login_required
def patient_consultation_history(request, patient_id):
    """
    View all consultations/encounters for a patient
    Shows complete medical history with all details
    """
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    # Get all encounters for this patient
    encounters = Encounter.objects.filter(
        patient=patient,
        is_deleted=False
    ).select_related(
        'provider__user', 'provider__department'
    ).prefetch_related(
        Prefetch('orders', queryset=Order.objects.filter(is_deleted=False)),
        Prefetch('vitals', queryset=VitalSign.objects.filter(is_deleted=False).order_by('-recorded_at'))
    ).order_by('-started_at')
    
    # Get clinical notes for all encounters
    try:
        from .models_advanced import ClinicalNote, ProblemList
        
        clinical_notes = ClinicalNote.objects.filter(
            encounter__patient=patient,
            is_deleted=False
        ).select_related('encounter', 'created_by__user').order_by('-created')
        
        problems = ProblemList.objects.filter(
            patient=patient,
            is_deleted=False
        ).select_related('encounter', 'created_by__user').order_by('-created')
    except ImportError:
        clinical_notes = []
        problems = []
    
    # Get prescriptions
    prescriptions = Prescription.objects.filter(
        order__encounter__patient=patient,
        is_deleted=False
    ).select_related('drug', 'prescribed_by__user', 'order__encounter').order_by('-created')
    
    # Statistics
    stats = {
        'total_encounters': encounters.count(),
        'active_encounters': encounters.filter(status='active').count(),
        'completed_encounters': encounters.filter(status='completed').count(),
        'total_prescriptions': prescriptions.count(),
        'active_problems': problems.filter(status='active').count() if problems else 0,
    }
    
    context = {
        'title': f'Consultation History - {patient.full_name}',
        'patient': patient,
        'encounters': encounters[:50],  # Last 50 encounters
        'clinical_notes': clinical_notes[:20],
        'problems': problems[:20],
        'prescriptions': prescriptions[:30],
        'stats': stats,
    }
    return render(request, 'hospital/patient_consultation_history.html', context)


@login_required
def encounter_full_record(request, encounter_id):
    """
    View complete record of a single encounter
    Shows everything that happened during this consultation
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    # Get all related data
    vitals = encounter.vitals.filter(is_deleted=False).order_by('-recorded_at')
    orders = encounter.orders.filter(is_deleted=False).order_by('order_type', '-created')
    
    # Get prescriptions
    prescriptions = Prescription.objects.filter(
        order__encounter=encounter,
        is_deleted=False
    ).select_related('drug', 'prescribed_by__user')
    
    # Get lab results
    lab_results = LabResult.objects.filter(
        order__encounter=encounter,
        is_deleted=False
    ).select_related('test', 'verified_by__user')
    
    # Get clinical notes
    try:
        from .models_advanced import ClinicalNote, ProblemList
        
        clinical_notes = ClinicalNote.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('created_by__user').order_by('created')
        
        problems = ProblemList.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('created_by__user')
    except ImportError:
        clinical_notes = []
        problems = []
    
    # Get imaging studies
    try:
        from .models_advanced import ImagingStudy
        imaging_studies = ImagingStudy.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('ordered_by__user')
    except ImportError:
        imaging_studies = []
    
    # Get referrals
    try:
        from .models_specialists import Referral
        referrals = Referral.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('specialist__staff__user', 'specialty', 'referred_by__user')
    except ImportError:
        referrals = []
    
    # Calculate duration
    duration_minutes = encounter.get_duration_minutes()
    
    context = {
        'title': f'Encounter Record - {encounter.patient.full_name}',
        'encounter': encounter,
        'patient': encounter.patient,
        'vitals': vitals,
        'orders': orders,
        'prescriptions': prescriptions,
        'lab_results': lab_results,
        'clinical_notes': clinical_notes,
        'problems': problems,
        'imaging_studies': imaging_studies,
        'referrals': referrals,
        'duration_minutes': duration_minutes,
    }
    return render(request, 'hospital/encounter_full_record.html', context)


@login_required
def my_consultations(request):
    """
    Show all consultations for the current doctor
    Allows doctors to review their own consultation records
    """
    try:
        doctor = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to access consultations.')
        return redirect('hospital:dashboard')
    
    # Filter options
    status_filter = request.GET.get('status', 'all')
    date_filter = request.GET.get('date', 'all')
    search = request.GET.get('search', '')
    
    # Base queryset - encounters where this doctor was the provider
    encounters = Encounter.objects.filter(
        provider=doctor,
        is_deleted=False
    ).select_related('patient').order_by('-started_at')
    
    # Apply filters
    if status_filter != 'all':
        encounters = encounters.filter(status=status_filter)
    
    if date_filter == 'today':
        today = timezone.now().date()
        encounters = encounters.filter(started_at__date=today)
    elif date_filter == 'week':
        week_ago = timezone.now() - timedelta(days=7)
        encounters = encounters.filter(started_at__gte=week_ago)
    elif date_filter == 'month':
        month_ago = timezone.now() - timedelta(days=30)
        encounters = encounters.filter(started_at__gte=month_ago)
    
    if search:
        encounters = encounters.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__mrn__icontains=search) |
            Q(chief_complaint__icontains=search) |
            Q(diagnosis__icontains=search)
        )
    
    # Statistics for this doctor
    today = timezone.now().date()
    stats = {
        'total': encounters.count(),
        'today': encounters.filter(started_at__date=today).count(),
        'active': encounters.filter(status='active').count(),
        'completed_today': encounters.filter(status='completed', ended_at__date=today).count(),
    }
    
    context = {
        'title': f'My Consultations - Dr. {doctor.get_full_name()}',
        'doctor': doctor,
        'encounters': encounters[:100],  # Limit to last 100
        'stats': stats,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'search': search,
    }
    return render(request, 'hospital/my_consultations.html', context)


# Import VitalSign for type hints
from .models import VitalSign










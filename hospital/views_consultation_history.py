"""
Consultation History & Patient Records Views
Allows doctors to review past consultations and patient visit history
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
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
    
    # Resolve current staff profile (if any)
    staff_member = None
    if request.user.is_authenticated:
        try:
            staff_member = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
        except Staff.DoesNotExist:
            staff_member = None
    
    def _safe_dispensing_record(prescription_obj):
        """Safely fetch dispensing record without raising when missing."""
        try:
            return prescription_obj.dispensing_record
        except ObjectDoesNotExist:
            return None
    
    # Allow inline actions from the encounter record (e.g., delete prescription)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_prescription':
            if not staff_member and not request.user.is_superuser:
                messages.error(request, 'Only clinical staff can delete prescriptions.')
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            prescription_id = request.POST.get('prescription_id')
            if not prescription_id:
                messages.error(request, 'Prescription ID is required.')
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            try:
                prescription = Prescription.objects.get(
                    pk=prescription_id,
                    order__encounter=encounter,
                    is_deleted=False
                )
            except Prescription.DoesNotExist:
                messages.error(request, 'Prescription not found or already removed.')
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            user_can_delete = request.user.is_superuser
            if not user_can_delete and staff_member:
                user_can_delete = (
                    staff_member == prescription.prescribed_by or
                    staff_member == encounter.provider
                )
            
            if not user_can_delete:
                messages.error(request, 'You can only delete prescriptions you authored for this encounter.')
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            dispensing_record = _safe_dispensing_record(prescription)
            blocking_reason = ''
            if dispensing_record:
                quantity_dispensed = getattr(dispensing_record, 'quantity_dispensed', 0) or 0
                payment_in_progress = getattr(dispensing_record, 'payment_receipt_id', None) or getattr(dispensing_record, 'payment_verified_at', None)
                is_dispensed = getattr(dispensing_record, 'is_dispensed', False)
                
                if is_dispensed or quantity_dispensed > 0:
                    blocking_reason = 'Medication has already been dispensed.'
                elif payment_in_progress:
                    blocking_reason = 'Payment has already been registered for this prescription.'
                elif getattr(dispensing_record, 'dispensing_status', '') not in ['pending_payment']:
                    blocking_reason = 'Dispensing is already in progress.'
            
            if blocking_reason:
                messages.error(request, blocking_reason)
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            prescription.is_deleted = True
            prescription.save(update_fields=['is_deleted'])
            messages.success(request, f'Prescription for {prescription.drug.name} deleted successfully.')
            return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
    
    # Get all related data
    vitals = encounter.vitals.filter(is_deleted=False).order_by('-recorded_at')
    orders = encounter.orders.filter(is_deleted=False).order_by('order_type', '-created')
    
    # Get prescriptions and enrich with user permissions
    prescriptions_qs = Prescription.objects.filter(
        order__encounter=encounter,
        is_deleted=False
    ).select_related('drug', 'prescribed_by__user')
    prescriptions = list(prescriptions_qs)
    
    def _get_prescription_block_reason(prescription):
        dispensing_record = _safe_dispensing_record(prescription)
        if not dispensing_record:
            return ''
        quantity_dispensed = getattr(dispensing_record, 'quantity_dispensed', 0) or 0
        if getattr(dispensing_record, 'is_dispensed', False) or quantity_dispensed > 0:
            return 'Dispensing already completed.'
        if getattr(dispensing_record, 'payment_receipt_id', None) or getattr(dispensing_record, 'payment_verified_at', None):
            return 'Payment already verified.'
        if getattr(dispensing_record, 'dispensing_status', '') not in ['pending_payment']:
            return 'Dispensing already in progress.'
        return ''
    
    can_delete_any_prescription = False
    for rx in prescriptions:
        rx.dispensing_record_obj = _safe_dispensing_record(rx)
        rx.delete_block_reason = _get_prescription_block_reason(rx)
        rx.can_user_delete = False
        if request.user.is_superuser:
            rx.can_user_delete = not bool(rx.delete_block_reason)
        elif staff_member:
            if staff_member == rx.prescribed_by or staff_member == encounter.provider:
                rx.can_user_delete = not bool(rx.delete_block_reason)
        if rx.can_user_delete:
            can_delete_any_prescription = True
    
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
        ).select_related(
            'specialist__staff__user',
            'specialty',
            'referring_doctor__user'
        )
    except ImportError:
        referrals = []
    
    # Patient flow stages for enhanced timeline
    flow_stages = []
    flow_summary = {
        'total': 0,
        'completed': 0,
        'percent': 0,
        'current': None,
        'next': None,
    }
    try:
        from .models_workflow import PatientFlowStage
        flow_qs = PatientFlowStage.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('completed_by__user').order_by('created')
        flow_stages = list(flow_qs)
        flow_summary['total'] = len(flow_stages)
        flow_summary['completed'] = sum(1 for stage in flow_stages if stage.status == 'completed')
        if flow_summary['total']:
            flow_summary['percent'] = (flow_summary['completed'] / flow_summary['total']) * 100
            flow_summary['current'] = next(
                (stage for stage in flow_stages if stage.status in ['in_progress', 'pending']),
                None
            )
            if flow_summary['completed'] < flow_summary['total']:
                try:
                    flow_summary['next'] = flow_stages[flow_summary['completed']]
                except IndexError:
                    flow_summary['next'] = None
    except ImportError:
        pass
    
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
        'flow_stages': flow_stages,
        'flow_summary': flow_summary,
        'can_delete_any_prescription': can_delete_any_prescription,
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
    
    # Base queryset - encounters linked to this doctor
    # Prefer provider field, but also include encounters where the doctor requested orders
    base_qs = Encounter.objects.filter(
        is_deleted=False
    ).filter(
        Q(provider=doctor) | Q(orders__requested_by=doctor)
    ).select_related('patient').distinct().order_by('-started_at')

    encounters = base_qs
    
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
    
    # Statistics for this doctor (always use the full base queryset)
    today = timezone.now().date()
    stats = {
        'total': base_qs.count(),
        'today': base_qs.filter(started_at__date=today).count(),
        'active': base_qs.filter(status='active').count(),
        'completed_today': base_qs.filter(status='completed', ended_at__date=today).count(),
    }
    
    doctor_name = doctor.get_full_name() if hasattr(doctor, 'get_full_name') else doctor.user.get_full_name()
    context = {
        'title': f'My Consultations - Dr. {doctor_name}',
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














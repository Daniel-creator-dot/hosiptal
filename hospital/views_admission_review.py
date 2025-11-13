"""
Admission Review & Shift Handover System
Allows doctors to review admitted patients, add notes and medications
Next shift doctors can read records before continuing care
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch, Count
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Patient, Encounter, Staff, Prescription, Order, Drug
from .models import VitalSign

logger = logging.getLogger(__name__)


@login_required
def admitted_patients_list(request):
    """
    Show all currently admitted patients
    Dashboard for doctors to see who needs review
    """
    try:
        current_staff = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to access this page.')
        return redirect('hospital:dashboard')
    
    # Get all active encounters for admitted patients
    admitted_encounters = Encounter.objects.filter(
        encounter_type='admission',
        status__in=['active', 'in_progress'],
        is_deleted=False
    ).select_related(
        'patient', 'provider__user', 'provider__department'
    ).prefetch_related(
        Prefetch('vitals', queryset=VitalSign.objects.filter(is_deleted=False).order_by('-recorded_at')),
        Prefetch('orders', queryset=Order.objects.filter(is_deleted=False))
    ).order_by('-started_at')
    
    # Get clinical notes and problems
    try:
        from .models_advanced import ClinicalNote
        
        # For each encounter, get latest note
        for encounter in admitted_encounters:
            encounter.latest_note = ClinicalNote.objects.filter(
                encounter=encounter,
                is_deleted=False
            ).order_by('-created').first()
    except ImportError:
        pass
    
    # Statistics
    stats = {
        'total_admitted': admitted_encounters.count(),
        'needs_review': admitted_encounters.filter(
            started_at__lt=timezone.now() - timedelta(hours=6)
        ).count(),
        'critical': admitted_encounters.filter(
            patient__status='critical'
        ).count() if hasattr(Patient, 'status') else 0,
    }
    
    # Filter options
    department_filter = request.GET.get('department', 'all')
    review_filter = request.GET.get('review', 'all')
    
    if department_filter != 'all' and current_staff.department:
        admitted_encounters = admitted_encounters.filter(provider__department=current_staff.department)
    
    if review_filter == 'needs_review':
        # Patients not reviewed in last 6 hours
        six_hours_ago = timezone.now() - timedelta(hours=6)
        admitted_encounters = admitted_encounters.filter(
            Q(updated__lt=six_hours_ago) | Q(updated__isnull=True)
        )
    
    context = {
        'title': 'Admitted Patients - Review Dashboard',
        'admitted_encounters': admitted_encounters,
        'stats': stats,
        'current_staff': current_staff,
        'department_filter': department_filter,
        'review_filter': review_filter,
    }
    return render(request, 'hospital/admitted_patients_list.html', context)


@login_required
def admission_review(request, encounter_id):
    """
    Review an admitted patient
    Add progress notes, medications, update status
    Works with any encounter type for admitted patients
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    # Check if patient is actually admitted (has an active admission record)
    try:
        from .models import Admission
        admission = Admission.objects.filter(
            encounter=encounter,
            status='admitted',
            is_deleted=False
        ).first()
        
        # If encounter type is not admission but patient has admission record, update it
        if admission and encounter.encounter_type != 'admission':
            encounter.encounter_type = 'admission'
            encounter.save(update_fields=['encounter_type'])
            
    except ImportError:
        pass  # Admission model might not exist in some setups
    
    try:
        current_doctor = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff.')
        return redirect('hospital:dashboard')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_progress_note':
            # Add progress note for shift handover
            try:
                from .models_advanced import ClinicalNote
                
                subjective = request.POST.get('subjective', '')
                objective = request.POST.get('objective', '')
                assessment = request.POST.get('assessment', '')
                plan = request.POST.get('plan', '')
                note_content = request.POST.get('note_content', '')
                
                ClinicalNote.objects.create(
                    encounter=encounter,
                    note_type='progress',
                    subjective=subjective,
                    objective=objective,
                    assessment=assessment,
                    plan=plan,
                    notes=note_content,
                    created_by=current_doctor
                )
                
                # Update encounter timestamp
                encounter.updated = timezone.now()
                encounter.save(update_fields=['updated'])
                
                messages.success(request, '✅ Progress note added successfully. Next shift can now review.')
                
            except ImportError:
                # Fallback to encounter notes
                note_content = request.POST.get('note_content', '')
                if encounter.notes:
                    encounter.notes += f"\n\n[{timezone.now().strftime('%Y-%m-%d %H:%M')} - Dr. {current_doctor.get_full_name()}]\n{note_content}"
                else:
                    encounter.notes = f"[{timezone.now().strftime('%Y-%m-%d %H:%M')} - Dr. {current_doctor.get_full_name()}]\n{note_content}"
                encounter.save()
                messages.success(request, '✅ Progress note added.')
        
        elif action == 'add_medication':
            # Add new medication
            drug_id = request.POST.get('drug_id')
            quantity = request.POST.get('quantity', 1)
            dosage = request.POST.get('dosage_instructions', '')
            frequency = request.POST.get('frequency', '')
            duration = request.POST.get('duration_days', '')
            route = request.POST.get('route', 'oral')
            
            try:
                drug = Drug.objects.get(pk=drug_id, is_deleted=False)
                
                # Get or create medication order
                med_order, created = Order.objects.get_or_create(
                    encounter=encounter,
                    order_type='medication',
                    status='active',
                    is_deleted=False,
                    defaults={
                        'requested_by': current_doctor,
                        'priority': 'routine'
                    }
                )
                
                # Create prescription
                Prescription.objects.create(
                    order=med_order,
                    drug=drug,
                    quantity=int(quantity) if quantity else 1,
                    dosage_instructions=dosage,
                    frequency=frequency,
                    duration_days=int(duration) if duration else None,
                    route=route,
                    prescribed_by=current_doctor
                )
                
                messages.success(request, f'✅ Added {drug.name} to patient medications.')
                
            except Drug.DoesNotExist:
                messages.error(request, 'Drug not found.')
            except Exception as e:
                messages.error(request, f'Error adding medication: {str(e)}')
        
        elif action == 'update_status':
            # Update patient status/condition
            new_diagnosis = request.POST.get('diagnosis', '')
            new_notes = request.POST.get('status_notes', '')
            
            if new_diagnosis:
                encounter.diagnosis = new_diagnosis
            
            if new_notes:
                if encounter.notes:
                    encounter.notes += f"\n\n[Status Update - {timezone.now().strftime('%Y-%m-%d %H:%M')}]\n{new_notes}"
                else:
                    encounter.notes = f"[Status Update - {timezone.now().strftime('%Y-%m-%d %H:%M')}]\n{new_notes}"
            
            encounter.updated = timezone.now()
            encounter.save()
            
            messages.success(request, '✅ Patient status updated.')
        
        return redirect('hospital:admission_review', encounter_id=encounter.pk)
    
    # Get all data for display
    # Latest vitals
    latest_vitals = encounter.vitals.filter(is_deleted=False).order_by('-recorded_at').first()
    recent_vitals = encounter.vitals.filter(is_deleted=False).order_by('-recorded_at')[:5]
    
    # Current medications
    current_prescriptions = Prescription.objects.filter(
        order__encounter=encounter,
        order__order_type='medication',
        is_deleted=False
    ).select_related('drug', 'prescribed_by__user').order_by('-created')
    
    # Clinical notes (progress notes for handover)
    try:
        from .models_advanced import ClinicalNote, ProblemList
        
        clinical_notes = ClinicalNote.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('created_by__user').order_by('-created')[:10]
        
        problems = ProblemList.objects.filter(
            patient=encounter.patient,
            status='active',
            is_deleted=False
        ).order_by('-created')
    except ImportError:
        clinical_notes = []
        problems = []
    
    # Lab results
    try:
        from .models import LabResult
        recent_lab_results = LabResult.objects.filter(
            order__encounter=encounter,
            is_deleted=False
        ).select_related('test').order_by('-created')[:10]
    except:
        recent_lab_results = []
    
    # All orders
    orders = Order.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).order_by('-created')[:20]
    
    # Available drugs for prescription
    available_drugs = Drug.objects.filter(
        is_active=True,
        is_deleted=False
    ).order_by('name')[:100]
    
    # Calculate admission duration
    if encounter.started_at:
        admission_duration = timezone.now() - encounter.started_at
        days_admitted = admission_duration.days
        hours_admitted = admission_duration.seconds // 3600
    else:
        days_admitted = 0
        hours_admitted = 0
    
    context = {
        'title': f'Admission Review - {encounter.patient.full_name}',
        'encounter': encounter,
        'patient': encounter.patient,
        'current_doctor': current_doctor,
        'latest_vitals': latest_vitals,
        'recent_vitals': recent_vitals,
        'current_prescriptions': current_prescriptions,
        'clinical_notes': clinical_notes,
        'problems': problems,
        'recent_lab_results': recent_lab_results,
        'orders': orders,
        'available_drugs': available_drugs,
        'days_admitted': days_admitted,
        'hours_admitted': hours_admitted,
    }
    return render(request, 'hospital/admission_review.html', context)


@login_required
def shift_handover_report(request):
    """
    Generate shift handover report
    Shows all admitted patients with recent updates for incoming doctor
    """
    try:
        current_doctor = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff.')
        return redirect('hospital:dashboard')
    
    # Get shift timeframe (last 8 hours for typical shift)
    shift_start = timezone.now() - timedelta(hours=8)
    
    # Get all admitted patients
    admitted_encounters = Encounter.objects.filter(
        encounter_type='admission',
        status__in=['active', 'in_progress'],
        is_deleted=False
    ).select_related('patient', 'provider__user').order_by('patient__last_name')
    
    # For each patient, get recent activity
    handover_data = []
    for encounter in admitted_encounters:
        # Latest vitals
        latest_vitals = encounter.vitals.filter(is_deleted=False).order_by('-recorded_at').first()
        
        # Recent notes (during this shift)
        try:
            from .models_advanced import ClinicalNote
            shift_notes = ClinicalNote.objects.filter(
                encounter=encounter,
                created__gte=shift_start,
                is_deleted=False
            ).select_related('created_by__user').order_by('-created')
        except ImportError:
            shift_notes = []
        
        # New medications (during this shift)
        new_medications = Prescription.objects.filter(
            order__encounter=encounter,
            created__gte=shift_start,
            is_deleted=False
        ).select_related('drug', 'prescribed_by__user')
        
        # Current medications (all active)
        current_medications = Prescription.objects.filter(
            order__encounter=encounter,
            is_deleted=False
        ).select_related('drug')
        
        # Recent lab results
        try:
            from .models import LabResult
            recent_labs = LabResult.objects.filter(
                order__encounter=encounter,
                created__gte=shift_start,
                is_deleted=False
            ).select_related('test')
        except:
            recent_labs = []
        
        # Compile handover info
        handover_data.append({
            'encounter': encounter,
            'patient': encounter.patient,
            'latest_vitals': latest_vitals,
            'shift_notes': shift_notes,
            'new_medications': new_medications,
            'current_medications': current_medications,
            'recent_labs': recent_labs,
            'has_updates': shift_notes.exists() or new_medications.exists() or recent_labs.exists() if shift_notes else (new_medications.exists() or recent_labs.exists()),
        })
    
    context = {
        'title': 'Shift Handover Report',
        'handover_data': handover_data,
        'shift_start': shift_start,
        'current_doctor': current_doctor,
        'total_patients': len(handover_data),
        'patients_with_updates': sum(1 for d in handover_data if d['has_updates']),
    }
    return render(request, 'hospital/shift_handover_report.html', context)


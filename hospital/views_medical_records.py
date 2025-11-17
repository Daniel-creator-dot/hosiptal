"""
Comprehensive Medical Records & Clinical Documentation System
For detailed forensic analysis and proper clinical reporting
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Prefetch
from datetime import timedelta

from .models import Patient, Encounter, Staff, VitalSign, LabResult
from .models_advanced import Triage, ClinicalNote, Diagnosis, Procedure, CarePlan, ProblemList, ImagingStudy


@login_required
def comprehensive_medical_record(request, patient_id):
    """
    Complete medical record view with forensic-level detail
    Shows entire patient history for clinical review
    """
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    # Get all encounters with related data
    encounters = Encounter.objects.filter(
        patient=patient,
        is_deleted=False
    ).select_related(
        'provider__user',
        'location'
    ).prefetch_related(
        'clinical_notes',
        'diagnoses',
        'procedures',
        'care_plans'
    ).order_by('-started_at')
    
    # Get all vital signs
    vital_signs = VitalSign.objects.filter(
        encounter__patient=patient,
        is_deleted=False
    ).order_by('-recorded_at')[:50]
    
    # Get all triage records
    triage_records = Triage.objects.filter(
        encounter__patient=patient,
        is_deleted=False
    ).select_related('encounter', 'triaged_by__user').order_by('-triage_time')
    
    # Get allergies and medications
    allergies = patient.allergies.split(',') if hasattr(patient, 'allergies') and patient.allergies else []
    current_medications = patient.current_medications.split(',') if hasattr(patient, 'current_medications') and patient.current_medications else []
    
    # Recent imaging studies with assets
    imaging_studies = ImagingStudy.objects.filter(
        patient=patient,
        is_deleted=False
    ).prefetch_related('images').order_by('-performed_at', '-created')[:6]
    
    # Calculate statistics
    total_encounters = encounters.count()
    total_admissions = encounters.filter(encounter_type='inpatient').count()
    last_visit = encounters.first().started_at if encounters.exists() else None
    
    context = {
        'patient': patient,
        'encounters': encounters,
        'vital_signs': vital_signs,
        'triage_records': triage_records,
        'allergies': allergies,
        'current_medications': current_medications,
        'total_encounters': total_encounters,
        'total_admissions': total_admissions,
        'last_visit': last_visit,
        'medical_history': getattr(patient, 'medical_history', ''),
        'surgical_history': getattr(patient, 'surgical_history', ''),
        'family_history': getattr(patient, 'family_history', ''),
        'social_history': getattr(patient, 'social_history', ''),
        'recent_imaging': imaging_studies,
    }
    
    return render(request, 'hospital/medical_records/comprehensive_record.html', context)


@login_required
def encounter_documentation(request, encounter_id):
    """
    Detailed encounter documentation view
    For comprehensive clinical note-taking
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'clinical_note':
            return save_clinical_note(request, encounter)
        elif action == 'diagnosis':
            return save_diagnosis(request, encounter)
        elif action == 'procedure':
            return save_procedure(request, encounter)
    
    # Get existing documentation
    clinical_notes = ClinicalNote.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).select_related('created_by__user').order_by('-created')
    
    diagnoses = Diagnosis.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).order_by('-created')
    
    procedures = Procedure.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).order_by('-procedure_date')
    
    # Get lab tests and imaging
    lab_tests = LabResult.objects.filter(
        order__encounter=encounter,
        is_deleted=False
    ).select_related('test').order_by('-created')
    
    imaging_studies = ImagingStudy.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).prefetch_related('images').order_by('-created')
    
    # Get vital signs
    vital_signs = VitalSign.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).order_by('-recorded_at')
    
    context = {
        'encounter': encounter,
        'patient': encounter.patient,
        'clinical_notes': clinical_notes,
        'diagnoses': diagnoses,
        'procedures': procedures,
        'lab_tests': lab_tests,
        'imaging_studies': imaging_studies,
        'vital_signs': vital_signs,
    }
    
    return render(request, 'hospital/medical_records/encounter_documentation.html', context)


def save_clinical_note(request, encounter):
    """Save comprehensive clinical note"""
    try:
        staff = Staff.objects.get(user=request.user)
        
        ClinicalNote.objects.create(
            encounter=encounter,
            note_type=request.POST.get('note_type', 'soap'),
            subjective=request.POST.get('subjective', ''),
            objective=request.POST.get('objective', ''),
            assessment=request.POST.get('assessment', ''),
            plan=request.POST.get('plan', ''),
            notes=request.POST.get('notes', ''),
            created_by=staff
        )
        
        messages.success(request, '✅ Clinical note saved successfully')
    except Exception as e:
        messages.error(request, f'Error saving clinical note: {str(e)}')
    
    return redirect('hospital:encounter_documentation', encounter_id=encounter.pk)


def save_diagnosis(request, encounter):
    """Save diagnosis"""
    try:
        Diagnosis.objects.create(
            encounter=encounter,
            diagnosis_code=request.POST.get('diagnosis_code', ''),
            diagnosis_name=request.POST.get('diagnosis_name', ''),
            is_primary=request.POST.get('is_primary', 'true') == 'true'
        )
        
        messages.success(request, '✅ Diagnosis saved successfully')
    except Exception as e:
        messages.error(request, f'Error saving diagnosis: {str(e)}')
    
    return redirect('hospital:encounter_documentation', encounter_id=encounter.pk)


def save_procedure(request, encounter):
    """Save procedure"""
    try:
        Procedure.objects.create(
            encounter=encounter,
            procedure_name=request.POST.get('procedure_name', ''),
            procedure_code=request.POST.get('procedure_code', ''),
            notes=request.POST.get('notes', ''),
            procedure_date=timezone.now()
        )
        
        messages.success(request, '✅ Procedure recorded successfully')
    except Exception as e:
        messages.error(request, f'Error recording procedure: {str(e)}')
    
    return redirect('hospital:encounter_documentation', encounter_id=encounter.pk)


@login_required
def patient_timeline(request, patient_id):
    """
    Complete patient timeline - chronological view of all medical events
    """
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    # Collect all events
    events = []
    
    # Encounters
    for encounter in Encounter.objects.filter(patient=patient, is_deleted=False):
        events.append({
            'date': encounter.started_at,
            'type': 'encounter',
            'title': f'{encounter.get_encounter_type_display()} Visit',
            'description': f'Attending: {encounter.attending_physician.user.get_full_name() if encounter.attending_physician else "N/A"}',
            'object': encounter
        })
    
    # Diagnoses
    for diagnosis in Diagnosis.objects.filter(patient=patient, is_deleted=False):
        events.append({
            'date': diagnosis.diagnosis_date,
            'type': 'diagnosis',
            'title': f'Diagnosis: {diagnosis.diagnosis_name}',
            'description': diagnosis.notes,
            'object': diagnosis
        })
    
    # Investigations
    for investigation in Investigation.objects.filter(patient=patient, is_deleted=False):
        events.append({
            'date': investigation.ordered_at,
            'type': 'investigation',
            'title': f'Investigation: {investigation.investigation_name}',
            'description': investigation.indication,
            'object': investigation
        })
    
    # Sort by date
    events.sort(key=lambda x: x['date'], reverse=True)
    
    context = {
        'patient': patient,
        'events': events,
    }
    
    return render(request, 'hospital/medical_records/patient_timeline.html', context)

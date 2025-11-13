"""
📋 COMPREHENSIVE MEDICAL HISTORY SYSTEM
Detailed visit-by-visit patient history for doctors
Shows medications, tests, diagnoses, procedures from all previous visits
World-class forensic medical record keeping
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Prefetch
from django.utils import timezone
from datetime import timedelta

from .models import Patient, Encounter, VitalSign, LabResult, Order, Prescription


@login_required
def patient_medical_history_comprehensive(request, patient_id):
    """
    Comprehensive medical history - visit by visit
    Shows everything: vitals, diagnoses, medications, lab tests, procedures
    """
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    
    # Get all encounters with related data - prefetch for performance
    encounters = Encounter.objects.filter(
        patient=patient,
        is_deleted=False
    ).select_related(
        'provider__user',
        'provider__department'
    ).prefetch_related(
        Prefetch('vitals', queryset=VitalSign.objects.filter(is_deleted=False).order_by('-recorded_at')),
        # Note: Diagnoses and procedures would need proper model imports if available
        Prefetch('orders', queryset=Order.objects.filter(is_deleted=False).prefetch_related(
            Prefetch('lab_results', queryset=LabResult.objects.filter(is_deleted=False)),
            Prefetch('prescriptions', queryset=Prescription.objects.filter(is_deleted=False))
        ))
    ).order_by('-started_at')
    
    # Get allergies (if available)
    allergies = []
    try:
        from .models_advanced import Allergy
        allergies = Allergy.objects.filter(
            patient=patient,
            is_deleted=False,
            is_active=True
        ).order_by('-severity', '-recorded_date')
    except ImportError:
        pass
    
    # Build comprehensive visit history
    visit_history = []
    
    for encounter in encounters:
        # Get vitals
        vitals = encounter.vitals.all()
        latest_vitals = vitals.first() if vitals else None
        
        # Get diagnoses (if available)
        diagnoses = []
        try:
            diagnoses = encounter.diagnoses.all()
        except:
            pass
        
        # Get procedures (if available)
        procedures = []
        try:
            procedures = encounter.procedures.all()
        except:
            pass
        
        # Get lab tests and results
        lab_tests = []
        for order in encounter.orders.filter(order_type='lab'):
            for lab_result in order.lab_results.all():
                lab_tests.append({
                    'test': lab_result.test,
                    'result': lab_result,
                    'status': lab_result.status,
                    'value': lab_result.value,
                    'units': lab_result.units,
                    'reference_range': lab_result.reference_range,
                    'is_abnormal': lab_result.is_abnormal,
                    'verified_at': lab_result.verified_at,
                    'verified_by': lab_result.verified_by
                })
        
        # Get medications/prescriptions
        medications = []
        for order in encounter.orders.filter(order_type='medication'):
            for prescription in order.prescriptions.all():
                medications.append({
                    'drug': prescription.drug,
                    'dosage': prescription.dosage,
                    'frequency': prescription.frequency,
                    'duration': prescription.duration,
                    'quantity': prescription.quantity,
                    'instructions': prescription.instructions,
                    'prescribed_date': order.created
                })
        
        # Compile visit data
        visit_data = {
            'encounter': encounter,
            'date': encounter.started_at,
            'provider': encounter.provider,
            'type': encounter.get_encounter_type_display(),
            'status': encounter.get_status_display(),
            'chief_complaint': encounter.chief_complaint,
            'history': encounter.history_of_present_illness,
            'vitals': latest_vitals,
            'all_vitals': list(vitals),
            'diagnoses': list(diagnoses),
            'procedures': list(procedures),
            'lab_tests': lab_tests,
            'medications': medications,
            'notes': encounter.clinical_notes,
            'duration': encounter.get_duration_minutes(),
        }
        
        visit_history.append(visit_data)
    
    # Calculate summary statistics
    total_visits = encounters.count()
    total_diagnoses = sum(len(v['diagnoses']) for v in visit_history)
    total_medications = sum(len(v['medications']) for v in visit_history)
    total_lab_tests = sum(len(v['lab_tests']) for v in visit_history)
    total_procedures = sum(len(v['procedures']) for v in visit_history)
    
    # Get current medications (from last 30 days)
    recent_date = timezone.now() - timedelta(days=30)
    current_medications = []
    seen_drugs = set()
    
    for visit in visit_history:
        if visit['date'] < recent_date:
            break
        for med in visit['medications']:
            drug_id = med['drug'].id if med['drug'] else None
            if drug_id and drug_id not in seen_drugs:
                current_medications.append(med)
                seen_drugs.add(drug_id)
    
    # Get chronic conditions (recurring diagnoses)
    diagnosis_counts = {}
    for visit in visit_history:
        for diagnosis in visit['diagnoses']:
            condition = diagnosis.condition.name if diagnosis.condition else 'Unknown'
            diagnosis_counts[condition] = diagnosis_counts.get(condition, 0) + 1
    
    chronic_conditions = [
        {'condition': condition, 'count': count} 
        for condition, count in diagnosis_counts.items() 
        if count >= 2  # Appears in 2+ visits
    ]
    chronic_conditions.sort(key=lambda x: x['count'], reverse=True)
    
    context = {
        'title': f'Medical History - {patient.full_name}',
        'patient': patient,
        'visit_history': visit_history,
        'allergies': allergies,
        'total_visits': total_visits,
        'total_diagnoses': total_diagnoses,
        'total_medications': total_medications,
        'total_lab_tests': total_lab_tests,
        'total_procedures': total_procedures,
        'current_medications': current_medications,
        'chronic_conditions': chronic_conditions,
    }
    
    return render(request, 'hospital/medical_history_comprehensive.html', context)


@login_required
def patient_medical_timeline(request, patient_id):
    """
    Visual timeline of patient medical history
    Shows key events in chronological order
    """
    patient = get_object_or_404(Patient, id=patient_id, is_deleted=False)
    
    # Build timeline events
    timeline = []
    
    # Add encounters
    encounters = Encounter.objects.filter(
        patient=patient,
        is_deleted=False
    ).select_related('provider').order_by('-started_at')
    
    for encounter in encounters:
        timeline.append({
            'date': encounter.started_at,
            'type': 'encounter',
            'icon': 'hospital',
            'color': '#3b82f6',
            'title': f'{encounter.get_encounter_type_display()} Visit',
            'description': encounter.chief_complaint or 'No chief complaint recorded',
            'provider': encounter.provider.user.get_full_name() if encounter.provider else 'Unknown',
            'object': encounter
        })
    
    # Add diagnoses (if available)
    try:
        from .models_advanced import Diagnosis
        diagnoses = Diagnosis.objects.filter(
            encounter__patient=patient,
            is_deleted=False
        ).select_related('encounter', 'condition').order_by('-diagnosis_date')
        
        for diagnosis in diagnoses:
            timeline.append({
                'date': diagnosis.diagnosis_date,
                'type': 'diagnosis',
                'icon': 'clipboard2-pulse',
                'color': '#ef4444',
                'title': 'Diagnosis',
                'description': diagnosis.condition.name if diagnosis.condition else 'Unknown condition',
                'notes': diagnosis.clinical_notes,
                'object': diagnosis
            })
    except ImportError:
        pass
    
    # Add procedures (if available)
    try:
        from .models_advanced import Procedure
        procedures = Procedure.objects.filter(
            encounter__patient=patient,
            is_deleted=False
        ).select_related('encounter').order_by('-procedure_date')
        
        for procedure in procedures:
            timeline.append({
                'date': procedure.procedure_date,
                'type': 'procedure',
                'icon': 'scissors',
                'color': '#8b5cf6',
                'title': 'Procedure',
                'description': procedure.procedure_name,
                'notes': procedure.notes,
                'object': procedure
            })
    except ImportError:
        pass
    
    # Add allergies (if available)
    try:
        from .models_advanced import Allergy
        allergies = Allergy.objects.filter(
            patient=patient,
            is_deleted=False
        ).order_by('-recorded_date')
        
        for allergy in allergies:
            timeline.append({
                'date': allergy.recorded_date,
                'type': 'allergy',
                'icon': 'exclamation-triangle',
                'color': '#f59e0b',
                'title': 'Allergy Recorded',
                'description': f'{allergy.allergen} - {allergy.get_severity_display()}',
                'reaction': allergy.reaction,
                'object': allergy
            })
    except ImportError:
        pass
    
    # Sort timeline by date (newest first)
    timeline.sort(key=lambda x: x['date'], reverse=True)
    
    context = {
        'title': f'Medical Timeline - {patient.full_name}',
        'patient': patient,
        'timeline': timeline,
    }
    
    return render(request, 'hospital/medical_timeline.html', context)


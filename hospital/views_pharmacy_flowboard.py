"""
Pharmacy Patient Flowboard
Shows patients in pharmacy queue with time spent blinking
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, F, Count
from datetime import timedelta

from .models import Encounter, Order, Prescription, Patient
from .models_workflow import PatientFlowStage
from .models_payment_verification import PharmacyDispensing


@login_required
def pharmacy_flowboard(request):
    """
    Pharmacy-specific patient flowboard showing patients waiting for medication
    with blinking time spent indicators
    """
    # Get all encounters with pharmacy stage
    pharmacy_stages = PatientFlowStage.objects.filter(
        stage_type='pharmacy',
        status__in=['pending', 'in_progress'],
        is_deleted=False
    ).select_related(
        'encounter__patient',
        'encounter__provider__user',
        'completed_by__user'
    ).order_by('started_at', 'created')
    
    # Get encounters with pending pharmacy orders
    pending_orders = Order.objects.filter(
        order_type='medication',
        status='pending',
        is_deleted=False
    ).select_related(
        'encounter__patient',
        'requested_by__user'
    ).order_by('requested_at')
    
    # Get prescriptions with pending dispensing
    pending_dispensing = PharmacyDispensing.objects.filter(
        dispensing_status__in=['pending_payment', 'ready_to_dispense'],
        is_deleted=False
    ).select_related(
        'prescription__drug',
        'prescription__order__encounter__patient',
        'patient'
    ).order_by('created')
    
    # Organize by status
    queue_by_status = {
        'pending_payment': [],
        'ready_to_dispense': [],
        'in_progress': [],
    }
    
    now = timezone.now()
    
    # Process pending dispensing records
    for dispensing in pending_dispensing:
        encounter = dispensing.prescription.order.encounter
        patient = encounter.patient
        
        # Calculate wait time
        wait_start = dispensing.created
        wait_minutes = int((now - wait_start).total_seconds() / 60)
        
        patient_data = {
            'encounter_id': str(encounter.id),
            'patient_id': str(patient.id),
            'patient_name': patient.full_name,
            'mrn': patient.mrn,
            'encounter_type': encounter.get_encounter_type_display(),
            'wait_minutes': wait_minutes,
            'wait_start': wait_start,
            'prescription': dispensing.prescription,
            'drug': dispensing.prescription.drug,
            'quantity': dispensing.quantity_ordered,
            'status': dispensing.dispensing_status,
            'dispensing_record': dispensing,
        }
        
        # Paid items must not be in the "pending payment" queue
        if dispensing.dispensing_status == 'pending_payment' and not dispensing.payment_receipt_id:
            queue_by_status['pending_payment'].append(patient_data)
        elif dispensing.dispensing_status == 'ready_to_dispense':
            queue_by_status['ready_to_dispense'].append(patient_data)
        else:
            queue_by_status['in_progress'].append(patient_data)
    
    # Process pharmacy flow stages
    for stage in pharmacy_stages:
        encounter = stage.encounter
        patient = encounter.patient
        
        # Calculate wait time
        wait_start = stage.started_at or stage.created
        wait_minutes = int((now - wait_start).total_seconds() / 60)
        
        patient_data = {
            'encounter_id': str(encounter.id),
            'patient_id': str(patient.id),
            'patient_name': patient.full_name,
            'mrn': patient.mrn,
            'encounter_type': encounter.get_encounter_type_display(),
            'wait_minutes': wait_minutes,
            'wait_start': wait_start,
            'flow_stage': stage,
            'status': stage.status,
        }
        
        queue_by_status['in_progress'].append(patient_data)
    
    # Sort by wait time (longest first)
    for status in queue_by_status:
        queue_by_status[status].sort(key=lambda x: x['wait_minutes'], reverse=True)
    
    # Statistics
    total_patients = sum(len(patients) for patients in queue_by_status.values())
    avg_wait_time = 0
    if total_patients > 0:
        all_wait_times = [p['wait_minutes'] for patients in queue_by_status.values() for p in patients]
        avg_wait_time = int(sum(all_wait_times) / len(all_wait_times)) if all_wait_times else 0
    
    delayed_count = sum(1 for patients in queue_by_status.values() for p in patients if p['wait_minutes'] > 60)
    
    context = {
        'title': 'Pharmacy Patient Flowboard',
        'queue_by_status': queue_by_status,
        'total_patients': total_patients,
        'avg_wait_time': avg_wait_time,
        'delayed_count': delayed_count,
        'now': now,
    }
    
    return render(request, 'hospital/pharmacy_flowboard.html', context)

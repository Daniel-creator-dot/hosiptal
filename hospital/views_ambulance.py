"""
Ambulance System Views
Real-time ambulance dispatch and billing management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal
from datetime import timedelta

from .models import Patient, Encounter, Staff
from .models_ambulance import (
    AmbulanceUnit, AmbulanceDispatch, AmbulanceBilling,
    AmbulanceServiceType, AmbulanceServiceCharge
)


@login_required
def create_ambulance_dispatch(request, patient_id=None):
    """
    Create new ambulance dispatch - can be linked to patient
    """
    patient = None
    if patient_id:
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            # Get form data
            unit_id = request.POST.get('ambulance_unit')
            call_type = request.POST.get('call_type')
            priority = request.POST.get('priority')
            pickup_address = request.POST.get('pickup_address')
            chief_complaint = request.POST.get('chief_complaint', '')
            
            # Get ambulance unit
            unit = AmbulanceUnit.objects.get(pk=unit_id)
            
            # Generate dispatch number
            dispatch_number = f"DISP-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create dispatch
            dispatch = AmbulanceDispatch.objects.create(
                dispatch_number=dispatch_number,
                ambulance_unit=unit,
                call_type=call_type,
                priority=priority,
                pickup_address=pickup_address,
                chief_complaint=chief_complaint,
                patient=patient,
                call_received_at=timezone.now(),
                dispatch_time=timezone.now()
            )
            
            # Update unit status
            unit.status = 'en_route'
            unit.current_location = pickup_address
            unit.save()
            
            messages.success(request, f'🚑 Ambulance {unit.unit_number} dispatched successfully! Dispatch #{dispatch_number}')
            return redirect('hospital:triage_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error creating dispatch: {str(e)}')
    
    # Get available units
    available_units = AmbulanceUnit.objects.filter(
        is_deleted=False,
        status='available'
    )
    
    context = {
        'patient': patient,
        'available_units': available_units,
        'call_types': AmbulanceDispatch.CALL_TYPES,
        'priority_levels': AmbulanceDispatch.PRIORITY_LEVELS,
    }
    
    return render(request, 'hospital/ambulance/create_dispatch.html', context)


@login_required
def patient_request_ambulance(request, encounter_id):
    """
    Request ambulance for a patient encounter
    Creates dispatch and updates encounter
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            unit_id = request.POST.get('ambulance_unit')
            destination = request.POST.get('destination_address')
            priority = request.POST.get('priority', 'code_2')
            
            unit = AmbulanceUnit.objects.get(pk=unit_id)
            
            # Create dispatch
            dispatch = AmbulanceDispatch.objects.create(
                dispatch_number=f"DISP-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                ambulance_unit=unit,
                call_type='transfer',
                priority=priority,
                pickup_address=f"Hospital - Patient: {encounter.patient.full_name}",
                destination_address=destination,
                chief_complaint=f"Transfer request - {encounter.get_encounter_type_display()}",
                patient=encounter.patient,
                encounter=encounter,
                call_received_at=timezone.now(),
                dispatch_time=timezone.now()
            )
            
            # Update unit
            unit.status = 'transporting'
            unit.save()
            
            messages.success(request, f'Ambulance {unit.unit_number} dispatched for patient transfer')
            return redirect('hospital:encounter_detail', pk=encounter_id)
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    available_units = AmbulanceUnit.objects.filter(is_deleted=False, status='available')
    
    context = {
        'encounter': encounter,
        'patient': encounter.patient,
        'available_units': available_units,
    }
    
    return render(request, 'hospital/ambulance/request_transfer.html', context)


@login_required
def complete_ambulance_dispatch(request, dispatch_id):
    """
    Mark dispatch as completed and create billing
    """
    dispatch = get_object_or_404(AmbulanceDispatch, pk=dispatch_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            # Update dispatch times
            if not dispatch.hospital_arrival_time:
                dispatch.hospital_arrival_time = timezone.now()
            dispatch.call_completed_time = timezone.now()
            
            # Get data from form
            miles = Decimal(request.POST.get('miles_traveled', '0'))
            service_type_id = request.POST.get('service_type')
            pre_hospital_report = request.POST.get('pre_hospital_report', '')
            vital_signs = request.POST.get('vital_signs', '')
            
            dispatch.miles_traveled = miles
            dispatch.pre_hospital_report = pre_hospital_report
            dispatch.vital_signs_on_scene = vital_signs
            dispatch.patient_transported = True
            dispatch.save()
            
            # Update unit status
            dispatch.ambulance_unit.status = 'available'
            dispatch.ambulance_unit.current_location = dispatch.ambulance_unit.home_station
            dispatch.ambulance_unit.mileage += int(miles)
            dispatch.ambulance_unit.save()
            
            # Create billing if requested
            if service_type_id:
                service_type = AmbulanceServiceType.objects.get(pk=service_type_id)
                
                # Calculate charges
                base = service_type.base_charge
                mileage = service_type.per_mile_charge * miles
                emergency = service_type.emergency_surcharge if dispatch.priority == 'code_3' else Decimal('0.00')
                
                billing = AmbulanceBilling.objects.create(
                    dispatch=dispatch,
                    service_type=service_type,
                    patient=dispatch.patient,
                    encounter=dispatch.encounter,
                    base_charge=base,
                    miles_traveled=miles,
                    mileage_charge=mileage,
                    emergency_surcharge=emergency,
                    equipment_fees=service_type.equipment_fee,
                    subtotal=base + mileage + emergency + service_type.equipment_fee,
                    total_amount=base + mileage + emergency + service_type.equipment_fee,
                    balance=base + mileage + emergency + service_type.equipment_fee,
                    status='pending',
                    invoice_date=timezone.now()
                )
                
                messages.success(request, f'Dispatch completed! Invoice {billing.invoice_number} created for GHS {billing.total_amount}')
            else:
                messages.success(request, f'Dispatch completed! Unit {dispatch.ambulance_unit.unit_number} is now available.')
            
            return redirect('hospital:triage_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    service_types = AmbulanceServiceType.objects.filter(is_deleted=False, is_active=True)
    
    context = {
        'dispatch': dispatch,
        'service_types': service_types,
    }
    
    return render(request, 'hospital/ambulance/complete_dispatch.html', context)


@login_required
def ambulance_dashboard(request):
    """
    Dedicated ambulance management dashboard
    """
    now = timezone.now()
    
    # Get all units
    units = AmbulanceUnit.objects.filter(is_deleted=False).select_related(
        'primary_paramedic__user',
        'primary_emt__user'
    )
    
    # Recent dispatches (last 48 hours)
    recent_dispatches = AmbulanceDispatch.objects.filter(
        is_deleted=False,
        call_received_at__gte=now - timedelta(hours=48)
    ).select_related(
        'ambulance_unit',
        'patient',
        'encounter__patient'
    ).order_by('-call_received_at')
    
    # Pending bills
    pending_bills = AmbulanceBilling.objects.filter(
        is_deleted=False,
        status='pending'
    ).select_related('dispatch__ambulance_unit', 'patient')
    
    # Statistics
    stats = {
        'total_units': units.count(),
        'available': units.filter(status='available').count(),
        'active_calls': recent_dispatches.filter(call_completed_time__isnull=True).count(),
        'completed_today': recent_dispatches.filter(
            call_completed_time__date=now.date()
        ).count(),
        'pending_bills': pending_bills.count(),
    }
    
    context = {
        'units': units,
        'recent_dispatches': recent_dispatches[:20],
        'pending_bills': pending_bills[:10],
        'stats': stats,
    }
    
    return render(request, 'hospital/ambulance/dashboard.html', context)


















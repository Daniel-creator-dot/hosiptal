"""
Blood Bank & Transfusion Management Views
State-of-the-art blood bank operations
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, F
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta, date
import logging

from .models import Patient, Staff, Encounter
from .models_blood_bank import (
    BloodDonor, BloodDonation, BloodInventory, TransfusionRequest,
    BloodCrossmatch, BloodTransfusion, BloodCompatibilityMatrix,
    BLOOD_GROUP_CHOICES, BLOOD_COMPONENT_CHOICES
)

logger = logging.getLogger(__name__)


@login_required
def blood_bank_dashboard(request):
    """
    Main blood bank dashboard with overview
    """
    # Inventory statistics by blood group
    inventory_stats = []
    for group_code, group_name in BLOOD_GROUP_CHOICES:
        available = BloodInventory.objects.filter(
            blood_group=group_code,
            status='available',
            expiry_date__gt=timezone.now().date(),
            is_deleted=False
        ).count()
        
        expiring_soon = BloodInventory.objects.filter(
            blood_group=group_code,
            status='available',
            expiry_date__lte=timezone.now().date() + timedelta(days=7),
            expiry_date__gt=timezone.now().date(),
            is_deleted=False
        ).count()
        
        inventory_stats.append({
            'group': group_code,
            'available': available,
            'expiring_soon': expiring_soon,
            'status': 'critical' if available < 5 else 'low' if available < 10 else 'ok'
        })
    
    # Recent donations
    recent_donations = BloodDonation.objects.filter(
        is_deleted=False
    ).select_related('donor', 'collected_by__user').order_by('-donation_date')[:10]
    
    # Pending transfusion requests
    pending_requests = TransfusionRequest.objects.filter(
        status__in=['pending', 'crossmatch_in_progress'],
        is_deleted=False
    ).select_related('patient', 'requested_by__user').order_by('-requested_at')[:10]
    
    # Statistics
    today = timezone.now().date()
    stats = {
        'total_inventory': BloodInventory.objects.filter(status='available', expiry_date__gt=today, is_deleted=False).count(),
        'expiring_soon': BloodInventory.objects.filter(
            status='available',
            expiry_date__lte=today + timedelta(days=7),
            expiry_date__gt=today,
            is_deleted=False
        ).count(),
        'pending_requests': pending_requests.count(),
        'active_donors': BloodDonor.objects.filter(is_active=True, is_eligible=True, is_deleted=False).count(),
        'donations_today': BloodDonation.objects.filter(donation_date__date=today, is_deleted=False).count(),
        'transfusions_today': BloodTransfusion.objects.filter(started_at__date=today, is_deleted=False).count(),
    }
    
    context = {
        'title': 'Blood Bank Dashboard',
        'inventory_stats': inventory_stats,
        'recent_donations': recent_donations,
        'pending_requests': pending_requests,
        'stats': stats,
    }
    return render(request, 'hospital/blood_bank_dashboard.html', context)


@login_required
def blood_inventory_list(request):
    """
    Blood inventory management - view all blood units
    """
    # Filters
    blood_group_filter = request.GET.get('blood_group', '')
    component_filter = request.GET.get('component', '')
    status_filter = request.GET.get('status', 'available')
    
    inventory = BloodInventory.objects.filter(is_deleted=False).select_related('donation__donor')
    
    if blood_group_filter:
        inventory = inventory.filter(blood_group=blood_group_filter)
    if component_filter:
        inventory = inventory.filter(component_type=component_filter)
    if status_filter:
        inventory = inventory.filter(status=status_filter)
    
    # Expiry check
    today = timezone.now().date()
    inventory = inventory.filter(expiry_date__gt=today) if status_filter == 'available' else inventory
    
    inventory = inventory.order_by('expiry_date', 'blood_group')
    
    context = {
        'title': 'Blood Inventory',
        'inventory': inventory,
        'blood_groups': BLOOD_GROUP_CHOICES,
        'components': BLOOD_COMPONENT_CHOICES,
        'blood_group_filter': blood_group_filter,
        'component_filter': component_filter,
        'status_filter': status_filter,
    }
    return render(request, 'hospital/blood_inventory_list.html', context)


@login_required
def transfusion_request_create(request, patient_id=None, encounter_id=None):
    """
    Create new transfusion request
    """
    if patient_id:
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
        encounter = patient.encounters.filter(status='active', is_deleted=False).first()
    elif encounter_id:
        encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
        patient = encounter.patient
    else:
        messages.error(request, 'Patient or encounter required.')
        return redirect('hospital:blood_bank_dashboard')
    
    try:
        current_doctor = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff.')
        return redirect('hospital:blood_bank_dashboard')
    
    if request.method == 'POST':
        try:
            # Generate request number
            import uuid
            request_number = f"TR-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            
            # Create transfusion request
            transfusion_req = TransfusionRequest.objects.create(
                request_number=request_number,
                patient=patient,
                encounter=encounter,
                requested_by=current_doctor,
                patient_blood_group=request.POST.get('blood_group'),
                component_type=request.POST.get('component_type'),
                units_requested=int(request.POST.get('units_requested', 1)),
                indication=request.POST.get('indication'),
                clinical_notes=request.POST.get('clinical_notes', ''),
                urgency=request.POST.get('urgency', 'routine'),
                pre_transfusion_hb=request.POST.get('pre_hb') or None,
                pre_transfusion_bp_systolic=request.POST.get('pre_bp_sys') or None,
                pre_transfusion_bp_diastolic=request.POST.get('pre_bp_dia') or None,
            )
            
            messages.success(request, f'✅ Transfusion request {request_number} created successfully.')
            return redirect('hospital:transfusion_request_detail', request_id=transfusion_req.pk)
            
        except Exception as e:
            logger.error(f"Error creating transfusion request: {str(e)}")
            messages.error(request, f'Error creating request: {str(e)}')
    
    context = {
        'title': f'Request Blood Transfusion - {patient.full_name}',
        'patient': patient,
        'encounter': encounter,
        'blood_groups': BLOOD_GROUP_CHOICES,
        'components': BLOOD_COMPONENT_CHOICES,
    }
    return render(request, 'hospital/transfusion_request_create.html', context)


@login_required
def transfusion_requests_list(request):
    """
    List all transfusion requests
    """
    status_filter = request.GET.get('status', '')
    urgency_filter = request.GET.get('urgency', '')
    
    requests = TransfusionRequest.objects.filter(is_deleted=False).select_related(
        'patient', 'requested_by__user', 'approved_by__user'
    ).order_by('-requested_at')
    
    if status_filter:
        requests = requests.filter(status=status_filter)
    if urgency_filter:
        requests = requests.filter(urgency=urgency_filter)
    
    context = {
        'title': 'Transfusion Requests',
        'requests': requests,
        'status_filter': status_filter,
        'urgency_filter': urgency_filter,
    }
    return render(request, 'hospital/transfusion_requests_list.html', context)


@login_required
def transfusion_request_detail(request, request_id):
    """
    Detailed view of transfusion request with crossmatch and issue capability
    """
    transfusion_req = get_object_or_404(TransfusionRequest, pk=request_id, is_deleted=False)
    
    try:
        current_staff = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff.')
        return redirect('hospital:transfusion_requests_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'process':
            # Lab technician processing
            transfusion_req.status = 'crossmatch_in_progress'
            transfusion_req.processed_by = current_staff
            transfusion_req.processed_at = timezone.now()
            transfusion_req.save()
            messages.success(request, 'Request marked as processing.')
        
        elif action == 'complete_crossmatch':
            # Complete crossmatch
            transfusion_req.crossmatch_completed = True
            transfusion_req.crossmatch_compatible = request.POST.get('compatible') == 'yes'
            transfusion_req.crossmatch_notes = request.POST.get('crossmatch_notes', '')
            
            if transfusion_req.crossmatch_compatible:
                transfusion_req.status = 'approved'
                transfusion_req.is_approved = True
                transfusion_req.approved_by = current_staff
                transfusion_req.approved_at = timezone.now()
                messages.success(request, '✅ Crossmatch complete - Blood ready for issue!')
            else:
                transfusion_req.status = 'cancelled'
                transfusion_req.rejection_reason = request.POST.get('crossmatch_notes', 'Incompatible crossmatch')
                messages.warning(request, '⚠️ Crossmatch incompatible - Request cancelled.')
            
            transfusion_req.save()
        
        elif action == 'issue_blood':
            # Issue blood units
            unit_ids = request.POST.getlist('blood_units')
            if unit_ids:
                for unit_id in unit_ids:
                    unit = BloodInventory.objects.get(pk=unit_id)
                    unit.status = 'issued'
                    unit.save()
                
                transfusion_req.status = 'issued'
                transfusion_req.save()
                messages.success(request, f'✅ {len(unit_ids)} blood unit(s) issued successfully!')
            else:
                messages.error(request, 'Please select blood units to issue.')
        
        return redirect('hospital:transfusion_request_detail', request_id=transfusion_req.pk)
    
    # Find compatible blood units
    compatible_groups = BloodCompatibilityMatrix.get_compatible_groups(
        transfusion_req.patient_blood_group,
        transfusion_req.component_type
    )
    
    available_units = BloodInventory.objects.filter(
        blood_group__in=compatible_groups,
        component_type=transfusion_req.component_type,
        status='available',
        expiry_date__gt=timezone.now().date(),
        is_deleted=False
    ).select_related('donation__donor').order_by('expiry_date')[:20]
    
    # Get crossmatches
    crossmatches = BloodCrossmatch.objects.filter(
        transfusion_request=transfusion_req,
        is_deleted=False
    ).select_related('blood_unit', 'tested_by__user')
    
    # Get issued transfusions
    transfusions = BloodTransfusion.objects.filter(
        transfusion_request=transfusion_req,
        is_deleted=False
    ).select_related('blood_unit', 'administered_by__user')
    
    context = {
        'title': f'Transfusion Request - {transfusion_req.request_number}',
        'transfusion_req': transfusion_req,
        'available_units': available_units,
        'compatible_groups': compatible_groups,
        'crossmatches': crossmatches,
        'transfusions': transfusions,
    }
    return render(request, 'hospital/transfusion_request_detail.html', context)


@login_required
def donor_registration(request):
    """
    Register new blood donor
    """
    if request.method == 'POST':
        try:
            # Generate donor ID
            import uuid
            donor_id = f"DON-{timezone.now().strftime('%Y')}-{str(uuid.uuid4())[:6].upper()}"
            
            # Check if patient
            patient_mrn = request.POST.get('patient_mrn', '')
            patient = None
            if patient_mrn:
                patient = Patient.objects.filter(mrn=patient_mrn, is_deleted=False).first()
            
            donor = BloodDonor.objects.create(
                donor_id=donor_id,
                patient=patient,
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                date_of_birth=request.POST.get('date_of_birth'),
                gender=request.POST.get('gender'),
                phone_number=request.POST.get('phone_number', ''),
                email=request.POST.get('email', ''),
                address=request.POST.get('address', ''),
                blood_group=request.POST.get('blood_group'),
                weight_kg=request.POST.get('weight') or None,
                hemoglobin_level=request.POST.get('hemoglobin') or None,
                notes=request.POST.get('notes', ''),
            )
            
            messages.success(request, f'✅ Donor {donor_id} registered successfully!')
            return redirect('hospital:donor_detail', donor_id=donor.pk)
            
        except Exception as e:
            logger.error(f"Error registering donor: {str(e)}")
            messages.error(request, f'Error registering donor: {str(e)}')
    
    context = {
        'title': 'Register Blood Donor',
        'blood_groups': BLOOD_GROUP_CHOICES,
    }
    return render(request, 'hospital/donor_registration.html', context)


@login_required
def donors_list(request):
    """
    List all blood donors
    """
    search = request.GET.get('search', '')
    blood_group = request.GET.get('blood_group', '')
    status = request.GET.get('status', 'active')
    
    donors = BloodDonor.objects.filter(is_deleted=False)
    
    if search:
        donors = donors.filter(
            Q(donor_id__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone_number__icontains=search)
        )
    
    if blood_group:
        donors = donors.filter(blood_group=blood_group)
    
    if status == 'active':
        donors = donors.filter(is_active=True, is_eligible=True)
    elif status == 'inactive':
        donors = donors.filter(is_active=False)
    elif status == 'ineligible':
        donors = donors.filter(is_eligible=False)
    
    donors = donors.order_by('-last_donation_date', 'last_name')
    
    context = {
        'title': 'Blood Donors',
        'donors': donors,
        'blood_groups': BLOOD_GROUP_CHOICES,
        'search': search,
        'blood_group': blood_group,
        'status': status,
    }
    return render(request, 'hospital/donors_list.html', context)


@login_required
def donor_detail(request, donor_id):
    """
    Donor profile with donation history
    """
    donor = get_object_or_404(BloodDonor, pk=donor_id, is_deleted=False)
    
    # Donation history
    donations = BloodDonation.objects.filter(
        donor=donor,
        is_deleted=False
    ).order_by('-donation_date')
    
    # Check eligibility
    can_donate, reason = donor.can_donate()
    
    context = {
        'title': f'Donor Profile - {donor.full_name}',
        'donor': donor,
        'donations': donations,
        'can_donate': can_donate,
        'eligibility_reason': reason,
    }
    return render(request, 'hospital/donor_detail.html', context)


@login_required
def record_donation(request, donor_id):
    """
    Record a new blood donation
    """
    donor = get_object_or_404(BloodDonor, pk=donor_id, is_deleted=False)
    
    # Check eligibility
    can_donate, reason = donor.can_donate()
    if not can_donate:
        messages.error(request, f'Donor is not eligible: {reason}')
        return redirect('hospital:donor_detail', donor_id=donor.pk)
    
    try:
        current_staff = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff.')
        return redirect('hospital:donors_list')
    
    if request.method == 'POST':
        try:
            # Generate donation number
            import uuid
            donation_number = f"BLD-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            
            donation = BloodDonation.objects.create(
                donor=donor,
                donation_number=donation_number,
                blood_group=donor.blood_group,
                pre_donation_hemoglobin=request.POST.get('hemoglobin'),
                pre_donation_weight=request.POST.get('weight'),
                pre_donation_bp_systolic=request.POST.get('bp_systolic'),
                pre_donation_bp_diastolic=request.POST.get('bp_diastolic'),
                pre_donation_temperature=request.POST.get('temperature'),
                volume_collected_ml=int(request.POST.get('volume', 450)),
                collected_by=current_staff,
                notes=request.POST.get('notes', ''),
            )
            
            # Update donor
            donor.last_donation_date = timezone.now().date()
            donor.total_donations += 1
            donor.save()
            
            messages.success(request, f'✅ Donation {donation_number} recorded successfully!')
            return redirect('hospital:donation_detail', donation_id=donation.pk)
            
        except Exception as e:
            logger.error(f"Error recording donation: {str(e)}")
            messages.error(request, f'Error recording donation: {str(e)}')
    
    context = {
        'title': f'Record Donation - {donor.full_name}',
        'donor': donor,
    }
    return render(request, 'hospital/record_donation.html', context)


@login_required
def donation_detail(request, donation_id):
    """
    Donation details with testing and approval
    """
    donation = get_object_or_404(BloodDonation, pk=donation_id, is_deleted=False)
    
    try:
        current_staff = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff.')
        return redirect('hospital:blood_bank_dashboard')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            donation.approve_donation(current_staff)
            
            # Create blood inventory units
            import uuid
            components = request.POST.getlist('components')
            for component in components:
                unit_number = f"UNIT-{timezone.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
                
                # Calculate expiry based on component
                expiry_days = {
                    'whole_blood': 35,
                    'packed_rbc': 42,
                    'fresh_frozen_plasma': 365,
                    'platelets': 5,
                    'cryoprecipitate': 365,
                }.get(component, 35)
                
                BloodInventory.objects.create(
                    unit_number=unit_number,
                    donation=donation,
                    blood_group=donation.blood_group,
                    component_type=component,
                    volume_ml=450 if component == 'whole_blood' else 250,
                    collection_date=donation.donation_date.date(),
                    expiry_date=donation.donation_date.date() + timedelta(days=expiry_days),
                    storage_location='Main Blood Bank Fridge',
                    status='available',
                )
            
            messages.success(request, f'✅ Donation approved and {len(components)} unit(s) added to inventory!')
        
        elif action == 'reject':
            donation.testing_status = 'rejected'
            donation.rejection_reason = request.POST.get('rejection_reason', '')
            donation.save()
            messages.warning(request, 'Donation rejected.')
        
        return redirect('hospital:donation_detail', donation_id=donation.pk)
    
    # Get created blood units
    blood_units = BloodInventory.objects.filter(donation=donation, is_deleted=False)
    
    context = {
        'title': f'Donation - {donation.donation_number}',
        'donation': donation,
        'blood_units': blood_units,
        'components': BLOOD_COMPONENT_CHOICES,
    }
    return render(request, 'hospital/donation_detail.html', context)






















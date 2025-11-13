"""
Specialist Views - Dental, Cardiology, Ophthalmology, etc.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
import logging

from .models import Patient, Encounter, Staff
from .models_specialists import (
    Specialty, SpecialistProfile, DentalChart, ToothCondition, DentalProcedure,
    CardiologyChart, OphthalmologyChart, SpecialistConsultation, Referral,
    DentalProcedureCatalog
)
from .forms import ReferralForm, ReferralResponseForm

logger = logging.getLogger(__name__)


@login_required
def specialist_dashboard(request):
    """List all specialists"""
    specialties = Specialty.objects.filter(is_active=True)
    specialists = SpecialistProfile.objects.filter(is_active=True).select_related('staff__user', 'specialty')
    
    # Group by specialty
    specialists_by_specialty = {}
    for specialist in specialists:
        specialty_name = specialist.specialty.name
        if specialty_name not in specialists_by_specialty:
            specialists_by_specialty[specialty_name] = []
        specialists_by_specialty[specialty_name].append(specialist)
    
    context = {
        'specialties': specialties,
        'specialists_by_specialty': specialists_by_specialty,
    }
    return render(request, 'hospital/specialists/dashboard.html', context)


@login_required
def specialist_patient_select(request):
    """Select a patient for specialist consultation"""
    specialty_filter = request.GET.get('specialty', '').lower()
    search_query = request.GET.get('q', '')
    
    # Get active encounters with patients
    from .models import Encounter
    from django.core.paginator import Paginator
    
    encounters = Encounter.objects.filter(
        status='active',
        is_deleted=False
    ).select_related('patient').order_by('-started_at')
    
    # Apply search if provided
    if search_query:
        encounters = encounters.filter(
            Q(patient__first_name__icontains=search_query) |
            Q(patient__last_name__icontains=search_query) |
            Q(patient__mrn__icontains=search_query)
        )
    
    # Paginate
    paginator = Paginator(encounters, 20)
    page = request.GET.get('page', 1)
    encounters_page = paginator.get_page(page)
    
    # Determine consultation URL based on specialty
    specialty_url_map = {
        'dental': 'hospital:dental_consultation_encounter',
        'dentistry': 'hospital:dental_consultation_encounter',
        'cardiology': 'hospital:cardiology_consultation_encounter',
        'ophthalmology': 'hospital:ophthalmology_consultation_encounter',
    }
    
    consultation_url = specialty_url_map.get(specialty_filter, 'hospital:encounter_detail')
    
    context = {
        'encounters': encounters_page,
        'specialty': specialty_filter,
        'search_query': search_query,
        'consultation_url': consultation_url,
        'specialty_display': specialty_filter.title() if specialty_filter else 'Specialist',
    }
    return render(request, 'hospital/specialists/patient_select.html', context)


@login_required
def dentist_dashboard(request):
    """Dashboard for dentist specialists - shows referrals and dental consultations"""
    # Get current staff
    try:
        current_staff = request.user.staff
    except AttributeError:
        messages.error(request, 'You must be registered as staff to access this page.')
        return redirect('hospital:dashboard')
    
    # Check if user is a dentist specialist
    try:
        specialist_profile = current_staff.specialist_profile
        # Check if specialty is dental or dentistry
        specialty_name = specialist_profile.specialty.name.lower()
        if 'dental' not in specialty_name and 'dentistry' not in specialty_name:
            messages.error(request, 'This dashboard is only for dental specialists.')
            return redirect('hospital:dashboard')
    except AttributeError:
        messages.error(request, 'You are not registered as a specialist.')
        return redirect('hospital:dashboard')
    
    # Get pending/active referrals for this dentist
    pending_referrals = Referral.objects.filter(
        specialist=specialist_profile,
        status__in=['pending', 'accepted'],
        is_deleted=False
    ).select_related('patient', 'encounter', 'referring_doctor__user', 'specialty').order_by('-referred_date')[:10]
    
    # Get recent referrals
    recent_referrals = Referral.objects.filter(
        specialist=specialist_profile,
        is_deleted=False
    ).select_related('patient', 'encounter', 'referring_doctor__user').order_by('-referred_date')[:10]
    
    # Get recent dental charts
    recent_dental_charts = DentalChart.objects.filter(
        created_by=current_staff,
        is_deleted=False
    ).select_related('patient', 'encounter').order_by('-chart_date')[:10]
    
    # Statistics
    stats = {
        'pending_referrals_count': Referral.objects.filter(
            specialist=specialist_profile,
            status='pending',
            is_deleted=False
        ).count(),
        'active_referrals_count': Referral.objects.filter(
            specialist=specialist_profile,
            status='accepted',
            is_deleted=False
        ).count(),
        'total_charts_today': DentalChart.objects.filter(
            created_by=current_staff,
            chart_date=timezone.now().date(),
            is_deleted=False
        ).count(),
        'total_charts_this_month': DentalChart.objects.filter(
            created_by=current_staff,
            chart_date__month=timezone.now().month,
            chart_date__year=timezone.now().year,
            is_deleted=False
        ).count(),
    }
    
    context = {
        'specialist_profile': specialist_profile,
        'current_staff': current_staff,
        'pending_referrals': pending_referrals,
        'recent_referrals': recent_referrals,
        'recent_dental_charts': recent_dental_charts,
        'stats': stats,
    }
    return render(request, 'hospital/specialists/dentist_dashboard.html', context)


@login_required
def dental_consultation(request, patient_id=None, encounter_id=None):
    """
    Dental consultation page with interactive teeth diagram.
    Supports both patient-based and encounter-based access with smart redirecting.
    """
    patient = None
    encounter = None
    dental_chart = None
    
    logger.info(f"Dental consultation accessed - patient_id: {patient_id}, encounter_id: {encounter_id}")
    
    # If encounter_id is provided, use it (preferred method)
    if encounter_id:
        encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
        patient = encounter.patient
        
        # Get or create dental chart for this encounter
        dental_chart = DentalChart.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).first()
        
        if not dental_chart:
            # Check if there's a chart for this patient
            dental_chart = DentalChart.objects.filter(
                patient=patient,
                is_deleted=False
            ).order_by('-chart_date').first()
    
    # If only patient_id is provided
    elif patient_id:
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
        
        # Check if there's an active encounter for this patient
        active_encounter = Encounter.objects.filter(
            patient=patient,
            status='in_progress',
            is_deleted=False
        ).order_by('-started_at').first()
        
        # If there's an active encounter, redirect to use encounter-based URL
        if active_encounter:
            logger.info(f"Redirecting to encounter-based dental consultation for patient {patient_id} -> encounter {active_encounter.pk}")
            messages.info(request, f"Opened dental chart for active encounter (Visit #{active_encounter.pk})")
            return redirect('hospital:dental_consultation_encounter', encounter_id=active_encounter.pk)
        
        # Otherwise, get or create latest dental chart
        dental_chart = DentalChart.objects.filter(
            patient=patient,
            is_deleted=False
        ).order_by('-chart_date').first()
    else:
        # Neither patient_id nor encounter_id provided - redirect to specialist dashboard
        messages.warning(request, "Please select a patient or encounter to start a dental consultation.")
        return redirect('hospital:specialist_dashboard')
    
    # Get current staff member
    current_staff = None
    if hasattr(request.user, 'staff_profile'):
        current_staff = request.user.staff
    
    # Create new chart if none exists
    if patient and not dental_chart:
        dental_chart = DentalChart.objects.create(
            patient=patient,
            encounter=encounter,
            created_by=current_staff
        )
        logger.info(f"Created new dental chart {dental_chart.pk} for patient {patient.pk}")
        messages.success(request, f"New dental chart created for {patient.full_name}")
    
    # Get existing tooth conditions - simplified for template
    # Create mapping from FDI to sequential numbers (1-32)
    # Upper right: 18-11 -> 1-8, Upper left: 21-28 -> 9-16
    # Lower left: 31-38 -> 17-24, Lower right: 41-48 -> 25-32
    fdi_to_sequential = {}
    sequential_to_fdi = {}
    tooth_conditions_map = {}
    
    # Upper right (18-11) -> 1-8
    upper_right_fdi = ['18', '17', '16', '15', '14', '13', '12', '11']
    for i, fdi in enumerate(upper_right_fdi, 1):
        fdi_to_sequential[fdi] = str(i)
        sequential_to_fdi[str(i)] = fdi
    
    # Upper left (21-28) -> 9-16
    upper_left_fdi = ['21', '22', '23', '24', '25', '26', '27', '28']
    for i, fdi in enumerate(upper_left_fdi, 9):
        fdi_to_sequential[fdi] = str(i)
        sequential_to_fdi[str(i)] = fdi
    
    # Lower left (31-38) -> 17-24
    lower_left_fdi = ['31', '32', '33', '34', '35', '36', '37', '38']
    for i, fdi in enumerate(lower_left_fdi, 17):
        fdi_to_sequential[fdi] = str(i)
        sequential_to_fdi[str(i)] = fdi
    
    # Lower right (41-48) -> 25-32
    lower_right_fdi = ['41', '42', '43', '44', '45', '46', '47', '48']
    for i, fdi in enumerate(lower_right_fdi, 25):
        fdi_to_sequential[fdi] = str(i)
        sequential_to_fdi[str(i)] = fdi
    
    if dental_chart:
        conditions = ToothCondition.objects.filter(
            dental_chart=dental_chart,
            is_deleted=False
        )
        for condition in conditions:
            # Map FDI to sequential number for display
            sequential_num = fdi_to_sequential.get(condition.tooth_number)
            if sequential_num:
                if sequential_num not in tooth_conditions_map:
                    tooth_conditions_map[sequential_num] = condition.condition_type
    
    # Get procedures
    procedures = []
    if dental_chart:
        procedures = DentalProcedure.objects.filter(
            dental_chart=dental_chart,
            is_deleted=False
        ).order_by('-created')
    
    # Get dental procedure catalog for billing
    procedure_catalog = DentalProcedureCatalog.objects.filter(is_active=True).order_by('code')
    
    context = {
        'patient': patient,
        'encounter': encounter,
        'dental_chart': dental_chart,
        'tooth_conditions_map': tooth_conditions_map,
        'sequential_to_fdi': sequential_to_fdi,  # For converting back to FDI when saving
        'fdi_to_sequential': fdi_to_sequential,  # For displaying sequential numbers
        'procedures': procedures,
        'procedure_catalog': procedure_catalog,
        'condition_types': ToothCondition.CONDITION_TYPES,
        'procedure_types': DentalProcedure.PROCEDURE_TYPES,
    }
    return render(request, 'hospital/specialists/dental_consultation.html', context)


@login_required
def save_tooth_condition(request):
    """Save tooth condition via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        dental_chart_id = request.POST.get('dental_chart_id')
        tooth_number = request.POST.get('tooth_number')
        condition_type = request.POST.get('condition_type')
        surface = request.POST.get('surface', '')
        color_code = request.POST.get('color_code', '')
        notes = request.POST.get('notes', '')
        
        dental_chart = get_object_or_404(DentalChart, pk=dental_chart_id, is_deleted=False)
        
        # Get or create condition
        condition, created = ToothCondition.objects.get_or_create(
            dental_chart=dental_chart,
            tooth_number=tooth_number,
            surface=surface,
            defaults={
                'condition_type': condition_type,
                'color_code': color_code,
                'notes': notes,
            }
        )
        
        if not created:
            condition.condition_type = condition_type
            condition.color_code = color_code
            condition.notes = notes
            condition.save()
        
        return JsonResponse({
            'success': True,
            'id': condition.id,
            'message': 'Tooth condition saved successfully'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def save_dental_procedure(request):
    """Save dental procedure and create invoice line"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        dental_chart_id = request.POST.get('dental_chart_id')
        procedure_code = request.POST.get('procedure_code')
        procedure_name = request.POST.get('procedure_name')
        procedure_type = request.POST.get('procedure_type')
        teeth = request.POST.get('teeth', '')
        quantity = int(request.POST.get('quantity', 1))
        fee = float(request.POST.get('fee', 0))
        notes = request.POST.get('notes', '')
        
        dental_chart = get_object_or_404(DentalChart, pk=dental_chart_id, is_deleted=False)
        
        # Get current staff
        current_staff = None
        if hasattr(request.user, 'staff_profile'):
            current_staff = request.user.staff
        
        # Get or create procedure catalog entry
        procedure_catalog = None
        if procedure_code:
            procedure_catalog = DentalProcedureCatalog.objects.filter(code=procedure_code).first()
            if procedure_catalog and fee == 0:
                fee = float(procedure_catalog.default_price)
        
        procedure = DentalProcedure.objects.create(
            dental_chart=dental_chart,
            procedure_code=procedure_code,
            procedure_name=procedure_name,
            procedure_type=procedure_type,
            teeth=teeth,
            quantity=quantity,
            fee=fee,
            performed_by=current_staff,
            notes=notes,
        )
        
        # Create invoice line if encounter exists
        if dental_chart.encounter and fee > 0:
            from .models import Invoice, InvoiceLine, ServiceCode, Payer
            from .utils_billing import get_or_create_encounter_invoice
            
            try:
                invoice = get_or_create_encounter_invoice(dental_chart.encounter)
                
                # Get or create service code for dental procedure
                service_code, _ = ServiceCode.objects.get_or_create(
                    code=f'DENT-{procedure_code}',
                    defaults={
                        'description': procedure_name,
                        'category': 'Dental',
                        'is_active': True,
                    }
                )
                
                # Create invoice line
                InvoiceLine.objects.create(
                    invoice=invoice,
                    service_code=service_code,
                    description=f"{procedure_name} - {teeth}" if teeth else procedure_name,
                    quantity=quantity,
                    unit_price=fee,
                    line_total=fee * quantity,
                )
                
                # Update invoice totals
                invoice.update_totals()
            except Exception as e:
                # Don't fail if invoice creation fails, just log it
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create invoice line for dental procedure: {e}")
        
        return JsonResponse({
            'success': True,
            'id': procedure.id,
            'message': 'Procedure saved successfully and invoiced'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def cardiology_consultation(request, patient_id=None, encounter_id=None):
    """Cardiology consultation page"""
    patient = None
    encounter = None
    cardiology_chart = None
    
    if patient_id:
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
        cardiology_chart = CardiologyChart.objects.filter(
            patient=patient,
            is_deleted=False
        ).order_by('-chart_date').first()
    
    if encounter_id:
        encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
        if not patient:
            patient = encounter.patient
    
    current_staff = None
    if hasattr(request.user, 'staff'):
        current_staff = request.user.staff
    
    if patient and not cardiology_chart:
        cardiology_chart = CardiologyChart.objects.create(
            patient=patient,
            encounter=encounter,
            created_by=current_staff
        )
    
    # Handle form submission
    if request.method == 'POST':
        try:
            # Update chart with form data
            if cardiology_chart:
                cardiology_chart.systolic_bp = request.POST.get('systolic_bp', '')
                cardiology_chart.diastolic_bp = request.POST.get('diastolic_bp', '')
                cardiology_chart.heart_rate = request.POST.get('heart_rate', '')
                cardiology_chart.respiratory_rate = request.POST.get('respiratory_rate', '')
                cardiology_chart.rhythm = request.POST.get('rhythm', '')
                cardiology_chart.heart_sounds = request.POST.get('heart_sounds', '')
                cardiology_chart.peripheral_pulses = request.POST.get('peripheral_pulses', '')
                cardiology_chart.ecg_findings = request.POST.get('ecg_findings', '')
                cardiology_chart.other_investigations = request.POST.get('other_investigations', '')
                cardiology_chart.diagnosis = request.POST.get('diagnosis', '')
                cardiology_chart.treatment_plan = request.POST.get('treatment_plan', '')
                cardiology_chart.notes = request.POST.get('notes', '')
                cardiology_chart.save()
                
                messages.success(request, '✅ Cardiology consultation saved successfully!')
                
                # If save_complete, mark encounter as completed
                if request.POST.get('action') == 'save_complete' and encounter:
                    encounter.complete()
                    messages.success(request, '✅ Encounter marked as completed!')
                    return redirect('hospital:specialist_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error saving consultation: {str(e)}')
    
    context = {
        'patient': patient,
        'encounter': encounter,
        'cardiology_chart': cardiology_chart,
    }
    return render(request, 'hospital/specialists/cardiology_consultation.html', context)


@login_required
def ophthalmology_consultation(request, patient_id=None, encounter_id=None):
    """Ophthalmology consultation page"""
    patient = None
    encounter = None
    ophthalmology_chart = None
    
    if patient_id:
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
        ophthalmology_chart = OphthalmologyChart.objects.filter(
            patient=patient,
            is_deleted=False
        ).order_by('-chart_date').first()
    
    if encounter_id:
        encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
        if not patient:
            patient = encounter.patient
    
    current_staff = None
    if hasattr(request.user, 'staff'):
        current_staff = request.user.staff
    
    if patient and not ophthalmology_chart:
        ophthalmology_chart = OphthalmologyChart.objects.create(
            patient=patient,
            encounter=encounter,
            created_by=current_staff
        )
    
    # Handle form submission
    if request.method == 'POST':
        try:
            # Update chart with form data
            if ophthalmology_chart:
                ophthalmology_chart.right_eye_distance_va = request.POST.get('right_eye_distance_va', '')
                ophthalmology_chart.right_eye_near_va = request.POST.get('right_eye_near_va', '')
                ophthalmology_chart.right_eye_iop = request.POST.get('right_eye_iop', '')
                ophthalmology_chart.left_eye_distance_va = request.POST.get('left_eye_distance_va', '')
                ophthalmology_chart.left_eye_near_va = request.POST.get('left_eye_near_va', '')
                ophthalmology_chart.left_eye_iop = request.POST.get('left_eye_iop', '')
                ophthalmology_chart.external_exam = request.POST.get('external_exam', '')
                ophthalmology_chart.anterior_segment = request.POST.get('anterior_segment', '')
                ophthalmology_chart.posterior_segment = request.POST.get('posterior_segment', '')
                ophthalmology_chart.diagnosis = request.POST.get('diagnosis', '')
                ophthalmology_chart.treatment_plan = request.POST.get('treatment_plan', '')
                ophthalmology_chart.notes = request.POST.get('notes', '')
                ophthalmology_chart.save()
                
                messages.success(request, '✅ Ophthalmology consultation saved successfully!')
                
                # If save_complete, mark encounter as completed
                if request.POST.get('action') == 'save_complete' and encounter:
                    encounter.complete()
                    messages.success(request, '✅ Encounter marked as completed!')
                    return redirect('hospital:specialist_dashboard')
            
        except Exception as e:
            messages.error(request, f'Error saving consultation: {str(e)}')
    
    context = {
        'patient': patient,
        'encounter': encounter,
        'ophthalmology_chart': ophthalmology_chart,
    }
    return render(request, 'hospital/specialists/ophthalmology_consultation.html', context)


# ==================== REFERRAL VIEWS ====================

@login_required
def create_referral(request, encounter_id):
    """Create a referral for a patient to a specialist"""
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    # Get current doctor
    try:
        referring_doctor = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to create referrals.')
        return redirect('hospital:encounter_detail', pk=encounter_id)
    
    if request.method == 'POST':
        form = ReferralForm(request.POST)
        if form.is_valid():
            try:
                referral = form.save(commit=False)
                referral.patient = encounter.patient
                referral.encounter = encounter
                referral.referring_doctor = referring_doctor
                referral.specialty = form.cleaned_data['specialty']
                referral.save()
                
                messages.success(request, f'✅ Referral created successfully to {referral.specialist.staff.user.get_full_name()}')
                # Redirect back to encounter detail page
                return redirect('hospital:encounter_detail', pk=encounter_id)
            except Exception as e:
                logger.error(f"Error creating referral: {str(e)}")
                messages.error(request, f'❌ Error creating referral: {str(e)}')
        else:
            # Show form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ReferralForm()
    
    context = {
        'form': form,
        'encounter': encounter,
        'patient': encounter.patient,
        'referring_doctor': referring_doctor,
    }
    return render(request, 'hospital/specialists/create_referral.html', context)


@login_required
def referral_list(request):
    """List referrals - filtered by user role"""
    try:
        current_staff = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to view referrals.')
        return redirect('hospital:dashboard')
    
    # Check if user is a specialist
    is_specialist = hasattr(current_staff, 'specialist_profile') and current_staff.specialist_profile.is_active
    
    if is_specialist:
        # Show referrals received by this specialist
        referrals = Referral.objects.filter(
            specialist=current_staff.specialist_profile,
            is_deleted=False
        ).select_related('patient', 'encounter', 'referring_doctor__user', 'specialty').order_by('-referred_date')
        referral_type = 'received'
    else:
        # Show referrals made by this doctor
        referrals = Referral.objects.filter(
            referring_doctor=current_staff,
            is_deleted=False
        ).select_related('patient', 'encounter', 'specialist__staff__user', 'specialty').order_by('-referred_date')
        referral_type = 'made'
    
    # Filter by status if provided
    status_filter = request.GET.get('status', '')
    if status_filter:
        referrals = referrals.filter(status=status_filter)
    
    context = {
        'referrals': referrals,
        'referral_type': referral_type,
        'is_specialist': is_specialist,
        'current_staff': current_staff,
        'status_filter': status_filter,
    }
    return render(request, 'hospital/specialists/referral_list.html', context)


@login_required
def referral_detail(request, referral_id):
    """View and manage referral details"""
    referral = get_object_or_404(Referral, pk=referral_id, is_deleted=False)
    
    try:
        current_staff = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to view referrals.')
        return redirect('hospital:dashboard')
    
    # Check permissions
    is_referring_doctor = referral.referring_doctor == current_staff
    is_specialist = hasattr(current_staff, 'specialist_profile') and referral.specialist == current_staff.specialist_profile
    
    if not (is_referring_doctor or is_specialist):
        messages.error(request, 'You do not have permission to view this referral.')
        return redirect('hospital:referral_list')
    
    # Handle specialist response
    if is_specialist and request.method == 'POST':
        form = ReferralResponseForm(request.POST, instance=referral)
        action = request.POST.get('action')
        
        if action == 'accept':
            if form.is_valid():
                referral.accept(
                    specialist_notes=form.cleaned_data.get('specialist_notes', ''),
                    appointment_date=form.cleaned_data.get('appointment_date')
                )
                messages.success(request, 'Referral accepted successfully.')
                return redirect('hospital:referral_detail', referral_id=referral_id)
        elif action == 'decline':
            reason = request.POST.get('declined_reason', '')
            referral.decline(reason=reason)
            messages.info(request, 'Referral declined.')
            return redirect('hospital:referral_detail', referral_id=referral_id)
        elif action == 'complete':
            specialist_notes = request.POST.get('specialist_notes', '')
            referral.complete(specialist_notes=specialist_notes)
            messages.success(request, 'Referral marked as completed.')
            return redirect('hospital:referral_detail', referral_id=referral_id)
    else:
        if is_specialist:
            form = ReferralResponseForm(instance=referral)
        else:
            form = None
    
    context = {
        'referral': referral,
        'form': form,
        'is_referring_doctor': is_referring_doctor,
        'is_specialist': is_specialist,
        'current_staff': current_staff,
    }
    return render(request, 'hospital/specialists/referral_detail.html', context)


@login_required
def get_specialists_by_specialty(request):
    """AJAX endpoint to get specialists by specialty"""
    specialty_id = request.GET.get('specialty_id')
    if not specialty_id:
        return JsonResponse({'error': 'Specialty ID required'}, status=400)
    
    try:
        specialty = Specialty.objects.get(pk=specialty_id, is_active=True, is_deleted=False)
        specialists = SpecialistProfile.objects.filter(
            specialty=specialty,
            is_active=True,
            is_deleted=False
        ).select_related('staff__user')
        
        specialists_list = [
            {
                'id': spec.id,
                'name': spec.staff.user.get_full_name(),
                'specialty': spec.specialty.name,
                'qualification': spec.qualification,
            }
            for spec in specialists
        ]
        
        return JsonResponse({'specialists': specialists_list})
    except Specialty.DoesNotExist:
        return JsonResponse({'error': 'Specialty not found'}, status=404)


@login_required
def get_all_specialists(request):
    """AJAX endpoint to get all active specialists (fallback when filter is unavailable)"""
    specialists = SpecialistProfile.objects.filter(
        is_active=True,
        is_deleted=False
    ).select_related('staff__user', 'specialty')
    specialists_list = [
        {
            'id': spec.id,
            'name': spec.staff.user.get_full_name(),
            'specialty': spec.specialty.name,
            'qualification': spec.qualification,
        }
        for spec in specialists
    ]
    return JsonResponse({'specialists': specialists_list})


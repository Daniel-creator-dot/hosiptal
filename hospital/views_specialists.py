"""
Specialist Views - Dental, Cardiology, Ophthalmology, etc.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Value
from django.db.models.functions import Concat
import logging

from .models import Patient, Encounter, Staff
from .models_specialists import (
    Specialty, SpecialistProfile, DentalChart, ToothCondition, DentalProcedure,
    CardiologyChart, OphthalmologyChart, PsychiatricChart, GynecologyChart, SpecialistConsultation, Referral,
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
def specialist_personal_dashboard(request):
    """
    Comprehensive Specialist-Friendly Dashboard
    Shows personalized information for the logged-in specialist
    """
    from datetime import timedelta
    from django.db.models import Count, Q
    from .models import Appointment
    
    # Get current staff
    try:
        current_staff = request.user.staff
    except AttributeError:
        messages.error(request, 'You must be registered as staff to access this page.')
        return redirect('hospital:dashboard')
    
    # Check if user is a specialist
    try:
        specialist_profile = current_staff.specialist_profile
        if not specialist_profile.is_active:
            messages.error(request, 'Your specialist profile is not active.')
            return redirect('hospital:dashboard')
    except AttributeError:
        messages.error(request, 'You are not registered as a specialist.')
        return redirect('hospital:dashboard')
    
    # Date calculations
    today = timezone.now().date()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    # ========== STATISTICS ==========
    # Pending referrals
    pending_referrals_count = Referral.objects.filter(
        specialist=specialist_profile,
        status='pending',
        is_deleted=False
    ).count()
    
    # Active referrals
    active_referrals_count = Referral.objects.filter(
        specialist=specialist_profile,
        status__in=['accepted', 'in_progress'],
        is_deleted=False
    ).count()
    
    # Today's consultations
    consultations_today = SpecialistConsultation.objects.filter(
        specialist=specialist_profile,
        consultation_date__date=today,
        is_deleted=False
    ).count()
    
    # This week's consultations
    consultations_this_week = SpecialistConsultation.objects.filter(
        specialist=specialist_profile,
        consultation_date__gte=week_start,
        is_deleted=False
    ).count()
    
    # This month's consultations
    consultations_this_month = SpecialistConsultation.objects.filter(
        specialist=specialist_profile,
        consultation_date__gte=month_start,
        is_deleted=False
    ).count()
    
    # Today's appointments
    appointments_today = Appointment.objects.filter(
        provider=current_staff,
        appointment_date__date=today,
        status__in=['scheduled', 'confirmed'],
        is_deleted=False
    ).count()
    
    # ========== PENDING REFERRALS ==========
    pending_referrals = Referral.objects.filter(
        specialist=specialist_profile,
        status='pending',
        is_deleted=False
    ).select_related('patient', 'encounter', 'referring_doctor__user', 'specialty').order_by(
        '-priority', '-referred_date'
    )[:10]
    
    # ========== ACTIVE REFERRALS ==========
    active_referrals = Referral.objects.filter(
        specialist=specialist_profile,
        status__in=['accepted', 'in_progress'],
        is_deleted=False
    ).select_related('patient', 'encounter', 'referring_doctor__user', 'specialty').order_by(
        '-priority', '-referred_date'
    )[:10]
    
    # ========== TODAY'S CONSULTATIONS ==========
    today_consultations = SpecialistConsultation.objects.filter(
        specialist=specialist_profile,
        consultation_date__date=today,
        is_deleted=False
    ).select_related('patient', 'encounter').order_by('-consultation_date')[:10]
    
    # ========== TODAY'S APPOINTMENTS ==========
    today_appointments = Appointment.objects.filter(
        provider=current_staff,
        appointment_date__date=today,
        status__in=['scheduled', 'confirmed'],
        is_deleted=False
    ).select_related('patient', 'department').order_by('appointment_date')[:10]
    
    # ========== RECENT CONSULTATIONS ==========
    recent_consultations = SpecialistConsultation.objects.filter(
        specialist=specialist_profile,
        is_deleted=False
    ).select_related('patient', 'encounter').order_by('-consultation_date')[:10]
    
    # ========== SPECIALTY-SPECIFIC CHARTS ==========
    specialty_name = specialist_profile.specialty.name.lower()
    recent_charts = []
    
    if 'dental' in specialty_name or 'dentistry' in specialty_name:
        recent_dental_charts = DentalChart.objects.filter(
            created_by=current_staff,
            is_deleted=False
        ).select_related('patient', 'encounter').order_by('-chart_date')[:5]
        recent_charts = recent_dental_charts
    elif 'cardiology' in specialty_name:
        recent_cardiology_charts = CardiologyChart.objects.filter(
            created_by=current_staff,
            is_deleted=False
        ).select_related('patient', 'encounter').order_by('-chart_date')[:5]
        recent_charts = recent_cardiology_charts
    elif 'ophthalmology' in specialty_name:
        recent_ophthalmology_charts = OphthalmologyChart.objects.filter(
            created_by=current_staff,
            is_deleted=False
        ).select_related('patient', 'encounter').order_by('-chart_date')[:5]
        recent_charts = recent_ophthalmology_charts
    elif 'psychiatric' in specialty_name or 'psychiatry' in specialty_name or 'mental' in specialty_name:
        recent_psychiatric_charts = PsychiatricChart.objects.filter(
            created_by=current_staff,
            is_deleted=False
        ).select_related('patient', 'encounter').order_by('-chart_date')[:5]
        recent_charts = recent_psychiatric_charts
    elif 'gynecology' in specialty_name or 'gynec' in specialty_name or 'obstetric' in specialty_name or 'obgyn' in specialty_name:
        recent_gynecology_charts = GynecologyChart.objects.filter(
            created_by=current_staff,
            is_deleted=False
        ).select_related('patient', 'encounter').order_by('-chart_date')[:5]
        recent_charts = recent_gynecology_charts
    
    # ========== GET CONSULTATION URL BASED ON SPECIALTY ==========
    consultation_url_map = {
        'dental': 'hospital:dental_consultation_encounter',
        'dentistry': 'hospital:dental_consultation_encounter',
        'cardiology': 'hospital:cardiology_consultation_encounter',
        'ophthalmology': 'hospital:ophthalmology_consultation_encounter',
        'psychiatric': 'hospital:psychiatric_consultation_encounter',
        'psychiatry': 'hospital:psychiatric_consultation_encounter',
        'mental': 'hospital:psychiatric_consultation_encounter',
        'gynecology': 'hospital:gynecology_consultation_encounter',
        'gynec': 'hospital:gynecology_consultation_encounter',
        'obstetric': 'hospital:gynecology_consultation_encounter',
        'obgyn': 'hospital:gynecology_consultation_encounter',
    }
    
    consultation_url = consultation_url_map.get(specialty_name, 'hospital:encounter_detail')
    
    context = {
        'specialist_profile': specialist_profile,
        'current_staff': current_staff,
        'specialty': specialist_profile.specialty,
        'consultation_url': consultation_url,
        
        # Statistics
        'stats': {
            'pending_referrals': pending_referrals_count,
            'active_referrals': active_referrals_count,
            'consultations_today': consultations_today,
            'consultations_this_week': consultations_this_week,
            'consultations_this_month': consultations_this_month,
            'appointments_today': appointments_today,
        },
        
        # Data lists
        'pending_referrals': pending_referrals,
        'active_referrals': active_referrals,
        'today_consultations': today_consultations,
        'today_appointments': today_appointments,
        'recent_consultations': recent_consultations,
        'recent_charts': recent_charts,
        
        # Date info
        'today': today,
    }
    
    return render(request, 'hospital/specialists/personal_dashboard.html', context)


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
        'psychiatric': 'hospital:psychiatric_consultation_encounter',
        'psychiatry': 'hospital:psychiatric_consultation_encounter',
        'mental': 'hospital:psychiatric_consultation_encounter',
        'gynecology': 'hospital:gynecology_consultation_encounter',
        'gynec': 'hospital:gynecology_consultation_encounter',
        'obstetric': 'hospital:gynecology_consultation_encounter',
        'obgyn': 'hospital:gynecology_consultation_encounter',
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
        
        # Staff profile is User.staff (OneToOne), not staff_profile
        current_staff = getattr(request.user, 'staff', None)

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
        
        # Invoice: procedure fee + GHS 150 supplies/items per procedure (per unit quantity).
        # Use unique ServiceCode per procedure row so InvoiceLine.save() merge logic does not
        # collapse multiple procedures into one line.
        if dental_chart.encounter:
            from decimal import Decimal
            from .models import InvoiceLine, ServiceCode
            from .utils_billing import get_or_create_encounter_invoice

            DENTAL_ITEMS_UNIT = Decimal('150.00')
            fee_dec = Decimal(str(fee))
            qty_dec = Decimal(str(quantity))

            try:
                invoice = get_or_create_encounter_invoice(dental_chart.encounter)
                if not invoice:
                    raise ValueError('Could not create invoice for encounter (no payer)')

                if fee_dec > 0:
                    proc_code = f'DENT-PROC-{procedure.pk}'
                    proc_desc = (procedure_name or '').strip()[:120] or 'Dental procedure'
                    service_code, _ = ServiceCode.objects.get_or_create(
                        code=proc_code,
                        defaults={
                            'description': procedure_code or proc_desc,
                            'category': 'Dental',
                            'is_active': True,
                        }
                    )
                    InvoiceLine.objects.create(
                        invoice=invoice,
                        service_code=service_code,
                        description=(f"{procedure_name} - {teeth}" if teeth else procedure_name)[:200],
                        quantity=qty_dec,
                        unit_price=fee_dec,
                        line_total=fee_dec * qty_dec,
                    )

                items_sc, _ = ServiceCode.objects.get_or_create(
                    code=f'DENT-ITEMS-{procedure.pk}',
                    defaults={
                        'description': 'Dental procedure supplies & items',
                        'category': 'Dental',
                        'is_active': True,
                    }
                )
                items_desc = (
                    f'Supplies & items — {procedure_name}'
                    + (f' ({teeth})' if teeth else '')
                )
                InvoiceLine.objects.create(
                    invoice=invoice,
                    service_code=items_sc,
                    description=items_desc[:200],
                    quantity=qty_dec,
                    unit_price=DENTAL_ITEMS_UNIT,
                    line_total=DENTAL_ITEMS_UNIT * qty_dec,
                )

                invoice.update_totals()
            except Exception as e:
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


@login_required
def psychiatric_consultation(request, patient_id=None, encounter_id=None):
    """Comprehensive psychiatric consultation page"""
    patient = None
    encounter = None
    psychiatric_chart = None
    
    if patient_id:
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
        psychiatric_chart = PsychiatricChart.objects.filter(
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
    
    if patient and not psychiatric_chart:
        psychiatric_chart = PsychiatricChart.objects.create(
            patient=patient,
            encounter=encounter,
            created_by=current_staff
        )
    
    # Handle form submission
    if request.method == 'POST':
        try:
            if psychiatric_chart:
                # Chief Complaint & Presenting Problem
                psychiatric_chart.chief_complaint = request.POST.get('chief_complaint', '')
                psychiatric_chart.presenting_problem = request.POST.get('presenting_problem', '')
                psychiatric_chart.duration_of_symptoms = request.POST.get('duration_of_symptoms', '')
                
                # Mental Status Examination
                psychiatric_chart.appearance = request.POST.get('appearance', '')
                psychiatric_chart.behavior = request.POST.get('behavior', '')
                psychiatric_chart.speech = request.POST.get('speech', '')
                psychiatric_chart.mood = request.POST.get('mood', '')
                psychiatric_chart.affect = request.POST.get('affect', '')
                psychiatric_chart.thought_process = request.POST.get('thought_process', '')
                psychiatric_chart.thought_content = request.POST.get('thought_content', '')
                psychiatric_chart.perception = request.POST.get('perception', '')
                psychiatric_chart.cognition = request.POST.get('cognition', '')
                psychiatric_chart.insight = request.POST.get('insight', '')
                psychiatric_chart.judgment = request.POST.get('judgment', '')
                
                # Assessment Scales
                phq9 = request.POST.get('phq9_score', '')
                psychiatric_chart.phq9_score = int(phq9) if phq9 else None
                gad7 = request.POST.get('gad7_score', '')
                psychiatric_chart.gad7_score = int(gad7) if gad7 else None
                pcl5 = request.POST.get('pcl5_score', '')
                psychiatric_chart.pcl5_score = int(pcl5) if pcl5 else None
                mmse = request.POST.get('mmse_score', '')
                psychiatric_chart.mmse_score = int(mmse) if mmse else None
                ybocs = request.POST.get('ybocs_score', '')
                psychiatric_chart.ybocs_score = int(ybocs) if ybocs else None
                
                # Risk Assessment
                psychiatric_chart.suicide_risk = request.POST.get('suicide_risk', '')
                psychiatric_chart.suicide_ideation = request.POST.get('suicide_ideation', '')
                psychiatric_chart.suicide_plan = request.POST.get('suicide_plan', '')
                psychiatric_chart.suicide_means = request.POST.get('suicide_means', '')
                psychiatric_chart.homicide_risk = request.POST.get('homicide_risk', '')
                psychiatric_chart.violence_risk = request.POST.get('violence_risk', '')
                psychiatric_chart.self_harm_risk = request.POST.get('self_harm_risk', '')
                
                # History
                psychiatric_chart.psychiatric_history = request.POST.get('psychiatric_history', '')
                psychiatric_chart.previous_diagnoses = request.POST.get('previous_diagnoses', '')
                psychiatric_chart.previous_treatments = request.POST.get('previous_treatments', '')
                psychiatric_chart.hospitalizations = request.POST.get('hospitalizations', '')
                psychiatric_chart.family_psychiatric_history = request.POST.get('family_psychiatric_history', '')
                psychiatric_chart.substance_use_history = request.POST.get('substance_use_history', '')
                
                # Medications
                psychiatric_chart.current_medications = request.POST.get('current_medications', '')
                psychiatric_chart.medication_compliance = request.POST.get('medication_compliance', '')
                psychiatric_chart.medication_side_effects = request.POST.get('medication_side_effects', '')
                
                # Social History
                psychiatric_chart.living_situation = request.POST.get('living_situation', '')
                psychiatric_chart.occupation = request.POST.get('occupation', '')
                psychiatric_chart.education = request.POST.get('education', '')
                psychiatric_chart.social_support = request.POST.get('social_support', '')
                psychiatric_chart.stressors = request.POST.get('stressors', '')
                psychiatric_chart.coping_mechanisms = request.POST.get('coping_mechanisms', '')
                
                # Diagnosis
                psychiatric_chart.primary_diagnosis = request.POST.get('primary_diagnosis', '')
                psychiatric_chart.secondary_diagnosis = request.POST.get('secondary_diagnosis', '')
                psychiatric_chart.provisional_diagnosis = request.POST.get('provisional_diagnosis', '')
                psychiatric_chart.differential_diagnosis = request.POST.get('differential_diagnosis', '')
                
                # Treatment Plan
                psychiatric_chart.treatment_plan = request.POST.get('treatment_plan', '')
                psychiatric_chart.psychotherapy_plan = request.POST.get('psychotherapy_plan', '')
                psychiatric_chart.medication_plan = request.POST.get('medication_plan', '')
                psychiatric_chart.behavioral_interventions = request.POST.get('behavioral_interventions', '')
                psychiatric_chart.goals = request.POST.get('goals', '')
                
                # Progress & Follow-up
                psychiatric_chart.progress_notes = request.POST.get('progress_notes', '')
                psychiatric_chart.response_to_treatment = request.POST.get('response_to_treatment', '')
                follow_up = request.POST.get('follow_up_date', '')
                if follow_up:
                    from datetime import datetime
                    try:
                        psychiatric_chart.follow_up_date = datetime.strptime(follow_up, '%Y-%m-%d').date()
                    except:
                        pass
                psychiatric_chart.follow_up_instructions = request.POST.get('follow_up_instructions', '')
                psychiatric_chart.notes = request.POST.get('notes', '')
                psychiatric_chart.recommendations = request.POST.get('recommendations', '')
                
                psychiatric_chart.save()
                
                messages.success(request, '✅ Psychiatric consultation saved successfully!')
                
                # Create or update specialist consultation record
                try:
                    specialist_profile = current_staff.specialist_profile
                    consultation, created = SpecialistConsultation.objects.get_or_create(
                        patient=patient,
                        encounter=encounter,
                        specialist=specialist_profile,
                        consultation_date__date=timezone.now().date(),
                        defaults={
                            'chief_complaint': psychiatric_chart.chief_complaint,
                            'assessment': psychiatric_chart.primary_diagnosis,
                            'plan': psychiatric_chart.treatment_plan,
                            'notes': psychiatric_chart.notes,
                        }
                    )
                    if not created:
                        consultation.chief_complaint = psychiatric_chart.chief_complaint
                        consultation.assessment = psychiatric_chart.primary_diagnosis
                        consultation.plan = psychiatric_chart.treatment_plan
                        consultation.notes = psychiatric_chart.notes
                        consultation.save()
                except:
                    pass  # If specialist profile doesn't exist, skip
                
                return redirect('hospital:psychiatric_consultation_encounter', encounter_id=encounter_id) if encounter_id else redirect('hospital:psychiatric_consultation', patient_id=patient_id)
        except Exception as e:
            logger.error(f"Error saving psychiatric consultation: {str(e)}")
            messages.error(request, f'❌ Error saving consultation: {str(e)}')
    
    # Get previous charts for history
    previous_charts = PsychiatricChart.objects.filter(
        patient=patient,
        is_deleted=False
    ).exclude(pk=psychiatric_chart.pk if psychiatric_chart else None).order_by('-chart_date')[:5] if patient else []
    
    context = {
        'patient': patient,
        'encounter': encounter,
        'psychiatric_chart': psychiatric_chart,
        'previous_charts': previous_charts,
    }
    return render(request, 'hospital/specialists/psychiatric_consultation.html', context)


@login_required
def psychiatric_dashboard(request):
    """Comprehensive psychiatric specialist dashboard with charts and analytics"""
    # Get current staff
    try:
        current_staff = request.user.staff
    except AttributeError:
        messages.error(request, 'You must be registered as staff to access this page.')
        return redirect('hospital:dashboard')
    
    # Check if user is a psychiatric specialist
    try:
        specialist_profile = current_staff.specialist_profile
        specialty_name = specialist_profile.specialty.name.lower()
        if 'psychiatric' not in specialty_name and 'psychiatry' not in specialty_name and 'mental' not in specialty_name:
            messages.error(request, 'This dashboard is only for psychiatric specialists.')
            return redirect('hospital:dashboard')
    except AttributeError:
        messages.error(request, 'You are not registered as a specialist.')
        return redirect('hospital:dashboard')
    
    from datetime import timedelta
    from django.db.models import Count, Q, Avg, Max, Min
    from django.db.models.functions import TruncDate
    
    today = timezone.now().date()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    
    # ========== STATISTICS ==========
    # Today's consultations
    consultations_today = PsychiatricChart.objects.filter(
        created_by=current_staff,
        chart_date=today,
        is_deleted=False
    ).count()
    
    # This week's consultations
    consultations_this_week = PsychiatricChart.objects.filter(
        created_by=current_staff,
        chart_date__gte=week_start,
        is_deleted=False
    ).count()
    
    # This month's consultations
    consultations_this_month = PsychiatricChart.objects.filter(
        created_by=current_staff,
        chart_date__gte=month_start,
        is_deleted=False
    ).count()
    
    # Pending referrals
    pending_referrals = Referral.objects.filter(
        specialist=specialist_profile,
        status='pending',
        is_deleted=False
    ).count()
    
    # Active referrals
    active_referrals = Referral.objects.filter(
        specialist=specialist_profile,
        status__in=['accepted', 'in_progress'],
        is_deleted=False
    ).count()
    
    # High risk patients
    high_risk_patients = PsychiatricChart.objects.filter(
        created_by=current_staff,
        is_deleted=False
    ).filter(
        Q(suicide_risk__in=['high', 'imminent']) |
        Q(homicide_risk='high') |
        Q(violence_risk='high')
    ).values('patient').distinct().count()
    
    # ========== CHART DATA ==========
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    
    # Consultations over time (last 30 days)
    consultations_by_date = list(PsychiatricChart.objects.filter(
        created_by=current_staff,
        chart_date__gte=today - timedelta(days=30),
        is_deleted=False
    ).values('chart_date').annotate(count=Count('id')).order_by('chart_date'))
    
    # PHQ-9 scores over time (patient__full_name is a @property; use Concat for DB query)
    phq9_scores = list(PsychiatricChart.objects.filter(
        created_by=current_staff,
        phq9_score__isnull=False,
        chart_date__gte=month_start,
        is_deleted=False
    ).annotate(
        patient_name=Concat('patient__first_name', Value(' '), 'patient__last_name')
    ).order_by('chart_date').values('chart_date', 'phq9_score', 'patient_name'))
    
    # GAD-7 scores over time (patient__full_name is a @property; use Concat for DB query)
    gad7_scores = list(PsychiatricChart.objects.filter(
        created_by=current_staff,
        gad7_score__isnull=False,
        chart_date__gte=month_start,
        is_deleted=False
    ).annotate(
        patient_name=Concat('patient__first_name', Value(' '), 'patient__last_name')
    ).order_by('chart_date').values('chart_date', 'gad7_score', 'patient_name'))
    
    # Risk assessment distribution
    suicide_risk_dist = list(PsychiatricChart.objects.filter(
        created_by=current_staff,
        suicide_risk__isnull=False,
        suicide_risk__gt='',
        chart_date__gte=month_start,
        is_deleted=False
    ).values('suicide_risk').annotate(count=Count('id')))
    
    # Diagnosis distribution
    diagnosis_dist = list(PsychiatricChart.objects.filter(
        created_by=current_staff,
        primary_diagnosis__isnull=False,
        primary_diagnosis__gt='',
        chart_date__gte=month_start,
        is_deleted=False
    ).values('primary_diagnosis').annotate(count=Count('id')).order_by('-count')[:10])
    
    # Medication compliance
    compliance_dist = list(PsychiatricChart.objects.filter(
        created_by=current_staff,
        medication_compliance__isnull=False,
        medication_compliance__gt='',
        chart_date__gte=month_start,
        is_deleted=False
    ).values('medication_compliance').annotate(count=Count('id')))
    
    # Treatment response distribution
    treatment_response_dist = list(PsychiatricChart.objects.filter(
        created_by=current_staff,
        response_to_treatment__isnull=False,
        response_to_treatment__gt='',
        chart_date__gte=month_start,
        is_deleted=False
    ).values('response_to_treatment').annotate(count=Count('id')))
    
    # High risk cases over time
    high_risk_by_date = list(PsychiatricChart.objects.filter(
        created_by=current_staff,
        chart_date__gte=today - timedelta(days=30),
        is_deleted=False
    ).filter(
        Q(suicide_risk__in=['high', 'imminent']) |
        Q(homicide_risk='high') |
        Q(violence_risk='high')
    ).values('chart_date').annotate(count=Count('id')).order_by('chart_date'))
    
    # Average scores
    avg_phq9 = PsychiatricChart.objects.filter(
        created_by=current_staff,
        phq9_score__isnull=False,
        chart_date__gte=month_start,
        is_deleted=False
    ).aggregate(avg=Avg('phq9_score'))['avg'] or 0
    
    avg_gad7 = PsychiatricChart.objects.filter(
        created_by=current_staff,
        gad7_score__isnull=False,
        chart_date__gte=month_start,
        is_deleted=False
    ).aggregate(avg=Avg('gad7_score'))['avg'] or 0
    
    # ========== RECENT DATA ==========
    recent_consultations = PsychiatricChart.objects.filter(
        created_by=current_staff,
        is_deleted=False
    ).select_related('patient', 'encounter').order_by('-chart_date')[:10]
    
    pending_referrals_list = Referral.objects.filter(
        specialist=specialist_profile,
        status='pending',
        is_deleted=False
    ).select_related('patient', 'encounter', 'referring_doctor__user', 'specialty').order_by(
        '-priority', '-referred_date'
    )[:10]
    
    high_risk_list = PsychiatricChart.objects.filter(
        created_by=current_staff,
        is_deleted=False
    ).filter(
        Q(suicide_risk__in=['high', 'imminent']) |
        Q(homicide_risk='high') |
        Q(violence_risk='high')
    ).select_related('patient', 'encounter').order_by('-chart_date')[:10]
    
    context = {
        'specialist_profile': specialist_profile,
        'today': today,
        'stats': {
            'consultations_today': consultations_today,
            'consultations_this_week': consultations_this_week,
            'consultations_this_month': consultations_this_month,
            'pending_referrals': pending_referrals,
            'active_referrals': active_referrals,
            'high_risk_patients': high_risk_patients,
            'avg_phq9': round(avg_phq9, 1) if avg_phq9 else 0,
            'avg_gad7': round(avg_gad7, 1) if avg_gad7 else 0,
        },
        'chart_data': {
            'consultations_by_date': json.dumps(consultations_by_date, cls=DjangoJSONEncoder),
            'phq9_scores': json.dumps(phq9_scores, cls=DjangoJSONEncoder),
            'gad7_scores': json.dumps(gad7_scores, cls=DjangoJSONEncoder),
            'suicide_risk_dist': json.dumps(suicide_risk_dist, cls=DjangoJSONEncoder),
            'diagnosis_dist': json.dumps(diagnosis_dist, cls=DjangoJSONEncoder),
            'compliance_dist': json.dumps(compliance_dist, cls=DjangoJSONEncoder),
            'treatment_response_dist': json.dumps(treatment_response_dist, cls=DjangoJSONEncoder),
            'high_risk_by_date': json.dumps(high_risk_by_date, cls=DjangoJSONEncoder),
        },
        'recent_consultations': recent_consultations,
        'pending_referrals_list': pending_referrals_list,
        'high_risk_list': high_risk_list,
    }
    return render(request, 'hospital/specialists/psychiatric_dashboard.html', context)


@login_required
def gynecology_consultation(request, patient_id=None, encounter_id=None):
    """Comprehensive gynecology consultation page"""
    patient = None
    encounter = None
    gynecology_chart = None
    
    if patient_id:
        patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
        gynecology_chart = GynecologyChart.objects.filter(
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
    
    if patient and not gynecology_chart:
        gynecology_chart = GynecologyChart.objects.create(
            patient=patient,
            encounter=encounter,
            created_by=current_staff
        )
    
    # Handle form submission
    if request.method == 'POST':
        try:
            if gynecology_chart:
                # Chief Complaint & History
                gynecology_chart.chief_complaint = request.POST.get('chief_complaint', '')
                gynecology_chart.presenting_problem = request.POST.get('presenting_problem', '')
                gynecology_chart.menstrual_history = request.POST.get('menstrual_history', '')
                gynecology_chart.obstetric_history = request.POST.get('obstetric_history', '')
                gynecology_chart.gynecological_history = request.POST.get('gynecological_history', '')
                gynecology_chart.contraceptive_history = request.POST.get('contraceptive_history', '')
                gynecology_chart.sexual_history = request.POST.get('sexual_history', '')
                
                # Current Pregnancy
                gynecology_chart.is_pregnant = request.POST.get('is_pregnant') == 'on'
                ga_weeks = request.POST.get('gestational_age_weeks', '')
                gynecology_chart.gestational_age_weeks = int(ga_weeks) if ga_weeks else None
                edd = request.POST.get('edd', '')
                if edd:
                    from datetime import datetime
                    try:
                        gynecology_chart.edd = datetime.strptime(edd, '%Y-%m-%d').date()
                    except:
                        pass
                gynecology_chart.pregnancy_complications = request.POST.get('pregnancy_complications', '')
                gynecology_chart.prenatal_care = request.POST.get('prenatal_care', '')
                
                # Physical Examination
                gynecology_chart.general_examination = request.POST.get('general_examination', '')
                gynecology_chart.abdominal_examination = request.POST.get('abdominal_examination', '')
                gynecology_chart.pelvic_examination = request.POST.get('pelvic_examination', '')
                gynecology_chart.breast_examination = request.POST.get('breast_examination', '')
                gynecology_chart.cervical_examination = request.POST.get('cervical_examination', '')
                
                # Vital Signs
                gynecology_chart.blood_pressure = request.POST.get('blood_pressure', '')
                pulse = request.POST.get('pulse', '')
                gynecology_chart.pulse = int(pulse) if pulse else None
                temp = request.POST.get('temperature', '')
                gynecology_chart.temperature = float(temp) if temp else None
                weight = request.POST.get('weight', '')
                gynecology_chart.weight = float(weight) if weight else None
                height = request.POST.get('height', '')
                gynecology_chart.height = float(height) if height else None
                bmi = request.POST.get('bmi', '')
                gynecology_chart.bmi = float(bmi) if bmi else None
                
                # Investigations
                gynecology_chart.pap_smear_result = request.POST.get('pap_smear_result', '')
                pap_date = request.POST.get('pap_smear_date', '')
                if pap_date:
                    from datetime import datetime
                    try:
                        gynecology_chart.pap_smear_date = datetime.strptime(pap_date, '%Y-%m-%d').date()
                    except:
                        pass
                gynecology_chart.hiv_status = request.POST.get('hiv_status', '')
                hiv_date = request.POST.get('hiv_test_date', '')
                if hiv_date:
                    from datetime import datetime
                    try:
                        gynecology_chart.hiv_test_date = datetime.strptime(hiv_date, '%Y-%m-%d').date()
                    except:
                        pass
                gynecology_chart.other_investigations = request.POST.get('other_investigations', '')
                
                # Diagnosis
                gynecology_chart.primary_diagnosis = request.POST.get('primary_diagnosis', '')
                gynecology_chart.secondary_diagnosis = request.POST.get('secondary_diagnosis', '')
                gynecology_chart.provisional_diagnosis = request.POST.get('provisional_diagnosis', '')
                gynecology_chart.differential_diagnosis = request.POST.get('differential_diagnosis', '')
                
                # Treatment Plan
                gynecology_chart.treatment_plan = request.POST.get('treatment_plan', '')
                gynecology_chart.medications_prescribed = request.POST.get('medications_prescribed', '')
                gynecology_chart.procedures_planned = request.POST.get('procedures_planned', '')
                gynecology_chart.lifestyle_advice = request.POST.get('lifestyle_advice', '')
                
                # Follow-up
                follow_up = request.POST.get('follow_up_date', '')
                if follow_up:
                    from datetime import datetime
                    try:
                        gynecology_chart.follow_up_date = datetime.strptime(follow_up, '%Y-%m-%d').date()
                    except:
                        pass
                gynecology_chart.follow_up_instructions = request.POST.get('follow_up_instructions', '')
                gynecology_chart.progress_notes = request.POST.get('progress_notes', '')
                gynecology_chart.notes = request.POST.get('notes', '')
                gynecology_chart.recommendations = request.POST.get('recommendations', '')
                
                gynecology_chart.save()
                
                messages.success(request, '✅ Gynecology consultation saved successfully!')
                
                # Create or update specialist consultation record
                try:
                    specialist_profile = current_staff.specialist_profile
                    consultation, created = SpecialistConsultation.objects.get_or_create(
                        patient=patient,
                        encounter=encounter,
                        specialist=specialist_profile,
                        consultation_date__date=timezone.now().date(),
                        defaults={
                            'chief_complaint': gynecology_chart.chief_complaint,
                            'assessment': gynecology_chart.primary_diagnosis,
                            'plan': gynecology_chart.treatment_plan,
                            'notes': gynecology_chart.notes,
                        }
                    )
                    if not created:
                        consultation.chief_complaint = gynecology_chart.chief_complaint
                        consultation.assessment = gynecology_chart.primary_diagnosis
                        consultation.plan = gynecology_chart.treatment_plan
                        consultation.notes = gynecology_chart.notes
                        consultation.save()
                except:
                    pass
                
                return redirect('hospital:gynecology_consultation_encounter', encounter_id=encounter_id) if encounter_id else redirect('hospital:gynecology_consultation', patient_id=patient_id)
        except Exception as e:
            logger.error(f"Error saving gynecology consultation: {str(e)}")
            messages.error(request, f'❌ Error saving consultation: {str(e)}')
    
    # Get previous charts for history
    previous_charts = GynecologyChart.objects.filter(
        patient=patient,
        is_deleted=False
    ).exclude(pk=gynecology_chart.pk if gynecology_chart else None).order_by('-chart_date')[:5] if patient else []
    
    context = {
        'patient': patient,
        'encounter': encounter,
        'gynecology_chart': gynecology_chart,
        'previous_charts': previous_charts,
    }
    return render(request, 'hospital/specialists/gynecology_consultation.html', context)


@login_required
def gynecology_dashboard(request):
    """Comprehensive gynecology specialist dashboard with charts and analytics"""
    # Get current staff
    try:
        current_staff = request.user.staff
    except AttributeError:
        messages.error(request, 'You must be registered as staff to access this page.')
        return redirect('hospital:dashboard')
    
    # Check if user is a gynecology specialist
    try:
        specialist_profile = current_staff.specialist_profile
        specialty_name = specialist_profile.specialty.name.lower()
        if 'gynecology' not in specialty_name and 'gynec' not in specialty_name and 'obstetric' not in specialty_name and 'obgyn' not in specialty_name:
            messages.error(request, 'This dashboard is only for gynecology specialists.')
            return redirect('hospital:dashboard')
    except AttributeError:
        messages.error(request, 'You are not registered as a specialist.')
        return redirect('hospital:dashboard')
    
    from datetime import timedelta
    from django.db.models import Count, Q, Avg, Max, Min
    from django.db.models.functions import TruncDate
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    
    today = timezone.now().date()
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today - timedelta(days=7)
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    
    # ========== STATISTICS ==========
    # Today's consultations
    consultations_today = GynecologyChart.objects.filter(
        created_by=current_staff,
        chart_date=today,
        is_deleted=False
    ).count()
    
    # This week's consultations
    consultations_this_week = GynecologyChart.objects.filter(
        created_by=current_staff,
        chart_date__gte=week_start,
        is_deleted=False
    ).count()
    
    # This month's consultations
    consultations_this_month = GynecologyChart.objects.filter(
        created_by=current_staff,
        chart_date__gte=month_start,
        is_deleted=False
    ).count()
    
    # Pregnant patients
    pregnant_patients = GynecologyChart.objects.filter(
        created_by=current_staff,
        is_pregnant=True,
        is_deleted=False
    ).values('patient').distinct().count()
    
    # Pending referrals
    pending_referrals = Referral.objects.filter(
        specialist=specialist_profile,
        status='pending',
        is_deleted=False
    ).count()
    
    # Active referrals
    active_referrals = Referral.objects.filter(
        specialist=specialist_profile,
        status__in=['accepted', 'in_progress'],
        is_deleted=False
    ).count()
    
    # Average BMI
    avg_bmi = GynecologyChart.objects.filter(
        created_by=current_staff,
        bmi__isnull=False,
        chart_date__gte=month_start,
        is_deleted=False
    ).aggregate(avg=Avg('bmi'))['avg'] or 0
    
    # ========== CHART DATA ==========
    # Consultations over time (last 30 days)
    consultations_by_date = list(GynecologyChart.objects.filter(
        created_by=current_staff,
        chart_date__gte=today - timedelta(days=30),
        is_deleted=False
    ).values('chart_date').annotate(count=Count('id')).order_by('chart_date'))
    
    # BMI distribution (patient__full_name is a @property; use Concat for DB query)
    bmi_data = list(GynecologyChart.objects.filter(
        created_by=current_staff,
        bmi__isnull=False,
        chart_date__gte=month_start,
        is_deleted=False
    ).annotate(
        patient_name=Concat('patient__first_name', Value(' '), 'patient__last_name')
    ).order_by('chart_date').values('chart_date', 'bmi', 'patient_name'))
    
    # Pregnancy status distribution
    pregnancy_dist = list(GynecologyChart.objects.filter(
        created_by=current_staff,
        chart_date__gte=month_start,
        is_deleted=False
    ).values('is_pregnant').annotate(count=Count('id')))
    
    # Gestational age distribution (for pregnant patients)
    gestational_age_data = list(GynecologyChart.objects.filter(
        created_by=current_staff,
        is_pregnant=True,
        gestational_age_weeks__isnull=False,
        chart_date__gte=month_start,
        is_deleted=False
    ).order_by('gestational_age_weeks').values('gestational_age_weeks').annotate(count=Count('id')))
    
    # Diagnosis distribution
    diagnosis_dist = list(GynecologyChart.objects.filter(
        created_by=current_staff,
        primary_diagnosis__isnull=False,
        primary_diagnosis__gt='',
        chart_date__gte=month_start,
        is_deleted=False
    ).values('primary_diagnosis').annotate(count=Count('id')).order_by('-count')[:10])
    
    # HIV status distribution
    hiv_dist = list(GynecologyChart.objects.filter(
        created_by=current_staff,
        hiv_status__isnull=False,
        hiv_status__gt='',
        chart_date__gte=month_start,
        is_deleted=False
    ).values('hiv_status').annotate(count=Count('id')))
    
    # Pap smear results
    pap_smear_dist = list(GynecologyChart.objects.filter(
        created_by=current_staff,
        pap_smear_result__isnull=False,
        pap_smear_result__gt='',
        chart_date__gte=month_start,
        is_deleted=False
    ).values('pap_smear_result').annotate(count=Count('id')))
    
    # ========== RECENT DATA ==========
    recent_consultations = GynecologyChart.objects.filter(
        created_by=current_staff,
        is_deleted=False
    ).select_related('patient', 'encounter').order_by('-chart_date')[:10]
    
    pending_referrals_list = Referral.objects.filter(
        specialist=specialist_profile,
        status='pending',
        is_deleted=False
    ).select_related('patient', 'encounter', 'referring_doctor__user', 'specialty').order_by(
        '-priority', '-referred_date'
    )[:10]
    
    pregnant_patients_list = GynecologyChart.objects.filter(
        created_by=current_staff,
        is_pregnant=True,
        is_deleted=False
    ).select_related('patient', 'encounter').order_by('-chart_date')[:10]
    
    context = {
        'specialist_profile': specialist_profile,
        'today': today,
        'stats': {
            'consultations_today': consultations_today,
            'consultations_this_week': consultations_this_week,
            'consultations_this_month': consultations_this_month,
            'pregnant_patients': pregnant_patients,
            'pending_referrals': pending_referrals,
            'active_referrals': active_referrals,
            'avg_bmi': round(avg_bmi, 1) if avg_bmi else 0,
        },
        'chart_data': {
            'consultations_by_date': json.dumps(consultations_by_date, cls=DjangoJSONEncoder),
            'bmi_data': json.dumps(bmi_data, cls=DjangoJSONEncoder),
            'pregnancy_dist': json.dumps(pregnancy_dist, cls=DjangoJSONEncoder),
            'gestational_age_data': json.dumps(gestational_age_data, cls=DjangoJSONEncoder),
            'diagnosis_dist': json.dumps(diagnosis_dist, cls=DjangoJSONEncoder),
            'hiv_dist': json.dumps(hiv_dist, cls=DjangoJSONEncoder),
            'pap_smear_dist': json.dumps(pap_smear_dist, cls=DjangoJSONEncoder),
        },
        'recent_consultations': recent_consultations,
        'pending_referrals_list': pending_referrals_list,
        'pregnant_patients_list': pregnant_patients_list,
    }
    return render(request, 'hospital/specialists/gynecology_dashboard.html', context)


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


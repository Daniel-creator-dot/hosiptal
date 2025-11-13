"""
World-Class Admission and Bed Management Views
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, F
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
import logging

from .models import Patient, Encounter, Bed, Ward, Admission, Staff, Department
from .forms import AdmissionForm

logger = logging.getLogger(__name__)


@login_required
def bed_management_worldclass(request):
    """World-class bed management dashboard"""
    # Get filters
    ward_filter = request.GET.get('ward', '')
    status_filter = request.GET.get('status', '')
    
    # Get all wards
    all_wards = Ward.objects.filter(
        is_active=True,
        is_deleted=False
    ).select_related('department')
    
    # Get beds
    beds = Bed.objects.filter(
        is_active=True,
        is_deleted=False
    ).select_related('ward', 'ward__department')
    
    # Apply filters
    if ward_filter:
        beds = beds.filter(ward_id=ward_filter)
    
    if status_filter:
        beds = beds.filter(status=status_filter)
    
    # Get current admissions for occupied beds
    current_admissions = Admission.objects.filter(
        status='admitted',
        is_deleted=False
    ).select_related('encounter__patient', 'bed', 'ward')
    
    # Create a map of bed_id to admission
    admission_map = {adm.bed_id: adm for adm in current_admissions if adm.bed_id}
    
    # Convert queryset to list to work with
    beds_list = list(beds)
    
    # Enhance beds with patient info
    for bed in beds_list:
        if bed.status == 'occupied' and bed.pk in admission_map:
            admission = admission_map[bed.pk]
            bed.current_patient = admission.encounter.patient if admission.encounter else None
            bed.admission_days = admission.get_duration_days()
        else:
            bed.current_patient = None
            bed.admission_days = 0
    
    # Calculate ward statistics separately (since regroup doesn't preserve dynamic attributes)
    ward_stats = {}
    for ward in all_wards:
        ward_beds = [b for b in beds_list if b.ward_id == ward.pk]
        occupied = sum(1 for b in ward_beds if b.status == 'occupied')
        available = sum(1 for b in ward_beds if b.status == 'available')
        occupancy = round((occupied / ward.capacity * 100) if ward.capacity > 0 else 0, 1)
        
        ward_stats[str(ward.pk)] = {
            'occupied_count': occupied,
            'available_count': available,
            'occupancy_percentage': occupancy,
        }
    
    # Overall statistics
    total_beds = len(beds_list)
    available_beds = sum(1 for b in beds_list if b.status == 'available')
    occupied_beds = sum(1 for b in beds_list if b.status == 'occupied')
    maintenance_beds = sum(1 for b in beds_list if b.status == 'maintenance')
    reserved_beds = sum(1 for b in beds_list if b.status == 'reserved')
    occupancy_rate = round((occupied_beds / total_beds * 100) if total_beds > 0 else 0, 1)
    
    context = {
        'beds': beds_list,
        'all_wards': all_wards,
        'ward_stats': ward_stats,
        'total_beds': total_beds,
        'available_beds': available_beds,
        'occupied_beds': occupied_beds,
        'maintenance_beds': maintenance_beds,
        'reserved_beds': reserved_beds,
        'occupancy_rate': occupancy_rate,
        'ward_filter': ward_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'hospital/bed_management_worldclass.html', context)


@login_required
def admission_create_enhanced(request):
    """Enhanced admission form with bed selection"""
    # Get available beds
    available_beds = Bed.objects.filter(
        status='available',
        is_active=True,
        is_deleted=False
    ).select_related('ward', 'ward__department').order_by('ward__name', 'bed_number')
    
    # Get active encounters without admission
    encounters_without_admission = Encounter.objects.filter(
        status='active',
        is_deleted=False,
        admission__isnull=True
    ).select_related('patient', 'provider').order_by('-started_at')[:50]
    
    # Pre-select bed if provided (from bed management)
    bed_id = request.GET.get('bed')
    selected_bed = None
    if bed_id:
        try:
            selected_bed = Bed.objects.get(pk=bed_id, is_deleted=False)
        except Bed.DoesNotExist:
            pass
    
    # Pre-select encounter if provided (from consultation)
    encounter_id = request.GET.get('encounter')
    selected_encounter = None
    if encounter_id:
        try:
            selected_encounter = Encounter.objects.get(pk=encounter_id, is_deleted=False)
        except Encounter.DoesNotExist:
            pass
    
    if request.method == 'POST':
        encounter_id = request.POST.get('encounter_id')
        bed_id = request.POST.get('bed_id')
        diagnosis = request.POST.get('diagnosis_icd10', '')
        notes = request.POST.get('notes', '')
        
        try:
            encounter = Encounter.objects.get(pk=encounter_id, is_deleted=False)
            bed = Bed.objects.get(pk=bed_id, is_deleted=False)
            
            # Get current staff
            try:
                staff = Staff.objects.get(user=request.user, is_deleted=False)
            except Staff.DoesNotExist:
                staff = None
            
            # Create admission
            admission = Admission.objects.create(
                encounter=encounter,
                ward=bed.ward,
                bed=bed,
                admitting_doctor=staff or encounter.provider,
                diagnosis_icd10=diagnosis,
                notes=notes,
                status='admitted'
            )
            
            # Update bed status
            bed.occupy()
            
            # Update encounter status
            encounter.encounter_type = 'inpatient'
            encounter.save()
            
            # Create flow stage
            from .models_workflow import PatientFlowStage
            PatientFlowStage.objects.create(
                encounter=encounter,
                stage_type='admission',
                status='completed',
                started_at=timezone.now(),
                completed_at=timezone.now(),
                completed_by=staff
            )
            
            # 💰 AUTO-BILLING: Create bed charges (GHS 120 per day)
            try:
                from .services.bed_billing_service import bed_billing_service
                billing_result = bed_billing_service.create_admission_bill(admission, days=1)
                
                if billing_result.get('success'):
                    logger.info(
                        f"✅ Bed billing created for {encounter.patient.full_name}: "
                        f"GHS {billing_result['total_charge']}"
                    )
                    messages.success(
                        request,
                        f'✅ Patient {encounter.patient.full_name} admitted to {bed.ward.name} - Bed {bed.bed_number}. '
                        f'💰 Bed charges: GHS {billing_result["total_charge"]} ({billing_result["days"]} day @ GHS {billing_result["daily_rate"]}/day)'
                    )
                else:
                    logger.warning(f"Bed billing failed: {billing_result.get('error')}")
                    messages.success(
                        request,
                        f'✅ Patient {encounter.patient.full_name} admitted to {bed.ward.name} - Bed {bed.bed_number}. '
                        f'⚠️ Bed billing pending - please add charges manually.'
                    )
            except Exception as e:
                logger.error(f"Error creating bed billing: {str(e)}", exc_info=True)
                messages.success(
                    request,
                    f'✅ Patient {encounter.patient.full_name} admitted to {bed.ward.name} - Bed {bed.bed_number}. '
                    f'⚠️ Auto-billing error - please add charges manually.'
                )
            
            return redirect('hospital:admission_detail', pk=admission.pk)
            
        except Encounter.DoesNotExist:
            messages.error(request, 'Encounter not found')
        except Bed.DoesNotExist:
            messages.error(request, 'Bed not found')
        except Exception as e:
            messages.error(request, f'Error creating admission: {str(e)}')
    
    # Get diagnosis codes for dropdown
    try:
        from .models_diagnosis import DiagnosisCode
        diagnosis_codes = DiagnosisCode.objects.filter(
            is_active=True,
            is_deleted=False,
            is_common=True
        ).order_by('short_description')[:100]
    except ImportError:
        diagnosis_codes = []
    
    context = {
        'available_beds': available_beds,
        'encounters': encounters_without_admission,
        'selected_bed': selected_bed,
        'selected_encounter': selected_encounter,
        'diagnosis_codes': diagnosis_codes,
    }
    
    return render(request, 'hospital/admission_create_enhanced.html', context)


@login_required
def admission_detail(request, pk):
    """Admission detail view with bed charges"""
    admission = get_object_or_404(Admission, pk=pk, is_deleted=False)
    
    # Get current bed charges
    bed_charges = None
    try:
        from .services.bed_billing_service import bed_billing_service
        bed_charges = bed_billing_service.get_bed_charges_summary(admission)
    except Exception as e:
        logger.error(f"Error getting bed charges: {str(e)}")
    
    context = {
        'admission': admission,
        'bed_charges': bed_charges,
    }
    
    return render(request, 'hospital/admission_detail_enhanced.html', context)


@login_required
def discharge_patient(request, admission_id):
    """Discharge patient and free bed"""
    admission = get_object_or_404(Admission, pk=admission_id, is_deleted=False)
    
    if request.method == 'POST':
        discharge_notes = request.POST.get('discharge_notes', '')
        
        # 💰 AUTO-BILLING: Update bed charges based on actual stay duration
        try:
            from .services.bed_billing_service import bed_billing_service
            billing_result = bed_billing_service.update_bed_charges_on_discharge(admission)
            
            if billing_result.get('success'):
                charge_info = billing_result['charge_breakdown']
                logger.info(
                    f"✅ Final bed charges calculated: {admission.encounter.patient.full_name} - "
                    f"{charge_info['days']} days @ GHS {charge_info['daily_rate']} = GHS {charge_info['total_charge']}"
                )
        except Exception as e:
            logger.error(f"Error updating bed charges on discharge: {str(e)}", exc_info=True)
        
        # Discharge
        admission.discharge()
        admission.notes = f"{admission.notes}\n\nDischarge Notes: {discharge_notes}" if discharge_notes else admission.notes
        admission.save()
        
        # Create discharge flow stage
        try:
            staff = Staff.objects.get(user=request.user, is_deleted=False)
        except Staff.DoesNotExist:
            staff = None
        
        from .models_workflow import PatientFlowStage
        PatientFlowStage.objects.create(
            encounter=admission.encounter,
            stage_type='discharge',
            status='completed',
            started_at=timezone.now(),
            completed_at=timezone.now(),
            completed_by=staff
        )
        
        # Show discharge message with final charges
        try:
            from .services.bed_billing_service import bed_billing_service
            charge_summary = bed_billing_service.get_bed_charges_summary(admission)
            messages.success(
                request,
                f'✅ Patient discharged successfully. Bed {admission.bed.bed_number} is now available. '
                f'💰 Total bed charges: GHS {charge_summary["current_charges"]} '
                f'({charge_summary["days_admitted"]} days @ GHS {charge_summary["daily_rate"]}/day)'
            )
        except:
            messages.success(request, f'✅ Patient discharged successfully. Bed {admission.bed.bed_number} is now available.')
        
        return redirect('hospital:bed_management_worldclass')
    
    context = {
        'admission': admission,
    }
    
    return render(request, 'hospital/discharge_form.html', context)


@login_required
def bed_details_api(request, bed_id):
    """API endpoint for bed details"""
    try:
        bed = Bed.objects.get(pk=bed_id, is_deleted=False)
        
        data = {
            'bed_number': bed.bed_number,
            'ward': bed.ward.name,
            'status': bed.status,
            'bed_type': bed.get_bed_type_display(),
        }
        
        # Get current admission if occupied
        if bed.status == 'occupied':
            try:
                admission = Admission.objects.get(
                    bed=bed,
                    status='admitted',
                    is_deleted=False
                )
                data['patient'] = {
                    'name': admission.encounter.patient.full_name,
                    'mrn': admission.encounter.patient.mrn,
                }
                data['admission_id'] = str(admission.pk)
                data['encounter_id'] = str(admission.encounter.pk)  # For admission review
                data['admission_date'] = admission.admit_date.strftime('%d %b %Y')
                data['admission_days'] = admission.get_duration_days()
                
                # Add bed charges info
                try:
                    from .services.bed_billing_service import bed_billing_service
                    charges = bed_billing_service.get_bed_charges_summary(admission)
                    data['bed_charges'] = {
                        'daily_rate': float(charges['daily_rate']),
                        'days': charges['days_admitted'],
                        'total': float(charges['current_charges'])
                    }
                except Exception as e:
                    logger.error(f"Error getting bed charges: {str(e)}")
            except Admission.DoesNotExist:
                pass
        
        return JsonResponse(data)
    except Bed.DoesNotExist:
        return JsonResponse({'error': 'Bed not found'}, status=404)


@login_required
def admission_list_enhanced(request):
    """Enhanced admission list with filters and search"""
    status_filter = request.GET.get('status', '')
    ward_filter = request.GET.get('ward', '')
    search_query = request.GET.get('q', '')
    
    admissions = Admission.objects.filter(
        is_deleted=False
    ).select_related(
        'encounter__patient',
        'bed',
        'ward',
        'admitting_doctor__user'
    )
    
    # Apply filters
    if status_filter:
        admissions = admissions.filter(status=status_filter)
    else:
        # Default to active admissions
        admissions = admissions.filter(status='admitted')
    
    if ward_filter:
        admissions = admissions.filter(ward_id=ward_filter)
    
    if search_query:
        admissions = admissions.filter(
            Q(encounter__patient__first_name__icontains=search_query) |
            Q(encounter__patient__last_name__icontains=search_query) |
            Q(encounter__patient__mrn__icontains=search_query) |
            Q(bed__bed_number__icontains=search_query)
        )
    
    # Calculate statistics
    total_admissions = admissions.count()
    active_admissions = admissions.filter(status='admitted').count()
    discharged_today = Admission.objects.filter(
        is_deleted=False,
        discharge_date__date=timezone.now().date()
    ).count()
    
    # Get wards with bed availability
    wards = Ward.objects.filter(is_active=True, is_deleted=False)
    
    # Calculate total bed statistics
    total_beds = Bed.objects.filter(is_deleted=False, is_active=True).count()
    available_beds = Bed.objects.filter(is_deleted=False, is_active=True, status='available').count()
    occupied_beds = Bed.objects.filter(is_deleted=False, is_active=True, status='occupied').count()
    occupancy_rate = round((occupied_beds / total_beds * 100) if total_beds > 0 else 0, 1)
    
    # Add bed charges to each admission
    admissions_list = list(admissions.order_by('-admit_date')[:100])
    try:
        from .services.bed_billing_service import bed_billing_service
        for admission in admissions_list:
            try:
                admission.bed_charges_summary = bed_billing_service.get_bed_charges_summary(admission)
            except Exception as e:
                logger.error(f"Error getting bed charges for admission {admission.pk}: {str(e)}")
                admission.bed_charges_summary = None
    except Exception as e:
        logger.error(f"Error loading bed billing service: {str(e)}")
    
    context = {
        'admissions': admissions_list,
        'total_admissions': total_admissions,
        'active_admissions': active_admissions,
        'discharged_today': discharged_today,
        'total_beds': total_beds,
        'available_beds': available_beds,
        'occupied_beds': occupied_beds,
        'occupancy_rate': occupancy_rate,
        'wards': wards,
        'status_filter': status_filter,
        'ward_filter': ward_filter,
        'search_query': search_query,
    }
    
    return render(request, 'hospital/admission_list_enhanced.html', context)


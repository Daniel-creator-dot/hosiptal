"""
World-Class Admission and Bed Management Views
"""
from collections import defaultdict
from datetime import timedelta
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, F
from django.utils import timezone
from django.http import JsonResponse
from django.db import IntegrityError
from django.db.utils import DataError

from .models import Patient, Encounter, Bed, Ward, Admission, Staff, Department
from .forms import AdmissionForm


def ensure_beds_for_ward(ward, desired_count, prefix):
    """Ensure a ward has at least the desired number of beds."""
    existing_beds = Bed.objects.filter(ward=ward, is_deleted=False)
    current_count = existing_beds.count()
    if current_count >= desired_count:
        return
    
    existing_numbers = set(existing_beds.values_list('bed_number', flat=True))
    next_index = 1
    while current_count < desired_count:
        bed_number = f"{prefix}-{next_index:02d}"
        next_index += 1
        if bed_number in existing_numbers:
            continue
        
        Bed.objects.create(
            ward=ward,
            bed_number=bed_number,
            bed_type='general',
            status='available',
            is_active=True
        )
        existing_numbers.add(bed_number)
        current_count += 1


def ensure_default_bed_structure():
    """
    Ensure core wards (Emergency, Female, Male, Children, VIP) exist so the bed dashboard always shows them
    and seed a baseline number of beds per ward.
    Also guarantees there is at least one active department to attach these wards to.
    """
    # Ensure we have a fallback department
    default_department, _ = Department.objects.get_or_create(
        name='General Medicine',
        defaults={
            'code': 'GEN',
            'description': 'Auto-generated department for bed management setup.',
            'is_active': True,
        }
    )
    if not default_department.is_active:
        default_department.is_active = True
        default_department.save(update_fields=['is_active'])
    
    default_wards = [
        {'name': 'Emergency Ward', 'code': 'ER', 'ward_type': 'emergency', 'capacity': 12, 'bed_prefix': 'ER', 'bed_count': 12},
        {'name': 'Female Ward', 'code': 'FEM', 'ward_type': 'female', 'capacity': 16, 'bed_prefix': 'FEM', 'bed_count': 12},
        {'name': 'Male Ward', 'code': 'MAL', 'ward_type': 'male', 'capacity': 16, 'bed_prefix': 'MAL', 'bed_count': 8},
        {'name': "Children's Ward", 'code': 'PED', 'ward_type': 'paediatric', 'capacity': 14, 'bed_prefix': 'PED', 'bed_count': 10},
        {'name': 'VIP Ward', 'code': 'VIP', 'ward_type': 'general', 'capacity': 20, 'bed_prefix': 'VIP', 'bed_count': 20},
    ]
    
    for spec in default_wards:
        ward = Ward.objects.filter(
            ward_type=spec['ward_type'],
            is_deleted=False
        ).first()
        
        if not ward:
            code = spec['code']
            suffix = 2
            while Ward.objects.filter(code=code).exists():
                code = f"{spec['code']}{suffix}"
                suffix += 1
            
            ward = Ward.objects.create(
                name=spec['name'],
                code=code,
                ward_type=spec['ward_type'],
                department=default_department,
                capacity=spec['capacity'],
                is_active=True
            )
        ensure_beds_for_ward(ward, spec['bed_count'], spec['bed_prefix'])

logger = logging.getLogger(__name__)


@login_required
def bed_management_worldclass(request):
    """World-class bed management dashboard"""
    ensure_default_bed_structure()
    
    # Get filters
    ward_filter = request.GET.get('ward', '')
    status_filter = request.GET.get('status', '')
    
    # Get all wards
    ward_queryset = Ward.objects.filter(
        is_active=True,
        is_deleted=False
    ).select_related('department')
    
    ward_type_order = [
        'emergency', 'female', 'male', 'paediatric',
        'maternity', 'icu', 'hdu', 'surgery', 'other'
    ]
    
    all_wards = list(ward_queryset)
    all_wards.sort(
        key=lambda w: (
            ward_type_order.index(w.ward_type) if w.ward_type in ward_type_order else len(ward_type_order),
            w.name.lower()
        )
    )
    
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
    beds_by_ward = defaultdict(list)
    for bed in beds_list:
        beds_by_ward[bed.ward_id].append(bed)
    
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
        ward_beds = beds_by_ward.get(ward.pk, [])
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
    
    # Build ward sections so even wards without beds display
    ward_sections = []
    for ward in all_wards:
        if ward_filter and str(ward.pk) != ward_filter:
            continue
        
        section_stats = ward_stats.get(str(ward.pk), {
            'occupied_count': 0,
            'available_count': 0,
            'occupancy_percentage': 0,
        })
        
        ward_sections.append({
            'ward': ward,
            'beds': beds_by_ward.get(ward.pk, []),
            'stats': section_stats,
        })
    
    if not ward_sections and ward_filter:
        # ward filter applied but ward has no beds; still show placeholder
        for ward in all_wards:
            if str(ward.pk) == ward_filter:
                ward_sections.append({
                    'ward': ward,
                    'beds': [],
                    'stats': ward_stats.get(str(ward.pk), {
                        'occupied_count': 0,
                        'available_count': 0,
                        'occupancy_percentage': 0,
                    }),
                })
                break
    
    context = {
        'beds': beds_list,
        'all_wards': all_wards,
        'ward_stats': ward_stats,
        'ward_sections': ward_sections,
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
    
    # Get encounters without admission (active OR completed - all patients can be admitted)
    # Get distinct encounters - prefer most recent per patient per day
    # Handle exact timestamp matches by using ID as tie-breaker
    from django.db import connection
    
    # Get most recent encounter ID per patient per day using DISTINCT ON (UUID-compatible)
    # Include both 'active' and 'completed' so all patients with encounters can be admitted
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT ON (e.patient_id, e.started_at::date) e.id
            FROM hospital_encounter e
            LEFT JOIN hospital_admission a ON a.encounter_id = e.id AND a.is_deleted = false
            WHERE e.is_deleted = false 
              AND e.status IN ('active', 'completed')
              AND a.id IS NULL
            ORDER BY e.patient_id, e.started_at::date, e.id DESC
            LIMIT 200
        """)
        latest_ids = [row[0] for row in cursor.fetchall()]
    
    encounters_without_admission = Encounter.objects.filter(
        id__in=latest_ids
    ).select_related('patient', 'provider').order_by('-started_at', '-id')
    
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
            # If this encounter is already admitted (active), redirect to existing admission
            existing = Admission.objects.filter(encounter_id=selected_encounter.pk).first()
            if existing and not existing.is_deleted:
                messages.info(
                    request,
                    f'This encounter is already admitted. Redirecting to admission details.'
                )
                return redirect('hospital:admission_detail', pk=existing.pk)
        except Encounter.DoesNotExist:
            pass
    
    if request.method == 'POST':
        encounter_id = request.POST.get('encounter_id')
        patient_id = request.POST.get('patient_id')  # Alternative: admit any patient (creates encounter if needed)
        bed_id = request.POST.get('bed_id')
        diagnosis = (request.POST.get('diagnosis_icd10') or '').strip()[:255]
        notes = request.POST.get('notes', '')
        
        try:
            # Resolve encounter: from encounter_id, or from patient_id (find or create)
            if encounter_id:
                encounter = Encounter.objects.get(pk=encounter_id, is_deleted=False)
            elif patient_id:
                patient = Patient.objects.get(pk=patient_id, is_deleted=False)
                # Find patient's most recent encounter without admission (active or completed)
                encounter = Encounter.objects.filter(
                    patient=patient, is_deleted=False,
                    status__in=('active', 'completed')
                ).exclude(
                    id__in=Admission.objects.filter(is_deleted=False).values_list('encounter_id', flat=True)
                ).order_by('-started_at', '-id').first()
                if not encounter:
                    # Create new encounter for direct admission
                    try:
                        staff = Staff.objects.get(user=request.user, is_deleted=False)
                    except Staff.DoesNotExist:
                        staff = None
                    encounter = Encounter.objects.create(
                        patient=patient,
                        encounter_type='outpatient',  # Will be set to inpatient below
                        chief_complaint='Direct admission',
                        status='active',
                        provider=staff,
                    )
            else:
                messages.error(request, 'Please select a patient.')
                return redirect('hospital:admission_create')
            
            bed = Bed.objects.get(pk=bed_id, is_deleted=False)
            
            # Get current staff (needed for both create and restore paths)
            try:
                staff = Staff.objects.get(user=request.user, is_deleted=False)
            except Staff.DoesNotExist:
                staff = None
            
            # Avoid duplicate: one admission per encounter (DB unique on encounter_id)
            # Use encounter_id (pk) so we always see the row regardless of manager/soft-delete
            existing_admission = Admission.objects.filter(encounter_id=encounter.pk).first()
            if existing_admission:
                if not existing_admission.is_deleted:
                    messages.info(
                        request,
                        'This encounter is already admitted. Redirecting to admission details.'
                    )
                    return redirect('hospital:admission_detail', pk=existing_admission.pk)
                # Restore soft-deleted admission and assign new bed (avoids unique constraint violation)
                existing_admission.is_deleted = False
                existing_admission.ward = bed.ward
                existing_admission.bed = bed
                existing_admission.admitting_doctor = staff or encounter.provider
                existing_admission.diagnosis_icd10 = diagnosis
                existing_admission.notes = notes
                existing_admission.status = 'admitted'
                existing_admission.save()
                admission = existing_admission
                bed.occupy()
                encounter.encounter_type = 'inpatient'
                encounter.save()
                from .models_workflow import PatientFlowStage
                if not PatientFlowStage.objects.filter(
                    encounter=encounter, stage_type='admission', is_deleted=False
                ).exists():
                    PatientFlowStage.objects.create(
                        encounter=encounter,
                        stage_type='admission',
                        status='completed',
                        started_at=timezone.now(),
                        completed_at=timezone.now(),
                        completed_by=staff,
                    )
                try:
                    from .services.bed_billing_service import bed_billing_service
                    billing_result = bed_billing_service.create_admission_bill(admission, days=1)
                    if billing_result.get('success'):
                        messages.success(
                            request,
                            f'✅ Patient {encounter.patient.full_name} admitted to {bed.ward.name} - Bed {bed.bed_number}. '
                            f'💰 Provisional charge: GHS {billing_result["total_charge"]}'
                        )
                    else:
                        messages.success(request, f'✅ Patient {encounter.patient.full_name} admitted to {bed.ward.name} - Bed {bed.bed_number}.')
                except Exception:
                    messages.success(request, f'✅ Patient {encounter.patient.full_name} admitted to {bed.ward.name} - Bed {bed.bed_number}.')
                return redirect('hospital:admission_detail', pk=admission.pk)
            
            # Create admission
            try:
                admission = Admission.objects.create(
                    encounter=encounter,
                    ward=bed.ward,
                    bed=bed,
                    admitting_doctor=staff or encounter.provider,
                    diagnosis_icd10=diagnosis,
                    notes=notes,
                    status='admitted'
                )
            except IntegrityError as e:
                if 'hospital_admission_encounter_id_key' in str(e) or 'encounter_id' in str(e):
                    existing_admission = Admission.objects.filter(encounter_id=encounter.pk).first()
                    if existing_admission:
                        if not existing_admission.is_deleted:
                            messages.info(
                                request,
                                'This encounter is already admitted. Redirecting to admission details.'
                            )
                            return redirect('hospital:admission_detail', pk=existing_admission.pk)
                        existing_admission.is_deleted = False
                        existing_admission.ward = bed.ward
                        existing_admission.bed = bed
                        existing_admission.admitting_doctor = staff or encounter.provider
                        existing_admission.diagnosis_icd10 = diagnosis
                        existing_admission.notes = notes
                        existing_admission.status = 'admitted'
                        existing_admission.save()
                        admission = existing_admission
                        bed.occupy()
                        encounter.encounter_type = 'inpatient'
                        encounter.save()
                        from .models_workflow import PatientFlowStage
                        if not PatientFlowStage.objects.filter(
                            encounter=encounter, stage_type='admission', is_deleted=False
                        ).exists():
                            PatientFlowStage.objects.create(
                                encounter=encounter,
                                stage_type='admission',
                                status='completed',
                                started_at=timezone.now(),
                                completed_at=timezone.now(),
                                completed_by=staff,
                            )
                        try:
                            from .services.bed_billing_service import bed_billing_service
                            bed_billing_service.create_admission_bill(admission, days=1)
                        except Exception:
                            pass
                        messages.success(
                            request,
                            f'✅ Patient {encounter.patient.full_name} admitted to {bed.ward.name} - Bed {bed.bed_number}.'
                        )
                        return redirect('hospital:admission_detail', pk=admission.pk)
                raise
            
            # Update bed status
            bed.occupy()
            
            # Update encounter status
            encounter.encounter_type = 'inpatient'
            encounter.save()
            
            # Create flow stage
            from .models_workflow import PatientFlowStage
            # Check for existing admission stage before creating
            existing_stage = PatientFlowStage.objects.filter(
                encounter=encounter,
                stage_type='admission',
                is_deleted=False
            ).first()
            
            if not existing_stage:
                PatientFlowStage.objects.create(
                    encounter=encounter,
                    stage_type='admission',
                    status='completed',
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    completed_by=staff
                )
            
            # 💰 AUTO-BILLING: Create provisional accommodation charges (final on discharge)
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
                        f'💰 Provisional charge: GHS {billing_result["total_charge"]} (final on discharge: detention GHS 120 if < 12 hrs, or admission + doctor/nursing care + consumables, billed per night if ≥12 hrs)'
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
        except DataError as e:
            logger.exception('Admission create failed (database value error)')
            hint = ''
            err = str(e).lower()
            if 'varying(10)' in err or 'character varying' in err:
                hint = ' If this mentions varchar length, run database migrations (python manage.py migrate) on the server.'
            messages.error(request, f'Error creating admission: {e!s}.{hint}')
        except Exception as e:
            logger.exception('Admission create failed')
            messages.error(request, f'Error creating admission: {e!s}')
    
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
                log_msg = (
                    f"Detention GHS {charge_info['total_charge']}"
                    if charge_info.get('is_detention')
                    else f"Admission {charge_info['days']} night(s) @ GHS {charge_info['daily_rate']} + care = GHS {charge_info['total_charge']}"
                )
                logger.info(
                    f"✅ Final bed charges calculated: {admission.encounter.patient.full_name} - {log_msg}"
                )
        except Exception as e:
            logger.error(f"Error updating bed charges on discharge: {str(e)}", exc_info=True)

        # Close billing for this encounter so no new charges can be added (plan §5)
        encounter = admission.encounter
        if encounter and not encounter.billing_closed_at:
            encounter.billing_closed_at = timezone.now()
            encounter.save(update_fields=['billing_closed_at', 'modified'])
        
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
        # Check for existing discharge stage before creating
        existing_stage = PatientFlowStage.objects.filter(
            encounter=admission.encounter,
            stage_type='discharge',
            is_deleted=False
        ).first()
        
        if not existing_stage:
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
            if charge_summary.get('is_detention'):
                charge_msg = f'Detention (< 12 hrs): GHS {charge_summary["current_charges"]}'
            else:
                charge_msg = (
                    f'Admission {charge_summary["days_admitted"]} night(s): accommodation @ GHS {charge_summary["daily_rate"]}/night '
                    f'+ Doctor care (GHS 80/day) + Nursing care (GHS 70/day) + Consumables (GHS 50/day) = GHS {charge_summary["current_charges"]}'
                )
            messages.success(
                request,
                f'✅ Patient discharged successfully. Bed {admission.bed.bed_number} is now available. '
                f'💰 {charge_msg}'
            )
        except Exception:
            messages.success(request, f'✅ Patient discharged successfully. Bed {admission.bed.bed_number} is now available.')
        
        return redirect('hospital:bed_management_worldclass')
    
    context = {
        'admission': admission,
    }
    
    return render(request, 'hospital/discharge_form.html', context)


@login_required
def api_admission_patient_search(request):
    """
    Search any patient for admission. Returns patients with optional encounter_id.
    Use encounter_id when available; otherwise use patient_id (backend creates encounter on submit).
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    from django.db.models import Q
    query_parts = query.split()
    search_q = Q(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(middle_name__icontains=query) |
        Q(mrn__icontains=query) |
        Q(phone_number__icontains=query)
    )
    if len(query_parts) >= 2:
        fp, lp = query_parts[0], ' '.join(query_parts[1:])
        search_q |= Q(first_name__icontains=fp, last_name__icontains=lp)
        search_q |= Q(first_name__icontains=lp, last_name__icontains=fp)

    admitted_ids = set(Admission.objects.filter(is_deleted=False).values_list('encounter_id', flat=True))
    patients = Patient.objects.filter(search_q, is_deleted=False).distinct()[:30]

    results = []
    for p in patients:
        enc = Encounter.objects.filter(
            patient=p, is_deleted=False,
            status__in=('active', 'completed')
        ).exclude(id__in=admitted_ids).order_by('-started_at', '-id').first()
        results.append({
            'id': str(p.id),
            'name': p.full_name,
            'mrn': p.mrn or 'N/A',
            'display': f"{p.full_name} (MRN: {p.mrn or 'N/A'})",
            'encounter_id': str(enc.id) if enc else None,
        })
    return JsonResponse({'results': results})


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


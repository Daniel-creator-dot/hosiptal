"""
Admission Review & Shift Handover System
Allows doctors and nurses to review admitted patients, add notes and medications.
Next shift doctors can read records before continuing care.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Q, Prefetch, Count, Case, When, Value, IntegerField
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import logging
import uuid

from .models import Patient, Encounter, Staff, Prescription, Order, Drug, LabTest, LabResult
from .models import VitalSign, Admission
from .decorators import role_required
from .utils_roles import is_pharmacy_user

logger = logging.getLogger(__name__)


def _queue_admission_prescription_for_pharmacy(prescription, encounter, doctor):
    """Ensure an inpatient prescription has a PharmacyDispensing queue row and alerts pharmacy."""
    from .services.pharmacy_queue_service import queue_prescription_for_pharmacy

    queue_prescription_for_pharmacy(
        prescription,
        encounter,
        doctor,
        inpatient=True,
    )


@login_required
@role_required(
    'admin', 'doctor', 'nurse', 'midwife', 'pharmacist',
    message='Only doctors, nurses, midwives, pharmacists, and admins can view the admitted patients list.',
)
def admitted_patients_list(request):
    """
    Show all currently admitted and detained patients.
    Driven by Admission table (status=admitted) so both full admissions and
    detention stays appear on the dashboard.
    """
    try:
        current_staff = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to access this page.')
        return redirect('hospital:dashboard')
    
    # All active admissions (includes detained: same Admission record, billing differs by stay duration)
    active_admission_encounter_ids = list(
        Admission.objects.filter(
            status='admitted',
            is_deleted=False,
            encounter_id__isnull=False
        ).values_list('encounter_id', flat=True)
    )
    
    admitted_encounters = Encounter.objects.filter(
        id__in=active_admission_encounter_ids,
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
            Q(modified__lt=six_hours_ago) | Q(modified__isnull=True)
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
@role_required(
    'admin', 'doctor', 'nurse', 'midwife', 'pharmacist',
    message='Only doctors, nurses, midwives, pharmacists, and admins can open the admission review page.',
)
def admission_review(request, encounter_id):
    """
    Review an admitted patient
    Add progress notes, medications, update status
    Works with any encounter type for admitted patients
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    # Check if patient is actually admitted (has an active admission record)
    admission = None
    try:
        from .models import Admission
        admission = Admission.objects.filter(
            encounter=encounter,
            status='admitted',
            is_deleted=False
        ).first()
        
        # Align encounter type with model choices (Admission flow uses 'inpatient')
        if admission and encounter.encounter_type != 'inpatient':
            encounter.encounter_type = 'inpatient'
            encounter.save(update_fields=['encounter_type'])
            
    except Exception:
        admission = None
    
    try:
        current_doctor = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff.')
        return redirect('hospital:dashboard')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action and is_pharmacy_user(request.user):
            messages.error(
                request,
                'Pharmacy staff have read-only access here. Open the patient from the dispensing queue to verify and dispense medications.',
            )
            return redirect('hospital:admission_review', encounter_id=encounter.pk)

        if action == 'add_progress_note':
            # CRITICAL: Never allow auto-save to add progress notes (these are final submissions)
            is_auto_save = request.POST.get('auto_save') == 'true' or \
                          request.META.get('HTTP_X_AUTO_SAVE') == 'true'
            
            if is_auto_save:
                # Auto-save should NEVER add progress notes - return error
                from django.http import JsonResponse
                return JsonResponse({
                    'status': 'ignored',
                    'message': 'Progress note creation cannot be auto-saved'
                }, status=400)
            
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
                encounter.modified = timezone.now()
                encounter.save(update_fields=['modified'])
                
                messages.success(request, '✅ Progress note added successfully. It appears in Clinical Notes above and in Progress Notes (Shift Handover) below.')
                
            except ImportError:
                # Fallback to encounter notes
                note_content = request.POST.get('note_content', '')
                if encounter.notes:
                    encounter.notes += f"\n\n[{timezone.now().strftime('%Y-%m-%d %H:%M')} - Dr. {current_doctor.get_full_name()}]\n{note_content}"
                else:
                    encounter.notes = f"[{timezone.now().strftime('%Y-%m-%d %H:%M')} - Dr. {current_doctor.get_full_name()}]\n{note_content}"
                encounter.save()
                messages.success(request, '✅ Progress note added.')

        elif action == 'edit_progress_note':
            note_id = request.POST.get('note_id')
            if not note_id:
                messages.error(request, 'Note ID is required to edit.')
                return redirect('hospital:admission_review', encounter_id=encounter.pk)
            try:
                from .models_advanced import ClinicalNote
            except ImportError:
                messages.error(request, 'Clinical notes are not available.')
                return redirect('hospital:admission_review', encounter_id=encounter.pk)
            try:
                note = ClinicalNote.objects.get(
                    pk=note_id,
                    encounter=encounter,
                    is_deleted=False
                )
                note.subjective = request.POST.get('subjective', '')
                note.objective = request.POST.get('objective', '')
                note.assessment = request.POST.get('assessment', '')
                note.plan = request.POST.get('plan', '')
                note.notes = request.POST.get('note_content', '') or note.notes
                note.save(update_fields=['subjective', 'objective', 'assessment', 'plan', 'notes', 'modified'])
                messages.success(request, '✅ Progress note updated. You can edit it again anytime.')
            except ClinicalNote.DoesNotExist:
                messages.error(request, 'Progress note not found or does not belong to this admission.')
            return redirect('hospital:admission_review', encounter_id=encounter.pk)
        
        elif action == 'add_medication':
            # Add new medication (order goes to pharmacy as pending)
            drug_id = (request.POST.get('drug_id') or '').strip()
            quantity = request.POST.get('quantity', 1)
            dosage = request.POST.get('dosage_instructions', '')
            frequency = request.POST.get('frequency', '')
            duration = request.POST.get('duration_days', '')
            route = request.POST.get('route', 'oral')

            if not drug_id:
                messages.error(
                    request,
                    'Please search and select a medication from the list before adding.',
                )
                return redirect('hospital:admission_review', encounter_id=encounter.pk)
            try:
                uuid.UUID(str(drug_id))
            except (ValueError, TypeError, AttributeError):
                messages.error(request, 'Invalid medication selection. Please search again and pick a drug from the list.')
                return redirect('hospital:admission_review', encounter_id=encounter.pk)
            
            try:
                with transaction.atomic():
                    drug = Drug.objects.get(pk=drug_id, is_deleted=False)
                    
                    # Use existing pending medication order or create one (avoids MultipleObjectsReturned if duplicates exist)
                    med_order = Order.objects.filter(
                        encounter=encounter,
                        order_type='medication',
                        status='pending',
                        is_deleted=False,
                    ).order_by('-id').first()
                    if med_order is None:
                        med_order = Order.objects.create(
                            encounter=encounter,
                            order_type='medication',
                            status='pending',
                            is_deleted=False,
                            requested_by=current_doctor,
                            priority='routine',
                        )
                    
                    # Create prescription (Prescription model uses: dose, duration, instructions)
                    duration_str = f"{duration} days" if duration and str(duration).strip() else "As directed"
                    prescription = Prescription.objects.create(
                        order=med_order,
                        drug=drug,
                        quantity=int(quantity) if quantity else 1,
                        dose=dosage or "As directed",
                        route=route,
                        frequency=frequency or "Once daily",
                        duration=duration_str,
                        instructions="",
                        prescribed_by=current_doctor,
                    )
                    _queue_admission_prescription_for_pharmacy(prescription, encounter, current_doctor)
                
                messages.success(
                    request,
                    f'✅ Added {drug.name} to patient medications. Queued for pharmacy.',
                )
                
            except Drug.DoesNotExist:
                messages.error(request, 'Drug not found.')
            except MultipleObjectsReturned:
                # Duplicate pending medication orders exist (e.g. from old get_or_create). Use one and merge.
                try:
                    with transaction.atomic():
                        drug = Drug.objects.get(pk=drug_id, is_deleted=False)
                        pending = Order.objects.filter(
                            encounter=encounter,
                            order_type='medication',
                            status='pending',
                            is_deleted=False,
                        ).order_by('-id')
                        med_order = pending.first()
                        if not med_order:
                            messages.error(request, 'No medication order found.')
                        else:
                            # Move prescriptions from duplicate orders into the one we keep
                            for dup in pending[1:]:
                                dup.prescriptions.filter(is_deleted=False).update(order_id=med_order.id)
                                dup.is_deleted = True
                                dup.save(update_fields=['is_deleted'])
                            duration_str = f"{duration} days" if duration and str(duration).strip() else "As directed"
                            prescription = Prescription.objects.create(
                                order=med_order,
                                drug=drug,
                                quantity=int(quantity) if quantity else 1,
                                dose=dosage or "As directed",
                                route=route,
                                frequency=frequency or "Once daily",
                                duration=duration_str,
                                instructions="",
                                prescribed_by=current_doctor,
                            )
                            _queue_admission_prescription_for_pharmacy(prescription, encounter, current_doctor)
                            messages.success(
                                request,
                                f'✅ Added {drug.name} to patient medications. Duplicate orders were merged. Queued for pharmacy.',
                            )
                except Drug.DoesNotExist:
                    messages.error(request, 'Drug not found.')
                except Exception as e2:
                    messages.error(request, f'Error adding medication: {str(e2)}')
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
            
            encounter.save()
            
            messages.success(request, '✅ Patient status updated.')
        
        elif action == 'order_labs':
            test_ids = []
            for raw in request.POST.getlist('test_ids'):
                s = (raw or '').strip()
                if not s:
                    continue
                try:
                    uuid.UUID(s)
                except (ValueError, TypeError, AttributeError):
                    continue
                test_ids.append(s)
            priority = request.POST.get('priority', 'routine')
            notes = request.POST.get('notes', '')
            if test_ids:
                try:
                    with transaction.atomic():
                        tests = list(
                            LabTest.objects.filter(
                                pk__in=test_ids,
                                is_active=True,
                                is_deleted=False,
                                name__isnull=False,
                            ).exclude(name__iexact='').exclude(name__icontains='INVALID')
                        )
                        if tests:
                            lab_order = Order.objects.create(
                                encounter=encounter,
                                order_type='lab',
                                status='pending',
                                priority=priority,
                                notes=notes or '',
                                requested_by=current_doctor,
                                requested_at=timezone.now(),
                            )
                            lab_order.refresh_from_db()
                            created_lines = 0
                            for test in tests:
                                existing = LabResult.objects.filter(
                                    order=lab_order, test=test, is_deleted=False
                                ).first()
                                if not existing:
                                    LabResult.objects.create(
                                        order=lab_order,
                                        test=test,
                                        status='pending',
                                    )
                                    created_lines += 1
                            if created_lines:
                                messages.success(
                                    request,
                                    f'✅ Lab order created with {created_lines} test(s).',
                                )
                            else:
                                messages.info(
                                    request,
                                    'Those tests are already on the most recent lab order for this patient.',
                                )
                        else:
                            messages.error(request, 'No valid tests selected.')
                except IntegrityError as e:
                    logger.warning('Lab order integrity error for encounter %s: %s', encounter.pk, e)
                    messages.error(
                        request,
                        'Could not create the lab order due to a data conflict. Please try again or order one panel at a time.',
                    )
                except Exception as e:
                    logger.exception('Error creating lab order from admission review')
                    messages.error(request, f'Error creating lab order: {str(e)}')
            else:
                messages.error(request, 'Please select at least one lab test.')
        
        elif action == 'order_imaging':
            imaging_catalog_ids = request.POST.getlist('imaging_catalog_ids')
            priority = request.POST.get('priority', 'routine')
            notes = request.POST.get('notes', '')
            if imaging_catalog_ids:
                try:
                    from .models_advanced import ImagingCatalog, ImagingStudy
                    imaging_catalog_items = ImagingCatalog.objects.filter(
                        pk__in=imaging_catalog_ids,
                        is_active=True,
                        is_deleted=False,
                        name__isnull=False
                    ).exclude(name__iexact='').exclude(name__icontains='INVALID')
                    if imaging_catalog_items.exists():
                        with transaction.atomic():
                            imaging_order = Order.objects.create(
                                encounter=encounter,
                                order_type='imaging',
                                status='pending',
                                priority=priority,
                                notes=notes,
                                requested_by=current_doctor,
                                requested_at=timezone.now()
                            )
                            for catalog_item in imaging_catalog_items:
                                existing_study = ImagingStudy.objects.filter(
                                    order=imaging_order,
                                    patient=encounter.patient,
                                    encounter=encounter,
                                    study_type=catalog_item.code or catalog_item.name,
                                    modality=catalog_item.modality,
                                    is_deleted=False
                                ).first()
                                if not existing_study:
                                    ImagingStudy.objects.create(
                                        order=imaging_order,
                                        patient=encounter.patient,
                                        encounter=encounter,
                                        modality=catalog_item.modality,
                                        body_part=catalog_item.body_part or '',
                                        study_type=catalog_item.code or catalog_item.name,
                                        status='scheduled',
                                        priority=priority,
                                        clinical_indication=notes,
                                    )
                        messages.success(
                            request,
                            f'✅ Imaging order created with {imaging_catalog_items.count()} study(ies).'
                        )
                    else:
                        messages.error(request, 'No valid imaging studies selected.')
                except Exception as e:
                    logger.exception('Error creating imaging order')
                    messages.error(request, f'Error creating imaging order: {str(e)}')
            else:
                messages.error(request, 'Please select at least one imaging study.')
        
        elif action == 'record_vitals':
            def _safe_int(value, default=None):
                if value is None or str(value).strip() == '':
                    return default
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default

            def _safe_decimal(value, default=None):
                if value is None or str(value).strip() == '':
                    return default
                try:
                    return Decimal(str(value))
                except (ValueError, TypeError):
                    return default

            vital_data = {
                'systolic_bp': _safe_int(request.POST.get('systolic_bp')),
                'diastolic_bp': _safe_int(request.POST.get('diastolic_bp')),
                'pulse': _safe_int(request.POST.get('pulse')),
                'temperature': _safe_decimal(request.POST.get('temperature')),
                'spo2': _safe_int(request.POST.get('spo2')),
                'respiratory_rate': _safe_int(request.POST.get('respiratory_rate')),
            }
            notes_text = (request.POST.get('notes') or '').strip()
            blood_glucose = _safe_decimal(request.POST.get('blood_glucose'))
            strip_type = (request.POST.get('poc_glucose_strip_type') or '').strip().lower()
            poc_glucose_strip_type = strip_type if strip_type in ('rbs', 'fbs') else ''
            has_any_core = any(
                v is not None
                for v in [
                    vital_data['systolic_bp'],
                    vital_data['diastolic_bp'],
                    vital_data['pulse'],
                    vital_data['temperature'],
                    vital_data['spo2'],
                    vital_data['respiratory_rate'],
                ]
            )
            if (
                not has_any_core
                and blood_glucose is None
                and not poc_glucose_strip_type
                and not notes_text
            ):
                messages.error(request, 'Enter at least one vital sign, glucose reading, strip charge, or a short note.')
                return redirect('hospital:admission_review', encounter_id=encounter.pk)

            patient = encounter.patient
            try:
                patient_age = int(patient.age) if patient.age is not None else 30
            except (TypeError, ValueError):
                patient_age = 30
            patient_gender = getattr(patient, 'gender', None) or None

            try:
                from .services.vital_signs_validator import VitalSignsValidator
                validation_results = VitalSignsValidator.validate_all_vitals(
                    vital_data,
                    patient_age,
                    patient_gender,
                )
            except Exception:
                validation_results = {'overall': {'is_ok': True, 'message': 'Vital signs saved.', 'status': 'normal'}}

            vital = VitalSign.objects.create(
                encounter=encounter,
                systolic_bp=vital_data['systolic_bp'],
                diastolic_bp=vital_data['diastolic_bp'],
                pulse=vital_data['pulse'],
                temperature=vital_data['temperature'],
                spo2=vital_data['spo2'],
                respiratory_rate=vital_data['respiratory_rate'],
                weight=_safe_decimal(request.POST.get('weight')),
                height=_safe_decimal(request.POST.get('height')),
                blood_glucose=blood_glucose,
                poc_glucose_strip_type=poc_glucose_strip_type,
                consciousness_level=request.POST.get('consciousness_level') or 'alert',
                pain_score=_safe_int(request.POST.get('pain_score')),
                supplemental_oxygen=request.POST.get('supplemental_oxygen') == 'on',
                oxygen_flow_rate=_safe_decimal(request.POST.get('oxygen_flow_rate')),
                position=request.POST.get('position') or '',
                notes=request.POST.get('notes', ''),
                recorded_by=current_doctor,
            )
            encounter.modified = timezone.now()
            encounter.save(update_fields=['modified'])

            if poc_glucose_strip_type:
                from .services.auto_billing_service import AutoBillingService

                bill_result = AutoBillingService.bill_poc_glucose_strip(
                    encounter, poc_glucose_strip_type, vital_sign=vital
                )
                if bill_result.get('success'):
                    messages.success(
                        request,
                        bill_result.get(
                            'message',
                            'POC glucose strip added to patient bill for cashier.',
                        ),
                    )
                    sf = bill_result.get('stock_shortfall')
                    if sf is not None and int(sf or 0) > 0:
                        messages.warning(
                            request,
                            'Glucose strip stock: shortfall recorded — restock pharmacy store.',
                        )
                else:
                    messages.warning(
                        request,
                        bill_result.get('message')
                        or 'POC glucose strip could not be added to the bill.',
                    )

            overall = validation_results.get('overall', {})
            if overall.get('is_ok'):
                messages.success(
                    request,
                    overall.get('message', 'Vital signs recorded for this admission.'),
                )
            elif 'critical' in str(overall.get('status', '')):
                messages.error(
                    request,
                    overall.get(
                        'message',
                        'Critical vital signs recorded — review immediately.',
                    ),
                )
            else:
                messages.warning(
                    request,
                    overall.get(
                        'message',
                        'Vital signs saved — one or more values are outside typical range.',
                    ),
                )

        elif action == 'log_treatment_dose':
            rx_id = (request.POST.get('prescription_id') or '').strip()
            if not rx_id:
                messages.error(request, 'Select a medication to log.')
                return redirect('hospital:admission_review', encounter_id=encounter.pk)
            rx = Prescription.objects.filter(
                pk=rx_id,
                is_deleted=False,
                order__encounter=encounter,
                order__order_type='medication',
            ).select_related('order').first()
            if not rx:
                messages.error(request, 'Prescription not found for this admission.')
                return redirect('hospital:admission_review', encounter_id=encounter.pk)
            try:
                from .models_advanced import MedicationAdministrationRecord
            except ImportError:
                messages.error(
                    request,
                    'Medication administration records are not available on this server.',
                )
                return redirect('hospital:admission_review', encounter_id=encounter.pk)

            dose_given = (request.POST.get('dose_given') or '').strip() or (rx.dose or '')[:50]
            notes = (request.POST.get('treatment_notes') or '').strip()
            raw_dt = (request.POST.get('administered_at') or '').strip()
            if raw_dt:
                try:
                    naive = datetime.strptime(raw_dt[:16], '%Y-%m-%dT%H:%M')
                    admin_at = timezone.make_aware(naive, timezone.get_current_timezone())
                except ValueError:
                    admin_at = timezone.now()
            else:
                admin_at = timezone.now()
            route = (rx.route or '')[:50]

            try:
                with transaction.atomic():
                    mar = MedicationAdministrationRecord.objects.create(
                        prescription=rx,
                        encounter=encounter,
                        patient=encounter.patient,
                        scheduled_time=admin_at,
                        administered_time=admin_at,
                        status='given',
                        administered_by=current_doctor,
                        dose_given=dose_given[:50],
                        route=route,
                        notes=notes,
                    )
                try:
                    from .models_drug_accountability import DrugAdministrationInventory

                    DrugAdministrationInventory.create_from_mar(mar, current_doctor)
                except Exception as inv_err:
                    logger.warning(
                        'Admission MAR logged; pharmacy inventory not updated: %s',
                        inv_err,
                    )
                    messages.success(
                        request,
                        f'✅ Recorded {rx.drug.name}. Pharmacy stock was not adjusted (see logs if needed).',
                    )
                else:
                    messages.success(
                        request,
                        f'✅ Recorded administration of {rx.drug.name}.',
                    )
                encounter.modified = timezone.now()
                encounter.save(update_fields=['modified'])
            except Exception as e:
                logger.exception('log_treatment_dose failed')
                messages.error(request, f'Could not log dose: {e}')

        elif action == 'complete_scheduled_mar':
            mar_id = (request.POST.get('mar_id') or '').strip()
            if not mar_id:
                messages.error(request, 'Missing administration record.')
                return redirect('hospital:admission_review', encounter_id=encounter.pk)
            try:
                from .models_advanced import MedicationAdministrationRecord
            except ImportError:
                messages.error(request, 'Medication administration records are not available.')
                return redirect('hospital:admission_review', encounter_id=encounter.pk)
            mar = MedicationAdministrationRecord.objects.filter(
                pk=mar_id,
                encounter=encounter,
                is_deleted=False,
                status='scheduled',
            ).select_related('prescription__drug').first()
            if not mar:
                messages.error(request, 'Scheduled dose not found or already completed.')
                return redirect('hospital:admission_review', encounter_id=encounter.pk)
            dose_given = (request.POST.get('dose_given') or '').strip() or (
                (mar.prescription.dose or '')[:50] if mar.prescription else ''
            )
            notes = (request.POST.get('treatment_notes') or '').strip()
            now = timezone.now()
            try:
                with transaction.atomic():
                    mar.status = 'given'
                    mar.administered_time = now
                    mar.administered_by = current_doctor
                    mar.dose_given = dose_given[:50]
                    if notes:
                        mar.notes = notes
                    mar.save()
                try:
                    from .models_drug_accountability import DrugAdministrationInventory

                    DrugAdministrationInventory.create_from_mar(mar, current_doctor)
                except Exception as inv_err:
                    logger.warning(
                        'Scheduled MAR completed; inventory not updated: %s',
                        inv_err,
                    )
                    messages.success(
                        request,
                        f'✅ Marked {mar.prescription.drug.name} as given. Stock may need manual check.',
                    )
                else:
                    messages.success(
                        request,
                        f'✅ Marked {mar.prescription.drug.name} as given.',
                    )
                encounter.modified = now
                encounter.save(update_fields=['modified'])
            except Exception as e:
                logger.exception('complete_scheduled_mar failed')
                messages.error(request, f'Could not update dose: {e}')
        
        return redirect('hospital:admission_review', encounter_id=encounter.pk)
    
    # Get all data for display
    # Latest vitals
    _vitals_qs = encounter.vitals.filter(is_deleted=False).select_related('recorded_by__user')
    latest_vitals = _vitals_qs.order_by('-recorded_at').first()
    recent_vitals = _vitals_qs.order_by('-recorded_at')[:5]
    
    # Current medications
    current_prescriptions = Prescription.objects.filter(
        order__encounter=encounter,
        order__order_type='medication',
        is_deleted=False
    ).select_related('drug', 'prescribed_by__user').order_by('-created')

    treatment_chart_available = False
    treatment_mar_given = []
    treatment_mar_pending = []
    admission_treatment_chart = {'events': []}
    try:
        from .models_advanced import MedicationAdministrationRecord

        treatment_chart_available = True
        treatment_mar_given = list(
            MedicationAdministrationRecord.objects.filter(
                encounter=encounter,
                is_deleted=False,
                status='given',
                administered_time__isnull=False,
            )
            .select_related('prescription__drug', 'administered_by__user')
            .order_by('-administered_time')[:80]
        )
        treatment_mar_pending = list(
            MedicationAdministrationRecord.objects.filter(
                encounter=encounter,
                is_deleted=False,
                status='scheduled',
            )
            .select_related('prescription__drug')
            .order_by('scheduled_time')[:40]
        )
        _ev_sorted = sorted(
            treatment_mar_given,
            key=lambda m: m.administered_time or m.scheduled_time,
        )[-60:]
        admission_treatment_chart = {
            'events': [
                {
                    't': timezone.localtime(
                        m.administered_time or m.scheduled_time
                    ).isoformat(),
                    'drug': (
                        m.prescription.drug.name
                        if m.prescription and m.prescription.drug
                        else 'Medication'
                    ),
                    'dose': (m.dose_given or '')[:80],
                    'id': str(m.id),
                }
                for m in _ev_sorted
            ]
        }
    except ImportError:
        pass
    except Exception as e:
        logger.exception('Admission treatment chart load failed: %s', e)
    
    # Clinical notes (progress notes for handover) — include this encounter AND any same-patient encounter during stay
    clinical_notes = []
    clinical_notes_calendar_data = []
    problems = []
    try:
        from .models_advanced import ClinicalNote, ProblemList

        # Include notes from this encounter and any same-patient encounter during stay (e.g. consultations)
        admission_start = encounter.started_at
        same_stay_encounter_ids = [encounter.id]
        if admission_start:
            same_stay_encounter_ids = list(
                Encounter.objects.filter(
                    patient=encounter.patient,
                    is_deleted=False,
                    started_at__gte=admission_start,
                ).values_list('id', flat=True)[:100]
            )
            if not same_stay_encounter_ids:
                same_stay_encounter_ids = [encounter.id]

        # Today's notes first, then newest first within each day (book-style order for doctors)
        today_local = timezone.localdate()
        clinical_notes = ClinicalNote.objects.filter(
            encounter_id__in=same_stay_encounter_ids,
            is_deleted=False
        ).select_related('created_by__user', 'encounter').annotate(
            is_today=Case(
                When(created__date=today_local, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by('-is_today', '-created')

        # JSON for calendar: build list without raising so list view always has notes
        for n in clinical_notes:
            try:
                created_local = timezone.localtime(n.created) if n.created else None
            except Exception:
                created_local = n.created
            date_str = ''
            time_str = ''
            if created_local:
                try:
                    date_str = created_local.strftime('%Y-%m-%d')
                    time_str = created_local.strftime('%H:%M')
                except Exception:
                    date_str = str(getattr(created_local, 'date', ''))[:10] if created_local else ''
            author = 'System'
            if n.created_by:
                try:
                    if getattr(n.created_by, 'user', None):
                        author = (n.created_by.user.get_full_name() or n.created_by.user.username or 'Staff') or 'Staff'
                    else:
                        author = getattr(n.created_by, 'get_full_name', lambda: 'Staff')() or 'Staff'
                except Exception:
                    pass
            summary = (n.assessment or n.plan or n.notes or n.subjective or n.objective or '')[:80]
            if len((n.assessment or '') + (n.plan or '') + (n.notes or '')) > 80:
                summary += '\u2026'
            clinical_notes_calendar_data.append({
                'id': str(n.id),
                'date': date_str or '',
                'time': time_str or '',
                'author': author,
                'summary': summary,
                'type': getattr(n, 'note_type', None) or 'progress',
                'subjective': (n.subjective or '')[:500],
                'objective': (n.objective or '')[:500],
                'assessment': (n.assessment or '')[:500],
                'plan': (n.plan or '')[:500],
                'notes': (n.notes or '')[:500],
            })
        problems = ProblemList.objects.filter(
            patient=encounter.patient,
            status='active',
            is_deleted=False
        ).order_by('-created')
    except ImportError:
        clinical_notes = []
        clinical_notes_calendar_data = []
        logger.warning('models_advanced not available: ClinicalNote/ProblemList not loaded for admission review')
    except Exception as e:
        logger.exception('Error loading clinical_notes for admission review: %s', e)
        clinical_notes_calendar_data = []
        # Keep clinical_notes for list view if we already had the queryset
        try:
            if clinical_notes and hasattr(clinical_notes, '__iter__'):
                clinical_notes = list(clinical_notes)
            else:
                clinical_notes = []
        except Exception:
            clinical_notes = []
    
    # Lab results (LabResult must not be re-imported in this function — it shadows the module import and breaks POST handlers.)
    try:
        recent_lab_results = LabResult.objects.filter(
            order__encounter=encounter,
            is_deleted=False
        ).select_related('test', 'order').order_by('-created')[:20]
    except Exception:
        recent_lab_results = []
    
    # Lab orders and imaging orders for this encounter
    lab_orders = Order.objects.filter(
        encounter=encounter,
        order_type='lab',
        is_deleted=False
    ).prefetch_related(Prefetch('lab_results', queryset=LabResult.objects.filter(is_deleted=False).select_related('test'))).order_by('-created')
    
    imaging_orders = Order.objects.filter(
        encounter=encounter,
        order_type='imaging',
        is_deleted=False
    ).order_by('-created')
    
    # Imaging studies with images/result files for this encounter
    imaging_studies_with_files = []
    try:
        from .models_advanced import ImagingStudy
        imaging_studies_with_files = list(ImagingStudy.objects.filter(
            order__encounter=encounter,
            order__is_deleted=False,
            is_deleted=False
        ).prefetch_related('images').select_related('order').order_by('-created'))
    except Exception:
        pass
    
    # PDF/result documents for lab and imaging (for "view result" links)
    lab_pdf_docs = []
    imaging_pdf_docs = []
    try:
        from .models_medical_records import PatientDocument
        lab_pdf_docs = list(PatientDocument.objects.filter(
            Q(patient=encounter.patient, encounter=encounter, document_type='lab_report') |
            Q(lab_result__order__encounter=encounter, document_type='lab_report'),
            is_deleted=False
        ).select_related('uploaded_by__user', 'lab_result').order_by('-created')[:20])
        imaging_pdf_docs = list(PatientDocument.objects.filter(
            Q(patient=encounter.patient, encounter=encounter, document_type='imaging_report') |
            Q(imaging_study__order__encounter=encounter, document_type='imaging_report'),
            is_deleted=False
        ).select_related('uploaded_by__user', 'imaging_study').order_by('-created')[:20])
    except Exception:
        pass
    
    # All orders (existing)
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
    
    progress_notes_today_date = timezone.localdate()

    # Time-series for TPR / vitals graphic sheet (Chart.js on admission review)
    admission_vitals_chart = {'points': []}
    try:
        _chart_rows = (
            encounter.vitals.filter(is_deleted=False)
            .order_by('recorded_at')
            .values(
                'recorded_at',
                'temperature',
                'systolic_bp',
                'diastolic_bp',
                'pulse',
                'spo2',
                'respiratory_rate',
            )[:240]
        )
        _pts = []
        for row in _chart_rows:
            ra = row.get('recorded_at')
            if ra is None:
                continue
            if timezone.is_naive(ra):
                ra = timezone.make_aware(ra, timezone.get_current_timezone())
            temp = row.get('temperature')
            sys_bp = row.get('systolic_bp')
            dia_bp = row.get('diastolic_bp')
            pulse_v = row.get('pulse')
            spo2_v = row.get('spo2')
            rr_v = row.get('respiratory_rate')
            if not any(
                v is not None
                for v in (temp, sys_bp, dia_bp, pulse_v, spo2_v, rr_v)
            ):
                continue
            _pts.append(
                {
                    't': timezone.localtime(ra).isoformat(),
                    'temp': float(temp) if temp is not None else None,
                    'sys': sys_bp,
                    'dia': dia_bp,
                    'pulse': pulse_v,
                    'spo2': spo2_v,
                    'rr': rr_v,
                }
            )
        admission_vitals_chart = {'points': _pts}
    except Exception as e:
        logger.exception('admission_vitals_chart build failed: %s', e)

    from django.conf import settings as django_settings

    context = {
        'title': f'Admission Review - {encounter.patient.full_name}',
        'encounter': encounter,
        'patient': encounter.patient,
        'admission': admission,
        'current_doctor': current_doctor,
        'latest_vitals': latest_vitals,
        'recent_vitals': recent_vitals,
        'admission_vitals_chart': admission_vitals_chart,
        'treatment_chart_available': treatment_chart_available,
        'treatment_mar_given': treatment_mar_given,
        'treatment_mar_pending': treatment_mar_pending,
        'admission_treatment_chart': admission_treatment_chart,
        'current_prescriptions': current_prescriptions,
        'clinical_notes': clinical_notes,
        'clinical_notes_calendar_data': clinical_notes_calendar_data,
        'progress_notes_today_date': progress_notes_today_date,
        'problems': problems,
        'recent_lab_results': recent_lab_results,
        'lab_orders': lab_orders,
        'imaging_orders': imaging_orders,
        'imaging_studies_with_files': imaging_studies_with_files,
        'lab_pdf_docs': lab_pdf_docs,
        'imaging_pdf_docs': imaging_pdf_docs,
        'orders': orders,
        'available_drugs': available_drugs,
        'days_admitted': days_admitted,
        'hours_admitted': hours_admitted,
        'poc_glucose_strip_ghs': django_settings.POC_GLUCOSE_STRIP_GHS,
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
    
    # Get all admitted and detained patients (from Admission table)
    active_admission_encounter_ids = list(
        Admission.objects.filter(
            status='admitted',
            is_deleted=False,
            encounter_id__isnull=False
        ).values_list('encounter_id', flat=True)
    )
    admitted_encounters = Encounter.objects.filter(
        id__in=active_admission_encounter_ids,
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
            recent_labs = LabResult.objects.filter(
                order__encounter=encounter,
                created__gte=shift_start,
                is_deleted=False
            ).select_related('test')
        except Exception:
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


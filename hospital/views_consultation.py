"""
Consultation views for doctors to prescribe medications and order tests.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
import logging

from .models import (
    Encounter, Patient, Order, Prescription, Drug, LabTest, Staff
)

logger = logging.getLogger(__name__)
try:
    from .forms import EncounterForm
except ImportError:
    from django import forms
    from .models import Encounter
    
    class EncounterForm(forms.ModelForm):
        class Meta:
            model = Encounter
            fields = ['encounter_type', 'provider', 'chief_complaint']


@login_required
def consultation_view(request, encounter_id):
    """Main consultation interface for doctors"""
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    # Get current doctor (staff member)
    try:
        doctor = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to access consultation.')
        return redirect('hospital:encounter_detail', pk=encounter_id)
    
    # Get available drugs
    available_drugs = Drug.objects.filter(is_active=True, is_deleted=False).order_by('name')
    
    # Get available lab tests
    available_lab_tests = LabTest.objects.filter(is_active=True, is_deleted=False).order_by('name')
    
    # Get existing orders for this encounter
    existing_orders = Order.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).select_related('requested_by').order_by('-created')
    
    # Get existing prescriptions
    existing_prescriptions = Prescription.objects.filter(
        order__encounter=encounter,
        is_deleted=False
    ).select_related('drug', 'prescribed_by', 'order').order_by('-created')
    
    # Handle form submissions
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'prescribe_drug':
            # Create prescription
            drug_id = request.POST.get('drug_id')
            quantity = int(request.POST.get('quantity', 1))
            dose = request.POST.get('dose', '')
            route = request.POST.get('route', 'oral')
            frequency = request.POST.get('frequency', '')
            duration = request.POST.get('duration', '')
            instructions = request.POST.get('instructions', '')
            
            try:
                drug = Drug.objects.get(pk=drug_id, is_active=True)
                
                # Get or create a medication order for this encounter
                medication_order = Order.objects.filter(
                    encounter=encounter,
                    order_type='medication',
                    status='pending',
                    is_deleted=False
                ).first()
                
                if not medication_order:
                    medication_order = Order.objects.create(
                        encounter=encounter,
                        order_type='medication',
                        status='pending',
                        requested_by=doctor,
                        priority='routine'
                    )
                
                # Create prescription
                prescription = Prescription.objects.create(
                    order=medication_order,
                    drug=drug,
                    quantity=quantity,
                    dose=dose,
                    route=route,
                    frequency=frequency,
                    duration=duration,
                    instructions=instructions,
                    prescribed_by=doctor
                )
                
                messages.success(request, f'Prescribed {drug.name} to {encounter.patient.full_name}')
                
            except Drug.DoesNotExist:
                messages.error(request, 'Selected drug not found.')
            except Exception as e:
                messages.error(request, f'Error creating prescription: {str(e)}')
        
        elif action == 'order_lab_test':
            # Create lab test order
            test_ids = request.POST.getlist('test_ids')
            priority = request.POST.get('priority', 'routine')
            notes = request.POST.get('notes', '')
            
            if test_ids:
                try:
                    tests = LabTest.objects.filter(pk__in=test_ids, is_active=True)
                    if tests.exists():
                        # Create lab order
                        lab_order = Order.objects.create(
                            encounter=encounter,
                            order_type='lab',
                            status='pending',
                            priority=priority,
                            notes=notes,
                            requested_by=doctor
                        )
                        
                        # Create lab results for each test
                        from .models import LabResult
                        for test in tests:
                            LabResult.objects.create(
                                order=lab_order,
                                test=test,
                                status='pending'
                            )
                        
                        messages.success(request, f'Ordered {tests.count()} lab test(s)')
                    else:
                        messages.error(request, 'No valid tests selected.')
                except Exception as e:
                    messages.error(request, f'Error creating lab order: {str(e)}')
            else:
                messages.error(request, 'Please select at least one test.')
        
        elif action == 'order_imaging':
            # Create imaging order
            imaging_type = request.POST.get('imaging_type', 'X-ray')
            priority = request.POST.get('priority', 'routine')
            notes = request.POST.get('notes', '')
            
            try:
                imaging_order = Order.objects.create(
                    encounter=encounter,
                    order_type='imaging',
                    status='pending',
                    priority=priority,
                    notes=f'{imaging_type}: {notes}',
                    requested_by=doctor
                )
                
                messages.success(request, f'Ordered {imaging_type} for {encounter.patient.full_name}')
                
            except Exception as e:
                messages.error(request, f'Error creating imaging order: {str(e)}')
        
        elif action == 'order_procedure':
            # Create procedure order
            procedure_name = request.POST.get('procedure_name', '')
            procedure_type = request.POST.get('procedure_type', 'other')
            priority = request.POST.get('priority', 'routine')
            notes = request.POST.get('notes', '')
            scheduled_date = request.POST.get('scheduled_date')
            
            if procedure_name:
                try:
                    from datetime import datetime
                    scheduled_datetime = None
                    if scheduled_date:
                        try:
                            scheduled_datetime = datetime.strptime(scheduled_date, '%Y-%m-%dT%H:%M')
                        except ValueError:
                            try:
                                scheduled_datetime = datetime.strptime(scheduled_date, '%Y-%m-%d')
                            except ValueError:
                                pass
                    
                    procedure_order = Order.objects.create(
                        encounter=encounter,
                        order_type='procedure',
                        status='pending',
                        priority=priority,
                        notes=f'{procedure_name} ({procedure_type}): {notes}',
                        requested_by=doctor
                    )
                    
                    messages.success(request, f'Ordered {procedure_name} procedure for {encounter.patient.full_name}')
                    
                except Exception as e:
                    messages.error(request, f'Error creating procedure order: {str(e)}')
            else:
                messages.error(request, 'Procedure name is required.')
        
        elif action == 'save_diagnosis':
            # Save diagnosis to problem list
            from .models_advanced import ProblemList
            icd10_code = request.POST.get('icd10_code', '')
            problem = request.POST.get('problem', '')
            description = request.POST.get('description', '')
            
            if problem:
                try:
                    ProblemList.objects.create(
                        patient=encounter.patient,
                        encounter=encounter,
                        icd10_code=icd10_code,
                        problem=problem,
                        description=description,
                        status='active',
                        created_by=doctor
                    )
                    
                    # Update encounter diagnosis
                    if icd10_code:
                        encounter.diagnosis = f"{encounter.diagnosis or ''}\n{icd10_code}: {problem}".strip()
                        encounter.save(update_fields=['diagnosis'])
                    
                    messages.success(request, f'Diagnosis "{problem}" added successfully.')
                    
                except Exception as e:
                    messages.error(request, f'Error saving diagnosis: {str(e)}')
            else:
                messages.error(request, 'Problem/diagnosis is required.')
        
        elif action == 'save_note':
            # Save clinical note and add consultation charge
            from .models_advanced import ClinicalNote
            note_type = request.POST.get('note_type', 'consultation')
            notes = request.POST.get('notes', '')
            subjective = request.POST.get('subjective', '')
            objective = request.POST.get('objective', '')
            assessment = request.POST.get('assessment', '')
            plan = request.POST.get('plan', '')
            
            try:
                clinical_note = ClinicalNote.objects.create(
                    encounter=encounter,
                    note_type=note_type,
                    subjective=subjective,
                    objective=objective,
                    assessment=assessment,
                    plan=plan,
                    notes=notes,
                    created_by=doctor
                )
                
                # Consultation charge will be added automatically via ClinicalNote.save() signal
                messages.success(request, 'Clinical note saved successfully.')
                
            except Exception as e:
                messages.error(request, f'Error saving note: {str(e)}')
        
        elif action == 'update_encounter' or action == 'save_progress':
            # Update encounter chief complaint, diagnosis, notes
            chief_complaint = request.POST.get('chief_complaint', '')
            diagnosis = request.POST.get('diagnosis', '')
            notes = request.POST.get('encounter_notes', '')
            subjective = request.POST.get('subjective', '')
            objective = request.POST.get('objective', '')
            assessment = request.POST.get('assessment', '')
            plan = request.POST.get('plan', '')
            
            # Update encounter
            if chief_complaint:
                encounter.chief_complaint = chief_complaint
            if diagnosis:
                encounter.diagnosis = diagnosis
            if notes:
                encounter.notes = notes
            encounter.save()
            
            # Save/update clinical note if SOAP fields provided
            if any([subjective, objective, assessment, plan]):
                try:
                    from .models_advanced import ClinicalNote
                    ClinicalNote.objects.create(
                        encounter=encounter,
                        note_type='progress',
                        subjective=subjective,
                        objective=objective,
                        assessment=assessment or diagnosis,
                        plan=plan,
                        notes=notes or 'Progress note saved',
                        created_by=doctor
                    )
                    messages.success(request, '✅ Consultation progress saved successfully.')
                except ImportError:
                    messages.success(request, '✅ Encounter information updated.')
            else:
                messages.success(request, '✅ Encounter information updated.')
        
        elif action == 'complete_consultation':
            # Complete consultation - save all info and mark as complete
            try:
                # Update encounter with final details
                chief_complaint = request.POST.get('chief_complaint', '')
                diagnosis = request.POST.get('diagnosis', '')
                notes = request.POST.get('encounter_notes', '')
                final_assessment = request.POST.get('final_assessment', '')
                follow_up_instructions = request.POST.get('follow_up_instructions', '')
                
                # Update encounter fields
                if chief_complaint:
                    encounter.chief_complaint = chief_complaint
                if diagnosis:
                    encounter.diagnosis = diagnosis
                if notes:
                    encounter.notes = notes
                
                # Mark encounter as completed
                encounter.status = 'completed'
                encounter.ended_at = timezone.now()
                encounter.save()
                
                # Save final clinical note
                try:
                    from .models_advanced import ClinicalNote
                    ClinicalNote.objects.create(
                        encounter=encounter,
                        note_type='consultation',
                        subjective=request.POST.get('subjective', ''),
                        objective=request.POST.get('objective', ''),
                        assessment=final_assessment or diagnosis,
                        plan=follow_up_instructions or 'Follow up as needed',
                        notes=f'CONSULTATION COMPLETED\n\n{notes}',
                        created_by=doctor
                    )
                except ImportError:
                    pass
                
                # Update patient flow stage to completed
                try:
                    from .models_workflow import PatientFlowStage
                    PatientFlowStage.objects.filter(
                        encounter=encounter,
                        stage_type='consultation',
                        is_deleted=False
                    ).update(
                        status='completed',
                        completed_at=timezone.now()
                    )
                except:
                    pass
                
                # Send notification to patient
                if encounter.patient.phone_number:
                    try:
                        from .services.sms_service import sms_service
                        message = (
                            f"Your consultation with Dr. {doctor.get_full_name()} is complete. "
                            f"Follow-up instructions: {follow_up_instructions or 'Follow prescriptions as directed'}. "
                            f"Thank you for choosing PrimeCare Medical."
                        )
                        sms_service.send_sms(
                            phone_number=encounter.patient.phone_number,
                            message=message,
                            message_type='consultation_complete',
                            recipient_name=encounter.patient.full_name
                        )
                    except Exception as e:
                        logger.error(f"Error sending consultation complete SMS: {str(e)}")
                
                messages.success(
                    request, 
                    f'✅ Consultation completed successfully for {encounter.patient.full_name}. '
                    f'Duration: {encounter.get_duration_minutes()} minutes. '
                    f'Patient has been notified.'
                )
                
                # Redirect to appropriate next page
                next_page = request.POST.get('next_page', 'dashboard')
                if next_page == 'patient':
                    return redirect('hospital:patient_detail', pk=encounter.patient.pk)
                elif next_page == 'queue':
                    return redirect('hospital:triage_queue')  # FIXED: Changed from queue_management to triage_queue
                else:
                    return redirect('hospital:dashboard')
                    
            except Exception as e:
                logger.error(f"Error completing consultation: {str(e)}", exc_info=True)
                messages.error(request, f'Error completing consultation: {str(e)}')
        
        elif action == 'update_lab_result':
            # Update existing lab result
            result_id = request.POST.get('result_id')
            try:
                from .models import LabResult
                result = LabResult.objects.get(pk=result_id, order__encounter=encounter, is_deleted=False)
                
                result.status = request.POST.get('status', result.status)
                result.value = request.POST.get('value', '')
                result.units = request.POST.get('units', '')
                result.range_low = request.POST.get('range_low', '')
                result.range_high = request.POST.get('range_high', '')
                result.is_abnormal = 'is_abnormal' in request.POST
                result.qualitative_result = request.POST.get('qualitative_result', '')
                result.notes = request.POST.get('notes', '')
                
                if result.status == 'completed':
                    result.verified_by = doctor
                    result.verified_at = timezone.now()
                
                result.save()
                messages.success(request, f'Lab result for {result.test.name} updated successfully.')
                
            except LabResult.DoesNotExist:
                messages.error(request, 'Lab result not found.')
            except Exception as e:
                messages.error(request, f'Error updating lab result: {str(e)}')
        
        elif action == 'create_lab_result':
            # Create new lab result directly
            test_name = request.POST.get('test_name', '')
            value = request.POST.get('value', '')
            units = request.POST.get('units', '')
            range_text = request.POST.get('range', '')
            status = request.POST.get('status', 'completed')
            is_abnormal = 'is_abnormal' in request.POST
            qualitative_result = request.POST.get('qualitative_result', '')
            notes = request.POST.get('notes', '')
            
            if test_name and value:
                try:
                    from .models import LabResult
                    
                    # Get or create lab test
                    lab_test, created = LabTest.objects.get_or_create(
                        name=test_name,
                        defaults={
                            'code': test_name.upper().replace(' ', '_'),
                            'specimen_type': 'Blood',
                            'is_active': True
                        }
                    )
                    
                    # Get or create lab order for this encounter
                    lab_order = Order.objects.filter(
                        encounter=encounter,
                        order_type='lab',
                        status='pending',
                        is_deleted=False
                    ).first()
                    
                    if not lab_order:
                        lab_order = Order.objects.create(
                            encounter=encounter,
                            order_type='lab',
                            status='pending',
                            requested_by=doctor,
                            priority='routine'
                        )
                    
                    # Parse range if provided (e.g., "3.5-7.0")
                    range_low = ''
                    range_high = ''
                    if range_text and '-' in range_text:
                        try:
                            parts = range_text.split('-')
                            range_low = parts[0].strip()
                            range_high = parts[1].strip()
                        except:
                            pass
                    
                    # Create lab result
                    result = LabResult.objects.create(
                        order=lab_order,
                        test=lab_test,
                        status=status,
                        value=value,
                        units=units,
                        range_low=range_low,
                        range_high=range_high,
                        is_abnormal=is_abnormal,
                        qualitative_result=qualitative_result,
                        notes=notes,
                        verified_by=doctor if status == 'completed' else None,
                        verified_at=timezone.now() if status == 'completed' else None
                    )
                    
                    messages.success(request, f'Lab result for {test_name} created successfully.')
                    
                except Exception as e:
                    messages.error(request, f'Error creating lab result: {str(e)}')
            else:
                messages.error(request, 'Test name and value are required.')
        
        elif action == 'delete_diagnosis':
            # Delete diagnosis from problem list
            from .models_advanced import ProblemList
            problem_id = request.POST.get('problem_id')
            
            if problem_id:
                try:
                    problem = ProblemList.objects.get(
                        pk=problem_id,
                        encounter=encounter,
                        is_deleted=False
                    )
                    problem_name = problem.problem
                    problem.is_deleted = True
                    problem.save(update_fields=['is_deleted'])
                    
                    messages.success(request, f'Diagnosis "{problem_name}" deleted successfully.')
                except ProblemList.DoesNotExist:
                    messages.error(request, 'Diagnosis not found.')
                except Exception as e:
                    messages.error(request, f'Error deleting diagnosis: {str(e)}')
            else:
                messages.error(request, 'Problem ID is required.')
        
        elif action == 'delete_prescription':
            # Delete prescription
            prescription_id = request.POST.get('prescription_id')
            
            if prescription_id:
                try:
                    prescription = Prescription.objects.get(
                        pk=prescription_id,
                        order__encounter=encounter,
                        is_deleted=False
                    )
                    drug_name = prescription.drug.name
                    prescription.is_deleted = True
                    prescription.save(update_fields=['is_deleted'])
                    
                    messages.success(request, f'Prescription for {drug_name} deleted successfully.')
                except Prescription.DoesNotExist:
                    messages.error(request, 'Prescription not found.')
                except Exception as e:
                    messages.error(request, f'Error deleting prescription: {str(e)}')
            else:
                messages.error(request, 'Prescription ID is required.')
        
        elif action == 'delete_order':
            # Delete order (lab, imaging, procedure, etc.)
            order_id = request.POST.get('order_id')
            
            if order_id:
                try:
                    order = Order.objects.get(
                        pk=order_id,
                        encounter=encounter,
                        is_deleted=False
                    )
                    order_type = order.get_order_type_display()
                    order.is_deleted = True
                    order.save(update_fields=['is_deleted'])
                    
                    messages.success(request, f'{order_type} order deleted successfully.')
                except Order.DoesNotExist:
                    messages.error(request, 'Order not found.')
                except Exception as e:
                    messages.error(request, f'Error deleting order: {str(e)}')
            else:
                messages.error(request, 'Order ID is required.')
        
        elif action == 'delete_clinical_note':
            # Delete clinical note
            from .models_advanced import ClinicalNote
            note_id = request.POST.get('note_id')
            
            if note_id:
                try:
                    note = ClinicalNote.objects.get(
                        pk=note_id,
                        encounter=encounter,
                        is_deleted=False
                    )
                    note_type = note.get_note_type_display()
                    note.is_deleted = True
                    note.save(update_fields=['is_deleted'])
                    
                    messages.success(request, f'{note_type} note deleted successfully.')
                except ClinicalNote.DoesNotExist:
                    messages.error(request, 'Clinical note not found.')
                except Exception as e:
                    messages.error(request, f'Error deleting clinical note: {str(e)}')
            else:
                messages.error(request, 'Note ID is required.')
        
        return redirect('hospital:consultation_view', encounter_id=encounter_id)
    
    # Get existing diagnoses/problems
    try:
        from .models_advanced import ProblemList, ClinicalNote
        problems = ProblemList.objects.filter(
            patient=encounter.patient,
            status='active',
            is_deleted=False
        ).order_by('-created')[:10]
        
        # Get ICD-10 descriptions for the problems
        diagnosis_code_map = {}
        if problems:
            try:
                from .models_diagnosis import DiagnosisCode
                icd10_codes = [p.icd10_code for p in problems if p.icd10_code]
                if icd10_codes:
                    diagnosis_codes = DiagnosisCode.objects.filter(
                        code__in=icd10_codes,
                        is_active=True,
                        is_deleted=False
                    ).values('code', 'short_description', 'description')
                    diagnosis_code_map = {
                        dc['code']: dc['short_description'] or dc['description']
                        for dc in diagnosis_codes
                    }
            except ImportError:
                pass
        
        # Add diagnosis description to each problem
        for problem in problems:
            if problem.icd10_code and problem.icd10_code in diagnosis_code_map:
                problem.icd10_description = diagnosis_code_map[problem.icd10_code]
            else:
                problem.icd10_description = None
        
        clinical_notes = ClinicalNote.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('created_by__user').order_by('-created')[:5]
    except ImportError:
        problems = []
        clinical_notes = []
    
    # Get patient's vital signs for display
    latest_vitals = encounter.vitals.filter(is_deleted=False).order_by('-recorded_at').first()
    
    # Get recent lab results
    recent_lab_results = []
    try:
        from .models import LabResult
        recent_lab_results = LabResult.objects.filter(
            order__encounter=encounter,
            status='completed',
            is_deleted=False
        ).select_related('test', 'verified_by__user').order_by('-verified_at')[:10]
    except:
        pass
    
    # Get referrals for this encounter
    referrals = []
    try:
        from .models_specialists import Referral
        referrals = Referral.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('specialist__staff__user', 'specialty').order_by('-referred_date')
    except:
        pass
    
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
    
    # Prepare summary data for completion modal
    # Get latest clinical note for pre-filling
    latest_note = clinical_notes[0] if clinical_notes else None
    
    # Build comprehensive summary for review
    consultation_summary = {
        'chief_complaint': encounter.chief_complaint or '',
        'diagnosis': encounter.diagnosis or '',
        'notes': encounter.notes or '',
        'subjective': latest_note.subjective if latest_note else '',
        'objective': latest_note.objective if latest_note else '',
        'assessment': latest_note.assessment if latest_note else (encounter.diagnosis or ''),
        'plan': latest_note.plan if latest_note else '',
        'prescriptions_count': existing_prescriptions.count(),
        'lab_orders_count': sum(1 for o in existing_orders if o.order_type == 'lab'),
        'imaging_orders_count': sum(1 for o in existing_orders if o.order_type == 'imaging'),
    }
    
    context = {
        'encounter': encounter,
        'patient': encounter.patient,
        'doctor': doctor,
        'available_drugs': available_drugs,
        'available_lab_tests': available_lab_tests,
        'existing_orders': existing_orders,
        'existing_prescriptions': existing_prescriptions,
        'problems': problems,
        'clinical_notes': clinical_notes,
        'latest_vitals': latest_vitals,
        'recent_lab_results': recent_lab_results,
        'referrals': referrals,
        'diagnosis_codes': diagnosis_codes,
        'consultation_summary': consultation_summary,
    }
    return render(request, 'hospital/consultation.html', context)


@login_required
def quick_consultation(request, patient_id):
    """Quick consultation - create encounter and start consultation"""
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    # Get current doctor
    try:
        doctor = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to access consultation.')
        return redirect('hospital:patient_detail', pk=patient_id)
    
    if request.method == 'POST':
        # Create new encounter
        form = EncounterForm(request.POST)
        if form.is_valid():
            encounter = form.save(commit=False)
            encounter.patient = patient
            encounter.provider = doctor
            encounter.status = 'active'
            encounter.save()
            
            messages.success(request, 'Consultation started.')
            return redirect('hospital:consultation_view', encounter_id=encounter.pk)
    else:
        # Pre-fill form with defaults
        initial_data = {
            'encounter_type': 'outpatient',
            'chief_complaint': '',
            'provider': doctor.pk,
        }
        form = EncounterForm(initial=initial_data)
    
    context = {
        'patient': patient,
        'form': form,
        'doctor': doctor,
    }
    return render(request, 'hospital/quick_consultation.html', context)


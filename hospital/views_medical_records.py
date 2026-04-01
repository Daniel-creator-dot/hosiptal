"""
Comprehensive Medical Records & Clinical Documentation System
For detailed forensic analysis and proper clinical reporting
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Prefetch
from datetime import timedelta

from .models import Patient, Encounter, Staff, VitalSign, LabResult, Order
from .models_advanced import Triage, ClinicalNote, Diagnosis, Procedure, CarePlan, ProblemList, ImagingStudy
from .models_medical_records import PatientDocument
from .utils_clinical_notes import dedupe_clinical_notes_timeline


def _get_current_staff(request):
    """Return current user's Staff profile if any."""
    if not request.user.is_authenticated:
        return None
    try:
        return Staff.objects.get(user=request.user, is_deleted=False)
    except Staff.DoesNotExist:
        return None


@login_required
def comprehensive_medical_record(request, patient_id):
    """
    Complete medical record view with forensic-level detail
    Shows entire patient history for clinical review
    """
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    # Continuity scope: include sibling patient rows with same MRN.
    # Prevents "empty" records when visits were saved under duplicate patient IDs.
    patient_scope_ids = [patient.id]
    patient_mrn = (getattr(patient, 'mrn', None) or '').strip()
    if patient_mrn:
        try:
            patient_scope_ids = list(
                Patient.objects.filter(mrn=patient_mrn, is_deleted=False).values_list('id', flat=True)
            ) or [patient.id]
        except Exception:
            patient_scope_ids = [patient.id]

    # Handle upload of external reports/scans (from other hospitals)
    if request.method == 'POST' and request.POST.get('action') == 'upload_external_report':
        title = (request.POST.get('title') or '').strip()
        description = (request.POST.get('description') or '').strip()
        uploaded_file = request.FILES.get('external_report_file')
        if not title:
            messages.error(request, 'Please enter a title for the document (e.g. "Lab results from XYZ Hospital").')
        elif not uploaded_file:
            messages.error(request, 'Please select a file to upload.')
        else:
            allowed_extensions = ('.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.doc', '.docx', '.dcm')
            max_file_size = 25 * 1024 * 1024  # 25MB
            fname = (getattr(uploaded_file, 'name', '') or '').lower()
            ext_ok = any(fname.endswith(ext) for ext in allowed_extensions)
            if not ext_ok:
                messages.error(request, 'Invalid file type. Allowed: PDF, JPG, PNG, GIF, WEBP, BMP, DOC, DOCX, DICOM.')
            elif uploaded_file.size > max_file_size:
                messages.error(request, f'File too large (max 25MB).')
            else:
                try:
                    current_staff = _get_current_staff(request)
                    PatientDocument.objects.create(
                        patient=patient,
                        encounter=None,
                        document_type='external_report',
                        title=title[:255],
                        description=description,
                        document_date=timezone.now().date(),
                        file=uploaded_file,
                        file_size=uploaded_file.size,
                        file_type=uploaded_file.content_type or 'application/octet-stream',
                        uploaded_by=current_staff,
                    )
                    messages.success(request, f'External report "{uploaded_file.name}" has been added to this patient\'s folder.')
                except Exception as e:
                    messages.error(request, f'Could not save file: {str(e)}. Please try again.')
        return redirect('hospital:comprehensive_medical_record', patient_id=patient.pk)

    # Get all encounters with related data (exclude front-desk registration-only; not clinical records)
    encounters = Encounter.objects.filter(
        patient_id__in=patient_scope_ids,
        is_deleted=False
    ).exclude(
        chief_complaint__iexact='New patient registration'
    ).select_related(
        'provider__user',
        'location'
    ).prefetch_related(
        'clinical_notes',
        'diagnoses',
        'procedures',
        'care_plans',
        'orders'
    ).order_by('-started_at', '-id')
    
    # Get all vital signs
    vital_signs = VitalSign.objects.filter(
        encounter__patient_id__in=patient_scope_ids,
        is_deleted=False
    ).order_by('-recorded_at')[:50]
    
    # Get all triage records
    triage_records = Triage.objects.filter(
        encounter__patient_id__in=patient_scope_ids,
        is_deleted=False
    ).select_related('encounter', 'triaged_by__user').order_by('-triage_time')
    
    # Get allergies and medications
    allergies = patient.allergies.split(',') if hasattr(patient, 'allergies') and patient.allergies else []
    current_medications = patient.current_medications.split(',') if hasattr(patient, 'current_medications') and patient.current_medications else []
    
    # Recent imaging studies with assets
    imaging_studies = ImagingStudy.objects.filter(
        patient_id__in=patient_scope_ids,
        is_deleted=False
    ).prefetch_related('images').order_by('-performed_at', '-created')[:6]

    # External reports/scans from other facilities (patient brings paper/PDF from elsewhere)
    external_documents = PatientDocument.objects.filter(
        patient_id__in=patient_scope_ids,
        document_type='external_report',
        is_deleted=False
    ).select_related('uploaded_by__user').order_by('-document_date', '-created')
    
    # Calculate statistics
    total_encounters = encounters.count()
    total_admissions = encounters.filter(encounter_type='inpatient').count()
    last_visit = encounters.first().started_at if encounters.exists() else None
    
    context = {
        'patient': patient,
        'encounters': encounters,
        'vital_signs': vital_signs,
        'triage_records': triage_records,
        'allergies': allergies,
        'current_medications': current_medications,
        'total_encounters': total_encounters,
        'total_admissions': total_admissions,
        'last_visit': last_visit,
        'medical_history': getattr(patient, 'medical_history', ''),
        'surgical_history': getattr(patient, 'surgical_history', ''),
        'family_history': getattr(patient, 'family_history', ''),
        'social_history': getattr(patient, 'social_history', ''),
        'recent_imaging': imaging_studies,
        'external_documents': external_documents,
    }
    
    return render(request, 'hospital/medical_records/comprehensive_record.html', context)


@login_required
def encounter_documentation(request, encounter_id):
    """
    Detailed encounter documentation view
    For comprehensive clinical note-taking
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'clinical_note':
            return save_clinical_note(request, encounter)
        elif action == 'diagnosis':
            return save_diagnosis(request, encounter)
        elif action == 'procedure':
            return save_procedure(request, encounter)
    
    # Get existing documentation (dedupe near-identical rows from double-save / auto-save)
    clinical_notes = dedupe_clinical_notes_timeline(
        list(
            ClinicalNote.objects.filter(
                encounter=encounter,
                is_deleted=False,
            ).select_related('created_by__user').order_by('-created')
        )
    )
    
    diagnoses = Diagnosis.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).order_by('-created')
    
    procedures = Procedure.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).order_by('-procedure_date')
    
    # Get lab tests and imaging
    lab_tests = LabResult.objects.filter(
        order__encounter=encounter,
        is_deleted=False
    ).select_related('test').order_by('-created')
    
    imaging_studies = ImagingStudy.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).prefetch_related('images').order_by('-created')
    
    # Get vital signs
    vital_signs = VitalSign.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).order_by('-recorded_at')
    
    # Get all documents/images for this encounter (including patient uploads)
    encounter_documents = PatientDocument.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).exclude(file='').exclude(file__isnull=True).select_related('uploaded_by__user').order_by('-created')
    
    context = {
        'encounter': encounter,
        'patient': encounter.patient,
        'clinical_notes': clinical_notes,
        'diagnoses': diagnoses,
        'procedures': procedures,
        'lab_tests': lab_tests,
        'imaging_studies': imaging_studies,
        'vital_signs': vital_signs,
        'encounter_documents': encounter_documents,
    }
    
    return render(request, 'hospital/medical_records/encounter_documentation.html', context)


def save_clinical_note(request, encounter):
    """Save comprehensive clinical note. Always creates a new note so saved notes show in the list."""
    is_auto_save = request.POST.get('auto_save') == 'true' or \
                  request.META.get('HTTP_X_AUTO_SAVE') == 'true'
    
    staff = _get_current_staff(request)
    note_type = request.POST.get('note_type', 'soap')
    subjective = request.POST.get('subjective', '')
    objective = request.POST.get('objective', '')
    assessment = request.POST.get('assessment', '')
    plan = request.POST.get('plan', '')
    notes = (request.POST.get('notes', '') or '').strip()
    
    if not notes and not any([subjective, objective, assessment, plan]):
        messages.warning(request, 'Please enter some note content before saving.')
        return redirect('hospital:encounter_documentation', encounter_id=encounter.pk)
    
    try:
        if is_auto_save:
            # For auto-save: Update existing draft note or create one if none exists
            draft_qs = ClinicalNote.objects.filter(
                encounter=encounter,
                note_type=note_type,
                is_deleted=False
            )
            if staff is not None:
                draft_qs = draft_qs.filter(created_by=staff)
            else:
                draft_qs = draft_qs.filter(created_by__isnull=True)
            draft_note = draft_qs.order_by('-created').first()
            
            if draft_note:
                # Update existing draft note
                draft_note.subjective = subjective
                draft_note.objective = objective
                draft_note.assessment = assessment
                draft_note.plan = plan
                draft_note.notes = notes
                draft_note.save(update_fields=['subjective', 'objective', 'assessment', 'plan', 'notes', 'modified'])
            else:
                # Create new draft note only if none exists
                ClinicalNote.objects.create(
                    encounter=encounter,
                    note_type=note_type,
                    subjective=subjective,
                    objective=objective,
                    assessment=assessment,
                    plan=plan,
                    notes=notes,
                    created_by=staff
                )
            
            # Return JSON response for auto-save
            from django.http import JsonResponse
            return JsonResponse({'status': 'saved', 'message': 'Draft saved'})
        else:
            # Manual save (e.g. "Save Note" on encounter documentation): always create a new note
            # so every save adds to the record history; no limit on number of notes.
            ClinicalNote.objects.create(
                encounter=encounter,
                note_type=note_type,
                subjective=subjective,
                objective=objective,
                assessment=assessment,
                plan=plan,
                notes=notes or '(No content)',
                created_by=staff
            )
            
            messages.success(request, 'Clinical note saved. It appears in the list above.')
    except Exception as e:
        if is_auto_save:
            from django.http import JsonResponse
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        messages.error(request, f'Error saving clinical note: {str(e)}')
    
    if is_auto_save:
        from django.http import JsonResponse
        return JsonResponse({'status': 'saved'})
    
    return redirect('hospital:encounter_documentation', encounter_id=encounter.pk)


def save_diagnosis(request, encounter):
    """Save diagnosis"""
    try:
        Diagnosis.objects.create(
            encounter=encounter,
            diagnosis_code=request.POST.get('diagnosis_code', ''),
            diagnosis_name=request.POST.get('diagnosis_name', ''),
            is_primary=request.POST.get('is_primary', 'true') == 'true'
        )
        
        messages.success(request, '✅ Diagnosis saved successfully')
    except Exception as e:
        messages.error(request, f'Error saving diagnosis: {str(e)}')
    
    return redirect('hospital:encounter_documentation', encounter_id=encounter.pk)


def save_procedure(request, encounter):
    """Save procedure"""
    try:
        Procedure.objects.create(
            encounter=encounter,
            procedure_name=request.POST.get('procedure_name', ''),
            procedure_code=request.POST.get('procedure_code', ''),
            notes=request.POST.get('notes', ''),
            procedure_date=timezone.now()
        )
        
        messages.success(request, '✅ Procedure recorded successfully')
    except Exception as e:
        messages.error(request, f'Error recording procedure: {str(e)}')
    
    return redirect('hospital:encounter_documentation', encounter_id=encounter.pk)


@login_required
def patient_timeline(request, patient_id):
    """
    Complete patient timeline - chronological view of all medical events
    """
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    patient_scope_ids = [patient.id]
    patient_mrn = (getattr(patient, 'mrn', None) or '').strip()
    if patient_mrn:
        try:
            patient_scope_ids = list(
                Patient.objects.filter(mrn=patient_mrn, is_deleted=False).values_list('id', flat=True)
            ) or [patient.id]
        except Exception:
            patient_scope_ids = [patient.id]
    
    # Collect all events
    events = []
    
    # Encounters (exclude front-desk registration-only; one per day to avoid duplicate display)
    enc_qs = Encounter.objects.filter(
        patient_id__in=patient_scope_ids, is_deleted=False
    ).exclude(chief_complaint__iexact='New patient registration').select_related('provider__user').order_by('-started_at', '-id')
    for encounter in enc_qs:
        provider_name = 'N/A'
        try:
            if encounter.provider and encounter.provider.user:
                provider_name = encounter.provider.user.get_full_name() or encounter.provider.user.username
        except Exception:
            pass
        
        events.append({
            'date': encounter.started_at,
            'type': 'encounter',
            'title': f'{encounter.get_encounter_type_display()} Visit',
            'description': f'Provider: {provider_name}',
            'object': encounter
        })
    
    # Diagnoses - OPTIMIZED: Use select_related to avoid N+1 queries
    for diagnosis in Diagnosis.objects.filter(patient_id__in=patient_scope_ids, is_deleted=False).select_related('encounter', 'diagnosis_code'):
        events.append({
            'date': diagnosis.diagnosis_date,
            'type': 'diagnosis',
            'title': f'Diagnosis: {diagnosis.diagnosis_name}',
            'description': diagnosis.notes,
            'object': diagnosis
        })
    
    # Investigations (Orders)
    for order in Order.objects.filter(encounter__patient_id__in=patient_scope_ids, is_deleted=False).select_related('requested_by__user', 'encounter'):
        order_description = f"{order.get_order_type_display()}"
        if order.notes:
            order_description += f" - {order.notes}"
        
        events.append({
            'date': order.requested_at,
            'type': 'investigation',
            'title': f'Order: {order.get_order_type_display()}',
            'description': order_description,
            'object': order
        })
    
    # Sort by date (handle None dates by putting them at the end)
    events.sort(key=lambda x: x['date'] if x['date'] else timezone.now() - timedelta(days=365*100), reverse=True)
    
    context = {
        'patient': patient,
        'events': events,
    }
    
    return render(request, 'hospital/medical_records/patient_timeline.html', context)

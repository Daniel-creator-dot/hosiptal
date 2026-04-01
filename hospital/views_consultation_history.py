"""
Consultation History & Patient Records Views
Allows doctors to review past consultations and patient visit history
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Count, Prefetch, Case, When, IntegerField
from django.utils import timezone
from datetime import timedelta
import logging
import uuid

from .models import Encounter, Patient, Staff, Prescription, Order, VitalSign
from .models import LabResult
from .models_queue import QueueEntry
from .utils_clinical_notes import dedupe_clinical_notes_timeline

logger = logging.getLogger(__name__)


@login_required
def patient_consultation_history(request, patient_id):
    """
    View all consultations/encounters for a patient
    Shows complete medical history with all details
    """
    patient = get_object_or_404(Patient, pk=patient_id, is_deleted=False)
    
    # Get all encounters for this patient
    encounters = Encounter.objects.filter(
        patient=patient,
        is_deleted=False
    ).select_related(
        'provider__user', 'provider__department'
    ).prefetch_related(
        Prefetch('orders', queryset=Order.objects.filter(is_deleted=False)),
        Prefetch('vitals', queryset=VitalSign.objects.filter(is_deleted=False).order_by('-recorded_at'))
    ).order_by('-started_at')
    
    # Get clinical notes for all encounters
    try:
        from .models_advanced import ClinicalNote, ProblemList
        
        clinical_notes = list(
            ClinicalNote.objects.filter(
                encounter__patient=patient,
                is_deleted=False
            ).select_related('encounter', 'created_by__user').order_by('-created')
        )
        clinical_notes = dedupe_clinical_notes_timeline(clinical_notes)
        
        problems = ProblemList.objects.filter(
            patient=patient,
            is_deleted=False
        ).select_related('encounter', 'created_by__user').order_by('-created')
    except ImportError:
        clinical_notes = []
        problems = []
    
    # Get prescriptions
    prescriptions = Prescription.objects.filter(
        order__encounter__patient=patient,
        is_deleted=False
    ).select_related('drug', 'prescribed_by__user', 'order__encounter').order_by('-created')
    
    # Statistics
    stats = {
        'total_encounters': encounters.count(),
        'active_encounters': encounters.filter(status='active').count(),
        'completed_encounters': encounters.filter(status='completed').count(),
        'total_prescriptions': prescriptions.count(),
        'active_problems': problems.filter(status='active').count() if problems else 0,
    }
    
    context = {
        'title': f'Consultation History - {patient.full_name}',
        'patient': patient,
        'encounters': encounters,
        'clinical_notes': clinical_notes,
        'problems': problems,
        'prescriptions': prescriptions,
        'stats': stats,
    }
    return render(request, 'hospital/patient_consultation_history.html', context)


@login_required
def encounter_full_record(request, encounter_id):
    """
    View complete record of a single encounter
    Shows everything that happened during this consultation
    """
    encounter = get_object_or_404(Encounter, pk=encounter_id, is_deleted=False)
    
    # Resolve current staff profile (if any)
    staff_member = None
    if request.user.is_authenticated:
        try:
            staff_member = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
        except Staff.DoesNotExist:
            staff_member = None
    
    def _safe_dispensing_record(prescription_obj):
        """Safely fetch dispensing record without raising when missing."""
        try:
            return prescription_obj.dispensing_record
        except ObjectDoesNotExist:
            return None
    
    # Allow inline actions from the encounter record (e.g., delete prescription)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_prescription':
            if not staff_member and not request.user.is_superuser:
                messages.error(request, 'Only clinical staff can delete prescriptions.')
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            prescription_id = request.POST.get('prescription_id')
            if not prescription_id:
                messages.error(request, 'Prescription ID is required.')
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            try:
                prescription = Prescription.objects.get(
                    pk=prescription_id,
                    order__encounter=encounter,
                    is_deleted=False
                )
            except Prescription.DoesNotExist:
                messages.error(request, 'Prescription not found or already removed.')
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            user_can_delete = request.user.is_superuser
            if not user_can_delete and staff_member:
                user_can_delete = (
                    staff_member == prescription.prescribed_by or
                    staff_member == encounter.provider
                )
            
            if not user_can_delete:
                messages.error(request, 'You can only delete prescriptions you authored for this encounter.')
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            dispensing_record = _safe_dispensing_record(prescription)
            blocking_reason = ''
            if dispensing_record:
                quantity_dispensed = getattr(dispensing_record, 'quantity_dispensed', 0) or 0
                payment_in_progress = getattr(dispensing_record, 'payment_receipt_id', None) or getattr(dispensing_record, 'payment_verified_at', None)
                is_dispensed = getattr(dispensing_record, 'is_dispensed', False)
                
                if is_dispensed or quantity_dispensed > 0:
                    blocking_reason = 'Medication has already been dispensed.'
                elif payment_in_progress:
                    blocking_reason = 'Payment has already been registered for this prescription.'
                elif getattr(dispensing_record, 'dispensing_status', '') not in ['pending_payment']:
                    blocking_reason = 'Dispensing is already in progress.'
            
            if blocking_reason:
                messages.error(request, blocking_reason)
                return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
            
            prescription.is_deleted = True
            prescription.save(update_fields=['is_deleted'])
            messages.success(request, f'Prescription for {prescription.drug.name} deleted successfully.')
            return redirect('hospital:encounter_full_record', encounter_id=encounter_id)
    
    # Get all related data
    vitals = encounter.vitals.filter(is_deleted=False).order_by('-recorded_at')
    orders = encounter.orders.filter(is_deleted=False).order_by('order_type', '-created')
    
    # Get prescriptions and enrich with user permissions
    prescriptions_qs = Prescription.objects.filter(
        order__encounter=encounter,
        is_deleted=False
    ).select_related('drug', 'prescribed_by__user')
    prescriptions = list(prescriptions_qs)
    
    def _get_prescription_block_reason(prescription):
        dispensing_record = _safe_dispensing_record(prescription)
        if not dispensing_record:
            return ''
        quantity_dispensed = getattr(dispensing_record, 'quantity_dispensed', 0) or 0
        if getattr(dispensing_record, 'is_dispensed', False) or quantity_dispensed > 0:
            return 'Dispensing already completed.'
        if getattr(dispensing_record, 'payment_receipt_id', None) or getattr(dispensing_record, 'payment_verified_at', None):
            return 'Payment already verified.'
        if getattr(dispensing_record, 'dispensing_status', '') not in ['pending_payment']:
            return 'Dispensing already in progress.'
        return ''
    
    can_delete_any_prescription = False
    for rx in prescriptions:
        rx.dispensing_record_obj = _safe_dispensing_record(rx)
        rx.delete_block_reason = _get_prescription_block_reason(rx)
        rx.can_user_delete = False
        if request.user.is_superuser:
            rx.can_user_delete = not bool(rx.delete_block_reason)
        elif staff_member:
            if staff_member == rx.prescribed_by or staff_member == encounter.provider:
                rx.can_user_delete = not bool(rx.delete_block_reason)
        if rx.can_user_delete:
            can_delete_any_prescription = True
    
    # Get lab results
    lab_results = LabResult.objects.filter(
        order__encounter=encounter,
        is_deleted=False
    ).select_related('test', 'verified_by__user')
    
    # Get clinical notes (doctor + nurse)
    try:
        from .models_advanced import ClinicalNote, ProblemList
        
        _cn_list = list(
            ClinicalNote.objects.filter(
                encounter=encounter,
                is_deleted=False
            ).select_related('created_by__user').order_by('-created')
        )
        _cn_list = dedupe_clinical_notes_timeline(_cn_list)
        clinical_notes = sorted(
            _cn_list,
            key=lambda n: n.created.timestamp()
            if getattr(n, 'created', None)
            else 0,
        )
        
        # Split progress notes by author: nurse notes and doctor notes (no limit)
        _progress_notes = [n for n in clinical_notes if getattr(n, "note_type", "") == "progress"]
        nurse_notes = [n for n in _progress_notes if getattr(getattr(n, "created_by", None), "profession", None) == "nurse"]
        doctor_notes = [n for n in _progress_notes if getattr(getattr(n, "created_by", None), "profession", None) == "doctor"]
        # Progress notes by other roles (e.g. midwife) appear in clinical_notes; nurse/doctor get dedicated sections
        
        problems = ProblemList.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('created_by__user')
    except ImportError:
        clinical_notes = []
        nurse_notes = []
        doctor_notes = []
        problems = []
    
    # Get imaging studies — no select_related to avoid invalid 'ordered_by' (ImagingStudy has no such field)
    try:
        from .models_advanced import ImagingStudy
        qs = ImagingStudy.objects.filter(encounter=encounter, is_deleted=False)
        imaging_studies = list(qs)  # force evaluation so template always gets a list, not a queryset
    except (ImportError, Exception):
        imaging_studies = []
    
    # Get referrals
    try:
        from .models_specialists import Referral
        referrals = Referral.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related(
            'specialist__staff__user',
            'specialty',
            'referring_doctor__user'
        )
    except ImportError:
        referrals = []
    
    # Patient flow stages for enhanced timeline
    flow_stages = []
    flow_summary = {
        'total': 0,
        'completed': 0,
        'percent': 0,
        'current': None,
        'next': None,
    }
    try:
        from .models_workflow import PatientFlowStage
        flow_qs = PatientFlowStage.objects.filter(
            encounter=encounter,
            is_deleted=False
        ).select_related('completed_by__user').order_by('created')
        flow_stages = list(flow_qs)
        flow_summary['total'] = len(flow_stages)
        flow_summary['completed'] = sum(1 for stage in flow_stages if stage.status == 'completed')
        if flow_summary['total']:
            flow_summary['percent'] = (flow_summary['completed'] / flow_summary['total']) * 100
            flow_summary['current'] = next(
                (stage for stage in flow_stages if stage.status in ['in_progress', 'pending']),
                None
            )
            if flow_summary['completed'] < flow_summary['total']:
                try:
                    flow_summary['next'] = flow_stages[flow_summary['completed']]
                except IndexError:
                    flow_summary['next'] = None
    except ImportError:
        pass
    
    # Calculate duration
    duration_minutes = encounter.get_duration_minutes()
    
    context = {
        'title': f'Encounter Record - {encounter.patient.full_name}',
        'encounter': encounter,
        'patient': encounter.patient,
        'vitals': vitals,
        'orders': orders,
        'prescriptions': prescriptions,
        'lab_results': lab_results,
        'clinical_notes': clinical_notes,
        'nurse_notes': nurse_notes,
        'doctor_notes': doctor_notes,
        'problems': problems,
        'imaging_studies': imaging_studies,
        'referrals': referrals,
        'duration_minutes': duration_minutes,
        'flow_stages': flow_stages,
        'flow_summary': flow_summary,
        'can_delete_any_prescription': can_delete_any_prescription,
    }
    return render(request, 'hospital/encounter_full_record.html', context)


@login_required
def my_consultations(request):
    """
    Show all consultations for the current doctor, or for another doctor when
    Health Service Provider filter is used. Allows doctors to view and consult
    patients under another doctor's consultations (e.g. when a doctor has closed shift).
    """
    try:
        doctor = Staff.objects.get(user=request.user, is_active=True, is_deleted=False)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to access consultations.')
        return redirect('hospital:dashboard')

    # Health Service Provider filter: when set, show that doctor's consultations
    # Note: Staff uses UUID primary key (BaseModel), not int
    # 'all' = all doctors' consultations; '' = my consultations; <uuid> = specific doctor
    provider_param = request.GET.get('provider', '').strip()
    show_all_doctors = provider_param == 'all'
    selected_provider_uuid = None
    if show_all_doctors:
        pass  # keep selected_provider_uuid None
    elif provider_param:
        try:
            selected_provider_uuid = uuid.UUID(provider_param)
        except (ValueError, TypeError):
            selected_provider_uuid = None

    # Filter options
    status_filter = request.GET.get('status', 'all')
    date_filter = request.GET.get('date', 'all')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    search = request.GET.get('search', '')

    # Providers for dropdown: only doctors (health service providers for consultations)
    try:
        providers = list(
            Staff.objects.filter(
                is_active=True,
                is_deleted=False,
                user__isnull=False,
                profession='doctor'
            )
            .select_related('user', 'department')
            .order_by('user__last_name', 'user__first_name', 'id')
        )
    except Exception:
        providers = []

    # Base queryset: all doctors, selected provider's consultations, or current doctor's
    # Deduplicate by (patient_id, minute) so the same consultation doesn't show twice (e.g. one Active + one Completed).
    from django.db import connection
    keep_ids = None
    try:
        if connection.vendor != 'postgresql':
            raise Exception('PostgreSQL required for DISTINCT ON')
        if show_all_doctors:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM (
                        SELECT DISTINCT ON (patient_id, date_trunc('minute', started_at))
                            id, started_at
                        FROM hospital_encounter
                        WHERE is_deleted = false
                        ORDER BY patient_id, date_trunc('minute', started_at) DESC,
                                 (CASE WHEN status = 'completed' THEN 0 ELSE 1 END), id DESC
                    ) sub
                    ORDER BY started_at DESC
                    LIMIT 50000
                    """
                )
                keep_ids = [row[0] for row in cursor.fetchall()]
        elif selected_provider_uuid:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM (
                        SELECT DISTINCT ON (patient_id, date_trunc('minute', started_at))
                            id, started_at
                        FROM hospital_encounter
                        WHERE is_deleted = false AND provider_id = %s
                        ORDER BY patient_id, date_trunc('minute', started_at) DESC,
                                 (CASE WHEN status = 'completed' THEN 0 ELSE 1 END), id DESC
                    ) sub
                    ORDER BY started_at DESC
                    LIMIT 50000
                    """,
                    [str(selected_provider_uuid)],
                )
                keep_ids = [row[0] for row in cursor.fetchall()]
        else:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM (
                        SELECT DISTINCT ON (e.patient_id, date_trunc('minute', e.started_at))
                            e.id, e.started_at
                        FROM hospital_encounter e
                        WHERE e.is_deleted = false
                          AND (e.provider_id = %s OR EXISTS (
                            SELECT 1 FROM hospital_order o
                            WHERE o.encounter_id = e.id AND o.requested_by_id = %s AND o.is_deleted = false
                          ))
                        ORDER BY e.patient_id, date_trunc('minute', e.started_at) DESC,
                                 (CASE WHEN e.status = 'completed' THEN 0 ELSE 1 END), e.id DESC
                    ) sub
                    ORDER BY started_at DESC
                    LIMIT 50000
                    """,
                    [str(doctor.id), str(doctor.id)],
                )
                keep_ids = [row[0] for row in cursor.fetchall()]
    except Exception:
        keep_ids = None

    if keep_ids:
        base_qs = (
            Encounter.objects.filter(id__in=keep_ids)
            .select_related('patient')
            .order_by('-started_at')
        )
    else:
        # Fallback when raw SQL fails or non-PostgreSQL: ORM only, dedupe in Python later
        if show_all_doctors:
            base_qs = (
                Encounter.objects.filter(is_deleted=False)
                .select_related('patient')
                .order_by('-started_at')
            )
        elif selected_provider_uuid:
            base_qs = (
                Encounter.objects.filter(
                    is_deleted=False,
                    provider_id=selected_provider_uuid
                )
                .select_related('patient')
                .order_by('-started_at')
            )
        else:
            base_qs = (
                Encounter.objects.filter(is_deleted=False)
                .filter(
                    Q(provider=doctor) | Q(orders__requested_by=doctor)
                )
                .select_related('patient')
                .distinct()
                .order_by('-started_at')
            )

    encounters = base_qs

    # Apply filters
    if status_filter != 'all':
        encounters = encounters.filter(status=status_filter)

    # Date range: custom date_from/date_to overrides preset date_filter
    if date_from or date_to:
        from datetime import datetime
        try:
            if date_from:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                encounters = encounters.filter(started_at__date__gte=date_from_obj)
            if date_to:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                encounters = encounters.filter(started_at__date__lte=date_to_obj)
        except ValueError:
            date_from = ''
            date_to = ''
    elif date_filter == 'today':
        today = timezone.now().date()
        encounters = encounters.filter(started_at__date=today)
    elif date_filter == 'week':
        week_ago = timezone.now() - timedelta(days=7)
        encounters = encounters.filter(started_at__gte=week_ago)
    elif date_filter == 'month':
        month_ago = timezone.now() - timedelta(days=30)
        encounters = encounters.filter(started_at__gte=month_ago)

    if search:
        encounters = encounters.filter(
            Q(patient__first_name__icontains=search) |
            Q(patient__last_name__icontains=search) |
            Q(patient__mrn__icontains=search) |
            Q(chief_complaint__icontains=search) |
            Q(diagnosis__icontains=search)
        )

    # Guarantee no duplicate (patient, same minute): dedupe in Python so list never shows same patient+time twice
    encounter_list = list(encounters)
    seen_key = {}
    deduped = []
    for enc in encounter_list:
        started = enc.started_at
        minute_key = (enc.patient_id, started.replace(second=0, microsecond=0) if started else None)
        if minute_key in seen_key:
            # Keep the one we prefer: completed over active, then higher id
            existing = seen_key[minute_key]
            enc_completed = 1 if (enc.status == 'completed') else 0
            ex_completed = 1 if (existing.status == 'completed') else 0
            if enc_completed > ex_completed or (enc_completed == ex_completed and enc.id > existing.id):
                idx = deduped.index(existing)
                deduped[idx] = enc
                seen_key[minute_key] = enc
            continue
        seen_key[minute_key] = enc
        deduped.append(enc)
    encounter_list = deduped

    today = timezone.now().date()
    encounter_ids = [e.id for e in encounter_list]
    call_patient_by_encounter = {}
    for enc in encounter_list:
        mrn = ''
        if enc.patient:
            mrn = getattr(enc.patient, 'mrn', '') or ''
        call_patient_by_encounter[str(enc.id)] = {
            'queue_id': '',
            'can_api_call': False,
            'display_ticket': mrn,
        }
    if encounter_ids:
        seen_queue_encounter = set()
        for qe in (
            QueueEntry.objects.filter(
                encounter_id__in=encounter_ids,
                queue_date=today,
                is_deleted=False,
            ).order_by('-check_in_time')
        ):
            eid = qe.encounter_id
            if not eid or eid in seen_queue_encounter:
                continue
            seen_queue_encounter.add(eid)
            key = str(eid)
            if key not in call_patient_by_encounter:
                continue
            info = call_patient_by_encounter[key]
            info['queue_id'] = str(qe.id)
            info['can_api_call'] = qe.status in ('checked_in', 'called')
            try:
                disp = qe.display_ticket_number
            except Exception:
                disp = ''
            if disp:
                info['display_ticket'] = disp

    queue_department = None
    queue_departments = []
    queue_assigned_entries = []
    queue_unassigned_entries = []
    current_room_assignment = None
    try:
        from .models import Department
        from .views_queue import _resolve_department

        queue_department = _resolve_department(request, request.user)
        queue_departments = list(
            Department.objects.filter(is_active=True, is_deleted=False).order_by('name')
        )
        queue_assigned_entries = list(
            QueueEntry.objects.filter(
                queue_date=today,
                is_deleted=False,
                assigned_doctor=request.user,
                status__in=['checked_in', 'called', 'vitals_completed', 'in_progress'],
            )
            .select_related('patient', 'department', 'encounter', 'encounter__patient')
            .order_by('department__name', 'status', 'priority', 'sequence_number')
        )
        # Everyone still "checked in" and unassigned, any department (Call next uses the same pool).
        unassigned_qs = (
            QueueEntry.objects.filter(
                queue_date=today,
                is_deleted=False,
                assigned_doctor__isnull=True,
                status='checked_in',
            )
            .select_related('patient', 'department', 'encounter', 'encounter__patient')
        )
        if queue_department:
            unassigned_qs = unassigned_qs.annotate(
                _dept_sort=Case(
                    When(department=queue_department, then=0),
                    When(department__isnull=True, then=1),
                    default=2,
                    output_field=IntegerField(),
                )
            ).order_by('_dept_sort', 'priority', 'sequence_number')
        else:
            unassigned_qs = unassigned_qs.order_by(
                'department__name', 'priority', 'sequence_number'
            )
        queue_unassigned_entries = list(unassigned_qs[:25])
        from .models_consulting_rooms import DoctorRoomAssignment

        current_room_assignment = (
            DoctorRoomAssignment.objects.filter(
                doctor=request.user,
                assignment_date=today,
                is_active=True,
                is_deleted=False,
            )
            .select_related('room')
            .first()
        )
    except Exception:
        pass

    # Statistics for the current view (selected provider or current doctor)
    stats = {
        'total': base_qs.count(),
        'today': base_qs.filter(started_at__date=today).count(),
        'active': base_qs.filter(status='active').count(),
        'completed_today': base_qs.filter(status='completed', ended_at__date=today).count(),
    }

    doctor_name = doctor.get_full_name() if hasattr(doctor, 'get_full_name') else doctor.user.get_full_name()
    selected_provider = None
    if selected_provider_uuid:
        selected_provider = next((p for p in providers if p.id == selected_provider_uuid), None)
        if not selected_provider:
            selected_provider = Staff.objects.filter(pk=selected_provider_uuid).select_related('user').first()

    context = {
        'title': f'My Consultations - Dr. {doctor_name}',
        'doctor': doctor,
        'encounters': encounter_list,
        'stats': stats,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
        'providers': providers,
        'selected_provider_id': selected_provider_uuid,  # UUID for template comparison with p.id
        'selected_provider': selected_provider,
        'show_all_doctors': show_all_doctors,
        'call_patient_by_encounter': call_patient_by_encounter,
        'queue_department': queue_department,
        'queue_departments': queue_departments,
        'queue_assigned_entries': queue_assigned_entries,
        'queue_unassigned_entries': queue_unassigned_entries,
        'current_room_assignment': current_room_assignment,
    }
    return render(request, 'hospital/my_consultations.html', context)




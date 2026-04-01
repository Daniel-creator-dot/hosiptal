"""
Consultation views for doctors to prescribe medications and order tests.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch, Count
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
import logging
import traceback
import json

from . import models as hospital_models
from .models import (
    Encounter, Patient, Order, Prescription, Drug, LabTest, LabResult, Staff,
    Invoice, InvoiceLine, ServiceCode, PharmacyStock, VitalSign
)

# Import advanced models at top level to avoid import errors
from .models_advanced import (
    ImagingCatalog, ImagingStudy, Procedure,
    ProblemList, Diagnosis, ClinicalNote
)

# Try to import ProcedureCatalog - may not exist on server yet
# Use a safer import method to avoid ImportError
ProcedureCatalog = None
try:
    import importlib
    try:
        models_advanced_module = importlib.import_module('hospital.models_advanced')
        if models_advanced_module and hasattr(models_advanced_module, 'ProcedureCatalog'):
            ProcedureCatalog = getattr(models_advanced_module, 'ProcedureCatalog', None)
    except (ImportError, ModuleNotFoundError, AttributeError):
        # Module doesn't exist or can't be imported
        ProcedureCatalog = None
except Exception:
    # Catch any other errors during import (including if importlib fails)
    ProcedureCatalog = None

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


from .decorators import role_required
from .consultation_post_handlers import (
    handle_order_lab_test_post,
    handle_prescribe_drug_post,
)
from .utils_clinical_notes import dedupe_clinical_notes_timeline


def _encounter_types_outpatient_like():
    """Visit types where duplicate intake + doctor encounters are common."""
    return frozenset({
        'outpatient', 'specialist', 'antenatal', 'gynae',
        'pre_employment', 'pre_admission', 'er', 'surgery',
    })


def vital_signs_queryset_for_consultation(encounter):
    """
    Vitals for this encounter plus same-visit vitals for the same patient.

    Nurses often chart on a different encounter UUID than the one the doctor opens. The old
    filter required sibling encounters to be active/completed and matched only by started_at
    date — that missed cancelled intakes, soft-deleted rows, null started_at, and midnight
    date skew. We merge using local calendar dates on recorded_at and encounter timestamps.
    """
    patient_id = encounter.patient_id
    visit_date = (
        timezone.localdate(encounter.started_at)
        if encounter.started_at
        else timezone.localdate()
    )
    today = timezone.localdate()
    day_set = {visit_date, today}

    outpatient_like = encounter.encounter_type in _encounter_types_outpatient_like()

    on_this_encounter = Q(encounter_id=encounter.id)

    if outpatient_like:
        by_recorded = Q()
        by_sibling_encounter = Q()
        for d in day_set:
            by_recorded |= Q(recorded_at__date=d)
            by_sibling_encounter |= Q(encounter__started_at__date=d)
            by_sibling_encounter |= Q(
                encounter__started_at__isnull=True,
                encounter__created__date=d,
            )
        # Patient-scoped branches: do not require encounter__is_deleted=False so vitals on a
        # soft-deleted or cancelled intake encounter still appear.
        return (
            VitalSign.objects.filter(is_deleted=False)
            .filter(
                on_this_encounter
                | (Q(encounter__patient_id=patient_id) & by_recorded)
                | (Q(encounter__patient_id=patient_id) & by_sibling_encounter)
            )
            .select_related('recorded_by', 'recorded_by__user', 'encounter')
            .order_by('-recorded_at')
        )

    # Inpatient only: keep vitals scoped to this encounter + same calendar day of admission on active siblings
    return (
        VitalSign.objects.filter(is_deleted=False)
        .filter(
            on_this_encounter
            | Q(
                encounter__patient_id=patient_id,
                encounter__started_at__date=visit_date,
                encounter__status__in=['active', 'completed'],
                encounter__is_deleted=False,
            )
        )
        .select_related('recorded_by', 'recorded_by__user', 'encounter')
        .order_by('-recorded_at')
    )


def vital_signs_for_consultation(encounter):
    """Return (latest_vital, ordered_queryset) for header + vitals tab + API."""
    qs = vital_signs_queryset_for_consultation(encounter)
    latest = qs.first()
    if latest is None and encounter.encounter_type in _encounter_types_outpatient_like():
        since = timezone.now() - timedelta(hours=48)
        qs = (
            VitalSign.objects.filter(
                is_deleted=False,
                encounter__patient_id=encounter.patient_id,
                recorded_at__gte=since,
            )
            .select_related('recorded_by', 'recorded_by__user', 'encounter')
            .order_by('-recorded_at')
        )
        latest = qs.first()
    return latest, qs


def _build_consultation_pricing_maps(encounter, available_drugs, available_lab_tests, available_imaging_studies):
    """
    Build drug/lab/imaging pricing maps for the consultation UI.
    Drug prices always use get_drug_price_for_prescription (same as prescribe sales, dispensing, and billing).
    Lab/imaging still use the pricing engine when the patient has insurance or corporate cover.
    """
    from .models import ServiceCode
    drug_pricing_map = {}
    lab_test_pricing_map = {}
    imaging_pricing_map = {}
    patient_payer = getattr(encounter.patient, 'primary_insurance', None)
    has_insurance = patient_payer and getattr(patient_payer, 'payer_type', None) in ('insurance', 'private', 'nhis')
    has_corporate = patient_payer and getattr(patient_payer, 'payer_type', None) == 'corporate'

    from .utils_billing import get_drug_price_for_prescription
    for drug in available_drugs:
        try:
            drug_pricing_map[drug.id] = float(
                get_drug_price_for_prescription(drug, patient_payer)
            )
        except Exception as e:
            logger.warning(f"Error getting drug price for consultation map {drug.id}: {e}")

    if not (has_insurance or has_corporate):
        return drug_pricing_map, lab_test_pricing_map, imaging_pricing_map
    try:
        from .services.pricing_engine_service import pricing_engine
        for test in available_lab_tests:
            try:
                test_service_code, _ = ServiceCode.objects.get_or_create(
                    code=f"LAB-{test.code if hasattr(test, 'code') else test.pk}",
                    defaults={
                        'description': test.name,
                        'category': 'Laboratory Services',
                        'is_active': True,
                    }
                )
                insurance_price = pricing_engine.get_service_price(test_service_code, encounter.patient, patient_payer)
                if insurance_price and insurance_price > 0:
                    lab_test_pricing_map[test.id] = float(insurance_price)
            except Exception as e:
                logger.warning(f"Error getting insurance price for lab test {test.id}: {e}")
        for study in available_imaging_studies:
            try:
                study_service_code, _ = ServiceCode.objects.get_or_create(
                    code=f"IMG-{study.code if hasattr(study, 'code') else study.pk}",
                    defaults={
                        'description': study.name,
                        'category': 'Imaging Services',
                        'is_active': True,
                    }
                )
                insurance_price = pricing_engine.get_service_price(study_service_code, encounter.patient, patient_payer)
                if insurance_price and insurance_price > 0:
                    imaging_pricing_map[study.id] = float(insurance_price)
            except Exception as e:
                logger.warning(f"Error getting insurance price for imaging study {study.id}: {e}")
    except Exception as e:
        logger.warning(f"Error setting up insurance pricing maps: {e}")
    return drug_pricing_map, lab_test_pricing_map, imaging_pricing_map


def _void_lab_invoice_lines_for_lab_result(lab_result):
    """
    When a doctor removes a lab test from a consultation, void the corresponding
    invoice line(s) so the cashier no longer shows the amount. Uses the same
    LAB-* service_code pattern as AutoBillingService.create_lab_bill.
    Also soft-deletes LabResultRelease so lab/cashier pending-payment queues drop it.
    """
    if not lab_result or not getattr(lab_result, 'order', None) or not lab_result.order.encounter:
        return
    from .models import Invoice, InvoiceLine
    encounter = lab_result.order.encounter
    test = getattr(lab_result, 'test', None)
    if not test:
        return
    # Must match hospital.services.auto_billing_service: LAB-{test.code or test.id or test.pk}
    lab_service_code = f"LAB-{test.code or test.id or test.pk}"

    invoices = list(Invoice.all_objects.filter(encounter=encounter, is_deleted=False))
    primary_voided = 0
    for invoice in invoices:
        updated = InvoiceLine.objects.filter(
            invoice=invoice,
            service_code__code=lab_service_code,
            is_deleted=False,
        ).update(is_deleted=True)
        primary_voided += updated
        if updated:
            invoice.update_totals()

    # If nothing matched (legacy billing used a different LAB-* code), void by exact description
    name = (getattr(test, 'name', None) or '').strip()
    if primary_voided == 0 and name:
        for invoice in invoices:
            updated = InvoiceLine.objects.filter(
                invoice=invoice,
                is_deleted=False,
                service_code__code__startswith='LAB-',
                description__iexact=name,
            ).update(is_deleted=True)
            if updated:
                invoice.update_totals()

    try:
        from hospital.models_payment_verification import LabResultRelease
        LabResultRelease.objects.filter(
            lab_result=lab_result, is_deleted=False
        ).update(is_deleted=True)
    except Exception:
        pass


@login_required
@role_required('doctor', 'pharmacist', 'nurse', 'admin', message='Access denied. Only doctors, pharmacists, and nurses can access consultation.')
def consultation_view(request, encounter_id):
    """
    Main consultation interface for doctors and pharmacists
    
    CRITICAL: Initialize all variables at function start to avoid UnboundLocalError.
    Python's scoping rules: if a variable is assigned anywhere in a function,
    it's treated as local for the entire function. Must initialize before any use.
    """
    # IMPORTANT: Use module-level timezone and timedelta imports (lines 10-11)
    # Do NOT create local variables with these names anywhere in this function
    # Explicitly reference module-level imports to avoid UnboundLocalError
    _timezone = timezone  # Reference module-level import
    _timedelta = timedelta  # Reference module-level import
    _logger = logger  # Reference module-level import
    
    # ========================================================================
    # CRITICAL: Initialize ALL variables that will be used later in the function
    # This prevents UnboundLocalError due to Python's scoping rules.
    # If a variable is assigned anywhere in the function, Python treats it as
    # local for the entire function scope, so it must be initialized first.
    # ========================================================================
    problems = []
    clinical_notes = []
    clinical_notes_calendar_data = []
    diagnosis_code_map = {}
    # Additional variables that might be used
    available_procedures = []
    procedures_by_category = {}
    available_drugs = None
    available_lab_tests = None
    available_imaging_studies = None
    imaging_by_modality = {}
    existing_orders = []
    existing_prescriptions = None
    latest_vitals = None
    vitals_intake_encounter_mismatch = False
    recent_lab_results = []
    referrals = []
    diagnosis_codes = []
    latest_note = None
    consultation_summary = {}
    preselected_drug = None
    
    # Optimized: Prefetch related data to avoid N+1 queries
    encounter = get_object_or_404(
        Encounter.objects.select_related('patient', 'patient__primary_insurance', 'provider', 'provider__user', 'provider__department', 'location'),
        pk=encounter_id, 
        is_deleted=False
    )
    # Continuity scope: include duplicate patient rows with same MRN.
    # Some workflows may create a new encounter under a sibling patient record.
    patient_scope_ids = [encounter.patient_id]
    patient_mrn = (getattr(encounter.patient, 'mrn', None) or '').strip()
    if patient_mrn:
        try:
            patient_scope_ids = list(
                Patient.objects.filter(mrn=patient_mrn, is_deleted=False).values_list('id', flat=True)
            ) or [encounter.patient_id]
        except Exception:
            patient_scope_ids = [encounter.patient_id]
    
    # Consultation expires at end of day after completion - allow view-only when expired
    consultation_read_only = encounter.consultation_expired()
    if consultation_read_only and request.method == 'POST':
        messages.warning(
            request,
            'This consultation has expired. You can view it in read-only mode but cannot make changes.'
        )
        return redirect('hospital:consultation_view', encounter_id=encounter_id)
    
    # Get current doctor/pharmacist/nurse (staff member) - optimized with select_related
    try:
        doctor = Staff.objects.select_related('user', 'department').get(user=request.user, is_active=True, is_deleted=False)
        # Additional check: ensure user is actually a doctor, pharmacist, or nurse
        if doctor.profession not in ['doctor', 'pharmacist', 'nurse'] and not request.user.is_superuser:
            messages.error(request, 'Access denied. Only doctors, pharmacists, and nurses can access consultation.')
            return redirect('hospital:encounter_detail', pk=encounter_id)
    except Staff.DoesNotExist:
        messages.error(request, 'You must be registered as staff to access consultation.')
        return redirect('hospital:encounter_detail', pk=encounter_id)

    
    # 🎯 ADD CONSULTATION CHARGE WHEN DOCTOR/PHARMACIST STARTS CONSULTATION (skip when view-only)
    # Check if this is the first time this doctor/pharmacist is accessing this consultation
    # by checking if consultation charge already exists
    if not consultation_read_only:
        try:
            from .utils_billing import add_consultation_charge, CONSULTATION_LINE_SERVICE_CODES
            from .models import Invoice, InvoiceLine

            # Use all_objects + invoice_id so lines on draft/zero-total invoices are visible (VisibleManager hides those invoices).
            encounter_inv_ids = Invoice.all_objects.filter(
                encounter=encounter, is_deleted=False
            ).values_list('pk', flat=True)
            consultation_charge_exists = (
                InvoiceLine.objects.filter(
                    invoice_id__in=encounter_inv_ids,
                    service_code__code__in=CONSULTATION_LINE_SERVICE_CODES,
                    is_deleted=False,
                ).exists()
                if encounter_inv_ids
                else False
            )

            if not consultation_charge_exists:
                # 🎯 IMMEDIATE CONSULTATION CHARGE - This is when consultation starts
                consultation_type = 'general'  # Default to general
                if encounter.encounter_type in ['er', 'emergency']:
                    consultation_type = 'specialist'
                elif doctor.department and 'specialist' in doctor.department.name.lower():
                    consultation_type = 'specialist'

                try:
                    invoice = add_consultation_charge(
                        encounter,
                        consultation_type=consultation_type,
                        doctor_staff=doctor,
                    )
                    if invoice:
                        _logger.info(
                            f"💰 Consultation charge added for encounter {encounter_id} "
                            f"(Patient: {encounter.patient.full_name}, Type: {consultation_type})"
                        )
                except Exception as charge_error:
                    _logger.error(
                        f"Failed to add consultation charge for encounter {encounter_id}: {charge_error}",
                        exc_info=True
                    )
        except Exception as e:
            # Don't block consultation if charge addition fails
            _logger.warning(f"Error checking/adding consultation charge: {e}")
    
    # Fast path: lab / prescribe POST without loading catalog lists (drugs, labs, imaging, etc.)
    if request.method == 'POST' and not consultation_read_only:
        _post_action = request.POST.get('action')
        if _post_action == 'prescribe_drug':
            return handle_prescribe_drug_post(request, encounter, doctor, encounter_id)
        if _post_action == 'order_lab_test':
            return handle_order_lab_test_post(request, encounter, doctor, encounter_id)
    
    # Get available drugs - USE CACHED VERSION for better performance with 200+ users
    from .utils_cache import get_cached_drugs
    from django.db.models import Q
    from collections import Counter
    
    try:
        cached_drugs = get_cached_drugs()
        # Single evaluation: one list() for drugs, then category_counts from that list (avoids extra DB query)
        if hasattr(cached_drugs, 'values_list'):
            available_drugs = list(cached_drugs[:300])
            category_counts = Counter(getattr(drug, 'category', None) for drug in available_drugs if getattr(drug, 'category', None))
        else:
            if isinstance(cached_drugs, (list, tuple)):
                available_drugs = cached_drugs[:500]
            else:
                available_drugs = list(cached_drugs)[:500] if hasattr(cached_drugs, '__iter__') else []
            category_counts = Counter(
                getattr(drug, 'category', None)
                for drug in available_drugs
                if hasattr(drug, 'category') and getattr(drug, 'category', None)
            )
    except Exception as e:
        _logger.error(f"Error loading drugs: {e}", exc_info=True)
        # Fallback to empty list - page should still load
        available_drugs = []
        category_counts = Counter()
    
    # Build category list with display names (from cached data)
    categories_list = []
    try:
        drug_categories_choices = getattr(Drug, 'CATEGORIES', [])
    except UnboundLocalError:
        # Safety net: if Python treats Drug as a local due to an assignment
        # elsewhere in this function in an older deployment, fall back gracefully.
        drug_categories_choices = []

    for category_code, count in category_counts.items():
        # Get display name from CATEGORIES choices if available, otherwise default to the raw code
        display_name = next(
            (name for code, name in drug_categories_choices if code == category_code),
            category_code,
        )
        categories_list.append(
            {
                'code': category_code,
                'name': display_name,
                'count': count,
            }
        )
    
    # Get available lab tests - USE CACHED VERSION for better performance
    from .utils_cache import get_cached_lab_tests
    try:
        cached_lab_tests = get_cached_lab_tests()
        # Convert queryset to list to avoid N+1 queries
        if hasattr(cached_lab_tests, '__iter__') and not isinstance(cached_lab_tests, (list, tuple)):
            available_lab_tests = list(cached_lab_tests[:500])  # Limit to prevent memory issues
        else:
            available_lab_tests = cached_lab_tests if isinstance(cached_lab_tests, (list, tuple)) else list(cached_lab_tests)[:500]
    except Exception as e:
        _logger.error(f"Error loading lab tests: {e}", exc_info=True)
        available_lab_tests = []
    
    # Get available imaging studies - USE CACHED VERSION for better performance
    from .utils_cache import get_cached_imaging_studies
    try:
        cached_imaging_studies = get_cached_imaging_studies()
        # Convert queryset to list to avoid N+1 queries
        if hasattr(cached_imaging_studies, '__iter__') and not isinstance(cached_imaging_studies, (list, tuple)):
            available_imaging_studies = list(cached_imaging_studies[:500])  # Limit to prevent memory issues
        else:
            available_imaging_studies = cached_imaging_studies if isinstance(cached_imaging_studies, (list, tuple)) else list(cached_imaging_studies)[:500]
        
        # Group imaging by modality for easier selection (optimized: single pass, use modality code not display)
        imaging_by_modality = {}
        try:
            modality_display_map = dict(ImagingStudy.MODALITY_CHOICES)
            for study in available_imaging_studies[:300]:  # Limit iteration
                modality_display = modality_display_map.get(study.modality, study.modality.title())
                if modality_display not in imaging_by_modality:
                    imaging_by_modality[modality_display] = []
                imaging_by_modality[modality_display].append(study)
        except:
            # Fallback if ImagingStudy not available
            for study in available_imaging_studies[:300]:  # Limit iteration
                modality_display = getattr(study, 'modality', 'Other').title()
                if modality_display not in imaging_by_modality:
                    imaging_by_modality[modality_display] = []
                imaging_by_modality[modality_display].append(study)
    except Exception as e:
        _logger.error(f"Error loading imaging studies: {e}", exc_info=True)
        available_imaging_studies = []
        imaging_by_modality = {}
    
    # Get available procedures - USE CACHED VERSION for better performance
    from .utils_cache import get_cached_procedures
    try:
        cached_procedures = get_cached_procedures()
        # Convert queryset to list to avoid N+1 queries
        if hasattr(cached_procedures, '__iter__') and not isinstance(cached_procedures, (list, tuple)):
            available_procedures = list(cached_procedures[:500])  # Limit to prevent memory issues
        else:
            available_procedures = cached_procedures if isinstance(cached_procedures, (list, tuple)) else list(cached_procedures)[:500]
    except Exception as e:
        _logger.error(f"Error loading procedures: {e}", exc_info=True)
        available_procedures = []
    
    # Group procedures by category for easier selection
    procedures_by_category = {}
    try:
        import importlib
        models_advanced_module = importlib.import_module('hospital.models_advanced')
        ProcedureCatalog = getattr(models_advanced_module, 'ProcedureCatalog', None)
        if ProcedureCatalog:
            category_display_map = dict(ProcedureCatalog.PROCEDURE_CATEGORIES)
            for procedure in available_procedures:
                category_display = category_display_map.get(procedure.category, procedure.category.replace('_', ' ').title())
                if category_display not in procedures_by_category:
                    procedures_by_category[category_display] = []
                procedures_by_category[category_display].append(procedure)
    except Exception as e:
        _logger.warning(f"Error grouping procedures: {e}")
        procedures_by_category = {}
    
    # Get existing orders for this encounter (with deduplication)
    # OPTIMIZED FOR 300+ USERS: Use select_related and prefetch_related efficiently
    # Note: Include encounter_id in only() to avoid conflicts when prefetching related prescriptions
    all_existing_orders = Order.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).select_related(
        'requested_by', 'requested_by__user',
        'encounter', 'encounter__patient'
    ).prefetch_related(
        'imaging_studies',
        Prefetch('lab_results', queryset=LabResult.objects.select_related('test').filter(is_deleted=False)),
        'prescriptions'
    ).only(
        'id', 'order_type', 'status', 'priority', 'requested_at', 'created', 'notes', 'encounter_id',
        'requested_by__id', 'requested_by__user__id', 'requested_by__user__first_name', 
        'requested_by__user__last_name', 'requested_by__user__username'
    ).order_by('-created')
    
    # Keep all non-deleted orders for this encounter.
    # Order IDs are already unique; collapsing by encounter/type hides valid multiple orders.
    existing_orders = list(all_existing_orders)

    # Full patient lab timeline (this visit + previous visits), used in consultation continuity UI.
    patient_lab_orders = list(
        Order.objects.filter(
            encounter__patient_id__in=patient_scope_ids,
            order_type='lab',
            is_deleted=False
        ).select_related(
            'requested_by', 'requested_by__user',
            'encounter', 'encounter__patient'
        ).prefetch_related(
            Prefetch('lab_results', queryset=LabResult.objects.select_related('test').filter(is_deleted=False))
        ).only(
            'id', 'order_type', 'status', 'priority', 'requested_at', 'created', 'notes', 'encounter_id',
            'requested_by__id', 'requested_by__user__id', 'requested_by__user__first_name',
            'requested_by__user__last_name', 'requested_by__user__username'
        ).order_by('-created')
    )
    
    # Get existing prescriptions for this encounter
    # OPTIMIZED FOR 300+ USERS: Efficient query with select_related
    # Note: Don't traverse order__encounter in select_related when using only() - causes FieldError
    all_prescriptions = hospital_models.Prescription.objects.filter(
        order__encounter=encounter,
        order__is_deleted=False,  # Also exclude prescriptions with deleted orders
        is_deleted=False
    ).select_related(
        'drug', 'prescribed_by', 'prescribed_by__user', 'order'
    ).only(
        'id', 'quantity', 'dose', 'frequency', 'duration', 'instructions', 'created',
        'drug__id', 'drug__name', 'drug__strength', 'drug__form', 'drug__unit_price',
        'prescribed_by__id', 'prescribed_by__user__first_name', 'prescribed_by__user__last_name',
        'order__id', 'order__status', 'order__encounter_id'  # Include encounter_id but don't traverse
    ).order_by('-created')
    
    # DEDUPLICATE: Group prescriptions by drug and keep the most recent one, sum quantities
    prescription_dict = {}
    for rx in all_prescriptions:
        drug_id = rx.drug.id
        if drug_id not in prescription_dict:
            prescription_dict[drug_id] = {
                'prescription': rx,
                'total_quantity': rx.quantity,
                'ids': [rx.id]
            }
        else:
            # Add quantity to existing prescription
            prescription_dict[drug_id]['total_quantity'] += rx.quantity
            prescription_dict[drug_id]['ids'].append(rx.id)
            # Keep the most recent prescription as the main one
            if rx.created > prescription_dict[drug_id]['prescription'].created:
                prescription_dict[drug_id]['prescription'] = rx
    
    # Create list of unique prescriptions with aggregated quantities
    existing_prescriptions = []
    for drug_id, data in prescription_dict.items():
        rx = data['prescription']
        # Add inventory quantity attribute
        rx.inventory_quantity = None
        rx.total_quantity = data['total_quantity']
        existing_prescriptions.append(rx)
    
    # Get inventory quantities from pharmacy store
    try:
        from .models_procurement import Store, InventoryItem
        pharmacy_store = Store.get_main_pharmacy_store()
        if pharmacy_store:
            drug_ids = [rx.drug.id for rx in existing_prescriptions]
            inventory_items = InventoryItem.objects.filter(
                store=pharmacy_store,
                drug_id__in=drug_ids,
                is_deleted=False,
                is_active=True
            ).values('drug_id', 'quantity_on_hand')
            
            # Create dictionary for quick lookup
            inventory_dict = {item['drug_id']: item['quantity_on_hand'] for item in inventory_items}
            
            # Attach inventory quantities to prescriptions
            for rx in existing_prescriptions:
                rx.inventory_quantity = inventory_dict.get(rx.drug.id, 0)
    except Exception as e:
        _logger.warning(f"Error getting inventory quantities: {e}")
        # Set default if error
        for rx in existing_prescriptions:
            if not hasattr(rx, 'inventory_quantity'):
                rx.inventory_quantity = None
    
    # Debug: Log prescription count and details (after deduplication)
    prescription_count = len(existing_prescriptions)
    if prescription_count > 0:
        _logger.info(f'Found {prescription_count} unique prescriptions (after deduplication) for encounter {encounter_id} (patient: {encounter.patient.full_name})')
        for rx in existing_prescriptions[:5]:  # Log first 5
            order_info = f"Order: {rx.order.id}" if rx.order else "NO ORDER"
            drug_info = rx.drug.name if rx.drug else "NO DRUG"
            inventory_qty = getattr(rx, 'inventory_quantity', 'N/A')
            total_qty = getattr(rx, 'total_quantity', rx.quantity)
            _logger.info(f'  - Prescription {rx.id}: {drug_info} (Qty: {total_qty}, Stock: {inventory_qty}) ({order_info})')
    else:
        _logger.debug(f'No prescriptions found for encounter {encounter_id}')
    
    # Handle form submissions (skip when viewing expired consultation read-only)
    if request.method == 'POST' and not consultation_read_only:
        action = request.POST.get('action')
        
        if action == 'order_imaging':
            # Create imaging order using ImagingCatalog
            imaging_catalog_ids = request.POST.getlist('imaging_catalog_ids')
            priority = request.POST.get('priority', 'routine')
            notes = (request.POST.get('clinical_indication') or request.POST.get('notes') or '').strip()
            
            if imaging_catalog_ids:
                try:
                    # Note: ImagingCatalog and ImagingStudy already imported at module level
                    if ImagingCatalog is None or ImagingStudy is None:
                        raise ImportError("ImagingCatalog or ImagingStudy not available")
                    
                    imaging_catalog_items = ImagingCatalog.objects.filter(
                        pk__in=imaging_catalog_ids,
                        is_active=True,
                        is_deleted=False,
                        name__isnull=False
                    ).exclude(
                        name__iexact=''
                    ).exclude(
                        name__icontains='INVALID'
                    )
                    
                    if imaging_catalog_items.exists():
                        # CRITICAL: Check for duplicate imaging orders for this encounter
                        # Look for existing pending imaging orders created in the last 2 minutes
                        # to prevent accidental duplicates from double-clicks or form resubmissions
                        time_threshold = _timezone.now() - _timedelta(minutes=2)
                        
                        recent_orders = Order.objects.filter(
                            encounter=encounter,
                            order_type='imaging',
                            status='pending',
                            is_deleted=False,
                            created__gte=time_threshold
                        ).order_by('-created')
                        
                        if recent_orders.exists():
                            # Check if the same catalog items are being ordered
                            catalog_ids_set = set(imaging_catalog_ids)
                            duplicate_order = None
                            
                            for existing_order in recent_orders:
                                # Get existing imaging studies for this order
                                existing_studies = ImagingStudy.objects.filter(
                                    order=existing_order,
                                    is_deleted=False
                                )
                                
                                # Try to match catalog items by checking if studies match
                                existing_catalog_ids = set()
                                for study in existing_studies:
                                    # Match by catalog code or name
                                    matching_catalogs = ImagingCatalog.objects.filter(
                                        Q(code=study.study_type) | Q(name__iexact=study.study_type),
                                        is_deleted=False,
                                        name__isnull=False
                                    ).exclude(
                                        name__iexact=''
                                    ).exclude(
                                        name__icontains='INVALID'
                                    )
                                    for catalog in matching_catalogs:
                                        existing_catalog_ids.add(str(catalog.pk))
                                
                                # If catalog IDs match (or if order was created very recently), it's likely a duplicate
                                if existing_catalog_ids == catalog_ids_set or (timezone.now() - existing_order.created).total_seconds() < 30:
                                    duplicate_order = existing_order
                                    break
                            
                            if duplicate_order:
                                messages.warning(
                                    request,
                                    f'⚠️ Duplicate imaging order detected! An identical order (#{duplicate_order.id}) was created {int((timezone.now() - duplicate_order.created).total_seconds())} seconds ago. '
                                    f'Please check the existing order or wait a moment before creating a new one.'
                                )
                                return redirect('hospital:consultation_view', encounter_id=encounter_id)
                        
                        # No duplicate found - proceed with creating new order
                        with transaction.atomic():
                            # Double-check for very recent duplicate (within last 5 minutes)
                            five_minutes_ago = _timezone.now() - _timedelta(minutes=5)
                            very_recent_order = Order.objects.filter(
                                encounter=encounter,
                                order_type='imaging',
                                is_deleted=False,
                                created__gte=five_minutes_ago
                            ).order_by('-created').first()
                            
                            if very_recent_order:
                                # Use existing order
                                imaging_order = very_recent_order
                                if notes:
                                    imaging_order.notes = notes
                                    imaging_order.save(update_fields=['notes'])
                            else:
                                # Create imaging order
                                imaging_order = Order.objects.create(
                                    encounter=encounter,
                                    order_type='imaging',
                                    status='pending',
                                    priority=priority,
                                    notes=notes,
                                    requested_by=doctor,
                                    requested_at=timezone.now()
                                )
                                
                                # Create ImagingStudy for each catalog item
                                created_studies = []
                                for catalog_item in imaging_catalog_items:
                                    # CRITICAL: Check for existing study more comprehensively
                                    # Check by order + patient + encounter + study_type (exact match)
                                    # Also check for recent duplicates (within last 5 minutes) to prevent rapid double-clicks
                                    time_threshold = _timezone.now() - _timedelta(minutes=5)
                                    
                                    existing_study = ImagingStudy.objects.filter(
                                        order=imaging_order,
                                        patient=encounter.patient,
                                        encounter=encounter,
                                        study_type=catalog_item.code or catalog_item.name,
                                        modality=catalog_item.modality,
                                        is_deleted=False
                                    ).first()
                                    
                                    # Also check for ANY existing duplicate (same patient + modality + study_type) regardless of time
                                    if not existing_study:
                                        # Check for any duplicate study for this patient/encounter with same modality and study_type
                                        duplicate_study = ImagingStudy.objects.filter(
                                            patient=encounter.patient,
                                            encounter=encounter,
                                            study_type=catalog_item.code or catalog_item.name,
                                            modality=catalog_item.modality,
                                            is_deleted=False
                                        ).exclude(order=imaging_order).order_by('-performed_at', '-created').first()
                                        
                                        if duplicate_study:
                                            # Check if the duplicate is very recent (within 1 hour) - if so, link it
                                            # Otherwise, it might be a legitimate separate study
                                            one_hour_ago = _timezone.now() - _timedelta(hours=1)
                                            if duplicate_study.created >= one_hour_ago or duplicate_study.performed_at and duplicate_study.performed_at >= one_hour_ago:
                                                # Link the existing study to this order instead of creating duplicate
                                                duplicate_study.order = imaging_order
                                                duplicate_study.save(update_fields=['order'])
                                                existing_study = duplicate_study
                                                created_studies.append(f"{catalog_item.name} (linked to existing)")
                                                continue  # Skip creating new study

                                    if not existing_study:
                                        imaging_study = ImagingStudy.objects.create(
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
                                        created_studies.append(catalog_item.name)
                                        
                                        # Auto-create bill so scan goes straight to cashier as a line item
                                        try:
                                            from .services.auto_billing_service import AutoBillingService
                                            result = AutoBillingService.create_imaging_bill(imaging_study)
                                            if not result.get('success'):
                                                _logger.warning('Imaging bill not created: %s', result.get('message') or result.get('error'))
                                                messages.warning(request, f"Scan added but billing failed: {result.get('message', 'add from cashier')}.")
                                        except Exception as e:
                                            _logger.warning('Could not auto-create imaging bill: %s', str(e), exc_info=True)
                                            messages.warning(request, f"Scan ordered. If it does not appear at cashier, add it from Add Services.")
                                    else:
                                        # Study already exists - update order reference if needed
                                        if existing_study.order != imaging_order:
                                            existing_study.order = imaging_order
                                            existing_study.save(update_fields=['order'])
                                
                                if created_studies:
                                    messages.success(
                                        request, 
                                        f'✅ Ordered {len(created_studies)} imaging study(ies) for {encounter.patient.full_name}: {", ".join(created_studies)}'
                                    )
                                else:
                                    messages.info(request, 'All selected imaging studies were already ordered for this encounter.')
                    else:
                        messages.error(request, 'No valid imaging studies selected.')
                except Exception as e:
                    _logger.error(f'Error creating imaging order: {str(e)}', exc_info=True)
                    messages.error(request, f'Error creating imaging order: {str(e)}')
            else:
                messages.error(request, 'Please select at least one imaging study.')
        
        elif action == 'record_vitals':
            # Record vital signs
            try:
                from .models import VitalSign
                
                # Get vital sign values from POST
                systolic_bp = request.POST.get('systolic_bp', '').strip()
                diastolic_bp = request.POST.get('diastolic_bp', '').strip()
                pulse = request.POST.get('pulse', '').strip()
                temperature = request.POST.get('temperature', '').strip()
                spo2 = request.POST.get('spo2', '').strip()
                respiratory_rate = request.POST.get('respiratory_rate', '').strip()
                weight = request.POST.get('weight', '').strip()
                height = request.POST.get('height', '').strip()
                blood_glucose = request.POST.get('blood_glucose', '').strip()
                consciousness_level = request.POST.get('consciousness_level', 'alert')
                pain_score = request.POST.get('pain_score', '').strip()
                supplemental_oxygen = request.POST.get('supplemental_oxygen') == 'on'
                oxygen_flow_rate = request.POST.get('oxygen_flow_rate', '').strip()
                position = request.POST.get('position', '')
                capillary_refill = request.POST.get('capillary_refill', '').strip()
                notes = request.POST.get('vitals_notes', '').strip()
                
                # Validate that at least one vital is provided
                vitals_provided = any([
                    systolic_bp, diastolic_bp, pulse, temperature, spo2, 
                    respiratory_rate, weight, height, blood_glucose, pain_score
                ])
                
                if not vitals_provided:
                    messages.error(request, 'Please enter at least one vital sign.')
                    return redirect('hospital:consultation_view', encounter_id=encounter_id)
                
                # Create vital signs record
                vital_sign = VitalSign.objects.create(
                    encounter=encounter,
                    recorded_by=doctor,
                    systolic_bp=int(systolic_bp) if systolic_bp else None,
                    diastolic_bp=int(diastolic_bp) if diastolic_bp else None,
                    pulse=int(pulse) if pulse else None,
                    temperature=float(temperature) if temperature else None,
                    spo2=int(spo2) if spo2 else None,
                    respiratory_rate=int(respiratory_rate) if respiratory_rate else None,
                    weight=float(weight) if weight else None,
                    height=float(height) if height else None,
                    blood_glucose=float(blood_glucose) if blood_glucose else None,
                    consciousness_level=consciousness_level,
                    pain_score=int(pain_score) if pain_score else None,
                    supplemental_oxygen=supplemental_oxygen,
                    oxygen_flow_rate=float(oxygen_flow_rate) if oxygen_flow_rate else None,
                    position=position if position else None,
                    capillary_refill=int(capillary_refill) if capillary_refill else None,
                    notes=notes
                )
                
                # Calculate NEWS2 score if possible
                try:
                    vital_sign.calculate_news2_score()
                    vital_sign.save()
                except:
                    pass
                
                messages.success(request, '✅ Vital signs recorded successfully!')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
                
            except ValueError as e:
                messages.error(request, f'Invalid value entered: {str(e)}. Please check your inputs.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            except Exception as e:
                _logger.error(f'Error recording vitals: {str(e)}', exc_info=True)
                messages.error(request, f'Error recording vital signs: {str(e)}')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
        
        elif action == 'order_procedure':
            # Create procedure order using ProcedureCatalog
            if not ProcedureCatalog:
                messages.error(request, 'Procedure catalog is not available. Please contact system administrator.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            
            procedure_catalog_ids = request.POST.getlist('procedure_catalog_ids')
            priority = request.POST.get('priority', 'routine')
            notes = request.POST.get('notes', '')
            scheduled_date = request.POST.get('scheduled_date')
            
            if procedure_catalog_ids:
                try:
                    from datetime import datetime
                    from decimal import Decimal
                    
                    procedure_catalog_items = ProcedureCatalog.objects.filter(
                        pk__in=procedure_catalog_ids,
                        is_active=True,
                        is_deleted=False,
                        name__isnull=False
                    ).exclude(
                        name__iexact=''
                    ).exclude(
                        name__icontains='INVALID'
                    )
                    
                    if procedure_catalog_items.exists():
                        # Parse scheduled date if provided
                        scheduled_datetime = None
                        if scheduled_date:
                            try:
                                scheduled_datetime = datetime.strptime(scheduled_date, '%Y-%m-%dT%H:%M')
                            except ValueError:
                                try:
                                    scheduled_datetime = datetime.strptime(scheduled_date, '%Y-%m-%d')
                                except ValueError:
                                    pass
                        
                        # Create procedure order
                        procedure_order = Order.objects.create(
                            encounter=encounter,
                            order_type='procedure',
                            status='pending',
                            priority=priority,
                            notes=notes or f'Procedure order: {", ".join([p.name for p in procedure_catalog_items])}',
                            requested_by=doctor,
                            requested_at=timezone.now()
                        )
                        
                        # Create Procedure records for each catalog item and auto-bill
                        created_procedures = []
                        total_charge = Decimal('0.00')
                        
                        for catalog_item in procedure_catalog_items:
                            # Create Procedure record
                            procedure = Procedure.objects.create(
                                encounter=encounter,
                                patient=encounter.patient,
                                procedure_code=catalog_item.code,
                                procedure_name=catalog_item.name,
                                description=catalog_item.description or notes,
                                performed_by=None,  # Will be set when procedure is performed
                                procedure_date=scheduled_datetime or timezone.now(),
                                location='',
                                notes=notes
                            )
                            created_procedures.append(procedure)
                            
                            # Auto-create bill for procedure (with charge)
                            try:
                                # Get or create service code for procedure
                                service_code, _ = ServiceCode.objects.get_or_create(
                                    code=catalog_item.code,
                                    defaults={
                                        'description': catalog_item.name,
                                        'category': 'procedure',
                                        'is_active': True
                                    }
                                )
                                
                                # Resolve payer for invoice
                                from .models import Payer
                                patient = encounter.patient
                                payer = patient.primary_insurance
                                if not payer:
                                    payer = Payer.objects.filter(
                                        payer_type='cash', is_active=True, is_deleted=False
                                    ).first() or Payer.objects.filter(is_active=True, is_deleted=False).first()
                                if not payer:
                                    payer = Payer.objects.create(
                                        name='Cash',
                                        payer_type='cash',
                                        is_active=True
                                    )
                                due_at = timezone.now() + timedelta(days=30)
                                # Get or create invoice for encounter
                                invoice, _ = Invoice.objects.get_or_create(
                                    encounter=encounter,
                                    is_deleted=False,
                                    defaults={
                                        'patient': patient,
                                        'payer': payer,
                                        'due_at': due_at,
                                        'status': 'draft',
                                        'total_amount': Decimal('0.00'),
                                    }
                                )
                                # Create invoice line for procedure
                                line_total = catalog_item.price
                                InvoiceLine.objects.create(
                                    invoice=invoice,
                                    service_code=service_code,
                                    description=f"{catalog_item.name} - {catalog_item.get_category_display()}",
                                    quantity=Decimal('1.00'),
                                    unit_price=catalog_item.price,
                                    line_total=line_total,
                                )
                                # Recalculate invoice total and balance from lines
                                invoice.update_totals()
                                
                                total_charge += catalog_item.price
                            except Exception as bill_error:
                                _logger.warning(f'Could not auto-create procedure bill for {catalog_item.name}: {bill_error}')
                        
                        messages.success(
                            request,
                            f'✅ Ordered {len(created_procedures)} procedure(s) for {encounter.patient.full_name}: '
                            f'{", ".join([p.procedure_name for p in created_procedures])}. '
                            f'Total charge: GHS {total_charge:.2f}'
                        )
                    else:
                        messages.error(request, 'No valid procedures selected.')
                except Exception as e:
                    _logger.error(f'Error creating procedure order: {str(e)}', exc_info=True)
                    messages.error(request, f'Error creating procedure order: {str(e)}')
            else:
                messages.error(request, 'Please select at least one procedure.')
        
        elif action == 'save_diagnosis':
            # Skip if this is an auto-save request (don't create diagnosis from auto-save)
            if request.POST.get('auto_save') == 'true':
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            # Save diagnosis to problem list and Diagnosis model
            # Note: ProblemList and Diagnosis already imported at module level
            if ProblemList is None or Diagnosis is None:
                msg = 'Diagnosis models not available.'
                messages.error(request, msg)
                if is_ajax:
                    return JsonResponse({'success': False, 'message': msg}, status=400)
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            
            from .models_diagnosis import DiagnosisCode
            
            icd10_code = request.POST.get('icd10_code', '').strip()
            problem = (
                request.POST.get('problem', '').strip()
                or request.POST.get('diagnosis_name', '').strip()
            )
            description = (
                request.POST.get('description', '')
                or request.POST.get('notes', '')
            )
            diagnosis_type = request.POST.get('diagnosis_type', 'primary')
            
            # Try to find DiagnosisCode
            diagnosis_code_obj = None
            if icd10_code:
                try:
                    diagnosis_code_obj = DiagnosisCode.objects.filter(
                        code=icd10_code,
                        is_active=True,
                        is_deleted=False
                    ).first()
                    if diagnosis_code_obj:
                        # Use the name from DiagnosisCode
                        problem = diagnosis_code_obj.short_description or diagnosis_code_obj.description
                        # Increment usage
                        diagnosis_code_obj.increment_usage()
                except Exception:
                    pass
            
            if problem or icd10_code:
                try:
                    # Create ProblemList entry (keep reference for AJAX response)
                    pl = ProblemList.objects.create(
                        patient=encounter.patient,
                        encounter=encounter,
                        icd10_code=icd10_code,
                        problem=problem or icd10_code,
                        description=description,
                        status='active',
                        created_by=doctor
                    )
                    
                    # Create Diagnosis entry with proper link to DiagnosisCode
                    Diagnosis.objects.create(
                        encounter=encounter,
                        patient=encounter.patient,
                        icd10_code=icd10_code,
                        diagnosis_code=diagnosis_code_obj,
                        diagnosis=problem or (diagnosis_code_obj.short_description if diagnosis_code_obj else icd10_code),
                        diagnosis_type=diagnosis_type,
                        description=description,
                        diagnosed_by=doctor
                    )
                    
                    # Update encounter diagnosis with name, not just code
                    diagnosis_display = problem or (diagnosis_code_obj.short_description if diagnosis_code_obj else icd10_code)
                    if icd10_code:
                        encounter.diagnosis = f"{encounter.diagnosis or ''}\n{diagnosis_display} ({icd10_code})".strip()
                    else:
                        encounter.diagnosis = f"{encounter.diagnosis or ''}\n{diagnosis_display}".strip()
                    encounter.save(update_fields=['diagnosis'])
                    
                    messages.success(request, f'Diagnosis "{diagnosis_display}" added successfully.')
                    if is_ajax:
                        return JsonResponse({
                            'success': True,
                            'message': f'Diagnosis "{diagnosis_display}" added.',
                            'problem': {
                                'id': pl.id,
                                'description': pl.problem or diagnosis_display,
                                'icd10_code': pl.icd10_code or '',
                            }
                        })
                except Exception as e:
                    msg = str(e)
                    messages.error(request, f'Error saving diagnosis: {msg}')
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': msg}, status=400)
            else:
                msg = 'Problem/diagnosis is required.'
                messages.error(request, msg)
                if is_ajax:
                    return JsonResponse({'success': False, 'message': msg}, status=400)
        
        elif action == 'save_note':
            # Check if this is an auto-save request
            is_auto_save = request.POST.get('auto_save') == 'true' or \
                          request.META.get('HTTP_X_AUTO_SAVE') == 'true'
            
            # Allow saving note without diagnosis so doctor notes always persist (diagnosis can be added later)
            if not is_auto_save and Diagnosis is not None:
                has_diagnosis = Diagnosis.objects.filter(encounter=encounter, is_deleted=False).exists()
                if not has_diagnosis:
                    messages.info(
                        request,
                        'Note saved. Add a diagnosis below when possible for the medical record.'
                    )
            
            # Note: ClinicalNote already imported at module level
            if ClinicalNote is None:
                messages.error(request, 'ClinicalNote model not available.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            
            note_type = request.POST.get('note_type', 'consultation')
            # Single-box clinical note: one field holds everything
            clinical_note = request.POST.get('clinical_note', '').strip()
            if not clinical_note:
                notes = request.POST.get('notes', '')
                subjective = request.POST.get('subjective', '')
                objective = request.POST.get('objective', '')
                assessment = request.POST.get('assessment', '')
                plan = request.POST.get('plan', '')
                clinical_note = '\n\n'.join(p for p in [subjective, notes, objective, assessment, plan] if (p or '').strip())
            if not (clinical_note or '').strip():
                messages.error(request, 'Please enter your clinical note before saving.')
                return redirect(reverse('hospital:consultation_view', kwargs={'encounter_id': encounter_id}))
            notes = clinical_note or ' '
            subjective = objective = assessment = plan = ''
            try:
                if is_auto_save:
                    # For auto-save: Update existing draft note or create one if none exists
                    draft_note = ClinicalNote.objects.filter(
                        encounter=encounter,
                        note_type=note_type,
                        created_by=doctor,
                        is_deleted=False
                    ).order_by('-created').first()
                    if draft_note:
                        draft_note.subjective = subjective
                        draft_note.objective = objective
                        draft_note.assessment = assessment
                        draft_note.plan = plan
                        draft_note.notes = notes
                        draft_note.save(update_fields=['subjective', 'objective', 'assessment', 'plan', 'notes', 'modified'])
                    else:
                        ClinicalNote.objects.create(
                            encounter=encounter,
                            note_type=note_type,
                            subjective=subjective,
                            objective=objective,
                            assessment=assessment,
                            plan=plan,
                            notes=notes,
                            created_by=doctor
                        )
                    return JsonResponse({'status': 'saved', 'message': 'Draft saved'})
                else:
                    # Allow additional notes even if one already exists for this encounter/note type.
                    # This keeps documentation collaborative across doctors.
                    ClinicalNote.objects.create(
                        encounter=encounter,
                        note_type=note_type,
                        subjective=subjective,
                        objective=objective,
                        assessment=assessment,
                        plan=plan,
                        notes=notes or ' ',
                        created_by=doctor
                    )
                    messages.success(request, 'Clinical note saved successfully. You can continue editing and save again anytime.')
                    return redirect(reverse('hospital:consultation_view', kwargs={'encounter_id': encounter_id}) + '?note_saved=1')
                
            except Exception as e:
                if is_auto_save:
                    return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
                _logger.exception('Error saving consultation note: %s', e)
                messages.error(request, f'Error saving note: {str(e)}')
                return redirect(reverse('hospital:consultation_view', kwargs={'encounter_id': encounter_id}))
        
        elif action == 'add_progress_note':
            # Add new note only (for "Add new note" button – other doctors adding progress/follow-up)
            # Does not update encounter.notes or chief_complaint; only creates a new ClinicalNote
            clinical_note = request.POST.get('clinical_note', '').strip()
            if not clinical_note:
                messages.error(request, 'Please enter your note before saving.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            if ClinicalNote is None:
                messages.error(request, 'ClinicalNote model not available.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            try:
                ClinicalNote.objects.create(
                    encounter=encounter,
                    note_type='progress',
                    subjective='',
                    objective='',
                    assessment='',
                    plan='',
                    notes=clinical_note,
                    created_by=doctor,
                )
                messages.success(request, '✅ New note saved. It appears in Clinical Notes and Previous history.')
                return redirect(reverse('hospital:consultation_view', kwargs={'encounter_id': encounter_id}) + '?note_saved=1')
            except Exception as e:
                _logger.exception('Error adding progress note: %s', e)
                messages.error(request, f'Error saving note: {str(e)}')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
        
        elif action == 'edit_progress_note':
            note_id = request.POST.get('note_id')
            if not note_id:
                messages.error(request, 'Note ID is required to edit.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            if ClinicalNote is None:
                messages.error(request, 'ClinicalNote model not available.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
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
                messages.success(request, 'Progress note updated successfully.')
            except ClinicalNote.DoesNotExist:
                messages.error(request, 'Note not found or does not belong to this consultation.')
            return redirect('hospital:consultation_view', encounter_id=encounter_id)
        
        elif action == 'update_consultation_note':
            # Allow doctor/superuser to edit the main consultation note after it was saved
            if getattr(doctor, 'profession', None) != 'doctor' and not request.user.is_superuser:
                messages.error(request, 'Only doctors can edit the clinical note.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            if ClinicalNote is None:
                messages.error(request, 'ClinicalNote model not available.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            clinical_note = request.POST.get('clinical_note', '').strip()
            if not clinical_note:
                messages.error(request, 'Please enter your clinical note before saving.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            existing_note = ClinicalNote.objects.filter(
                encounter=encounter,
                note_type='consultation',
                is_deleted=False
            ).order_by('-created').first()
            if not existing_note:
                messages.error(request, 'No consultation note found to update.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            try:
                existing_note.notes = clinical_note
                existing_note.save(update_fields=['notes'])
                messages.success(request, 'Clinical note updated successfully.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            except Exception as e:
                messages.error(request, f'Error updating note: {str(e)}')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
        
        elif action == 'update_encounter' or action == 'save_progress':
            # Check if this is an auto-save request
            is_auto_save = request.POST.get('auto_save') == 'true' or \
                          request.META.get('HTTP_X_AUTO_SAVE') == 'true'
            
            # Update encounter chief complaint, diagnosis, notes
            chief_complaint = request.POST.get('chief_complaint', '').strip()
            diagnosis = request.POST.get('diagnosis', '').strip()
            notes = request.POST.get('encounter_notes', '').strip()
            subjective = request.POST.get('subjective', '').strip()
            objective = request.POST.get('objective', '').strip()
            assessment = request.POST.get('assessment', '').strip()
            plan = request.POST.get('plan', '').strip()
            # Single-box clinical note (from Save progress / draft)
            clinical_note = request.POST.get('clinical_note', '').strip()
            if clinical_note:
                subjective = objective = assessment = plan = ''
                notes = notes or clinical_note  # use for encounter.notes if encounter_notes empty; progress note uses clinical_note below

            # CRITICAL: Ensure chief_complaint is not empty (required field in database)
            # Use existing chief_complaint if new one is empty
            if not chief_complaint and encounter.chief_complaint:
                chief_complaint = encounter.chief_complaint.strip()
            
            # If still empty, use a default value to prevent database constraint error
            if not chief_complaint:
                chief_complaint = 'Consultation in progress'  # Default value to prevent database error
            
            # Wrap all database operations in a transaction for atomicity
            try:
                with transaction.atomic():
                    # Update encounter (always update, even for auto-save)
                    encounter.chief_complaint = chief_complaint
                    if diagnosis:
                        encounter.diagnosis = diagnosis
                    if notes:
                        encounter.notes = notes
                    
                    # Save encounter - this may raise ValidationError or IntegrityError
                    encounter.save()
                    
                    # Save/update clinical note if SOAP fields or single clinical_note provided
                    progress_notes_content = clinical_note or notes or 'Progress note saved'
                    if any([subjective, objective, assessment, plan]) or clinical_note:
                        # Note: ClinicalNote already imported at module level
                        if ClinicalNote is None:
                            if is_auto_save:
                                return JsonResponse({'status': 'error', 'message': 'ClinicalNote model not available'})
                            messages.error(request, 'ClinicalNote model not available.')
                            return redirect('hospital:consultation_view', encounter_id=encounter_id)
                        
                        if is_auto_save:
                            # For auto-save: Update existing draft progress note or create one
                            draft_note = ClinicalNote.objects.filter(
                                encounter=encounter,
                                note_type='progress',
                                created_by=doctor,
                                is_deleted=False
                            ).order_by('-created').first()
                            
                            if draft_note:
                                # Update existing draft note
                                draft_note.subjective = subjective
                                draft_note.objective = objective
                                draft_note.assessment = assessment or diagnosis
                                draft_note.plan = plan
                                draft_note.notes = progress_notes_content
                                draft_note.save(update_fields=['subjective', 'objective', 'assessment', 'plan', 'notes', 'modified'])
                            else:
                                # Create new draft note only if none exists
                                ClinicalNote.objects.create(
                                    encounter=encounter,
                                    note_type='progress',
                                    subjective=subjective,
                                    objective=objective,
                                    assessment=assessment or diagnosis,
                                    plan=plan,
                                    notes=progress_notes_content,
                                    created_by=doctor
                                )
                            
                            # Return JSON response for auto-save
                            return JsonResponse({'status': 'saved', 'message': 'Draft saved'})
                        else:
                            # Manual save: Create new progress note
                            ClinicalNote.objects.create(
                                encounter=encounter,
                                note_type='progress',
                                subjective=subjective,
                                objective=objective,
                                assessment=assessment or diagnosis,
                                plan=plan,
                                notes=progress_notes_content,
                                created_by=doctor
                            )
                            messages.success(request, '✅ Consultation progress saved successfully. You can continue editing and save again anytime.')
                            return redirect(reverse('hospital:consultation_view', kwargs={'encounter_id': encounter_id}) + '?note_saved=1')
                    else:
                        # No SOAP fields - just update encounter
                        if is_auto_save:
                            return JsonResponse({'status': 'saved', 'message': 'Encounter updated'})
                        messages.success(request, '✅ Encounter information updated.')
                        # Redirect back to consultation page after manual save
                        return redirect('hospital:consultation_view', encounter_id=encounter_id)
                        
            except Exception as e:
                # Comprehensive error handling for all database and validation errors
                error_msg = str(e)
                _logger.error(f"Error saving consultation progress: {error_msg}", exc_info=True)
                
                if is_auto_save:
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'Error saving: {error_msg}'
                    }, status=500)
                
                # For manual saves, show error message and redirect
                messages.error(request, f'❌ Error saving consultation progress: {error_msg}')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
        
        elif action == 'complete_consultation':
            # CRITICAL: Never allow auto-save to complete consultations
            is_auto_save = request.POST.get('auto_save') == 'true' or \
                          request.META.get('HTTP_X_AUTO_SAVE') == 'true'
            
            if is_auto_save:
                # Auto-save should NEVER complete consultations - return error
                return JsonResponse({
                    'status': 'ignored',
                    'message': 'Consultation completion cannot be auto-saved'
                }, status=400)
            
            # Complete consultation - save all info and mark as complete
            try:
                # Update encounter with final details
                chief_complaint = request.POST.get('chief_complaint', '').strip()
                # Get diagnosis from diagnosis field (separate from final_assessment)
                diagnosis = request.POST.get('diagnosis', '').strip()
                # If diagnosis is empty, try to get from final_assessment as fallback
                if not diagnosis:
                    diagnosis = request.POST.get('final_assessment', '').strip()
                final_assessment = request.POST.get('final_assessment', '').strip()
                notes = request.POST.get('encounter_notes', '').strip()
                # Single clinical note from modal (replaces 5-part SOAP in UI)
                clinical_note = request.POST.get('clinical_note', '').strip()
                pmh = request.POST.get('clinical_note_notes', '').strip()  # legacy PMH field
                follow_up_instructions = request.POST.get('follow_up_instructions', '').strip()
                
                # Use existing chief_complaint if new one is empty
                if not chief_complaint and encounter.chief_complaint:
                    chief_complaint = encounter.chief_complaint.strip()
                
                # Ensure chief_complaint is not empty (required field in database)
                if not chief_complaint:
                    messages.error(request, '❌ Chief Complaint is required to complete consultation. Please enter the chief complaint.')
                    return redirect('hospital:consultation_view', encounter_id=encounter_id)
                
                # Wrap all database operations in a transaction for atomicity
                try:
                    with transaction.atomic():
                        # Update encounter fields - always set from modal so diagnosis/notes are saved
                        encounter.chief_complaint = chief_complaint
                        encounter.diagnosis = diagnosis or ''
                        encounter.notes = notes or ''
                        
                        # CRITICAL: Save diagnosis to Diagnosis model if provided
                        # This ensures diagnoses are properly tracked in the medical record
                        if diagnosis and Diagnosis is not None:
                            try:
                                from .models_diagnosis import DiagnosisCode
                                
                                # Check if diagnosis already exists for this encounter
                                existing_diagnosis = Diagnosis.objects.filter(
                                    encounter=encounter,
                                    diagnosis=diagnosis,
                                    is_deleted=False
                                ).first()
                                
                                if not existing_diagnosis:
                                    # Try to find matching DiagnosisCode
                                    diagnosis_code_obj = None
                                    # Extract ICD-10 code if present (format: "Diagnosis Name (B50.9)")
                                    import re
                                    code_match = re.search(r'\(([A-Z]\d{2}\.?\d*)\)', diagnosis)
                                    if code_match:
                                        icd10_code = code_match.group(1)
                                        try:
                                            diagnosis_code_obj = DiagnosisCode.objects.filter(
                                                code=icd10_code,
                                                is_active=True,
                                                is_deleted=False
                                            ).first()
                                        except:
                                            pass
                                    
                                    # Create Diagnosis record
                                    Diagnosis.objects.create(
                                        encounter=encounter,
                                        patient=encounter.patient,
                                        icd10_code=code_match.group(1) if code_match else '',
                                        diagnosis_code=diagnosis_code_obj,
                                        diagnosis=diagnosis.split('(')[0].strip() if '(' in diagnosis else diagnosis,
                                        diagnosis_type='primary',
                                        diagnosed_by=doctor
                                    )
                                    
                                    # Also create ProblemList entry
                                    if ProblemList is not None:
                                        ProblemList.objects.create(
                                            patient=encounter.patient,
                                            encounter=encounter,
                                            icd10_code=code_match.group(1) if code_match else '',
                                            problem=diagnosis.split('(')[0].strip() if '(' in diagnosis else diagnosis,
                                            status='active',
                                            created_by=doctor
                                        )
                            except Exception as diag_error:
                                _logger.warning(f'Could not save diagnosis to Diagnosis model: {diag_error}', exc_info=True)
                                # Don't fail the consultation completion if diagnosis save fails
                        
                        # Mark encounter as completed - explicit update_fields so diagnosis/notes persist
                        encounter.status = 'completed'
                        encounter.ended_at = timezone.now()
                        encounter.save(update_fields=[
                            'chief_complaint', 'diagnosis', 'notes', 'status', 'ended_at', 'modified'
                        ])

                        # Remove patient from queue immediately when consultation completes
                        # (mark queue entries as completed so ticket/name disappears from active queue views).
                        try:
                            completed_at = timezone.now()
                            today = completed_at.date()
                            from .models_queue import QueueEntry

                            # Some deployments create QueueEntry rows without linking `encounter` yet,
                            # so also complete today's active row for this patient.
                            QueueEntry.objects.filter(
                                is_deleted=False,
                            ).filter(
                                Q(encounter=encounter)
                                | Q(patient=encounter.patient, queue_date=today)
                            ).exclude(status__in=['completed', 'cancelled', 'no_show']).update(
                                status='completed',
                                completed_time=completed_at,
                            )
                        except Exception as queue_exc:
                            _logger.warning(
                                'Could not update QueueEntry on consultation completion: %s',
                                queue_exc,
                                exc_info=True,
                            )

                        try:
                            completed_at = timezone.now()
                            from .models_advanced import Queue as DepartmentQueue

                            DepartmentQueue.objects.filter(
                                encounter=encounter,
                                is_deleted=False,
                            ).exclude(status__in=['completed', 'skipped']).update(
                                status='completed',
                                completed_at=completed_at,
                            )
                        except Exception as adv_queue_exc:
                            _logger.warning(
                                'Could not update department Queue on consultation completion: %s',
                                adv_queue_exc,
                                exc_info=True,
                            )
                        
                        # Save final clinical note (check if one already exists to prevent duplicates)
                        # Note: ClinicalNote already imported at module level
                        if ClinicalNote is None:
                            # Log warning but continue - encounter is already saved
                            _logger.warning('ClinicalNote model not available during consultation completion')
                        else:
                            # Check if consultation note already exists (including recent ones within 5 minutes)
                            # Use module-level timedelta import (already imported at top of file)
                            five_minutes_ago = _timezone.now() - _timedelta(minutes=5)
                            
                            existing_note = ClinicalNote.objects.filter(
                                encounter=encounter,
                                note_type='consultation',
                                is_deleted=False
                            ).order_by('-created').first()
                            
                            # Also check for very recent duplicates (within 5 minutes)
                            if not existing_note or (existing_note and (timezone.now() - existing_note.created).total_seconds() > 300):
                                recent_duplicate = ClinicalNote.objects.filter(
                                    encounter=encounter,
                                    note_type='consultation',
                                    created__gte=five_minutes_ago,
                                    is_deleted=False
                                ).exclude(id=existing_note.id if existing_note else None).order_by('-created').first()
                                
                                if recent_duplicate:
                                    existing_note = recent_duplicate
                            
                            if existing_note:
                                # Notes are add-only: do not edit once saved (even on completion)
                                pass
                            else:
                                # Create new consultation note: single clinical_note or legacy 5-part
                                if clinical_note:
                                    ClinicalNote.objects.create(
                                        encounter=encounter,
                                        note_type='consultation',
                                        subjective='',
                                        objective='',
                                        assessment='',
                                        plan='',
                                        notes=clinical_note,
                                        created_by=doctor
                                    )
                                else:
                                    notes_content = pmh or ''
                                    if notes:
                                        notes_content = (notes_content + '\n\nCONSULTATION COMPLETED\n\n' + notes).strip()
                                    ClinicalNote.objects.create(
                                        encounter=encounter,
                                        note_type='consultation',
                                        subjective=request.POST.get('subjective', '').strip(),
                                        objective=request.POST.get('objective', '').strip(),
                                        assessment=(final_assessment or diagnosis or '').strip(),
                                        plan=(follow_up_instructions or 'Follow up as needed').strip(),
                                        notes=notes_content or 'Consultation completed.',
                                        created_by=doctor
                                    )
                except Exception as e:
                    _logger.error(f'Error completing consultation: {e}', exc_info=True)
                    messages.error(request, f'Error completing consultation: {str(e)}')
                    return redirect('hospital:consultation_view', encounter_id=encounter_id)
                
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
                            f"Your consultation with Dr. {doctor.user.get_full_name() if doctor.user else 'your doctor'} is complete. "
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
                        _logger.error(f"Error sending consultation complete SMS: {str(e)}")
                
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
                # Comprehensive error handling for all database and validation errors
                error_msg = str(e)
                _logger.error(f"Error completing consultation: {error_msg}", exc_info=True)
                messages.error(request, f'❌ Error completing consultation: {error_msg}. Please try again or contact support.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
        
        elif action == 'update_lab_result':
            # Update existing lab result
            result_id = request.POST.get('result_id')
            try:
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
                    
                    # Check for duplicate before creating
                    existing_result = LabResult.objects.filter(
                        order=lab_order,
                        test=lab_test,
                        is_deleted=False
                    ).first()
                    
                    if existing_result:
                        # Update existing result
                        existing_result.status = status
                        existing_result.value = value
                        existing_result.units = units
                        existing_result.range_low = range_low
                        existing_result.range_high = range_high
                        existing_result.is_abnormal = is_abnormal
                        existing_result.qualitative_result = qualitative_result
                        existing_result.notes = notes
                        existing_result.verified_by = doctor if status == 'completed' else existing_result.verified_by
                        existing_result.verified_at = timezone.now() if status == 'completed' else existing_result.verified_at
                        existing_result.save()
                        result = existing_result
                    else:
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
            is_ajax_delete = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            # Note: ProblemList already imported at module level
            if ProblemList is None:
                msg = 'ProblemList model not available.'
                messages.error(request, msg)
                if is_ajax_delete:
                    return JsonResponse({'success': False, 'message': msg}, status=400)
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
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
                    if is_ajax_delete:
                        return JsonResponse({'success': True, 'message': f'Diagnosis "{problem_name}" removed.'})
                except ProblemList.DoesNotExist:
                    msg = 'Diagnosis not found.'
                    messages.error(request, msg)
                    if is_ajax_delete:
                        return JsonResponse({'success': False, 'message': msg}, status=404)
                except Exception as e:
                    msg = str(e)
                    messages.error(request, f'Error deleting diagnosis: {msg}')
                    if is_ajax_delete:
                        return JsonResponse({'success': False, 'message': msg}, status=400)
            else:
                msg = 'Problem ID is required.'
                messages.error(request, msg)
                if is_ajax_delete:
                    return JsonResponse({'success': False, 'message': msg}, status=400)
        
        elif action == 'delete_prescription':
            # Delete prescription and cascade to pharmacy/invoice/cashier
            prescription_id = request.POST.get('prescription_id')

            if prescription_id:
                try:
                    prescription = hospital_models.Prescription.objects.get(
                        pk=prescription_id,
                        order__encounter=encounter,
                        is_deleted=False
                    )
                    drug_name = prescription.drug.name
                    # Cascade: waive invoice lines, cancel pharmacy dispensing
                    from hospital.services.prescription_cascade_service import cascade_prescription_deleted
                    cascade_prescription_deleted(prescription, waived_by_user=request.user)
                    prescription.is_deleted = True
                    prescription.save(update_fields=['is_deleted'])

                    messages.success(request, f'Prescription for {drug_name} removed. Pharmacy and cashier have been updated.')
                except hospital_models.Prescription.DoesNotExist:
                    messages.error(request, 'Prescription not found.')
                except Exception as e:
                    messages.error(request, f'Error deleting prescription: {str(e)}')
            else:
                messages.error(request, 'Prescription ID is required.')

        elif action == 'update_prescription':
            # Update prescription (dose, frequency, duration, quantity) and cascade to pharmacy/invoice
            prescription_id = request.POST.get('prescription_id')
            if prescription_id:
                try:
                    prescription = hospital_models.Prescription.objects.get(
                        pk=prescription_id,
                        order__encounter=encounter,
                        is_deleted=False
                    )
                    # Only allow update if not yet dispensed
                    try:
                        from django.db.models import ObjectDoesNotExist
                        disp = prescription.dispensing_record
                        if disp and getattr(disp, "is_dispensed", False):
                            messages.warning(request, 'Cannot edit: this prescription has already been dispensed.')
                            return redirect('hospital:consultation_view', encounter_id=encounter_id)
                    except ObjectDoesNotExist:
                        pass
                    updated = False
                    if request.POST.get('quantity') is not None:
                        try:
                            qty = int(request.POST.get('quantity'))
                            if qty > 0:
                                prescription.quantity = qty
                                updated = True
                        except (TypeError, ValueError):
                            pass
                    if request.POST.get('dose') is not None:
                        prescription.dose = (request.POST.get('dose') or '').strip() or prescription.dose
                        updated = True
                    if request.POST.get('route') is not None:
                        prescription.route = (request.POST.get('route') or '').strip() or prescription.route
                        updated = True
                    if request.POST.get('frequency') is not None:
                        prescription.frequency = (request.POST.get('frequency') or '').strip() or prescription.frequency
                        updated = True
                    if request.POST.get('duration') is not None:
                        prescription.duration = (request.POST.get('duration') or '').strip() or prescription.duration
                        updated = True
                    if request.POST.get('instructions') is not None:
                        prescription.instructions = (request.POST.get('instructions') or '').strip()
                        updated = True
                    if updated:
                        prescription.save(update_fields=['quantity', 'dose', 'route', 'frequency', 'duration', 'instructions', 'modified'])
                        from hospital.services.prescription_cascade_service import cascade_prescription_updated
                        cascade_prescription_updated(prescription, waived_by_user=request.user)
                        messages.success(request, f'Prescription for {prescription.drug.name} updated. Pharmacy and cashier have been updated.')
                    else:
                        messages.info(request, 'No changes to save.')
                except hospital_models.Prescription.DoesNotExist:
                    messages.error(request, 'Prescription not found.')
                except Exception as e:
                    messages.error(request, f'Error updating prescription: {str(e)}')
            else:
                messages.error(request, 'Prescription ID is required.')
        
        elif action == 'delete_lab_result':
            # Delete (soft-delete) a single lab test from an order
            result_id = request.POST.get('lab_result_id')
            if result_id:
                try:
                    result = LabResult.objects.get(
                        pk=result_id,
                        order__encounter=encounter,
                        is_deleted=False
                    )
                    # Void invoice line(s) for this lab so cashier no longer charges for it
                    _void_lab_invoice_lines_for_lab_result(result)
                    result.is_deleted = True
                    result.save(update_fields=['is_deleted'])
                    messages.success(request, f'Lab test "{result.test.name}" removed from order.')
                except LabResult.DoesNotExist:
                    messages.error(request, 'Lab result not found.')
                except Exception as e:
                    messages.error(request, f'Error removing lab test: {str(e)}')
            else:
                messages.error(request, 'Lab result ID is required.')

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
                    # If lab order: void invoice lines for each lab result so cashier no longer charges
                    if getattr(order, 'order_type', None) == 'lab':
                        for lab_result in order.lab_results.filter(is_deleted=False).select_related('test'):
                            _void_lab_invoice_lines_for_lab_result(lab_result)
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

        elif action == 'edit_lab_order':
            order_id = request.POST.get('order_id')
            notes = (request.POST.get('notes') or '').strip()
            priority = (request.POST.get('priority') or 'routine').strip()
            amount_override = request.POST.get('amount_override', '').strip()
            if order_id:
                try:
                    order = Order.objects.get(
                        pk=order_id,
                        encounter=encounter,
                        is_deleted=False,
                        order_type='lab'
                    )
                    order.notes = notes[:2000] if notes else ''
                    order.priority = priority
                    order.save(update_fields=['notes', 'priority'])
                    if amount_override:
                        try:
                            from decimal import Decimal
                            from .models import InvoiceLine
                            amt = Decimal(amount_override)
                            if amt >= 0:
                                for lab_result in order.lab_results.filter(is_deleted=False):
                                    InvoiceLine.objects.filter(
                                        invoice__encounter=encounter,
                                        invoice__patient=encounter.patient,
                                        is_deleted=False,
                                        waived_at__isnull=True,
                                        service_code__code__startswith='LAB-'
                                    ).filter(
                                        description__icontains=lab_result.test.name
                                    ).update(unit_price=amt, line_total=amt)
                                for inv in order.encounter.invoices.filter(is_deleted=False):
                                    inv.update_totals()
                        except Exception:
                            pass
                    messages.success(request, 'Lab order updated.')
                except Order.DoesNotExist:
                    messages.error(request, 'Lab order not found.')
                except Exception as e:
                    messages.error(request, f'Error updating lab order: {str(e)}')
            else:
                messages.error(request, 'Order ID is required.')

        elif action == 'edit_imaging_order':
            order_id = request.POST.get('order_id')
            notes = (request.POST.get('clinical_indication') or request.POST.get('notes') or '').strip()
            priority = (request.POST.get('priority') or 'routine').strip()
            amount_override = request.POST.get('amount_override', '').strip()
            if order_id:
                try:
                    order = Order.objects.get(
                        pk=order_id,
                        encounter=encounter,
                        is_deleted=False,
                        order_type='imaging'
                    )
                    order.notes = notes[:2000] if notes else ''
                    order.priority = priority
                    order.save(update_fields=['notes', 'priority'])
                    for study in order.imaging_studies.filter(is_deleted=False):
                        study.clinical_indication = notes[:2000] if notes else ''
                        study.save(update_fields=['clinical_indication'])
                    if amount_override:
                        try:
                            from decimal import Decimal
                            from .models import InvoiceLine
                            amt = Decimal(amount_override)
                            if amt >= 0:
                                for study in order.imaging_studies.filter(is_deleted=False):
                                    InvoiceLine.objects.filter(
                                        invoice__encounter=encounter,
                                        invoice__patient=encounter.patient,
                                        is_deleted=False,
                                        waived_at__isnull=True,
                                        description__icontains=(study.study_type or '')
                                    ).update(unit_price=amt, line_total=amt)
                                for inv in order.encounter.invoices.filter(is_deleted=False):
                                    inv.update_totals()
                        except Exception:
                            pass
                    messages.success(request, 'Imaging order updated.')
                except Order.DoesNotExist:
                    messages.error(request, 'Imaging order not found.')
                except Exception as e:
                    messages.error(request, f'Error updating imaging order: {str(e)}')
            else:
                messages.error(request, 'Order ID is required.')

        elif action == 'delete_clinical_note':
            # Delete clinical note
            # Note: ClinicalNote already imported at module level
            if ClinicalNote is None:
                messages.error(request, 'ClinicalNote model not available.')
                return redirect('hospital:consultation_view', encounter_id=encounter_id)
            
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
    # Variables already initialized at function start, now populate them
    try:
        # Note: ProblemList and ClinicalNote already imported at module level
        # Try to use them if available
        try:
            if ProblemList is not None and ClinicalNote is not None:
                problems = ProblemList.objects.filter(
                    patient=encounter.patient,
                    status='active',
                    is_deleted=False
                ).order_by('-created')
                
                # Encounter-scoped notes (for this visit’s summary / latest consultation note only)
                clinical_notes = list(ClinicalNote.objects.filter(
                    encounter=encounter,
                    is_deleted=False
                ).select_related('created_by', 'created_by__user').order_by('-created'))
            else:
                # Models are None, use empty lists
                problems = []
                clinical_notes = []
                clinical_notes_calendar_data = []
        except (NameError, AttributeError, TypeError) as model_error:
            # Models not imported or not available
            _logger.warning(f"Models not available: {model_error}")
            problems = []
            clinical_notes = []
            clinical_notes_calendar_data = []
        except Exception as db_error:
            # Database error when querying
            _logger.warning(f"Error querying problems/clinical notes: {db_error}")
            problems = []
            clinical_notes = []
            clinical_notes_calendar_data = []
        
        # Get ICD-10 descriptions for the problems
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
            except Exception as diag_error:
                _logger.warning(f"Error loading diagnosis codes: {diag_error}")
        
        # Add diagnosis description to each problem
        if problems and diagnosis_code_map:
            for problem in problems:
                try:
                    if problem.icd10_code and problem.icd10_code in diagnosis_code_map:
                        problem.icd10_description = diagnosis_code_map[problem.icd10_code]
                    else:
                        problem.icd10_description = None
                except Exception:
                    problem.icd10_description = None
                    
    except Exception as e:
        # Fallback if models are not available
        _logger.warning(f"Error loading problems/clinical notes: {e}", exc_info=True)
        # Variables already initialized at function start (lines 71-73)
        # Just ensure they're in a safe state
        problems = []
        clinical_notes = []
        clinical_notes_calendar_data = []
        diagnosis_code_map = {}
    
    # Vitals: include same-day sibling active encounters so nurse intake vitals appear in consulting
    latest_vitals, vitals_history = vital_signs_for_consultation(encounter)
    vitals_intake_encounter_mismatch = bool(
        latest_vitals
        and getattr(latest_vitals, 'encounter_id', None)
        and latest_vitals.encounter_id != encounter.id
    )

    # Full patient notes timeline across encounters (unified view for all doctors)
    patient_clinical_notes = []
    patient_clinical_notes_calendar_data = []
    patient_clinical_notes_for_json = []
    if ClinicalNote is not None:
        try:
            patient_clinical_notes = list(
                ClinicalNote.objects.filter(
                    encounter__patient_id__in=patient_scope_ids,
                    is_deleted=False
                ).select_related(
                    'created_by',
                    'created_by__user',
                    'encounter',
                ).order_by('-created')
            )
            patient_clinical_notes = dedupe_clinical_notes_timeline(patient_clinical_notes)
            for n in patient_clinical_notes:
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
                patient_clinical_notes_calendar_data.append({
                    'id': str(n.id),
                    'date': date_str or '',
                    'time': time_str or '',
                    'author': author,
                    'summary': summary,
                    'type': getattr(n, 'note_type', None) or 'progress',
                    'plan': (n.plan or '')[:500],
                    'assessment': (n.assessment or '')[:500],
                    'encounter_id': str(getattr(n, 'encounter_id', '') or ''),
                })
            patient_clinical_notes_for_json = [
                {
                    'type': n.get_note_type_display() if hasattr(n, 'get_note_type_display') else getattr(n, 'note_type', ''),
                    'created': n.created.isoformat() if getattr(n, 'created', None) else '',
                    'created_by': (n.created_by.user.get_full_name() or n.created_by.user.username) if getattr(n, 'created_by', None) and getattr(n.created_by, 'user', None) else '',
                    'subjective': (n.subjective or ''),
                    'objective': (n.objective or ''),
                    'assessment': (n.assessment or ''),
                    'plan': (n.plan or ''),
                    'notes': (getattr(n, 'notes', None) or ''),
                    'encounter_id': str(getattr(n, 'encounter_id', '') or ''),
                    'visit_date': (
                        n.encounter.started_at.isoformat()
                        if getattr(n, 'encounter', None) and getattr(n.encounter, 'started_at', None)
                        else ''
                    ),
                }
                for n in patient_clinical_notes
            ]
        except Exception:
            patient_clinical_notes = []
            patient_clinical_notes_calendar_data = []
            patient_clinical_notes_for_json = []

    # Calendar + modal JSON use full patient timeline (same as template "Previous history")
    clinical_notes_calendar_data = patient_clinical_notes_calendar_data

    # Get recent lab results for this encounter (for backward compatibility)
    recent_lab_results = []
    # Get all previous + current lab results for this patient (all visits) – for Labs & Imaging quick-view
    patient_lab_results = []
    try:
        from django.db.models import Q
        recent_lab_results = LabResult.objects.filter(
            order__encounter=encounter,
            status='completed',
            is_deleted=False,
            test__is_deleted=False,
            test__is_active=True,
            test__name__isnull=False
        ).exclude(
            Q(test__name__iexact='') | Q(test__name__icontains='INVALID')
        ).select_related('test', 'verified_by', 'verified_by__user').only(
            'id', 'test__id', 'test__name', 'test__code', 'value', 'qualitative_result', 
            'units', 'is_abnormal', 'verified_at', 'verified_by__id',
            'verified_by__user__first_name', 'verified_by__user__last_name'
        ).order_by('-verified_at')
        # All labs for this patient (this visit and all previous)
        patient_lab_results = LabResult.objects.filter(
            order__encounter__patient_id__in=patient_scope_ids,
            status='completed',
            is_deleted=False,
            test__is_deleted=False,
            test__is_active=True,
            test__name__isnull=False
        ).exclude(
            Q(test__name__iexact='') | Q(test__name__icontains='INVALID')
        ).select_related(
            'test', 'verified_by', 'verified_by__user', 'order', 'order__encounter'
        ).only(
            'id', 'test__id', 'test__name', 'test__code', 'value', 'qualitative_result', 
            'units', 'is_abnormal', 'verified_at', 'created', 'verified_by__id',
            'verified_by__user__first_name', 'verified_by__user__last_name',
            'order_id', 'order__id', 'order__encounter_id'
        ).order_by('-verified_at')
    except Exception:
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
    
    # Get diagnosis codes - USE CACHED VERSION for better performance
    from .utils_cache import get_cached_diagnosis_codes
    diagnosis_codes = get_cached_diagnosis_codes()
    
    # Prepare summary data for completion modal
    # Use latest CONSULTATION note for the editable box so doctors can edit and save again
    try:
        latest_consultation_note = next(
            (n for n in clinical_notes if getattr(n, 'note_type', None) == 'consultation'),
            None
        )
        latest_note = latest_consultation_note or (clinical_notes[0] if clinical_notes else None)
    except (IndexError, TypeError, AttributeError):
        latest_note = None
        latest_consultation_note = None

    # Doctors can continue documenting; do not lock note editing to first author/save.
    can_edit_consultation_note = (
        (getattr(doctor, 'profession', None) == 'doctor' or request.user.is_superuser)
    )
    consultation_note_author_name = None
    if latest_consultation_note and getattr(latest_consultation_note, 'created_by', None) and getattr(latest_consultation_note.created_by, 'user', None):
        consultation_note_author_name = (latest_consultation_note.created_by.user.get_full_name() or latest_consultation_note.created_by.user.username) or 'Doctor'
    assigned_doctor = getattr(encounter, 'provider', None)
    
    # Build comprehensive summary for review
    # IMPORTANT: Recalculate counts directly from database to ensure accuracy
    # This ensures counts reflect all items, not just the deduplicated list.
    # Order and Prescription are imported at module top.
    
    # Get fresh counts from database (use deduplicated count)
    prescriptions_count = len(existing_prescriptions)  # Use deduplicated list count
    
    lab_orders_count = Order.objects.filter(
        encounter=encounter,
        order_type='lab',
        is_deleted=False
    ).count()
    
    imaging_orders_count = Order.objects.filter(
        encounter=encounter,
        order_type='imaging',
        is_deleted=False
    ).count()
    
    # Single combined clinical note for display (one box): prefer notes, or join legacy 5-part fields
    clinical_note_combined = ''
    if latest_note:
        if (getattr(latest_note, 'notes', None) or '').strip():
            clinical_note_combined = (latest_note.notes or '').strip()
        else:
            parts = [
                (latest_note.subjective or '').strip(),
                (latest_note.notes or '').strip(),
                (latest_note.objective or '').strip(),
                (latest_note.assessment or '').strip(),
                (latest_note.plan or '').strip(),
            ]
            clinical_note_combined = '\n\n'.join(p for p in parts if p)
    # Fallback: show encounter.notes if no ClinicalNote yet (e.g. legacy or sync issue)
    if not clinical_note_combined and (encounter.notes or '').strip():
        clinical_note_combined = (encounter.notes or '').strip()
    consultation_summary = {
        'chief_complaint': encounter.chief_complaint or '',
        'diagnosis': encounter.diagnosis or '',
        'existing_diagnoses': list(Diagnosis.objects.filter(encounter=encounter, is_deleted=False).select_related('diagnosis_code').order_by('-diagnosis_date')) if Diagnosis is not None else [],
        'notes': latest_note.notes if latest_note else '',  # PMH (Past Medical/Family/Social/Drug History)
        'encounter_notes': encounter.notes or '',
        'subjective': latest_note.subjective if latest_note else '',  # PC (Presenting Complaints)
        'objective': latest_note.objective if latest_note else '',    # PE (Physical Examination)
        'assessment': latest_note.assessment if latest_note else (encounter.diagnosis or ''),
        'plan': latest_note.plan if latest_note else '',
        'clinical_note_combined': clinical_note_combined,
        'prescriptions_count': prescriptions_count,
        'lab_orders_count': lab_orders_count,
        'imaging_orders_count': imaging_orders_count,
    }
    
    # Get drug_id from query parameters (for drug guide linking)
    preselected_drug_id = request.GET.get('drug_id', None)
    preselected_drug = None
    preselected_drug_display_price = None
    if preselected_drug_id:
        try:
            preselected_drug = Drug.objects.filter(
                pk=preselected_drug_id, 
                is_active=True, 
                is_deleted=False,
                name__isnull=False
            ).exclude(
                name__iexact=''
            ).exclude(
                name__icontains='INVALID'
            ).first()
            if preselected_drug:
                from .utils_billing import get_drug_price_for_prescription
                patient_payer = encounter.patient.primary_insurance
                preselected_drug_display_price = float(
                    get_drug_price_for_prescription(preselected_drug, patient_payer)
                )
        except Drug.DoesNotExist:
            preselected_drug = None
    
    # Get patient's payer information for insurance/corporate pricing (drugs get 15% markup)
    patient_payer = encounter.patient.primary_insurance
    has_insurance = patient_payer and patient_payer.payer_type in ('insurance', 'private', 'nhis')
    has_corporate = patient_payer and patient_payer.payer_type == 'corporate'
    
    # Defer pricing to AJAX when patient has insurance/corporate so first load is fast (Option A)
    pricing_deferred = bool(has_insurance or has_corporate)
    if pricing_deferred:
        drug_pricing_map = {}
        lab_test_pricing_map = {}
        imaging_pricing_map = {}
    else:
        drug_pricing_map, lab_test_pricing_map, imaging_pricing_map = _build_consultation_pricing_maps(
            encounter, available_drugs, available_lab_tests, available_imaging_studies
        )
    
    # Get PDF documents for imaging and lab results for this encounter
    imaging_pdf_docs = []
    lab_pdf_docs = []
    patient_encounter_documents = []
    try:
        from .models_medical_records import PatientDocument
        from django.db.models import Q
        # Get imaging PDFs: by patient+encounter OR by imaging_study in this encounter's orders
        imaging_pdf_docs = PatientDocument.objects.filter(
            Q(patient=encounter.patient, encounter=encounter, document_type='imaging_report') |
            Q(imaging_study__order__encounter=encounter, document_type='imaging_report'),
            is_deleted=False
        ).select_related('uploaded_by__user', 'imaging_study').order_by('-created').distinct()
        
        # Get lab PDFs: by patient+encounter OR by lab_result in this encounter's orders
        lab_pdf_docs = PatientDocument.objects.filter(
            Q(patient=encounter.patient, encounter=encounter, document_type='lab_report') |
            Q(lab_result__order__encounter=encounter, document_type='lab_report'),
            is_deleted=False
        ).select_related('uploaded_by__user', 'lab_result').order_by('-created').distinct()
        # All other documents/images for this encounter (e.g. patient uploads, consent, other)
        patient_encounter_documents = PatientDocument.objects.filter(
            patient=encounter.patient,
            encounter=encounter,
            is_deleted=False
        ).exclude(file='').exclude(file__isnull=True).exclude(
            document_type__in=['imaging_report', 'lab_report']
        ).select_related('uploaded_by__user').order_by('-created')
    except Exception as e:
        _logger.warning(f"Error loading PDF documents: {e}")
    
    # Get imaging studies with their uploaded files for this encounter
    imaging_studies_with_files = []
    # All imaging studies for this patient (this visit and all previous) – for Labs & Imaging quick-view
    patient_imaging_studies = []
    try:
        if ImagingStudy:
            # Get all imaging studies for orders in this encounter
            imaging_studies_with_files = ImagingStudy.objects.filter(
                order__encounter=encounter,
                order__is_deleted=False,
                is_deleted=False
            ).prefetch_related('images').select_related('order', 'order__requested_by').order_by('-created')
            patient_imaging_studies = ImagingStudy.objects.filter(
                order__encounter__patient_id__in=patient_scope_ids,
                order__is_deleted=False,
                is_deleted=False
            ).select_related('order', 'order__encounter', 'order__requested_by').order_by('-created')
    except Exception as e:
        _logger.warning(f"Error loading imaging studies: {e}")
    
    # Drugs with stock expiring in next 30 days (for doctor awareness when prescribing)
    # Uses PharmacyStock first; falls back to InventoryBatch (procurement) if PharmacyStock is empty
    today_date = _timezone.now().date()
    expiring_soon_date = today_date + _timedelta(days=30)
    expiring_drugs = list(PharmacyStock.objects.filter(
        expiry_date__gte=today_date,
        expiry_date__lte=expiring_soon_date,
        quantity_on_hand__gt=0,
        is_deleted=False
    ).select_related('drug').order_by('expiry_date')[:20])
    
    if not expiring_drugs:
        try:
            from .models_inventory_advanced import InventoryBatch
            from .models_procurement import Store
            pharmacy_store = Store.get_main_pharmacy_store()
            if pharmacy_store:
                batches = InventoryBatch.objects.filter(
                    store=pharmacy_store,
                    inventory_item__drug__isnull=False,
                    expiry_date__gte=today_date,
                    expiry_date__lte=expiring_soon_date,
                    quantity_remaining__gt=0,
                    is_deleted=False,
                    is_expired=False
                ).select_related('inventory_item__drug').order_by('expiry_date')[:20]
                ExpiringItem = type('ExpiringItem', (), {})
                for b in batches:
                    if b.inventory_item and b.inventory_item.drug:
                        item = ExpiringItem()
                        item.drug = b.inventory_item.drug
                        item.expiry_date = b.expiry_date
                        item.quantity_on_hand = b.quantity_remaining
                        expiring_drugs.append(item)
        except Exception as e:
            _logger.debug(f"InventoryBatch fallback for expiring drugs: {e}")

    # Drugs (tablets & injections) that have had
    # no prescriptions in the last 3 weeks – for doctor awareness in prescribing.
    under_prescribed_drugs = []
    try:
        three_weeks_ago = timezone.now() - _timedelta(weeks=3)
        from .models import Prescription, Drug

        # Consider any drug whose form looks like tablet/capsule/injection/ampoule
        form_filter = (
            Q(form__icontains='tab') |
            Q(form__icontains='caps') |
            Q(form__icontains='inj') |
            Q(form__icontains='amp')
        )

        # All active tablet/injection drugs
        base_drugs = Drug.objects.filter(
            is_active=True,
        ).filter(form_filter)

        # Exclude drugs that have a prescription in the last 3 weeks
        silent_drugs = base_drugs.exclude(
            prescriptions__is_deleted=False,
            prescriptions__created__gte=three_weeks_ago,
        ).annotate(
            total_prescription_count=Count(
                'prescriptions',
                filter=Q(prescriptions__is_deleted=False),
            )
        ).order_by('-total_prescription_count')[:30]

        under_prescribed_drugs = list(silent_drugs)
    except Exception:
        under_prescribed_drugs = []
    
    context = {
        'encounter': encounter,
        'patient': encounter.patient,
        'doctor': doctor,
        'available_drugs': available_drugs,
        'available_lab_tests': available_lab_tests,
        'available_imaging_studies': available_imaging_studies,
        'imaging_by_modality': imaging_by_modality,
        'available_procedures': available_procedures,  # Procedures catalog (separate from imaging)
        'procedures_by_category': procedures_by_category,  # Grouped by category
        'existing_orders': existing_orders,
        'lab_orders': [o for o in existing_orders if getattr(o, 'order_type', None) == 'lab'],
        'patient_lab_orders': patient_lab_orders,
        'imaging_orders': [o for o in existing_orders if getattr(o, 'order_type', None) == 'imaging'],
        'existing_prescriptions': existing_prescriptions,
        'problems': problems,
        'clinical_notes': clinical_notes,
        'patient_clinical_notes': patient_clinical_notes,
        'clinical_notes_calendar_data': clinical_notes_calendar_data,
        'patient_clinical_notes_calendar_data': patient_clinical_notes_calendar_data,
        'clinical_notes_for_json': patient_clinical_notes_for_json,
        'patient_clinical_notes_for_json': patient_clinical_notes_for_json,
        'prescriptions_for_json': [
            {
                'drug_name': (p.drug.name if p.drug else ''),
                'strength': (p.drug.strength if p.drug else '') or '',
                'quantity': getattr(p, 'total_quantity', None) or p.quantity,
                'dose': (p.dose or ''),
                'route': (p.route or ''),
                'frequency': (p.frequency or ''),
                'duration': (p.duration or ''),
                'instructions': (p.instructions or ''),
                'prescribed_by': (p.prescribed_by.user.get_full_name() or p.prescribed_by.user.username) if getattr(p, 'prescribed_by', None) and getattr(p.prescribed_by, 'user', None) else '',
                'created': p.created.isoformat() if getattr(p, 'created', None) else '',
                'inventory_quantity': getattr(p, 'inventory_quantity', None),
            }
            for p in existing_prescriptions
        ],
        'lab_orders_for_json': [
            {
                'type': 'Lab Order',
                'order_id': str(o.id),
                'patient_name': (o.encounter.patient.full_name if o.encounter and o.encounter.patient else '') or (getattr(o.encounter.patient, 'mrn', None) if o.encounter and o.encounter.patient else '') or 'Unknown',
                'status': o.get_status_display() if hasattr(o, 'get_status_display') else (o.status or ''),
                'priority': o.get_priority_display() if hasattr(o, 'get_priority_display') else (o.priority or ''),
                'notes': (o.notes or ''),
                'requested_at': (o.requested_at or o.created).isoformat() if getattr(o, 'requested_at', None) or getattr(o, 'created', None) else '',
                'requested_by': (o.requested_by.user.get_full_name() or o.requested_by.user.username) if getattr(o, 'requested_by', None) and getattr(o.requested_by, 'user', None) else '',
                'lab_tests': [
                    {
                        'id': str(lr.id),
                        'name': (lr.test.name if lr.test else ''),
                        'code': (lr.test.code if lr.test else ''),
                        'status': lr.get_status_display() if hasattr(lr, 'get_status_display') else (lr.status or ''),
                        'value': (lr.value or ''),
                        'units': (lr.units or ''),
                        'qualitative_result': (lr.qualitative_result or ''),
                    }
                    for lr in (o.lab_results.filter(is_deleted=False) if hasattr(o, 'lab_results') else [])
                ],
            }
            for o in patient_lab_orders
        ],
        'imaging_orders_for_json': [
            {
                'type': 'Imaging Order',
                'status': o.get_status_display() if hasattr(o, 'get_status_display') else (o.status or ''),
                'priority': o.get_priority_display() if hasattr(o, 'get_priority_display') else (o.priority or ''),
                'notes': (o.notes or ''),
                'requested_at': (o.requested_at or o.created).isoformat() if getattr(o, 'requested_at', None) or getattr(o, 'created', None) else '',
                'requested_by': (o.requested_by.user.get_full_name() or o.requested_by.user.username) if getattr(o, 'requested_by', None) and getattr(o.requested_by, 'user', None) else '',
            }
            for o in existing_orders if getattr(o, 'order_type', None) == 'imaging'
        ],
        'problems_for_json': [
            {
                'name': (getattr(p, 'icd10_description', None) or p.problem or ''),
                'icd10_code': (p.icd10_code or ''),
                'description': (p.description or ''),
                'status': p.get_status_display() if hasattr(p, 'get_status_display') else (p.status or ''),
                'created': p.created.isoformat() if getattr(p, 'created', None) else '',
                'onset_date': str(p.onset_date) if getattr(p, 'onset_date', None) else '',
                'created_by': (p.created_by.user.get_full_name() or p.created_by.user.username) if getattr(p, 'created_by', None) and getattr(p.created_by, 'user', None) else '',
            }
            for p in problems
        ],
        'lab_pdf_docs_for_json': [
            {
                'title': (getattr(d, 'title', None) or ''),
                'uploaded_by': (d.uploaded_by.user.get_full_name() or d.uploaded_by.user.username) if getattr(d, 'uploaded_by', None) and getattr(d.uploaded_by, 'user', None) else '',
                'created': d.created.strftime('%b %d, %Y') if getattr(d, 'created', None) else '',
                'file_url': d.file.url if getattr(d, 'file', None) and d.file else '',
            }
            for d in (lab_pdf_docs if lab_pdf_docs else [])
        ],
        'latest_vitals': latest_vitals,
        'vitals_history': vitals_history,
        'vitals_intake_encounter_mismatch': vitals_intake_encounter_mismatch,
        'recent_lab_results': recent_lab_results,
        'patient_lab_results': patient_lab_results,  # All labs for this patient (all visits)
        'referrals': referrals,
        'diagnosis_codes': diagnosis_codes,
        'consultation_summary': consultation_summary,
        'drug_categories': categories_list,
        'all_drug_categories': Drug.CATEGORIES,  # For template dropdown
        'preselected_drug': preselected_drug,  # Drug selected from drug guide
        'preselected_drug_display_price': preselected_drug_display_price,  # Live pharmacy store price
        'patient_payer': patient_payer,  # Patient's payer/insurance
        'has_insurance': has_insurance,  # Whether patient has insurance
        'pricing_deferred': pricing_deferred,  # True when pricing loaded via AJAX
        'drug_pricing_map': drug_pricing_map,  # Insurance prices for drugs {drug_id: price}
        'lab_test_pricing_map': lab_test_pricing_map,  # Insurance prices for lab tests {test_id: price}
        'imaging_pricing_map': imaging_pricing_map,  # Insurance prices for imaging {study_id: price}
        # JSON for JavaScript: escape </ so it cannot close a <script> tag in HTML
        'drug_pricing_map_json': json.dumps({str(k): v for k, v in drug_pricing_map.items()}).replace('</', '<\\u002f'),
        'lab_test_pricing_map_json': json.dumps({str(k): v for k, v in lab_test_pricing_map.items()}).replace('</', '<\\u002f'),
        'imaging_pricing_map_json': json.dumps({str(k): v for k, v in imaging_pricing_map.items()}).replace('</', '<\\u002f'),
        'imaging_pdf_docs': imaging_pdf_docs,  # PDF documents for imaging studies
        'lab_pdf_docs': lab_pdf_docs,  # PDF documents for lab results
        'patient_encounter_documents': patient_encounter_documents,  # Documents/images from patient or this visit
        'imaging_studies_with_files': imaging_studies_with_files,  # Imaging studies with uploaded files
        'patient_imaging_studies': patient_imaging_studies,  # All imaging for this patient (all visits)
        'show_prescription_chat': True,  # Show Prescription Chat FAB on this page
        'prescription_chat_encounter_id': str(encounter.id),
        'expiring_drugs': expiring_drugs,  # Drugs expiring in 30 days - for doctor awareness when prescribing
        'under_prescribed_drugs': under_prescribed_drugs,  # Common tablets/injections quiet for last 3 weeks
        'consultation_read_only': consultation_read_only,  # True when consultation expired (view-only)
        'can_edit_consultation_note': can_edit_consultation_note,  # True only if current doctor is the note author (or no note yet)
        'consultation_note_author_name': consultation_note_author_name,  # Name of doctor who wrote the note (for nurses/other doctors)
        'assigned_doctor': assigned_doctor,  # Encounter's assigned provider (stays same when another doctor consults)
        'progress_notes_today_date': timezone.localdate(),  # For Progress Notes (Consultation) "today" highlight
    }
    return render(request, 'hospital/consultation.html', context)


@login_required
@role_required('doctor', 'pharmacist', 'nurse', 'admin', message='Access denied.')
def consultation_pricing_api(request, encounter_id):
    """
    JSON API returning drug/lab/imaging pricing maps for this encounter.
    Used when pricing is deferred on initial page load (Option A) so the page opens fast.
    """
    encounter = get_object_or_404(
        Encounter.objects.select_related('patient', 'patient__primary_insurance'),
        pk=encounter_id,
        is_deleted=False
    )
    from .utils_cache import get_cached_drugs, get_cached_lab_tests, get_cached_imaging_studies
    try:
        cached_drugs = get_cached_drugs()
        available_drugs = list(cached_drugs[:300]) if hasattr(cached_drugs, 'values_list') else (cached_drugs[:300] if isinstance(cached_drugs, (list, tuple)) else list(cached_drugs)[:300])
    except Exception:
        available_drugs = []
    try:
        cached_lab = get_cached_lab_tests()
        available_lab_tests = list(cached_lab[:500]) if hasattr(cached_lab, '__iter__') and not isinstance(cached_lab, (list, tuple)) else (cached_lab[:500] if isinstance(cached_lab, (list, tuple)) else list(cached_lab)[:500])
    except Exception:
        available_lab_tests = []
    try:
        cached_img = get_cached_imaging_studies()
        available_imaging_studies = list(cached_img[:500]) if hasattr(cached_img, '__iter__') and not isinstance(cached_img, (list, tuple)) else (cached_img[:500] if isinstance(cached_img, (list, tuple)) else list(cached_img)[:500])
    except Exception:
        available_imaging_studies = []
    drug_pricing_map, lab_test_pricing_map, imaging_pricing_map = _build_consultation_pricing_maps(
        encounter, available_drugs, available_lab_tests, available_imaging_studies
    )
    return JsonResponse({
        'drug_pricing': {str(k): v for k, v in drug_pricing_map.items()},
        'lab_test_pricing': {str(k): v for k, v in lab_test_pricing_map.items()},
        'imaging_pricing': {str(k): v for k, v in imaging_pricing_map.items()},
    })


@login_required
@role_required('doctor', 'pharmacist', 'nurse', 'admin', message='Access denied.')
def consultation_latest_vitals_api(request, encounter_id):
    """
    API returning latest vitals for an encounter so the consultation page can
    refresh vitals without full reload (doctors see new vitals soon after nurses record them).
    """
    encounter = get_object_or_404(
        Encounter.objects.select_related('patient'),
        pk=encounter_id,
        is_deleted=False
    )
    latest, history_qs = vital_signs_for_consultation(encounter)
    return JsonResponse({
        'latest': _vital_to_json(latest) if latest else None,
        'history': [_vital_to_json(v) for v in history_qs],
    })


def _vital_to_json(v):
    if not v:
        return None
    return {
        'id': str(v.id),
        'recorded_at': v.recorded_at.isoformat() if v.recorded_at else None,
        'systolic_bp': v.systolic_bp,
        'diastolic_bp': v.diastolic_bp,
        'pulse': v.pulse,
        'temperature': str(v.temperature) if v.temperature is not None else None,
        'spo2': v.spo2,
        'respiratory_rate': v.respiratory_rate,
        'weight': str(v.weight) if v.weight is not None else None,
        'height': str(v.height) if v.height is not None else None,
        'blood_glucose': str(v.blood_glucose) if v.blood_glucose is not None else None,
        'pain_score': v.pain_score,
        'notes': v.notes or '',
        'recorded_by': (v.recorded_by.user.get_full_name() or v.recorded_by.user.username) if getattr(v, 'recorded_by', None) and getattr(v.recorded_by, 'user', None) else '',
    }


@login_required
@role_required('doctor', 'pharmacist', 'admin', message='Access denied. Only doctors and pharmacists can start consultations.')
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
        # Create new encounter with duplicate prevention
        form = EncounterForm(request.POST)
        if form.is_valid():
            today = timezone.now().date()
            # 1) Prefer existing active encounter today (reuse, no duplicate)
            existing_active = Encounter.objects.filter(
                patient=patient,
                status='active',
                is_deleted=False,
                started_at__date=today
            ).order_by('-started_at').first()
            if existing_active:
                messages.info(
                    request,
                    f'Using existing active encounter from today. Consultation started.'
                )
                return redirect('hospital:consultation_view', encounter_id=existing_active.pk)
            # 2) If none active, check for completed encounter today - reopen instead of creating duplicate
            existing_completed_today = Encounter.objects.filter(
                patient=patient,
                status='completed',
                is_deleted=False,
                started_at__date=today
            ).order_by('-ended_at').first()
            if existing_completed_today and not existing_completed_today.consultation_expired():
                messages.info(
                    request,
                    'Patient already had a consultation today. Use Re-open to continue that consultation instead of creating a duplicate.'
                )
                return redirect('hospital:consultation_view', encounter_id=existing_completed_today.pk)
            # 3) No encounter today - create new one
            encounter = form.save(commit=False)
            encounter.patient = patient
            encounter.provider = doctor
            encounter.status = 'active'
            encounter.started_at = timezone.now()
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


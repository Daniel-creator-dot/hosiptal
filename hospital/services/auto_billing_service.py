"""
💰 AUTOMATIC BILLING SERVICE
Auto-generates bills when services are ordered
Ensures payment before service delivery
"""
from datetime import timedelta
from decimal import Decimal
import logging
import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class AutoBillingService:
    """
    Automatically create bills when services are ordered
    Ensures payment control from the start
    """

    @staticmethod
    def create_lab_bill(
        lab_result,
        *,
        notify_patient=True,
        billing_payer=None,
        pricing_patient=None,
        invoice_target=None,
        allow_on_closed_encounter=False,
        relax_encounter_match=False,
    ):
        """
        Auto-create bill when lab test is ordered.
        IDEMPOTENT: Calling multiple times (e.g. dashboard load, result entry) must NOT increase quantity.
        Lab quantity is always 1 per result - one test = one invoice line.
        Set notify_patient=False when batching (caller sends one notification per order).
        billing_payer: optional; when set, use for the encounter invoice instead of _ensure_payer
        (keeps corporate/insurer lines on the correct invoice during repair/sync).
        pricing_patient: optional Patient (e.g. loaded by invoice.patient_id UUID); used for price resolution
        so corporate enrollment / contract prices match the billed patient, not only encounter.patient.
        invoice_target: when set (e.g. corporate bill pack sync), create lines on this invoice instead of
        resolving the encounter invoice — fixes pharmacy-only corporate rows and split billing.
        allow_on_closed_encounter: allow lines when encounter.billing_closed_at is set (pack repair only).
        relax_encounter_match: allow invoice_target.encounter to differ from lab encounter (orphan invoice).
        """
        from hospital.models import InvoiceLine
        from hospital.models_payment_verification import LabResultRelease

        try:
            with transaction.atomic():
                patient = lab_result.order.encounter.patient
                price_patient = pricing_patient if pricing_patient is not None else patient
                encounter = lab_result.order.encounter
                test = lab_result.test
                try:
                    test.refresh_from_db(fields=['price', 'code', 'name'])
                except Exception:
                    pass

                if getattr(encounter, 'billing_closed_at', None) and not allow_on_closed_encounter:
                    return {
                        'success': False,
                        'error': 'Billing closed for this encounter',
                        'message': 'No new charges can be added after discharge.',
                    }

                release_record = LabResultRelease.objects.filter(lab_result=lab_result).first()

                def _resolve_payer():
                    if billing_payer is not None and not getattr(billing_payer, 'is_deleted', False):
                        return billing_payer
                    return AutoBillingService._ensure_payer(patient, encounter)

                payer = _resolve_payer()

                if invoice_target is not None:
                    inv = invoice_target
                    if getattr(inv, 'is_deleted', False) or getattr(inv, 'status', None) == 'cancelled':
                        return {
                            'success': False,
                            'error': 'invalid_target_invoice',
                            'message': 'Target invoice is not billable.',
                        }
                    if str(inv.patient_id) != str(patient.id):
                        return {
                            'success': False,
                            'error': 'patient_mismatch',
                            'message': 'Lab patient does not match invoice patient.',
                        }
                    if inv.encounter_id and str(inv.encounter_id) != str(encounter.id) and not relax_encounter_match:
                        return {
                            'success': False,
                            'error': 'encounter_mismatch',
                            'message': 'Invoice encounter does not match lab order encounter.',
                        }
                    invoice = inv
                    if payer and invoice.payer_id != payer.id:
                        invoice.payer = payer
                        invoice.save(update_fields=['payer', 'modified'])
                        AutoBillingService._ensure_insurance_claim_items(invoice)
                else:
                    invoice, _ = AutoBillingService._get_or_create_invoice(patient, encounter, payer)
                    if not invoice:
                        return {
                            'success': False,
                            'error': 'no_invoice',
                            'message': 'Could not resolve invoice for lab billing.',
                        }

                service_code = AutoBillingService._get_or_create_service_code(
                    code=f"LAB-{test.code or test.id or test.pk}",
                    description=test.name,
                    category='Laboratory Services',
                    default_price=test.price or Decimal('0.00')
                )

                existing_line = InvoiceLine.objects.filter(
                    invoice=invoice,
                    service_code=service_code,
                    is_deleted=False
                ).select_for_update().first()

                if release_record and existing_line:
                    return {
                        'success': True,
                        'invoice': invoice,
                        'invoice_line': existing_line,
                        'amount': existing_line.unit_price * existing_line.quantity,
                        'release_record': release_record,
                        'message': f'Bill already exists for {test.name}',
                    }

                unit_price = AutoBillingService._resolve_price(price_patient, payer, service_code, test.price)

                if release_record and not existing_line:
                    invoice_line = InvoiceLine.objects.create(
                        invoice=invoice,
                        service_code=service_code,
                        description=test.name,
                        quantity=Decimal('1.00'),
                        unit_price=unit_price,
                        line_total=unit_price,
                        patient_pay_cash=True,
                    )
                    AutoBillingService._finalize_invoice(invoice)
                    logger.info(
                        "✅ Lab bill repaired (release without line) for %s - %s - GHS %s",
                        test.name,
                        patient.full_name,
                        unit_price,
                    )
                    if notify_patient:
                        try:
                            from hospital.services.pending_payment_notification_service import (
                                notify_patient_pending_payment,
                                SERVICE_TYPE_LAB,
                            )
                            notify_patient_pending_payment(
                                patient, SERVICE_TYPE_LAB, test.name, unit_price,
                                message_type='pending_payment_lab',
                            )
                        except Exception as notify_exc:
                            logger.warning("Lab pending payment notification failed: %s", notify_exc)
                    return {
                        'success': True,
                        'invoice': invoice,
                        'invoice_line': invoice_line,
                        'amount': unit_price,
                        'release_record': release_record,
                        'message': f'Bill repaired: GHS {unit_price} for {test.name}',
                    }

                if existing_line:
                    existing_line.unit_price = unit_price
                    existing_line.line_total = existing_line.quantity * unit_price
                    existing_line.patient_pay_cash = True
                    existing_line.save()
                    invoice_line = existing_line
                else:
                    invoice_line, created = InvoiceLine.objects.get_or_create(
                        invoice=invoice,
                        service_code=service_code,
                        is_deleted=False,
                        defaults={
                            'description': test.name,
                            'quantity': Decimal('1.00'),
                            'unit_price': unit_price,
                            'line_total': unit_price,
                            'patient_pay_cash': True,
                        }
                    )

                    if not created:
                        invoice_line.unit_price = unit_price
                        invoice_line.line_total = invoice_line.quantity * unit_price
                        invoice_line.patient_pay_cash = True
                        invoice_line.save()

                AutoBillingService._finalize_invoice(invoice)

                release_record, _ = LabResultRelease.objects.get_or_create(
                    lab_result=lab_result,
                    patient=patient,
                    defaults={'release_status': 'pending_payment'}
                )

                logger.info(
                    "✅ Auto-bill created for %s - %s - GHS %s",
                    test.name,
                    patient.full_name,
                    unit_price,
                )

                if notify_patient:
                    try:
                        from hospital.services.pending_payment_notification_service import (
                            notify_patient_pending_payment,
                            SERVICE_TYPE_LAB,
                        )
                        notify_patient_pending_payment(
                            patient, SERVICE_TYPE_LAB, test.name, unit_price,
                            message_type='pending_payment_lab',
                        )
                    except Exception as notify_exc:
                        logger.warning("Lab pending payment notification failed: %s", notify_exc)

                return {
                    'success': True,
                    'invoice': invoice,
                    'invoice_line': invoice_line,
                    'amount': unit_price,
                    'release_record': release_record,
                    'message': f'Bill created: GHS {unit_price} for {test.name}',
                }

        except Exception as exc:
            err_msg = str(exc)
            logger.error("❌ Error creating lab bill: %s", err_msg, exc_info=True)
            return {
                'success': False,
                'error': err_msg,
                'message': f'Auto-billing failed: {err_msg}',
            }

    @staticmethod
    def _patient_has_active_admission(patient):
        """
        True if the patient currently has an active admission (admitted + not discharged).

        We intentionally check at the patient level because real workflows can create
        prescriptions on a different active encounter than the one linked to Admission.
        """
        if not patient:
            return False
        try:
            from hospital.models import Admission
            return Admission.objects.filter(
                is_deleted=False,
                status='admitted',
                discharge_date__isnull=True,
                encounter__is_deleted=False,
                encounter__patient=patient,
            ).exists()
        except Exception:
            return False

    @staticmethod
    def _encounter_is_inpatient_active(encounter):
        """
        True if the encounter represents an active inpatient stay (admitted, not discharged).
        IPD prescriptions flow to pharmacy immediately because admitted patients receive
        ongoing prescriptions throughout their stay (no per-visit "complete consultation").
        """
        if not encounter:
            return False
        try:
            from hospital.models import Admission

            # Authoritative: an Admission row for this encounter (covers encounter_type
            # 'admission', 'inpatient', or legacy values set by different entry points).
            if Admission.objects.filter(
                encounter=encounter,
                is_deleted=False,
                status='admitted',
                discharge_date__isnull=True,
            ).exists():
                return True

            # Explicit inpatient / admission encounter types with related Admission object
            et = (getattr(encounter, 'encounter_type', None) or '').strip().lower()
            if et in ('inpatient', 'admission', 'ipd'):
                admission = getattr(encounter, 'admission', None)
                if admission and not getattr(admission, 'is_deleted', False):
                    if getattr(admission, 'status', None) == 'admitted' and getattr(admission, 'discharge_date', None) is None:
                        return True

            # Fallback: patient-level admission (handles inconsistent encounter linkage).
            patient = getattr(encounter, 'patient', None)
            return AutoBillingService._patient_has_active_admission(patient)
        except Exception:
            return False

    @staticmethod
    def is_prescription_released_to_pharmacy(prescription):
        """
        Decides whether a prescription should be visible to the pharmacy queue.

        OPD (any non-inpatient encounter, or inpatient without an active admission):
            Released after "Complete Consultation", OR immediately when marked
            is_start_dose (initial/stat dose during an in-progress visit).
        IPD (inpatient with an active admission):
            Released immediately so pharmacy can dispense ongoing meds during the stay.
        """
        try:
            if getattr(prescription, 'is_start_dose', False):
                return True
            encounter = prescription.order.encounter
        except Exception:
            return False
        if AutoBillingService._encounter_is_inpatient_active(encounter):
            return True
        return getattr(encounter, 'status', None) == 'completed' or bool(getattr(encounter, 'ended_at', None))

    @staticmethod
    def create_pharmacy_dispensing_record_only(prescription, force=False):
        """
        Create PharmacyDispensing only - NO InvoiceLine. Used when prescription is first created.
        Puts prescription in pharmacy queue for check/edit before sending to cashier/insurer.
        Bill (InvoiceLine) is created only when pharmacy sends to cashier/insurance.

        Gate: For OPD encounters, the dispensing record is only created once the doctor
        completes the consultation. IPD (admitted) prescriptions are released immediately.
        Pass ``force=True`` to bypass this gate (e.g. when a downstream pharmacy/cashier
        path is explicitly handling an already-released prescription).
        """
        from hospital.models_payment_verification import PharmacyDispensing
        try:
            if not force and not AutoBillingService.is_prescription_released_to_pharmacy(prescription):
                return {
                    'success': False,
                    'gated': True,
                    'message': 'Prescription withheld from pharmacy until consultation is completed.',
                }
            with transaction.atomic():
                patient = prescription.order.encounter.patient
                PharmacyDispensing.objects.get_or_create(
                    prescription=prescription,
                    patient=patient,
                    defaults={
                        'dispensing_status': 'pending_payment',
                        'quantity_ordered': int(prescription.quantity or 0),
                    },
                )
                return {'success': True}
        except Exception as exc:
            logger.error("Error creating pharmacy dispensing record: %s", exc)
            return {'success': False, 'error': str(exc)}

    @staticmethod
    def backfill_missing_pharmacy_dispensing(limit=100):
        """
        Create PharmacyDispensing rows for prescriptions that should be in the
        pharmacy queue but have no dispensing record (signal miss, legacy data).

        Covers active IPD, completed OPD, and OPD start/stat doses on active visits.
        """
        from hospital.models import Prescription

        candidates = (
            Prescription.objects.filter(
                is_deleted=False,
                dispensing_record__isnull=True,
                order__is_deleted=False,
            )
            .select_related('order__encounter__patient', 'drug')
            .order_by('-created')
        )

        created = 0
        processed = 0
        for rx in candidates:
            if processed >= limit:
                break
            if not AutoBillingService.is_prescription_released_to_pharmacy(rx):
                continue
            processed += 1
            result = AutoBillingService.create_pharmacy_dispensing_record_only(rx, force=True)
            if result.get('success'):
                created += 1
        return {'created': created, 'processed': processed}

    @staticmethod
    def release_encounter_prescriptions_to_pharmacy(encounter):
        """
        Release every non-deleted prescription on this encounter to the pharmacy queue
        by ensuring each one has a PharmacyDispensing record. Called when the doctor
        clicks "Complete Consultation" on an OPD visit.

        Idempotent: prescriptions that already have a dispensing record are left alone.
        Returns dict with release counts.
        """
        from hospital.models import Prescription
        from hospital.models_payment_verification import PharmacyDispensing

        released = 0
        already = 0
        errors = 0

        if not encounter:
            return {'success': False, 'released': 0, 'already': 0, 'errors': 0}

        try:
            prescriptions = (
                Prescription.objects.filter(
                    order__encounter=encounter,
                    order__is_deleted=False,
                    is_deleted=False,
                )
                .select_related('order__encounter__patient', 'drug')
            )
            for rx in prescriptions:
                try:
                    if PharmacyDispensing.objects.filter(prescription=rx).exists():
                        already += 1
                        continue
                    result = AutoBillingService.create_pharmacy_dispensing_record_only(rx, force=True)
                    if result.get('success'):
                        released += 1
                    else:
                        errors += 1
                        logger.warning(
                            "Failed to release prescription %s to pharmacy: %s",
                            rx.id,
                            result.get('error') or result.get('message'),
                        )
                except Exception as inner_exc:
                    errors += 1
                    logger.error(
                        "Error releasing prescription %s on consultation completion: %s",
                        getattr(rx, 'id', '?'),
                        inner_exc,
                        exc_info=True,
                    )
        except Exception as exc:
            logger.error(
                "release_encounter_prescriptions_to_pharmacy failed for encounter %s: %s",
                getattr(encounter, 'id', '?'),
                exc,
                exc_info=True,
            )
            return {'success': False, 'released': released, 'already': already, 'errors': errors + 1}

        return {'success': True, 'released': released, 'already': already, 'errors': errors}

    @staticmethod
    def create_pharmacy_bill(prescription, substitute_drug=None, quantity_override=None, payer=None, invoice=None):
        """
        Create/update bill when pharmacy sends to cashier or insurer.
        Uses pharmacy's edited drug and quantity - NOT the initial prescription.

        Requires an existing PharmacyDispensing row (created when the doctor prescribes, or via
        create_pharmacy_dispensing_record_only). Invoice lines are never created for a prescription
        that has not hit the pharmacy queue first.

        Args:
            prescription: Prescription object
            substitute_drug: Optional Drug to dispense instead (pharmacy substitution)
            quantity_override: Optional quantity override (from pharmacy editing)
            payer: Optional Payer to use (e.g. when pharmacy selects "Bill to insurance/corporate");
                   when None, uses _ensure_payer(patient, encounter)
            invoice: Optional Invoice to use (when sending multiple prescriptions, pass same invoice to avoid N lookups)

        Returns:
            dict with bill and invoice details
        """
        from hospital.models import InvoiceLine, Drug
        from hospital.models_payment_verification import PharmacyDispensing
        from hospital.utils_billing import get_drug_price_for_prescription

        try:
            with transaction.atomic():
                patient = prescription.order.encounter.patient
                encounter = prescription.order.encounter
                if getattr(encounter, 'billing_closed_at', None):
                    return {
                        'success': False,
                        'error': 'Billing closed for this encounter',
                        'message': 'No new charges can be added after discharge.',
                    }

                # OneToOne on prescription — do not require patient match (stale FK would block billing)
                dispensing_record = PharmacyDispensing.objects.filter(
                    prescription=prescription,
                    is_deleted=False,
                ).select_for_update().first()
                if not dispensing_record:
                    logger.warning(
                        "create_pharmacy_bill blocked: no PharmacyDispensing for prescription %s",
                        prescription.id,
                    )
                    return {
                        'success': False,
                        'error': 'no_pharmacy_queue_record',
                        'message': (
                            'This prescription must be received at pharmacy before sending to payer. '
                            'Open it in the pharmacy workflow, verify details, then use Send to Cashier or Send to Insurance.'
                        ),
                    }

                drug = substitute_drug if substitute_drug else prescription.drug
                qty = quantity_override if quantity_override is not None else prescription.quantity

                # Waive old InvoiceLines for this prescription (from pre-pharmacy auto-bill)
                # Only waive lines with legacy service_code (no prescription ID suffix) to avoid
                # waiving our own newly-created line in concurrent double-send scenarios
                new_code_suffix = f"-{prescription.id}"
                existing_lines = list(InvoiceLine.objects.filter(
                    prescription=prescription,
                    is_deleted=False,
                    waived_at__isnull=True
                ).select_related('service_code'))
                for old_line in existing_lines:
                    sc = getattr(old_line.service_code, 'code', '') or ''
                    if new_code_suffix in sc:
                        continue  # Our own line from previous send - don't waive
                    old_line.waived_at = timezone.now()
                    old_line.waiver_reason = 'Replaced by pharmacy verification'
                    old_line.save()

                # Base unit price: Drug.unit_price or inventory fallback + payer markup (utils_billing)
                if payer is None:
                    payer = AutoBillingService._ensure_payer(patient, encounter)
                drug_price = get_drug_price_for_prescription(drug, payer=payer)
                if invoice is None:
                    invoice, _ = AutoBillingService._get_or_create_invoice(patient, encounter, payer)

                # One line per prescription - prevents "orphaned" prescriptions when merging
                # (merged lines could only link one prescription, others disappeared from both queues)
                service_code = AutoBillingService._get_or_create_service_code(
                    code=f"DRUG-{drug.code if hasattr(drug, 'code') else drug.pk}-{prescription.id}",
                    description=f"{drug.name} {drug.strength}".strip(),
                    category='Pharmacy Services',
                    default_price=drug_price,
                )

                # Use central pharmacy price only — do not run pricing_engine here or contract
                # prices override get_drug_price_for_prescription and disagree with consultation / prescribe sales.
                unit_price = drug_price
                
                # One line per prescription - always link to this prescription so it shows in both pharmacy and cashier
                invoice_line, created = InvoiceLine.objects.get_or_create(
                    invoice=invoice,
                    prescription=prescription,
                    is_deleted=False,
                    waived_at__isnull=True,
                    defaults={
                        'service_code': service_code,
                        'description': f"{drug.name} x{int(qty)}",
                        'quantity': Decimal(str(qty)),
                        'unit_price': unit_price,
                        'line_total': unit_price * Decimal(str(qty)),
                        'patient_pay_cash': True,
                    },
                )
                if not created:
                    # Duplicate send (e.g. pharmacy clicked twice) - update with latest pharmacy edits
                    invoice_line.service_code = service_code
                    invoice_line.quantity = Decimal(str(qty))
                    invoice_line.unit_price = unit_price
                    invoice_line.line_total = unit_price * Decimal(str(qty))
                    invoice_line.description = f"{drug.name} x{int(qty)}"
                    invoice_line.patient_pay_cash = True
                    invoice_line.save(update_fields=['service_code', 'quantity', 'unit_price', 'line_total', 'description', 'patient_pay_cash'])

                # Ensure insurance claim rows exist even when an existing InvoiceLine was updated
                # (post_save signal only creates on created=True).
                AutoBillingService._ensure_insurance_claim_items(invoice)

                AutoBillingService._finalize_invoice(invoice)

                # dispensing_record was loaded and locked above (pharmacy queue must exist first)
                # Always apply pharmacy edits (qty/drug) so re-send updates existing record
                dispensing_record.quantity_ordered = int(qty)
                dispensing_record.substitute_drug = substitute_drug
                update_disp = ['quantity_ordered', 'substitute_drug', 'modified']
                if dispensing_record.patient_id != patient.id:
                    dispensing_record.patient = patient
                    update_disp.append('patient')
                dispensing_record.save(update_fields=update_disp)

                # Insurance/corporate: go straight to ready_to_dispense (no pending); reduce stock
                payer_type = getattr(payer, 'payer_type', None) or ''
                if payer_type in ('insurance', 'private', 'nhis', 'corporate'):
                    dispensing_record.dispensing_status = 'ready_to_dispense'
                    dispensing_record.payment_verified_at = timezone.now()
                    update_fields = ['dispensing_status', 'payment_verified_at', 'modified']
                    drug_to_dispense = dispensing_record.drug_to_dispense or drug
                    qty_int = int(qty)
                    if drug_to_dispense and qty_int > 0 and not getattr(dispensing_record, 'stock_reduced_at', None):
                        from hospital.models_payment_verification import PharmacyStockDeductionLog
                        from hospital.pharmacy_stock_utils import reduce_pharmacy_stock_once

                        _sf, stock_applied = reduce_pharmacy_stock_once(
                            drug_to_dispense,
                            qty_int,
                            PharmacyStockDeductionLog.SOURCE_PHARMACY_DISPENSING,
                            dispensing_record.id,
                        )
                        if stock_applied:
                            dispensing_record.stock_reduced_at = timezone.now()
                            update_fields.append('stock_reduced_at')
                    dispensing_record.save(update_fields=update_fields)
                    logger.info(
                        "✅ Send to payer (insurance/corporate) – straight to ready: %s x%s - %s",
                        drug.name, qty, patient.full_name,
                    )
                else:
                    # Cash: line is on the invoice — stay pending until cashier posts payment_receipt
                    line_total = invoice_line.line_total
                    if not getattr(dispensing_record, 'payment_receipt_id', None):
                        if dispensing_record.dispensing_status != 'pending_payment':
                            dispensing_record.dispensing_status = 'pending_payment'
                            dispensing_record.save(update_fields=['dispensing_status', 'modified'])
                    logger.info(
                        "✅ Auto-bill created for %s x%s - %s - GHS %s",
                        drug.name,
                        qty,
                        patient.full_name,
                        line_total,
                    )
                    try:
                        from hospital.services.pending_payment_notification_service import (
                            notify_patient_pending_payment,
                            SERVICE_TYPE_PRESCRIPTION,
                        )
                        notify_patient_pending_payment(
                            patient, SERVICE_TYPE_PRESCRIPTION, 'Pharmacy total', line_total,
                            message_type='pending_payment_prescription',
                        )
                    except Exception as notify_exc:
                        logger.warning("Prescription pending payment notification failed: %s", notify_exc)

                # Calculate line total for return
                line_total = invoice_line.line_total

                return {
                    'success': True,
                    'invoice': invoice,
                    'invoice_line': invoice_line,
                    'amount': line_total,
                    'dispensing_record': dispensing_record,
                    'message': f'Bill created: GHS {line_total} for {drug.name}',
                }

        except Exception as exc:
            err_msg = str(exc)
            logger.error("❌ Error creating pharmacy bill: %s", err_msg, exc_info=True)
            return {
                'success': False,
                'error': err_msg,
                'message': f'Auto-billing failed: {err_msg}',
            }

    @staticmethod
    def create_imaging_bill(
        imaging_study,
        *,
        billing_payer=None,
        notify_patient=True,
        pricing_patient=None,
        invoice_target=None,
        allow_on_closed_encounter=False,
        relax_encounter_match=False,
    ):
        """
        Auto-create bill when imaging study is ordered (doctor or imaging dept).
        Creates a direct invoice line so the scan appears at cashier immediately.
        Resolves price from ImagingCatalog (match study_type to code/name).
        billing_payer: optional; when set, use for the encounter invoice instead of _ensure_payer.
        pricing_patient: optional Patient for pricing_engine resolution (e.g. invoice.patient_id UUID).
        invoice_target / allow_on_closed_encounter / relax_encounter_match: same semantics as create_lab_bill.
        """
        from hospital.models import InvoiceLine
        from hospital.models_payment_verification import ImagingRelease

        try:
            with transaction.atomic():
                # Support both order-based and direct patient/encounter (e.g. study created without order)
                order = getattr(imaging_study, 'order', None)
                if order is not None:
                    patient = order.encounter.patient
                    encounter = order.encounter
                else:
                    patient = getattr(imaging_study, 'patient', None)
                    encounter = getattr(imaging_study, 'encounter', None)
                    if not patient:
                        raise ValueError("ImagingStudy has no order and no patient; cannot create bill.")
                price_patient = pricing_patient if pricing_patient is not None else patient
                if encounter and getattr(encounter, 'billing_closed_at', None) and not allow_on_closed_encounter:
                    return {
                        'success': False,
                        'error': 'Billing closed for this encounter',
                        'message': 'No new charges can be added after discharge.',
                    }

                if billing_payer is not None and not getattr(billing_payer, 'is_deleted', False):
                    payer = billing_payer
                else:
                    payer = AutoBillingService._ensure_payer(patient, encounter)
                payer_type = getattr(payer, 'payer_type', None) or 'cash'
                if isinstance(payer_type, str):
                    payer_type = payer_type.lower()

                catalog = AutoBillingService._find_imaging_catalog_for_study(imaging_study)
                default_price, catalog_tier_applied = AutoBillingService._imaging_catalog_amount_and_tier_flag(
                    catalog, payer_type
                )

                if invoice_target is not None:
                    inv = invoice_target
                    if getattr(inv, 'is_deleted', False) or getattr(inv, 'status', None) == 'cancelled':
                        return {
                            'success': False,
                            'error': 'invalid_target_invoice',
                            'message': 'Target invoice is not billable.',
                        }
                    if str(inv.patient_id) != str(patient.id):
                        return {
                            'success': False,
                            'error': 'patient_mismatch',
                            'message': 'Imaging patient does not match invoice patient.',
                        }
                    if encounter and inv.encounter_id and str(inv.encounter_id) != str(encounter.id):
                        if not relax_encounter_match:
                            return {
                                'success': False,
                                'error': 'encounter_mismatch',
                                'message': 'Invoice encounter does not match imaging encounter.',
                            }
                    invoice = inv
                    if payer and invoice.payer_id != payer.id:
                        invoice.payer = payer
                        invoice.save(update_fields=['payer', 'modified'])
                        AutoBillingService._ensure_insurance_claim_items(invoice)
                else:
                    invoice, _ = AutoBillingService._get_or_create_invoice(patient, encounter, payer)

                # One line per scan; use canonical code so cashier add-to-invoice merges with this line
                desc = imaging_study.study_type or f"{imaging_study.get_modality_display()} - {imaging_study.body_part}"
                img_code_str = AutoBillingService.get_imaging_service_code_string(imaging_study)
                service_code = AutoBillingService._get_or_create_service_code(
                    code=img_code_str,
                    description=desc,
                    category='Imaging Services',
                    default_price=default_price,
                )

                unit_price = AutoBillingService._resolve_price(
                    price_patient,
                    payer,
                    service_code,
                    default_price,
                    catalog_tier_applied=catalog_tier_applied,
                )

                from hospital.utils_invoice_line import create_or_merge_invoice_line
                invoice_line, _ = create_or_merge_invoice_line(
                    invoice=invoice,
                    service_code=service_code,
                    quantity=Decimal('1.00'),
                    unit_price=unit_price,
                    description=desc,
                    max_quantity=1,
                )
                if not getattr(invoice_line, 'patient_pay_cash', False):
                    invoice_line.patient_pay_cash = True
                    invoice_line.save(update_fields=['patient_pay_cash'])

                AutoBillingService._finalize_invoice(invoice)

                release_record, _ = ImagingRelease.objects.get_or_create(
                    imaging_study=imaging_study,
                    defaults={
                        'patient': patient,
                        'release_status': 'pending_payment',
                    },
                )

                logger.info(
                    "✅ Auto-bill created for imaging %s - %s - GHS %s (catalog=%s tier_applied=%s)",
                    imaging_study.study_type or imaging_study.modality,
                    patient.full_name,
                    unit_price,
                    getattr(catalog, 'code', None) or '—',
                    catalog_tier_applied,
                )

                if notify_patient:
                    try:
                        from hospital.services.pending_payment_notification_service import (
                            notify_patient_pending_payment,
                            SERVICE_TYPE_IMAGING,
                        )
                        service_name = imaging_study.study_type or f"{imaging_study.get_modality_display()} - {imaging_study.body_part}"
                        notify_patient_pending_payment(
                            patient, SERVICE_TYPE_IMAGING, service_name, unit_price,
                            message_type='pending_payment_imaging',
                        )
                    except Exception as notify_exc:
                        logger.warning("Imaging pending payment notification failed: %s", notify_exc)

                return {
                    'success': True,
                    'invoice': invoice,
                    'invoice_line': invoice_line,
                    'amount': unit_price,
                    'release_record': release_record,
                    'message': f'Bill created: GHS {unit_price} for {imaging_study.study_type or "imaging"}',
                }

        except Exception as exc:
            err_msg = str(exc)
            logger.error("❌ Error creating imaging bill: %s", err_msg, exc_info=True)
            return {
                'success': False,
                'error': err_msg,
                'message': f'Auto-billing failed: {err_msg}',
            }

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    @staticmethod
    def get_imaging_service_code_string(imaging_study):
        """
        Canonical service code string for an imaging study.
        Use everywhere (create_imaging_bill, cashier add-to-invoice) so the same
        study always maps to the same code and lines merge instead of duplicating.
        """
        study_type = (getattr(imaging_study, 'study_type', None) or '').strip() or 'study'
        modality = getattr(imaging_study, 'modality', None) or 'study'
        # Use full ServiceCode.code length (80) so catalog study_type is not truncated for matching/pricing
        return f"IMG-{modality}-{study_type}"[:80]

    @staticmethod
    def _find_imaging_catalog_for_study(imaging_study):
        """
        Best-effort ImagingCatalog row for billing: study_type, then modality+study_type, then modality+body_part.
        """
        from hospital.models_advanced import ImagingCatalog

        study_type = (getattr(imaging_study, 'study_type', None) or '').strip()
        modality = (getattr(imaging_study, 'modality', None) or '').strip()
        body_part = (getattr(imaging_study, 'body_part', None) or '').strip()
        qs = ImagingCatalog.objects.filter(is_active=True, is_deleted=False)
        if study_type:
            row = qs.filter(
                Q(code__iexact=study_type)
                | Q(name__iexact=study_type)
                | Q(study_type__iexact=study_type)
            ).first()
            if row:
                return row
        if modality and study_type:
            row = (
                qs.filter(modality__iexact=modality)
                .filter(
                    Q(code__iexact=study_type)
                    | Q(name__iexact=study_type)
                    | Q(study_type__iexact=study_type)
                )
                .first()
            )
            if row:
                return row
        if modality and body_part:
            row = qs.filter(modality__iexact=modality, body_part__iexact=body_part).first()
            if row:
                return row
        return None

    @staticmethod
    def _imaging_catalog_amount_and_tier_flag(catalog, payer_type):
        """
        Return (amount, catalog_tier_applied).
        When corporate_price / insurance_price is used, amount is final — do not apply lab/imaging markup again.
        """
        if not catalog:
            return Decimal('0.00'), False
        pt = (payer_type or 'cash').lower() if isinstance(payer_type, str) else 'cash'
        if pt == 'corporate' and catalog.corporate_price is not None:
            return Decimal(str(catalog.corporate_price)), True
        if pt in ('nhis', 'private', 'insurance') and catalog.insurance_price is not None:
            return Decimal(str(catalog.insurance_price)), True
        if catalog.price is not None:
            return Decimal(str(catalog.price)), False
        return Decimal('0.00'), False

    @staticmethod
    def _ensure_payer(patient, encounter=None):
        """Resolve payer for billing. Uses get_patient_payer_info when encounter is given so
        corporate/insurance from CorporateEmployee or PatientInsurance is used for the invoice."""
        from hospital.models import Payer
        if encounter:
            from hospital.utils_billing import get_patient_payer_info
            info = get_patient_payer_info(patient, encounter)
            payer = info.get('payer')
            if payer and not getattr(payer, 'is_deleted', False):
                return payer

        payer = getattr(patient, 'primary_insurance', None)
        if payer and not getattr(payer, 'is_deleted', False):
            return payer

        payer = (
            Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
            or Payer.objects.filter(is_active=True, is_deleted=False).first()
        )
        if payer:
            return payer

        return Payer.objects.create(name='Cash', payer_type='cash', is_active=True)

    @staticmethod
    def _get_or_create_invoice(patient, encounter, payer):
        from hospital.models import Invoice
        from django.db import connection

        # Use all_objects so we find the encounter's invoice even if it's in the write-off
        # period (Dec–Feb 2026). Otherwise we'd create a duplicate and hit transaction errors.
        base_qs = Invoice.all_objects.filter(
            patient=patient,
            encounter=encounter,
            is_deleted=False,
        ).order_by('-created')

        # select_for_update requires an active transaction; use it only when already in atomic block
        if connection.in_atomic_block:
            invoice = base_qs.select_for_update().first()
        else:
            invoice = base_qs.first()
        if invoice:
            if payer and invoice.payer_id != payer.id:
                invoice.payer = payer
                invoice.save(update_fields=['payer'])
                AutoBillingService._ensure_insurance_claim_items(invoice)
            return invoice, False

        invoice = base_qs.first()
        if invoice:
            if payer and invoice.payer_id != payer.id:
                invoice.payer = payer
                invoice.save(update_fields=['payer'])
                AutoBillingService._ensure_insurance_claim_items(invoice)
            return invoice, False

        invoice = Invoice.all_objects.create(
            patient=patient,
            encounter=encounter,
            payer=payer,
            status='draft',
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=30),
        )
        return invoice, True

    @staticmethod
    def _get_or_create_service_code(code, description, category, default_price):
        from hospital.models import ServiceCode

        service_code, _ = ServiceCode.objects.get_or_create(
            code=str(code)[:80],
            defaults={
                'description': description[:200],
                'category': category[:50],
                'is_active': True,
            },
        )
        # Attach default price to price book if needed later
        return service_code

    @staticmethod
    def _resolve_price(patient, payer, service_code, fallback_price, *, catalog_tier_applied=False):
        """
        Resolve unit price for a service line.

        Lab (LAB-*) / imaging (IMG-*): hospital catalog is the source of truth when available.
        - Cash: catalog list price.
        - Corporate/insurance with catalog cash list only: apply lab/imaging markup on catalog.
        - When catalog_tier_applied=True (imaging corporate_price / insurance_price from catalog): amount is final.

        Other services: flexible pricing engine first, then fallback + markup where applicable.
        """
        from hospital.services.pricing_engine_service import pricing_engine
        from hospital.utils_invoice_line import lab_catalog_unit_price_for_service_code

        base = fallback_price if fallback_price is not None else Decimal('0.00')
        if not isinstance(base, Decimal):
            base = Decimal(str(base))

        payer_type = (getattr(payer, 'payer_type', None) or 'cash')
        if isinstance(payer_type, str):
            payer_type = payer_type.lower()

        code = (getattr(service_code, 'code', None) or '').strip().upper()
        cat = (getattr(service_code, 'category', None) or '').strip().lower()
        is_lab = (
            code.startswith('LAB-')
            or code.startswith('LABTEST-')
            or 'laboratory' in cat
            or cat == 'lab'
        )
        is_img = code.startswith('IMG-') or 'imaging' in cat or 'radiology' in cat or 'scan' in cat

        if is_lab and service_code:
            catalog_p = lab_catalog_unit_price_for_service_code(service_code)
            if catalog_p is not None and catalog_p > 0:
                base = catalog_p

        if payer_type == 'cash' and base > 0:
            return base

        if (is_lab or is_img) and base > 0:
            if catalog_tier_applied:
                return base
            return pricing_engine._apply_lab_imaging_markup(base, service_code, payer)

        try:
            price = pricing_engine.get_service_price(service_code=service_code, patient=patient, payer=payer)
            if price and price > 0:
                return price
        except Exception as exc:
            logger.warning("Pricing engine fallback for %s: %s", getattr(service_code, 'code', None), exc)
        return pricing_engine._apply_lab_imaging_markup(base, service_code, payer)

    @staticmethod
    def _finalize_invoice(invoice):
        invoice.status = 'issued'
        invoice.update_totals()

    @staticmethod
    def _ensure_insurance_claim_items(invoice):
        """
        Create InsuranceClaimItem for each invoice line that doesn't have one,
        when invoice payer is insurance (private/nhis). Used when we sync invoice
        payer to patient's primary_insurance so bills show under insurance billing.
        Uses get_or_create so we never raise inside the caller's atomic block.
        """
        if not invoice or not invoice.payer:
            return
        if invoice.payer.payer_type not in ('insurance', 'private', 'nhis'):
            return
        try:
            from hospital.models_insurance import InsuranceClaimItem
            from django.utils import timezone
            patient = invoice.patient
            if not patient:
                return
            insurance_id = (patient.insurance_id or patient.insurance_member_id) or "NOT_PROVIDED"
            for line in invoice.lines.filter(is_deleted=False):
                if line.is_insurance_excluded:
                    continue
                billed = (line.line_total or Decimal('0.00'))
                if billed < Decimal('0.01'):
                    billed = Decimal('0.01')
                service_desc = (line.description or (line.service_code.description if line.service_code else ''))[:500] or 'Service'
                InsuranceClaimItem.objects.get_or_create(
                    invoice_line=line,
                    defaults={
                        'patient': patient,
                        'payer': invoice.payer,
                        'patient_insurance_id': insurance_id,
                        'invoice': invoice,
                        'encounter': invoice.encounter,
                        'service_code': line.service_code,
                        'service_description': service_desc,
                        'service_date': invoice.issued_at.date() if invoice.issued_at else timezone.now().date(),
                        'billed_amount': billed,
                        'claim_status': 'pending',
                        'notes': f"Auto-generated from invoice line {line.id}",
                    },
                )
        except Exception as exc:
            logger.warning("Could not create insurance claim items for invoice %s: %s", getattr(invoice, 'invoice_number', invoice.pk), exc)

    @staticmethod
    def bill_poc_glucose_strip(encounter, strip_type, *, vital_sign=None):
        """
        Add a point-of-care glucose strip fee (RBS or FBS) to the encounter invoice.
        Merges quantity on repeat checks (same code on same invoice).
        Optionally deducts one formulary unit when settings.POC_GLUCOSE_STRIP_DRUG_ID is set
        (logged per VitalSign row to avoid double deduction).
        """
        from django.conf import settings as dj_settings

        from hospital.models import Drug
        from hospital.models_payment_verification import PharmacyStockDeductionLog
        from hospital.pharmacy_stock_utils import reduce_pharmacy_stock_once
        from hospital.utils_invoice_line import create_or_merge_invoice_line

        strip_type = (strip_type or '').strip().lower()
        if strip_type not in ('rbs', 'fbs'):
            return {'success': False, 'error': 'invalid_strip_type', 'message': 'Strip type must be rbs or fbs.'}

        if not encounter:
            return {'success': False, 'error': 'no_encounter', 'message': 'No encounter.'}
        if getattr(encounter, 'billing_closed_at', None):
            return {'success': False, 'error': 'billing_closed', 'message': 'Billing is closed for this encounter.'}

        patient = encounter.patient
        if not patient:
            return {'success': False, 'error': 'no_patient', 'message': 'Encounter has no patient.'}

        payer = AutoBillingService._ensure_payer(patient, encounter)
        base_price = getattr(dj_settings, 'POC_GLUCOSE_STRIP_GHS', Decimal('20'))
        if not isinstance(base_price, Decimal):
            base_price = Decimal(str(base_price))

        code_str = 'VITAL-POC-RBS' if strip_type == 'rbs' else 'VITAL-POC-FBS'
        label = 'POC glucose strip (RBS)' if strip_type == 'rbs' else 'POC glucose strip (FBS)'

        try:
            with transaction.atomic():
                invoice, _ = AutoBillingService._get_or_create_invoice(patient, encounter, payer)
                service_code = AutoBillingService._get_or_create_service_code(
                    code=code_str,
                    description=label,
                    category='Nursing Consumables',
                    default_price=base_price,
                )
                unit_price = AutoBillingService._resolve_price(
                    patient, payer, service_code, base_price, catalog_tier_applied=False
                )
                invoice_line, _ = create_or_merge_invoice_line(
                    invoice=invoice,
                    service_code=service_code,
                    quantity=Decimal('1'),
                    unit_price=unit_price,
                    description=label,
                )
                update_fields = []
                if not invoice_line.patient_pay_cash:
                    invoice_line.patient_pay_cash = True
                    update_fields.append('patient_pay_cash')
                if not getattr(invoice_line, 'is_insurance_excluded', False):
                    invoice_line.is_insurance_excluded = True
                    update_fields.append('is_insurance_excluded')
                if update_fields:
                    invoice_line.save(update_fields=update_fields)

                AutoBillingService._ensure_insurance_claim_items(invoice)
                AutoBillingService._finalize_invoice(invoice)

            stock_shortfall = None
            drug_id_str = (getattr(dj_settings, 'POC_GLUCOSE_STRIP_DRUG_ID', None) or '').strip()
            if drug_id_str and vital_sign is not None:
                try:
                    drug_uuid = uuid.UUID(str(drug_id_str))
                except (ValueError, TypeError, AttributeError):
                    drug_uuid = None
                if drug_uuid:
                    drug = Drug.objects.filter(pk=drug_uuid, is_deleted=False).first()
                    if drug:
                        try:
                            sf, applied = reduce_pharmacy_stock_once(
                                drug,
                                1,
                                PharmacyStockDeductionLog.SOURCE_VITAL_POC_GLUCOSE,
                                vital_sign.pk,
                            )
                            stock_shortfall = sf if applied else 0
                        except Exception as stock_exc:
                            logger.warning(
                                'POC glucose strip stock deduction failed encounter=%s vital=%s: %s',
                                encounter.pk,
                                vital_sign.pk,
                                stock_exc,
                                exc_info=True,
                            )

            return {
                'success': True,
                'invoice': invoice,
                'invoice_line': invoice_line,
                'stock_shortfall': stock_shortfall,
                'message': f'{label} added to bill.',
            }
        except Exception as exc:
            logger.exception('bill_poc_glucose_strip failed encounter=%s', getattr(encounter, 'pk', None))
            return {'success': False, 'error': str(exc), 'message': str(exc)}

    @staticmethod
    def check_payment_status(service_type, service_id):
        """
        Check if service has been paid for
        
        Args:
            service_type: 'lab', 'pharmacy', or 'imaging'
            service_id: ID of LabResult, Prescription, or ImagingStudy
        
        Returns:
            dict with payment status
        """
        try:
            if service_type == 'lab':
                from hospital.models import LabResult
                from hospital.models_payment_verification import LabResultRelease
                
                lab_result = LabResult.objects.get(id=service_id, is_deleted=False)
                
                try:
                    release_record = lab_result.release_record
                    is_paid = release_record.payment_receipt is not None
                    
                    return {
                        'paid': is_paid,
                        'status': release_record.release_status,
                        'receipt': release_record.payment_receipt if is_paid else None,
                        'message': 'Payment verified' if is_paid else 'Payment pending'
                    }
                except:
                    return {
                        'paid': False,
                        'status': 'pending_payment',
                        'receipt': None,
                        'message': 'Payment pending - bill not paid'
                    }
                    
            elif service_type == 'pharmacy':
                from hospital.models import Prescription
                from hospital.models_payment_verification import PharmacyDispensing
                
                prescription = Prescription.objects.get(id=service_id, is_deleted=False)
                
                try:
                    dispensing_record = prescription.dispensing_record
                    is_paid = dispensing_record.payment_receipt is not None
                    
                    return {
                        'paid': is_paid,
                        'status': dispensing_record.dispensing_status,
                        'receipt': dispensing_record.payment_receipt if is_paid else None,
                        'message': 'Payment verified' if is_paid else 'Payment pending'
                    }
                except:
                    return {
                        'paid': False,
                        'status': 'pending_payment',
                        'receipt': None,
                        'message': 'Payment pending - bill not paid'
                    }
            
            elif service_type == 'imaging':
                from hospital.models_advanced import ImagingStudy
                from hospital.models_payment_verification import ImagingRelease
                
                imaging_study = ImagingStudy.objects.get(id=service_id, is_deleted=False)
                
                try:
                    release_record = imaging_study.release_record
                    is_paid = release_record.payment_receipt is not None
                    
                    return {
                        'paid': is_paid,
                        'status': release_record.release_status,
                        'receipt': release_record.payment_receipt if is_paid else None,
                        'message': 'Payment verified' if is_paid else 'Payment pending'
                    }
                except:
                    return {
                        'paid': False,
                        'status': 'pending_payment',
                        'receipt': None,
                        'message': 'Payment pending - bill not paid'
                    }
                    
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
            return {
                'paid': False,
                'status': 'error',
                'receipt': None,
                'message': f'Error: {str(e)}'
            }


# Export
__all__ = ['AutoBillingService']


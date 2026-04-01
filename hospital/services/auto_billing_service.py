"""
💰 AUTOMATIC BILLING SERVICE
Auto-generates bills when services are ordered
Ensures payment before service delivery
"""
from datetime import timedelta
from decimal import Decimal
import logging

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
    def create_lab_bill(lab_result, *, notify_patient=True):
        """
        Auto-create bill when lab test is ordered.
        IDEMPOTENT: Calling multiple times (e.g. dashboard load, result entry) must NOT increase quantity.
        Lab quantity is always 1 per result - one test = one invoice line.
        Set notify_patient=False when batching (caller sends one notification per order).
        """
        from hospital.models import InvoiceLine
        from hospital.models_payment_verification import LabResultRelease

        try:
            with transaction.atomic():
                patient = lab_result.order.encounter.patient
                encounter = lab_result.order.encounter
                test = lab_result.test

                if getattr(encounter, 'billing_closed_at', None):
                    return {
                        'success': False,
                        'error': 'Billing closed for this encounter',
                        'message': 'No new charges can be added after discharge.',
                    }

                # IDEMPOTENCY: If this lab result was already billed (release record exists),
                # ALWAYS return without modifying - never fall through (prevents quantity inflation)
                release_record = LabResultRelease.objects.filter(lab_result=lab_result).first()
                if release_record:
                    payer = AutoBillingService._ensure_payer(patient, encounter)
                    invoice, _ = AutoBillingService._get_or_create_invoice(patient, encounter, payer)
                    if invoice:
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
                        ).first()
                        if existing_line:
                            return {
                                'success': True,
                                'invoice': invoice,
                                'invoice_line': existing_line,
                                'amount': existing_line.unit_price * existing_line.quantity,
                                'release_record': release_record,
                                'message': f'Bill already exists for {test.name}',
                            }
                    # Release exists but line not found (e.g. deleted invoice) - still return, do NOT add
                    return {
                        'success': True,
                        'invoice': invoice if invoice else None,
                        'invoice_line': None,
                        'amount': Decimal('0.00'),
                        'release_record': release_record,
                        'message': f'Bill already created for {test.name} (release record exists)',
                    }

                payer = AutoBillingService._ensure_payer(patient, encounter)
                invoice, _ = AutoBillingService._get_or_create_invoice(patient, encounter, payer)

                service_code = AutoBillingService._get_or_create_service_code(
                    code=f"LAB-{test.code or test.id or test.pk}",
                    description=test.name,
                    category='Laboratory Services',
                    default_price=test.price or Decimal('0.00')
                )

                unit_price = AutoBillingService._resolve_price(patient, payer, service_code, test.price)

                # Check for existing line - for labs, do NOT add quantity (one result = one bill)
                existing_line = InvoiceLine.objects.filter(
                    invoice=invoice,
                    service_code=service_code,
                    is_deleted=False
                ).select_for_update().first()
                
                if existing_line:
                    # Bill already exists - update price only, NEVER add quantity
                    # (prevents inflation from dashboard loads / repeated create_lab_bill calls)
                    existing_line.unit_price = unit_price
                    existing_line.line_total = existing_line.quantity * unit_price
                    existing_line.patient_pay_cash = True
                    existing_line.save()
                    invoice_line = existing_line
                    created = False
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
                            'patient_pay_cash': True,  # Pay at cashier before service
                        }
                    )

                    if not created:
                        # Race condition - line created by another process; do NOT add quantity
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
    def create_pharmacy_dispensing_record_only(prescription):
        """
        Create PharmacyDispensing only - NO InvoiceLine. Used when prescription is first created.
        Puts prescription in pharmacy queue for check/edit before sending to cashier/insurer.
        Bill (InvoiceLine) is created only when pharmacy sends to cashier/insurance.
        """
        from hospital.models_payment_verification import PharmacyDispensing
        try:
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

                        reduce_pharmacy_stock_once(
                            drug_to_dispense,
                            qty_int,
                            PharmacyStockDeductionLog.SOURCE_PHARMACY_DISPENSING,
                            dispensing_record.id,
                        )
                        dispensing_record.stock_reduced_at = timezone.now()
                        update_fields.append('stock_reduced_at')
                    dispensing_record.save(update_fields=update_fields)
                    logger.info(
                        "✅ Send to payer (insurance/corporate) – straight to ready: %s x%s - %s",
                        drug.name, qty, patient.full_name,
                    )
                else:
                    # Cash: notify patient to pay at cashier
                    line_total = invoice_line.line_total
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
    def create_imaging_bill(imaging_study):
        """
        Auto-create bill when imaging study is ordered (doctor or imaging dept).
        Creates a direct invoice line so the scan appears at cashier immediately.
        Resolves price from ImagingCatalog (match study_type to code/name).
        """
        from hospital.models import InvoiceLine
        from hospital.models_advanced import ImagingCatalog
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
                if encounter and getattr(encounter, 'billing_closed_at', None):
                    return {
                        'success': False,
                        'error': 'Billing closed for this encounter',
                        'message': 'No new charges can be added after discharge.',
                    }
                study_type = (imaging_study.study_type or '').strip()

                payer = AutoBillingService._ensure_payer(patient, encounter)
                payer_type = getattr(payer, 'payer_type', None) or 'cash'

                # Resolve price from ImagingCatalog by payer type (cash, corporate, insurance)
                default_price = Decimal('0.00')
                if study_type:
                    catalog = ImagingCatalog.objects.filter(
                        Q(code=study_type) | Q(name__iexact=study_type),
                        is_active=True,
                        is_deleted=False,
                    ).first()
                    if catalog:
                        if payer_type == 'corporate' and catalog.corporate_price is not None:
                            default_price = Decimal(str(catalog.corporate_price))
                        elif payer_type in ('nhis', 'private') and catalog.insurance_price is not None:
                            default_price = Decimal(str(catalog.insurance_price))
                        elif catalog.price is not None:
                            default_price = Decimal(str(catalog.price))

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
                    patient, payer, service_code, default_price
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
                    "✅ Auto-bill created for imaging %s - %s - GHS %s",
                    imaging_study.study_type or imaging_study.modality,
                    patient.full_name,
                    unit_price,
                )

                # Notify patient: pay at cashier before imaging service
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
        return f"IMG-{modality}-{study_type}"[:20]

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
    def _resolve_price(patient, payer, service_code, fallback_price):
        from hospital.services.pricing_engine_service import pricing_engine

        base = fallback_price or Decimal('0.00')
        payer_type = (getattr(payer, 'payer_type', None) or 'cash')
        if isinstance(payer_type, str):
            payer_type = payer_type.lower()

        # Cash patients: lab test / imaging catalog price is authoritative (avoids stale ServicePrice vs catalog UI)
        if payer_type == 'cash' and base > 0:
            return base

        try:
            price = pricing_engine.get_service_price(service_code=service_code, patient=patient, payer=payer)
            if price and price > 0:
                return price
        except Exception as exc:
            logger.warning("Pricing engine fallback for %s: %s", service_code.code, exc)
        # Fallback (e.g. lab test.price, imaging catalog price): still apply markup for insurance/corporate
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


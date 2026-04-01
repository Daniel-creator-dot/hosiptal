"""
Utility functions for safe InvoiceLine creation
Prevents duplicates by checking existing lines before creating new ones
"""
import logging
import re
import uuid as uuid_stdlib
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def _resolve_invoice_payer_for_line(invoice, patient):
    """Same rules as views_centralized_cashier._resolve_invoice_payer (kept here to avoid import cycles in display)."""
    if invoice and getattr(invoice, 'payer', None):
        return invoice.payer
    return getattr(patient, 'primary_insurance', None)


def resolve_lab_test_for_invoice_line(line):
    """
    Resolve LabTest from invoice line service code (LAB-*, LABTEST-*) or from descriptions.
    Billing uses LAB-{test.code|id|pk}; catalog may use different casing.
    """
    from hospital.models import LabTest

    sc = getattr(line, 'service_code', None)
    if not sc:
        return None
    code = (getattr(sc, 'code', None) or '').strip()
    if not code:
        return None
    cu = code.upper()
    if cu.startswith('LABTEST-'):
        rest = code[len('LABTEST-'):].strip()
        if not rest:
            return None
        return LabTest.objects.filter(pk=rest, is_deleted=False).first()
    if not cu.startswith('LAB-'):
        return None
    suffix = (code[4:] or '').strip()
    if not suffix:
        return None
    lab = LabTest.objects.filter(code__iexact=suffix, is_deleted=False).first()
    if lab:
        return lab
    lab = LabTest.objects.filter(pk=suffix, is_deleted=False).first()
    if lab:
        return lab
    try:
        lab = LabTest.objects.filter(pk=uuid_stdlib.UUID(suffix), is_deleted=False).first()
    except (ValueError, TypeError, AttributeError):
        lab = None
    if lab:
        return lab
    if len(suffix) == 32:
        try:
            u = uuid_stdlib.UUID(hex=suffix)
            lab = LabTest.objects.filter(pk=u, is_deleted=False).first()
            if lab:
                return lab
        except (ValueError, TypeError):
            pass
    for candidate in (
        (getattr(line, 'description', None) or '').strip(),
        (getattr(sc, 'description', None) or '').strip(),
    ):
        if not candidate:
            continue
        lab = LabTest.objects.filter(name__iexact=candidate, is_deleted=False).first()
        if lab:
            return lab
        first = candidate.split('(')[0].strip()
        if first and first != candidate:
            lab = LabTest.objects.filter(name__iexact=first, is_deleted=False).first()
            if lab:
                return lab
    return None


def lab_catalog_unit_price_for_line(line, patient, payer):
    """
    Unit price from LabTest.price + payer rules (AutoBillingService._resolve_price).
    Returns None if this line is not a resolvable lab catalog test.
    """
    from hospital.services.auto_billing_service import AutoBillingService

    sc = getattr(line, 'service_code', None)
    if not sc:
        return None
    lab = resolve_lab_test_for_invoice_line(line)
    if not lab:
        return None
    catalog = lab.price or Decimal('0.00')
    resolved = AutoBillingService._resolve_price(patient, payer, sc, catalog)
    if resolved is not None and resolved > 0:
        return Decimal(str(resolved))
    if catalog > 0:
        return Decimal(str(catalog))
    return None


_UUID_IN_TEXT = re.compile(
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
)


def resolve_drug_for_invoice_line(line):
    """
    Resolve Drug from DRUG-* service codes (uuid, DRUG-<drug_pk>-<prescription_pk>, or truncated id)
    or from line / service_code description. Consumables use DRUG-<drug_uuid> without prescription.
    """
    from django.db.models import CharField
    from django.db.models.functions import Cast

    from hospital.models import Drug

    if getattr(line, 'prescription', None) and getattr(line.prescription, 'drug', None):
        return line.prescription.drug
    sc = getattr(line, 'service_code', None)
    if not sc:
        return None
    code = (getattr(sc, 'code', None) or '').strip()
    if not code.upper().startswith('DRUG-'):
        return None
    rest = code[5:].strip()
    if not rest:
        return None

    for m in _UUID_IN_TEXT.findall(rest):
        try:
            u = uuid_stdlib.UUID(m)
            d = Drug.objects.filter(pk=u, is_deleted=False).first()
            if d:
                return d
        except (ValueError, TypeError):
            continue

    if len(rest) == 32 and all(c in '0123456789abcdefABCDEF' for c in rest):
        try:
            u = uuid_stdlib.UUID(hex=rest)
            d = Drug.objects.filter(pk=u, is_deleted=False).first()
            if d:
                return d
        except ValueError:
            pass

    try:
        u = uuid_stdlib.UUID(rest)
        d = Drug.objects.filter(pk=u, is_deleted=False).first()
        if d:
            return d
    except (ValueError, TypeError):
        pass

    try:
        qs = Drug.objects.filter(is_deleted=False).annotate(_idtxt=Cast('id', CharField())).filter(
            _idtxt__startswith=rest
        )
        d = qs.first()
        if d:
            return d
    except Exception:
        pass

    for candidate in (
        (getattr(line, 'description', None) or '').strip(),
        (getattr(sc, 'description', None) or '').strip(),
    ):
        if not candidate:
            continue
        first = candidate.split('(')[0].strip()
        for name in (candidate, first):
            if len(name) < 2:
                continue
            d = Drug.objects.filter(name__iexact=name, is_deleted=False).first()
            if d:
                return d
    return None


def drug_catalog_unit_price_for_line(line, patient, payer):
    """
    Unit price from Drug formulary (get_drug_price_for_prescription). Returns None if not a drug line.
    """
    from hospital.utils_billing import get_drug_price_for_prescription

    drug = resolve_drug_for_invoice_line(line)
    if not drug:
        return None
    price = get_drug_price_for_prescription(drug, payer=payer)
    if price is not None and price > 0:
        return Decimal(str(price))
    return None


def walkin_sale_item_unit_price_for_line(line):
    """
    Resolve unit price from WalkInPharmacySaleItem for WALKIN-* invoice lines.
    Description format is usually: "<drug name> <strength> (Sale PS....)".
    """
    from hospital.models_pharmacy_walkin import WalkInPharmacySale, WalkInPharmacySaleItem

    sc = getattr(line, 'service_code', None)
    code = (getattr(sc, 'code', None) or '').strip().upper() if sc else ''
    if not code.startswith('WALKIN-'):
        return None

    desc = (getattr(line, 'description', None) or '').strip()
    m = re.search(r'\(Sale\s+([^)]+)\)', desc, flags=re.IGNORECASE)
    if not m:
        return None
    sale_no = (m.group(1) or '').strip()
    if not sale_no:
        return None

    sale = WalkInPharmacySale.objects.filter(
        sale_number=sale_no,
        is_deleted=False,
    ).first()
    if not sale:
        return None

    item_label = desc.split('(Sale', 1)[0].strip()
    qs = WalkInPharmacySaleItem.objects.filter(
        sale=sale,
        is_deleted=False,
    ).select_related('drug')
    for item in qs:
        d = getattr(item, 'drug', None)
        if not d:
            continue
        label = f"{getattr(d, 'name', '')} {getattr(d, 'strength', '')}".strip()
        if item_label and label.lower() == item_label.lower():
            up = Decimal(str(getattr(item, 'unit_price', 0) or 0))
            if up > 0:
                return up

    # Fallback only when the sale has a single item (avoid mismatching multi-item baskets).
    if qs.count() == 1:
        only = qs.first()
        up = Decimal(str(getattr(only, 'unit_price', 0) or 0))
        if up > 0:
            return up
    return None


def imaging_catalog_unit_price_for_line(line, patient, payer):
    """
    Resolve imaging price from ImagingCatalog for IMGCAT-* and IMG-<modality>-<study_type> lines.
    Mirrors AutoBillingService.create_imaging_bill default catalog selection by payer type.
    """
    from django.db.models import Q

    from hospital.models_advanced import ImagingCatalog
    from hospital.services.auto_billing_service import AutoBillingService

    sc = getattr(line, 'service_code', None)
    if not sc:
        return None
    code = (getattr(sc, 'code', None) or '').strip()
    cu = code.upper()
    catalog = None

    if cu.startswith('IMGCAT-'):
        rest = code[len('IMGCAT-'):].strip()
        if rest:
            catalog = ImagingCatalog.objects.filter(pk=rest, is_deleted=False, is_active=True).first()
    elif cu.startswith('IMG-'):
        parts = code.split('-', 2)
        study_type = parts[2].strip() if len(parts) >= 3 else ''
        if study_type:
            catalog = ImagingCatalog.objects.filter(
                Q(code__iexact=study_type) | Q(name__iexact=study_type),
                is_deleted=False,
                is_active=True,
            ).first()

    if not catalog:
        return None

    payer_type = (getattr(payer, 'payer_type', None) or 'cash').lower()
    if payer_type == 'corporate' and catalog.corporate_price is not None:
        default_price = Decimal(str(catalog.corporate_price))
    elif payer_type in ('nhis', 'private', 'insurance') and catalog.insurance_price is not None:
        default_price = Decimal(str(catalog.insurance_price))
    else:
        default_price = Decimal(str(catalog.price or 0))

    if default_price <= 0:
        return None
    resolved = AutoBillingService._resolve_price(patient, payer, sc, default_price)
    if resolved is not None and resolved > 0:
        return Decimal(str(resolved))
    return default_price


def accommodation_unit_price_for_line(line):
    """Resolve bed/admission service defaults for DETENTION/ADM-* codes."""
    from hospital.services.bed_billing_service import BedBillingService

    sc = getattr(line, 'service_code', None)
    code = (getattr(sc, 'code', None) or '').strip().upper() if sc else ''
    if not code:
        return None
    if code == 'DETENTION':
        return Decimal(str(BedBillingService.DETENTION_RATE))
    if code == 'ADM-DOCTOR-CARE':
        return Decimal(str(BedBillingService.DOCTOR_CARE_PER_DAY))
    if code == 'ADM-NURSING-CARE':
        return Decimal(str(BedBillingService.NURSING_CARE_PER_DAY))
    if code == 'ADM-CONSUMABLES':
        return Decimal(str(BedBillingService.CONSUMABLES_PER_DAY))
    if code == 'ADM-ACCOM':
        desc = (getattr(line, 'description', None) or '').lower()
        if 'vip' in desc:
            return Decimal(str(BedBillingService.VIP_ADMISSION_DAILY_RATE))
        return Decimal(str(BedBillingService.ADMISSION_DAILY_RATE))
    return None


def create_or_merge_invoice_line(
    invoice,
    service_code,
    quantity,
    unit_price,
    description,
    prescription=None,
    discount_amount=Decimal('0.00'),
    tax_amount=Decimal('0.00'),
    max_quantity=None,
):
    """
    Safely create or merge invoice line - prevents duplicates
    
    Args:
        invoice: Invoice object
        service_code: ServiceCode object
        quantity: Decimal quantity
        unit_price: Decimal unit price
        description: String description
        prescription: Prescription object (optional)
        discount_amount: Decimal discount (default 0)
        tax_amount: Decimal tax (default 0)
        max_quantity: Optional cap when merging (e.g. 1 for imaging/consultation so line never exceeds this)
    
    Returns:
        tuple: (invoice_line, created) - created is True if new line was created, False if merged
    """
    from hospital.models import InvoiceLine
    
    quantity = Decimal(str(quantity))
    unit_price = Decimal(str(unit_price))
    discount_amount = Decimal(str(discount_amount))
    tax_amount = Decimal(str(tax_amount))
    
    with transaction.atomic():
        # Lock invoice to prevent race conditions. Use all_objects when available so
        # newly created invoices (e.g. total_amount=0) are findable; default manager
        # often excludes them (e.g. Invoice.VisibleManager filters total_amount__gt=0).
        manager = getattr(invoice.__class__, 'all_objects', invoice.__class__.objects)
        invoice = manager.select_for_update().get(pk=invoice.pk)
        
        # Check for existing line with same service_code
        existing_line = InvoiceLine.objects.filter(
            invoice=invoice,
            service_code=service_code,
            is_deleted=False
        ).select_for_update().first()
        
        if existing_line:
            # MERGE: Update existing line
            new_qty = existing_line.quantity + quantity
            # Cap at max_quantity when provided (e.g. imaging, consultation = 1 per line)
            if max_quantity is not None:
                new_qty = min(new_qty, Decimal(str(max_quantity)))
            # Consultation (CON001/CON002): always cap at 1 per encounter
            sc_code = getattr(service_code, 'code', None) or ''
            if (sc_code or '').strip().upper() in ('CON001', 'CON002'):
                new_qty = min(new_qty, Decimal('1'))
            existing_line.quantity = new_qty
            existing_line.unit_price = unit_price  # Use current price
            existing_line.discount_amount += discount_amount
            existing_line.tax_amount += tax_amount
            existing_line.line_total = (
                existing_line.quantity * existing_line.unit_price
                - existing_line.discount_amount
                + existing_line.tax_amount
            )
            
            # Update description to reflect total quantity
            if existing_line.description:
                base_desc = existing_line.description.split(' x')[0] if ' x' in existing_line.description else existing_line.description.split('(')[0].strip()
                existing_line.description = f"{base_desc} x{int(existing_line.quantity)}"
            elif description:
                base_desc = description.split(' x')[0] if ' x' in description else description.split('(')[0].strip()
                existing_line.description = f"{base_desc} x{int(existing_line.quantity)}"
            
            # Keep most recent prescription if provided
            if prescription:
                if not existing_line.prescription or (
                    existing_line.prescription and prescription.created and
                    prescription.created > existing_line.prescription.created
                ):
                    existing_line.prescription = prescription
            
            existing_line.save()
            
            logger.info(
                f"Merged invoice line: {service_code.code} on invoice {invoice.invoice_number} - "
                f"New qty: {quantity}, Total qty: {existing_line.quantity}"
            )
            
            return existing_line, False
        else:
            # CREATE: New line doesn't exist
            invoice_line = InvoiceLine.objects.create(
                invoice=invoice,
                service_code=service_code,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                discount_amount=discount_amount,
                tax_amount=tax_amount,
                line_total=quantity * unit_price - discount_amount + tax_amount,
                prescription=prescription,
            )
            
            logger.info(
                f"Created invoice line: {service_code.code} on invoice {invoice.invoice_number} - "
                f"Qty: {quantity}"
            )
            
            return invoice_line, True


def merge_duplicate_lines_on_invoice(invoice):
    """
    Merge duplicate invoice lines (same invoice + service_code) into one line per service_code.
    Keeps the first line, sums quantity from duplicates, updates line_total, soft-deletes the rest.
    Only considers billable lines (not waived) so waived history is left untouched.
    Returns the number of duplicate lines merged (removed).
    """
    from hospital.models import InvoiceLine

    lines = list(
        InvoiceLine.objects.filter(
            invoice=invoice, is_deleted=False, waived_at__isnull=True
        )
        .select_related("service_code")
        .order_by("id")
    )
    by_code = {}
    for line in lines:
        k = line.service_code_id
        if k not in by_code:
            by_code[k] = []
        by_code[k].append(line)

    merged_count = 0
    extra_ids = []
    for sc_id, group in by_code.items():
        if len(group) <= 1:
            continue
        keeper = group[0]
        extras = group[1:]
        total_qty = keeper.quantity
        for line in extras:
            total_qty += line.quantity
            extra_ids.append(line.id)
            merged_count += 1
            # Reassign insurance claim items from merged line to keeper so insurance stays correct
            try:
                from hospital.models_insurance import InsuranceClaimItem
                InsuranceClaimItem.objects.filter(
                    invoice_line_id=line.id, is_deleted=False
                ).update(invoice_line=keeper)
            except Exception:
                pass
        keeper.quantity = total_qty
        # Imaging/scan: one line per study, cap at 1 so merged duplicates don't show quantity > 1
        try:
            if getattr(keeper.service_code, 'code', None) and str(keeper.service_code.code or '').startswith('IMG-'):
                keeper.quantity = min(total_qty, Decimal('1'))
        except Exception:
            pass
        keeper.line_total = keeper.quantity * keeper.unit_price - keeper.discount_amount + keeper.tax_amount
        keeper.save(update_fields=["quantity", "line_total", "modified"])
    if extra_ids:
        InvoiceLine.objects.filter(id__in=extra_ids).update(is_deleted=True)
    return merged_count


def heal_invoice_zero_line_prices(invoice):
    """
    Persist unit_price/line_total when lines were saved as 0 but pricing/catalog can resolve
    an amount (e.g. after a bad repricing pass). Lazy-imports cashier pricing helpers.
    """
    from decimal import Decimal
    from hospital.models import InvoiceLine

    if not invoice or not getattr(invoice, 'pk', None):
        return False

    from hospital.views_centralized_cashier import (
        _compute_current_line_unit_price,
        _resolve_invoice_payer,
    )

    patient = invoice.patient
    payer = _resolve_invoice_payer(invoice, patient)
    changed = False

    lines = InvoiceLine.objects.filter(
        invoice=invoice,
        is_deleted=False,
        waived_at__isnull=True,
    ).select_related('service_code', 'prescription__drug')

    for line in lines:
        old_unit = Decimal(str(line.unit_price or 0))
        if old_unit > 0:
            continue
        new_unit = _compute_current_line_unit_price(line, patient, payer)
        if new_unit is None or new_unit <= 0:
            continue
        qty = Decimal(str(line.quantity or 1))
        line.unit_price = new_unit
        tax = Decimal(str(line.tax_amount or 0))
        discount = Decimal(str(line.discount_amount or 0))
        subtotal = qty * new_unit
        line.line_total = subtotal - discount + tax
        line.save(update_fields=['unit_price', 'line_total', 'modified'])
        changed = True

    if changed:
        invoice.update_totals()
    return changed


def invoice_line_display_unit_and_total(line):
    """
    Return (unit_price, line_total) for Total Bill / itemized views when stored values are 0
    but the line is still billable (repricing/sync bugs left zeros in the DB).
    Uses the same formula as InvoiceLine.save: qty * unit - discount + tax.
    When both unit and line total are zero, tries catalog/pricing resolution (same idea as
    heal_invoice_zero_line_prices, but read-only — does not persist).
    """
    up = Decimal(str(line.unit_price or 0))
    lt = Decimal(str(line.line_total or 0))
    qty = Decimal(str(line.quantity or 1))
    tax = Decimal(str(line.tax_amount or 0))
    disc = Decimal(str(line.discount_amount or 0))

    if getattr(line, 'waived_at', None):
        return up, lt

    if up == 0 and lt == 0:
        inv = getattr(line, 'invoice', None)
        if inv is not None:
            patient = inv.patient
            payer = _resolve_invoice_payer_for_line(inv, patient)
            # Catalog/default resolvers first (lab, drug, imaging, bed, walk-in).
            new_unit = lab_catalog_unit_price_for_line(line, patient, payer)
            if new_unit is None or new_unit <= 0:
                new_unit = drug_catalog_unit_price_for_line(line, patient, payer)
            if new_unit is None or new_unit <= 0:
                new_unit = imaging_catalog_unit_price_for_line(line, patient, payer)
            if new_unit is None or new_unit <= 0:
                new_unit = accommodation_unit_price_for_line(line)
            if new_unit is None or new_unit <= 0:
                new_unit = walkin_sale_item_unit_price_for_line(line)
            if new_unit is None or new_unit <= 0:
                try:
                    from hospital.views_centralized_cashier import _compute_current_line_unit_price

                    new_unit = _compute_current_line_unit_price(line, patient, payer)
                except Exception:
                    logger.exception('invoice_line_display_unit_and_total: fallback _compute_current_line_unit_price failed')
                    new_unit = None
            if new_unit is not None and new_unit > 0:
                up = new_unit
                lt = qty * up - disc + tax
    elif lt == 0 and up > 0:
        lt = qty * up - disc + tax
    elif up == 0 and lt > 0 and qty > 0:
        up = ((lt + disc - tax) / qty).quantize(Decimal('0.01'))
    return up, lt


def walkin_sale_item_display_unit_and_total(item):
    """Same idea for WalkInPharmacySaleItem rows on Total Bill."""
    up = Decimal(str(getattr(item, 'unit_price', None) or 0))
    lt = Decimal(str(getattr(item, 'line_total', None) or 0))
    qty = Decimal(str(getattr(item, 'quantity', None) or 1))
    if lt == 0 and up > 0 and qty > 0:
        lt = (up * qty).quantize(Decimal('0.01'))
    elif up == 0 and lt > 0 and qty > 0:
        up = (lt / qty).quantize(Decimal('0.01'))
    return up, lt



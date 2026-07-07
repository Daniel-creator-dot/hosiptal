"""
Utility functions for safe InvoiceLine creation
Prevents duplicates by checking existing lines before creating new ones
"""
import logging
import re
import uuid as uuid_stdlib
from decimal import Decimal
from functools import lru_cache
from django.db import transaction

logger = logging.getLogger(__name__)

_UUID_IN_TEXT = re.compile(
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
)


def _uuid_pk_from_string(value):
    """Return a UUID for pk lookup, or None when value is not uuid-shaped (e.g. lab code 000185)."""
    if not value:
        return None
    s = str(value).strip()
    try:
        if len(s) == 32 and all(c in '0123456789abcdefABCDEF' for c in s):
            return uuid_stdlib.UUID(hex=s)
        return uuid_stdlib.UUID(s)
    except (ValueError, TypeError, AttributeError):
        return None


def _lab_test_code_lookup_variants(suffix):
    """
    Distinct LabTest.code strings to try for a LAB-/LABTEST- suffix.
    Handles catalog codes with leading zeros (000185 vs 185) without treating them as UUIDs.
    """
    s = (suffix or '').strip()
    if not s:
        return
    seen = set()

    def _emit(v):
        v = (v or '').strip()
        if v and v not in seen:
            seen.add(v)
            return v
        return None

    for candidate in (s,):
        out = _emit(candidate)
        if out:
            yield out
    if s.isdigit():
        stripped = s.lstrip('0') or '0'
        for candidate in (stripped,):
            out = _emit(candidate)
            if out:
                yield out
        for width in (3, 4, 5, 6, 7, 8):
            out = _emit(stripped.zfill(width))
            if out:
                yield out


def _lookup_lab_test_by_code_variants(suffix):
    from hospital.models import LabTest

    qs = LabTest.objects.filter(is_deleted=False)
    for variant in _lab_test_code_lookup_variants(suffix):
        lab = qs.filter(code__iexact=variant).first()
        if lab:
            return lab
    return None


def _lookup_lab_test_by_descriptions(descriptions):
    from hospital.models import LabTest

    qs = LabTest.objects.filter(is_deleted=False)
    for raw in descriptions:
        candidate = (raw or '').strip()
        if not candidate:
            continue
        lab = qs.filter(name__iexact=candidate).first()
        if lab:
            return lab
        first = candidate.split('(')[0].strip()
        if first and first != candidate:
            lab = qs.filter(name__iexact=first).first()
            if lab:
                return lab
    return None


def _resolve_lab_test_from_suffix(suffix, description_hints=()):
    """Resolve LabTest from the part after LAB- / LABTEST- (code, uuid, or description hints)."""
    from hospital.models import LabTest

    suffix = (suffix or '').strip()
    if suffix:
        lab = _lookup_lab_test_by_code_variants(suffix)
        if lab:
            return lab
        pk = _uuid_pk_from_string(suffix)
        if pk:
            lab = LabTest.objects.filter(pk=pk, is_deleted=False).first()
            if lab:
                return lab
    return _lookup_lab_test_by_descriptions(description_hints)


def _resolve_invoice_payer_for_line(invoice, patient):
    """Same rules as views_centralized_cashier._resolve_invoice_payer (kept here to avoid import cycles in display)."""
    if invoice and getattr(invoice, 'payer', None):
        return invoice.payer
    return getattr(patient, 'primary_insurance', None)


def resolve_lab_test_for_invoice_line(line):
    """
    Resolve LabTest from invoice line service code (LAB-*, LABTEST-*) or from descriptions.
    Billing uses LAB-{test.code|id|pk}; catalog may use different casing or zero-padded codes.
    """
    sc = getattr(line, 'service_code', None)
    if not sc:
        return None
    code = (getattr(sc, 'code', None) or '').strip()
    if not code:
        return None
    cu = code.upper()
    hints = (
        (getattr(line, 'description', None) or '').strip(),
        (getattr(sc, 'description', None) or '').strip(),
    )
    if cu.startswith('LABTEST-'):
        suffix = code[len('LABTEST-'):].strip()
        if not suffix and not any(hints):
            return None
        return _resolve_lab_test_from_suffix(suffix, description_hints=hints)
    if not cu.startswith('LAB-'):
        return None
    suffix = (code[4:] or '').strip()
    if not suffix and not any(hints):
        return None
    return _resolve_lab_test_from_suffix(suffix, description_hints=hints)


def resolve_lab_test_for_service_code(service_code):
    """
    Resolve LabTest from a ServiceCode (LAB-*, LABTEST-*) using the same rules as invoice lines.
    """
    if not service_code:
        return None

    class _LineStub:
        pass

    stub = _LineStub()
    stub.service_code = service_code
    stub.description = (getattr(service_code, 'description', None) or '')
    stub.prescription = None
    return resolve_lab_test_for_invoice_line(stub)


def lab_catalog_unit_price_for_service_code(service_code):
    """Current LabTest.list price for this service code, or None if not a resolvable lab test."""
    lab = resolve_lab_test_for_service_code(service_code)
    if not lab or lab.price is None:
        return None
    d = Decimal(str(lab.price))
    return d if d > 0 else None


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


def resolve_imaging_catalog_for_invoice_line(line):
    """
    Return ImagingCatalog for IMGCAT-* and IMG-<modality>-<study_type> lines, or None.
    Used to merge duplicate imaging rows that use different ServiceCode rows for the same study.
    """
    from django.db.models import Q

    from hospital.models_advanced import ImagingCatalog

    sc = getattr(line, 'service_code', None)
    if not sc:
        return None
    code = (getattr(sc, 'code', None) or '').strip()
    cu = code.upper()
    catalog = None

    if cu.startswith('IMGCAT-'):
        rest = code[len('IMGCAT-'):].strip()
        if rest:
            catalog = ImagingCatalog.objects.filter(
                code__iexact=rest,
                is_deleted=False,
                is_active=True,
            ).first()
            if not catalog:
                pk = _uuid_pk_from_string(rest)
                if pk:
                    catalog = ImagingCatalog.objects.filter(
                        pk=pk, is_deleted=False, is_active=True
                    ).first()
    elif cu.startswith('IMG-'):
        parts = code.split('-', 2)
        study_type = parts[2].strip() if len(parts) >= 3 else ''
        modality = parts[1].strip() if len(parts) >= 2 else ''
        if study_type:
            catalog = ImagingCatalog.objects.filter(
                Q(code__iexact=study_type)
                | Q(name__iexact=study_type)
                | Q(study_type__iexact=study_type),
                is_deleted=False,
                is_active=True,
            ).first()
        if not catalog and modality and study_type:
            catalog = (
                ImagingCatalog.objects.filter(modality__iexact=modality, is_deleted=False, is_active=True)
                .filter(
                    Q(code__iexact=study_type)
                    | Q(name__iexact=study_type)
                    | Q(study_type__iexact=study_type)
                )
                .first()
            )

    return catalog


def imaging_catalog_unit_price_for_line(line, patient, payer):
    """
    Resolve imaging price from ImagingCatalog for IMGCAT-* and IMG-<modality>-<study_type> lines.
    Mirrors AutoBillingService.create_imaging_bill default catalog selection by payer type.
    """
    from hospital.services.auto_billing_service import AutoBillingService

    catalog = resolve_imaging_catalog_for_invoice_line(line)
    if not catalog:
        return None

    sc = getattr(line, 'service_code', None)

    payer_type = (getattr(payer, 'payer_type', None) or 'cash').lower()
    if payer_type == 'corporate' and catalog.corporate_price is not None:
        default_price = Decimal(str(catalog.corporate_price))
        catalog_tier_applied = True
    elif payer_type in ('nhis', 'private', 'insurance') and catalog.insurance_price is not None:
        default_price = Decimal(str(catalog.insurance_price))
        catalog_tier_applied = True
    else:
        default_price = Decimal(str(catalog.price or 0))
        catalog_tier_applied = False

    if default_price <= 0:
        return None
    resolved = AutoBillingService._resolve_price(
        patient, payer, sc, default_price, catalog_tier_applied=catalog_tier_applied
    )
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
        invoice.update_totals()
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


def invoice_line_effective_total(line):
    """
    Canonical line charge: qty × unit_price − discount + tax.
    Waived lines always contribute 0 (matches Invoice.calculate_totals).
    """
    if getattr(line, 'waived_at', None):
        return Decimal('0.00')
    qty = Decimal(str(line.quantity or 1))
    up = Decimal(str(line.unit_price or 0))
    disc = Decimal(str(line.discount_amount or 0))
    tax = Decimal(str(line.tax_amount or 0))
    return qty * up - disc + tax


def invoice_line_remaining_balances(invoice):
    """
    FIFO settlement of payments/deposits already applied to an invoice.

    Treat (sum of line totals - balance) as amount already collected and consume it
    against billable lines in created order. Returns one dict per billable line with
    remaining due.

    Call after invoice.update_totals() so balance is current.
    """
    from hospital.models import InvoiceLine

    if not invoice or not getattr(invoice, 'pk', None):
        return []

    inv_balance = Decimal(str(getattr(invoice, 'balance', None) or 0))

    lines = list(
        InvoiceLine.objects.filter(
            invoice=invoice,
            is_deleted=False,
            waived_at__isnull=True,
        )
        .select_related('service_code')
        .order_by('created', 'id')
    )

    if not lines:
        return []

    line_gross = sum(
        (invoice_line_effective_total(line) for line in lines),
        Decimal('0.00'),
    )
    # Use line gross (not invoice.total_amount) so stale header totals do not
    # over-mark lines as paid when total_amount > sum of lines.
    amount_already_applied = max(Decimal('0.00'), line_gross - inv_balance)

    if inv_balance <= 0:
        return [
            {
                'line': line,
                'line_total': invoice_line_effective_total(line),
                'amount_paid': invoice_line_effective_total(line),
                'amount_remaining': Decimal('0.00'),
                'is_fully_paid': True,
            }
            for line in lines
        ]

    pool = amount_already_applied
    rows = []
    open_indices = []

    for line in lines:
        line_total = invoice_line_effective_total(line)
        if line_total <= 0:
            rows.append({
                'line': line,
                'line_total': line_total,
                'amount_paid': Decimal('0.00'),
                'amount_remaining': Decimal('0.00'),
                'is_fully_paid': True,
            })
            continue

        if pool >= line_total:
            paid_on_line = line_total
            remaining = Decimal('0.00')
            pool -= line_total
            is_fully_paid = True
        elif pool > 0:
            paid_on_line = pool
            remaining = line_total - pool
            pool = Decimal('0.00')
            is_fully_paid = False
        else:
            paid_on_line = Decimal('0.00')
            remaining = line_total
            is_fully_paid = False

        rows.append({
            'line': line,
            'line_total': line_total,
            'amount_paid': paid_on_line,
            'amount_remaining': remaining,
            'is_fully_paid': is_fully_paid,
        })
        if not is_fully_paid and remaining > 0:
            open_indices.append(len(rows) - 1)

    # Penny drift: line remainders must sum to invoice.balance
    if open_indices:
        sum_remaining = sum(rows[i]['amount_remaining'] for i in open_indices)
        drift = inv_balance - sum_remaining
        if drift != 0:
            last_idx = open_indices[-1]
            adjusted = rows[last_idx]['amount_remaining'] + drift
            rows[last_idx]['amount_remaining'] = max(Decimal('0.00'), adjusted)
            rows[last_idx]['is_fully_paid'] = rows[last_idx]['amount_remaining'] <= 0
            if rows[last_idx]['is_fully_paid']:
                rows[last_idx]['amount_paid'] = rows[last_idx]['line_total']

    return rows


def invoice_open_balance_due(invoice):
    """
    Outstanding due for cashier display: sum of FIFO line remainings.
    Matches the Amount column on Total Bill / combined payment breakdowns.
    """
    rows = invoice_line_remaining_balances(invoice)
    if not rows:
        return Decimal(str(getattr(invoice, 'balance', None) or 0))
    return sum((r['amount_remaining'] for r in rows), Decimal('0.00'))


def invoice_breakdown_rows_for_display(invoice):
    """
    Build Total Bill / combined-payment breakdown rows with per-line remaining due (FIFO).
    Fully paid lines are included with is_paid=True and amount 0 for badge display.
    """
    inv_balance = getattr(invoice, 'balance', None) or Decimal('0.00')
    invoice_fully_paid = inv_balance <= 0
    remaining_rows = invoice_line_remaining_balances(invoice)
    breakdown = []

    for row in remaining_rows:
        line = row['line']
        desc = invoice_line_display_description(line)
        _up, _gross = invoice_line_display_unit_and_total(line)
        is_fully_paid = row['is_fully_paid'] or invoice_fully_paid
        amount = row['amount_remaining'] if not is_fully_paid else Decimal('0.00')
        breakdown.append({
            'description': desc,
            'quantity': line.quantity,
            'unit_price': _up,
            'amount': amount,
            'line_id': str(line.id),
            'is_waived': False,
            'is_paid': is_fully_paid,
            'line_total_gross': _gross,
            'amount_paid_on_line': row['amount_paid'],
        })

    if not breakdown:
        return [{
            'description': 'No line items yet',
            'quantity': 0,
            'unit_price': 0,
            'amount': Decimal('0.00'),
            'is_paid': invoice_fully_paid,
        }]

    return breakdown


def invoice_line_display_description(line):
    """
    Text to show patients/staff for an invoice line. Prefer the line's own description
    (set when the charge was added) over ServiceCode.description so CASH-MISC and similar
    do not show the generic \"Cashier-Added Service\" label when a specific name was stored.
    """
    ld = (getattr(line, 'description', None) or '').strip()
    if ld:
        return ld
    sc = getattr(line, 'service_code', None)
    return (getattr(sc, 'description', None) or '').strip() or '—'


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
        return Decimal('0'), Decimal('0')

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
    if up > 0:
        # Always derive from unit/qty/discount/tax — stored line_total can be stale after
        # merges, qty edits, or bulk updates and would disagree with invoice balance.
        lt = qty * up - disc + tax
    elif lt > 0 and qty > 0:
        up = ((lt + disc - tax) / qty).quantize(Decimal('0.01'))
    return up, lt


def align_invoice_breakdown_to_balance(breakdown, inv_balance):
    """
    Scale per-line breakdown amounts so they sum to the invoice balance due when
    deposits/partial payments mean balance < gross line charges.
    """
    if not breakdown:
        return breakdown
    inv_balance = Decimal(str(inv_balance or 0))
    if inv_balance <= 0:
        for row in breakdown:
            row['amount'] = Decimal('0.00')
        return breakdown
    gross = sum(Decimal(str(r.get('amount') or 0)) for r in breakdown)
    if gross <= 0 or gross == inv_balance:
        return breakdown
    if gross < inv_balance:
        return breakdown
    ratio = inv_balance / gross
    running = Decimal('0.00')
    last_idx = len(breakdown) - 1
    for i, row in enumerate(breakdown):
        if i == last_idx:
            row['amount'] = (inv_balance - running).quantize(Decimal('0.01'))
        else:
            amt = (Decimal(str(row.get('amount') or 0)) * ratio).quantize(Decimal('0.01'))
            row['amount'] = amt
            running += amt
    return breakdown


def walkin_sale_item_display_unit_and_total(item):
    """Same idea for WalkInPharmacySaleItem rows on Total Bill."""
    if getattr(item, 'waived_at', None):
        return Decimal('0'), Decimal('0')
    up = Decimal(str(getattr(item, 'unit_price', None) or 0))
    lt = Decimal(str(getattr(item, 'line_total', None) or 0))
    qty = Decimal(str(getattr(item, 'quantity', None) or 1))
    if lt == 0 and up > 0 and qty > 0:
        lt = (up * qty).quantize(Decimal('0.01'))
    elif up == 0 and lt > 0 and qty > 0:
        up = (lt / qty).quantize(Decimal('0.01'))
    return up, lt


def _corporate_pack_strip_qty_suffix(desc):
    """Remove trailing ' x1' / ' ×2' style quantity suffix from invoice line descriptions."""
    s = (desc or '').strip()
    if not s:
        return ''
    return re.sub(r'\s*[x×]\s*\d+(?:\.\d+)?\s*$', '', s, flags=re.IGNORECASE).strip()


def _corporate_pack_resolve_imaging_catalog_display(line):
    """
    ImagingCatalog for corporate pack display: IMGCAT-/IMG- codes plus plain catalog codes (e.g. ECG001).
    """
    cat = resolve_imaging_catalog_for_invoice_line(line)
    if cat:
        return cat
    sc = getattr(line, 'service_code', None)
    code = (getattr(sc, 'code', None) or '').strip()
    if not code:
        return None
    from hospital.models_advanced import ImagingCatalog

    return ImagingCatalog.objects.filter(
        code__iexact=code,
        is_deleted=False,
        is_active=True,
    ).first()


def corporate_pack_line_is_imaging(line, category=None):
    """True when the row should get imaging-style service description (name under code, refs)."""
    cat_cf = (category or '').casefold()
    if 'imaging' in cat_cf or 'radiology' in cat_cf or 'scan' in cat_cf:
        return True
    sc = getattr(line, 'service_code', None)
    cu = (getattr(sc, 'code', None) or '').strip().upper()
    if cu.startswith('IMG-') or cu.startswith('IMGCAT-'):
        return True
    return _corporate_pack_resolve_imaging_catalog_display(line) is not None


@lru_cache(maxsize=512)
def _corporate_employee_id_for_patient_pk(patient_pk: str) -> str:
    """Active corporate enrollment staff/company ID for patient (cached by pk string)."""
    if not patient_pk:
        return ''
    from hospital.models_enterprise_billing import CorporateEmployee

    row = (
        CorporateEmployee.objects.filter(
            patient_id=patient_pk,
            is_active=True,
            is_deleted=False,
        )
        .exclude(employee_id='')
        .order_by('-enrollment_date')
        .values_list('employee_id', flat=True)
        .first()
    )
    return (row or '').strip()


def corporate_pack_patient_staff_and_policy_refs(patient):
    """
    Company staff ID (corporate enrollment) plus insurance member/policy fields when set.
    Used under imaging lines on corporate bill pack UI and exports.
    """
    if not patient:
        return ''
    parts = []
    pk = getattr(patient, 'pk', None)
    if pk:
        ce = _corporate_employee_id_for_patient_pk(str(pk))
        if ce:
            parts.append(f'Staff ID: {ce}')
    member = (getattr(patient, 'insurance_member_id', None) or '').strip()
    ins_id = (getattr(patient, 'insurance_id', None) or '').strip()
    policy = (getattr(patient, 'insurance_policy_number', None) or '').strip()
    group = (getattr(patient, 'insurance_group_number', None) or '').strip()
    if member:
        parts.append(f'Member ID: {member}')
    elif ins_id:
        parts.append(f'Member ID: {ins_id}')
    if policy:
        parts.append(f'Policy: {policy}')
    if group:
        parts.append(f'Group: {group}')
    return ' · '.join(parts)


def corporate_pack_imaging_service_display_text(line, patient=None, category=None):
    """
    Multi-line service cell for imaging on corporate bill pack: code/qty row, catalog name when known,
    then staff/policy refs when available. Non-imaging lines return the stored description only.
    """
    raw = (getattr(line, 'description', None) or '').strip()
    if not raw:
        raw = '—'
    if not corporate_pack_line_is_imaging(line, category=category):
        return raw

    out = [raw]
    base_no_qty = _corporate_pack_strip_qty_suffix(raw)
    base_cf = base_no_qty.casefold()
    raw_cf = raw.casefold()

    catalog = _corporate_pack_resolve_imaging_catalog_display(line)
    human = None
    if catalog:
        name = (getattr(catalog, 'name', None) or '').strip()
        if name and name.casefold() not in (base_cf, raw_cf):
            human = name
        elif not human:
            desc = (getattr(catalog, 'description', None) or '').strip()
            if desc and desc.casefold() not in (base_cf, raw_cf):
                human = desc

    if not human:
        sc = getattr(line, 'service_code', None)
        sd = (getattr(sc, 'description', None) or '').strip()
        if sd and sd.casefold() not in (base_cf, raw_cf):
            human = sd

    if human:
        out.append(human)

    refs = corporate_pack_patient_staff_and_policy_refs(patient)
    if refs:
        out.append(refs)

    return '\n'.join(out)


def corporate_pack_excel_category_service_cell(category, line, patient):
    """
    One worksheet cell: 'Category — first line of service' then extra lines (imaging name, refs).
    """
    full = corporate_pack_imaging_service_display_text(line, patient=patient, category=category)
    lines = [ln for ln in full.split('\n') if ln.strip()]
    if not lines:
        return str(category)
    head = f'{category} — {lines[0]}'
    if len(lines) == 1:
        return head
    return head + '\n' + '\n'.join(lines[1:])



"""
Per-row receipt amounts for pharmacy dispensing UIs.

One cashier PaymentReceipt is often linked to every PharmacyDispensing on the same
encounter payment; showing payment_receipt.amount_paid on each row repeats the full total.

Shared rows are counted by payment_receipt (not prescription order), because multiple
prescriptions may sit on different orders while still sharing one receipt.

Line totals are resolved from InvoiceLine when possible. If the receipt's invoice FK
does not carry the pharmacy line (data quirks), we search any line for this prescription
on the encounter. If still unknown, we allocate the receipt across sibling dispensings
proportionally to catalog unit_price × quantity so rows are not all the full total.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional


def _decimal_line_total_from_invoice_line(il: Any) -> Optional[Decimal]:
    if il is None:
        return None
    try:
        tot = getattr(il, "display_line_total", None)
        if tot is None:
            tot = il.line_total
        if tot is None:
            qty = Decimal(str(il.quantity or 1))
            up = Decimal(str(il.unit_price or 0))
            tot = qty * up
        out = Decimal(str(tot))
        if out <= 0:
            return None
        return out
    except Exception:
        return None


def _invoice_line_for_prescription_on_invoice(invoice: Any, prescription: Any) -> Optional[Any]:
    if not invoice or not prescription:
        return None
    try:
        from .models import InvoiceLine

        return (
            InvoiceLine.objects.filter(
                invoice=invoice,
                prescription=prescription,
                is_deleted=False,
                waived_at__isnull=True,
            )
            .order_by("-created")
            .first()
        )
    except Exception:
        return None


def _invoice_line_for_prescription_on_encounter(prescription: Any, encounter_id: Any) -> Optional[Any]:
    """Any non-waived line for this prescription on an invoice for the encounter."""
    if not prescription or not encounter_id:
        return None
    try:
        from .models import InvoiceLine

        return (
            InvoiceLine.objects.filter(
                prescription=prescription,
                invoice__encounter_id=encounter_id,
                invoice__is_deleted=False,
                is_deleted=False,
                waived_at__isnull=True,
            )
            .exclude(invoice__status__iexact="cancelled")
            .select_related("invoice")
            .order_by("-invoice__created", "-created")
            .first()
        )
    except Exception:
        return None


def _invoice_line_by_service_code_suffix(prescription: Any, encounter_id: Any) -> Optional[Any]:
    """Billing uses DRUG-...-{prescription.id}; match when prescription FK is missing."""
    if not prescription or not encounter_id:
        return None
    try:
        from .models import InvoiceLine

        sid = str(prescription.pk)
        return (
            InvoiceLine.objects.filter(
                invoice__encounter_id=encounter_id,
                invoice__is_deleted=False,
                is_deleted=False,
                waived_at__isnull=True,
                service_code__code__endswith="-" + sid,
            )
            .exclude(invoice__status__iexact="cancelled")
            .select_related("invoice", "service_code")
            .order_by("-invoice__created", "-created")
            .first()
        )
    except Exception:
        return None


def _catalog_subtotal_for_dispensing(dispensing: Any) -> Decimal:
    drug = getattr(dispensing, "drug_to_dispense", None)
    if drug is None and getattr(dispensing, "prescription", None):
        drug = dispensing.prescription.drug
    qty = Decimal(str(dispensing.quantity_dispensed or dispensing.quantity_ordered or 1))
    if qty <= 0:
        qty = Decimal("1")
    if drug is None:
        return Decimal("0")
    try:
        up = Decimal(str(getattr(drug, "unit_price", None) or 0))
    except Exception:
        up = Decimal("0")
    return up * qty


def _sibling_dispensings_for_receipt(pr: Any):
    from .models_payment_verification import PharmacyDispensing

    return (
        PharmacyDispensing.objects.filter(
            payment_receipt_id=pr.id,
            is_deleted=False,
        )
        .exclude(dispensing_status="cancelled")
        .select_related("prescription__drug", "substitute_drug")
    )


def _weighted_amount_for_dispensing(pr: Any, dispensing: Any, siblings: List[Any]) -> Optional[Decimal]:
    """
    Split receipt amount across siblings by catalog subtotals (unit_price × qty).
    Rows with zero catalog subtotal get a tiny weight so the receipt is still split.
    """
    if not siblings:
        return None
    full = Decimal(str(pr.amount_paid or 0))
    raw = [_catalog_subtotal_for_dispensing(s) for s in siblings]
    adj = [w if w > 0 else Decimal("0.01") for w in raw]
    total_w = sum(adj)
    if total_w <= 0:
        return None
    try:
        idx = next(i for i, s in enumerate(siblings) if s.pk == dispensing.pk)
    except StopIteration:
        idx = 0
    try:
        return (full * (adj[idx] / total_w)).quantize(Decimal("0.01"))
    except Exception:
        return None


def attributed_receipt_amounts_for_dispensing(
    dispensing: Any,
    *,
    line_total_override: Optional[Decimal] = None,
) -> Dict[str, Any]:
    """
    Return line_amount (this row), receipt_full (actual receipt), shared_count.

    line_total_override: invoice line total when already loaded (e.g. served-detail API).

    If dispensing has no payment_receipt:
      line_amount and receipt_full are None, shared_count 0.
    """
    pr = getattr(dispensing, "payment_receipt", None)
    if not pr:
        return {"line_amount": None, "receipt_full": None, "shared_count": 0}

    full = Decimal(str(pr.amount_paid or 0))
    rx = getattr(dispensing, "prescription", None)

    siblings = list(_sibling_dispensings_for_receipt(pr))
    shared_count = len(siblings) if siblings else 1
    if shared_count <= 0:
        shared_count = 1

    attributed: Optional[Decimal] = None
    if line_total_override is not None:
        try:
            lt = Decimal(str(line_total_override))
            if lt > 0:
                attributed = lt
        except Exception:
            pass

    inv_from_receipt = getattr(pr, "invoice", None)
    if attributed is None and rx:
        il = None
        if inv_from_receipt:
            il = _invoice_line_for_prescription_on_invoice(inv_from_receipt, rx)
        if il is None and getattr(rx, "order", None):
            enc_id = getattr(rx.order, "encounter_id", None)
            if enc_id:
                il = _invoice_line_for_prescription_on_encounter(rx, enc_id)
                if il is None:
                    il = _invoice_line_by_service_code_suffix(rx, enc_id)
        if il is not None:
            attributed = _decimal_line_total_from_invoice_line(il)

    if attributed is None:
        if shared_count > 1:
            weighted = _weighted_amount_for_dispensing(pr, dispensing, siblings)
            if weighted is not None:
                attributed = weighted
            else:
                try:
                    attributed = (full / Decimal(shared_count)).quantize(Decimal("0.01"))
                except Exception:
                    attributed = full
        else:
            attributed = full

    return {"line_amount": attributed, "receipt_full": full, "shared_count": shared_count}

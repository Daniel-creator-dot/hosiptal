"""
JSON payloads for pharmacy served-medication detail modals (dashboard + dispensing UI).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.urls import reverse
from django.utils import timezone


def _fmt_dt(dt) -> str:
    if not dt:
        return ''
    try:
        return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return str(dt)


def _serialize_patient(patient) -> Dict[str, Any]:
    if not patient:
        return {}
    return {
        'id': str(patient.pk),
        'full_name': getattr(patient, 'full_name', '') or '',
        'mrn': getattr(patient, 'mrn', '') or '',
        'phone': getattr(patient, 'phone_number', '') or '',
    }


def _serialize_payer(patient, encounter) -> Dict[str, Any]:
    from .utils_billing import patient_payer_display_labels

    if not patient:
        return {'label': 'Cash'}
    labels = patient_payer_display_labels(patient, encounter) or []
    label = labels[0] if labels else 'Cash'
    return {'label': label, 'display_labels': labels}


def _serialize_order(order) -> Dict[str, Any]:
    if not order:
        return {}
    return {
        'id': str(order.pk),
        'requested_at': _fmt_dt(getattr(order, 'requested_at', None)),
        'status': getattr(order, 'status', '') or '',
    }


def _serialize_prescription(rx) -> Dict[str, Any]:
    if not rx:
        return {}
    prescribed_by = ''
    if getattr(rx, 'prescribed_by', None) and getattr(rx.prescribed_by, 'user', None):
        prescribed_by = rx.prescribed_by.user.get_full_name() or rx.prescribed_by.user.username
    drug = getattr(rx, 'drug', None)
    return {
        'id': str(rx.pk),
        'drug_name': drug.name if drug else '',
        'drug_strength': getattr(drug, 'strength', '') or '',
        'quantity': int(rx.quantity or 0),
        'dose': rx.dose or '',
        'frequency': rx.frequency or '',
        'route': rx.route or '',
        'instructions': rx.instructions or '',
        'prescribed_on': _fmt_dt(getattr(rx, 'created', None)),
        'prescribed_by': prescribed_by,
    }


def _serialize_invoice(inv) -> Optional[Dict[str, Any]]:
    if not inv:
        return None
    try:
        inv.calculate_totals()
    except Exception:
        pass
    balance = inv.balance if inv.balance is not None else inv.total_amount
    return {
        'id': str(inv.pk),
        'invoice_number': inv.invoice_number or '',
        'status': inv.status or '',
        'payer_name': getattr(inv.payer, 'name', '') if getattr(inv, 'payer', None) else '',
        'total_amount': float(inv.total_amount or 0),
        'balance': float(balance or 0),
    }


def _serialize_invoice_line(line) -> Optional[Dict[str, Any]]:
    if not line:
        return None
    return {
        'description': line.description or '',
        'quantity': float(line.quantity or 0),
        'unit_price': float(getattr(line, 'display_unit_price', None) or line.unit_price or 0),
        'line_total': float(getattr(line, 'display_line_total', None) or line.line_total or 0),
    }


def _invoice_line_for_prescription(rx, encounter):
    from .models import InvoiceLine

    if not rx:
        return None
    line = (
        InvoiceLine.objects.filter(
            prescription=rx,
            is_deleted=False,
            waived_at__isnull=True,
        )
        .select_related('invoice')
        .order_by('-created')
        .first()
    )
    if line:
        return line
    if not encounter:
        return None
    return (
        InvoiceLine.objects.filter(
            invoice__encounter=encounter,
            invoice__is_deleted=False,
            is_deleted=False,
            waived_at__isnull=True,
            service_code__code__endswith='-' + str(rx.pk),
        )
        .select_related('invoice', 'service_code')
        .order_by('-invoice__created', '-created')
        .first()
    )


def _serialize_receipt(pr, dispensing=None, *, line_total_override=None) -> Optional[Dict[str, Any]]:
    if not pr:
        return None
    from .utils_pharmacy_dispensing_display import attributed_receipt_amounts_for_dispensing

    attrs = attributed_receipt_amounts_for_dispensing(
        dispensing,
        line_total_override=line_total_override,
    ) if dispensing else {'line_amount': None, 'receipt_full': None, 'shared_count': 0}

    line_amt = attrs.get('line_amount')
    if line_amt is None:
        line_amt = Decimal(str(pr.amount_paid or 0))
    full_amt = attrs.get('receipt_full')
    if full_amt is None:
        full_amt = Decimal(str(pr.amount_paid or 0))

    inv = getattr(pr, 'invoice', None)
    return {
        'receipt_number': pr.receipt_number or '',
        'amount_paid': float(line_amt or 0),
        'receipt_full_amount': float(full_amt or 0),
        'receipt_shared_across_lines': int(attrs.get('shared_count') or 0),
        'payment_method': getattr(pr, 'payment_method', '') or '',
        'payment_method_display': pr.get_payment_method_display() if hasattr(pr, 'get_payment_method_display') else '',
        'receipt_date': _fmt_dt(getattr(pr, 'receipt_date', None) or getattr(pr, 'created', None)),
        'invoice_number': getattr(inv, 'invoice_number', '') if inv else '',
        'transaction_number': getattr(pr, 'transaction_number', '') or '',
        'detail_path': reverse('hospital:receipt_detail', args=[pr.pk]),
        'print_path': reverse('hospital:receipt_print', args=[pr.pk]),
    }


def _receipts_for_encounter(encounter) -> List[Dict[str, Any]]:
    from .models_accounting import PaymentReceipt

    if not encounter:
        return []
    rows = (
        PaymentReceipt.objects.filter(
            invoice__encounter=encounter,
            is_deleted=False,
        )
        .select_related('invoice')
        .order_by('-receipt_date', '-created')[:20]
    )
    out = []
    for pr in rows:
        ser = _serialize_receipt(pr)
        if ser:
            out.append(ser)
    return out


def _serialize_dispensing(disp) -> Optional[Dict[str, Any]]:
    if not disp:
        return None
    disp_by = ''
    if getattr(disp, 'dispensed_by', None) and getattr(disp.dispensed_by, 'user', None):
        disp_by = disp.dispensed_by.user.get_full_name() or disp.dispensed_by.user.username
    sub = getattr(disp, 'substitute_drug', None)
    return {
        'status': disp.get_dispensing_status_display() if hasattr(disp, 'get_dispensing_status_display') else disp.dispensing_status,
        'quantity_ordered': int(disp.quantity_ordered or 0),
        'quantity_dispensed': int(disp.quantity_dispensed or 0),
        'substitute_drug_name': sub.name if sub else '',
        'dispensed_at': _fmt_dt(getattr(disp, 'dispensed_at', None)),
        'dispensed_by': disp_by,
        'payment_verified_at': _fmt_dt(getattr(disp, 'payment_verified_at', None)),
        'stock_reduced_at': _fmt_dt(getattr(disp, 'stock_reduced_at', None)),
        'dispensing_notes': disp.dispensing_notes or '',
    }


def _serialize_dispense_history(history_qs) -> List[Dict[str, Any]]:
    out = []
    for h in history_qs:
        by_name = h.dispensed_by_name or ''
        if not by_name and getattr(h, 'dispensed_by', None) and getattr(h.dispensed_by, 'user', None):
            by_name = h.dispensed_by.user.get_full_name() or h.dispensed_by.user.username
        out.append(
            {
                'drug_name': h.drug_name or '',
                'quantity_dispensed': int(h.quantity_dispensed or 0),
                'dispensed_at': _fmt_dt(getattr(h, 'dispensed_at', None)),
                'dispensed_by_name': by_name,
            }
        )
    return out


def _serialize_stock_deductions(disp, history_qs) -> List[Dict[str, Any]]:
    from .models_payment_verification import PharmacyStockDeductionLog

    source_ids = []
    if disp:
        source_ids.append(str(disp.pk))
    for h in history_qs:
        source_ids.append(str(h.pk))
    if not source_ids:
        return []
    logs = (
        PharmacyStockDeductionLog.objects.filter(
            source_id__in=source_ids,
            is_deleted=False,
        )
        .select_related('drug')
        .order_by('-created')
    )
    return [
        {
            'source_type': lg.source_type,
            'quantity': int(lg.quantity or 0),
            'drug_name': lg.drug.name if lg.drug_id else '',
        }
        for lg in logs
    ]


def _medication_detail_bundle(rx, order, encounter) -> Dict[str, Any]:
    from .models_payment_verification import PharmacyDispensing, PharmacyDispenseHistory

    disp = (
        PharmacyDispensing.objects.filter(prescription=rx, is_deleted=False)
        .select_related('substitute_drug', 'payment_receipt__invoice', 'dispensed_by__user')
        .first()
    )
    inv_line = _invoice_line_for_prescription(rx, encounter)
    inv = inv_line.invoice if inv_line else None
    if not inv and encounter:
        from .models import Invoice

        inv = (
            Invoice.objects.filter(encounter=encounter, is_deleted=False)
            .select_related('payer')
            .order_by('-created')
            .first()
        )

    line_total = None
    if inv_line:
        try:
            line_total = Decimal(str(getattr(inv_line, 'display_line_total', None) or inv_line.line_total or 0))
        except Exception:
            line_total = None

    history_qs = list(
        PharmacyDispenseHistory.objects.filter(prescription=rx, is_deleted=False)
        .select_related('dispensed_by__user')
        .order_by('-dispensed_at', '-created')[:20]
    )

    return {
        'prescription': _serialize_prescription(rx),
        'invoice_line': _serialize_invoice_line(inv_line),
        'receipt': _serialize_receipt(
            getattr(disp, 'payment_receipt', None) if disp else None,
            dispensing=disp,
            line_total_override=line_total,
        ),
        'dispensing': _serialize_dispensing(disp),
        'dispense_history': _serialize_dispense_history(history_qs),
        'stock_deductions': _serialize_stock_deductions(disp, history_qs),
    }


def build_served_prescription_detail_payload(prescription) -> Dict[str, Any]:
    """Full served detail for one prescription (modal on pharmacy dashboard)."""
    rx = prescription
    order = getattr(rx, 'order', None)
    encounter = getattr(order, 'encounter', None) if order else None
    patient = getattr(encounter, 'patient', None) if encounter else None

    bundle = _medication_detail_bundle(rx, order, encounter)
    inv_line = _invoice_line_for_prescription(rx, encounter)
    inv = inv_line.invoice if inv_line else None
    if not inv and encounter:
        from .models import Invoice

        inv = (
            Invoice.objects.filter(encounter=encounter, is_deleted=False)
            .select_related('payer')
            .order_by('-created')
            .first()
        )

    return {
        'success': True,
        'is_order_summary': False,
        'patient': _serialize_patient(patient),
        'payer': _serialize_payer(patient, encounter),
        'order': _serialize_order(order),
        'prescription': bundle['prescription'],
        'dispensing': bundle['dispensing'],
        'invoice': _serialize_invoice(inv),
        'invoice_line': bundle['invoice_line'],
        'receipt': bundle['receipt'],
        'receipts_for_encounter': _receipts_for_encounter(encounter),
        'dispense_history': bundle['dispense_history'],
        'stock_deductions': bundle['stock_deductions'],
    }


def build_served_order_detail_payload(order) -> Dict[str, Any]:
    """Served detail for all medications on one order."""
    encounter = getattr(order, 'encounter', None)
    patient = getattr(encounter, 'patient', None) if encounter else None
    prescriptions = list(
        order.prescriptions.filter(is_deleted=False).select_related('drug', 'prescribed_by__user')
    )
    medications = [_medication_detail_bundle(rx, order, encounter) for rx in prescriptions]

    inv = None
    if encounter:
        from .models import Invoice

        inv = (
            Invoice.objects.filter(encounter=encounter, is_deleted=False)
            .select_related('payer')
            .order_by('-created')
            .first()
        )

    return {
        'success': True,
        'is_order_summary': True,
        'patient': _serialize_patient(patient),
        'payer': _serialize_payer(patient, encounter),
        'order': _serialize_order(order),
        'invoice': _serialize_invoice(inv),
        'receipts_for_encounter': _receipts_for_encounter(encounter),
        'medications': medications,
    }

"""
Helpers for clinical consumables billing, cashier queues, and revenue classification.
"""
from decimal import Decimal

from django.db.models import Q

D0 = Decimal('0.00')

_CONSUMABLE_CODE_EXACT = frozenset({'ADM-CONSUMABLES', 'CONS-PACK'})
_CONSUMABLE_CODE_PREFIXES = ('CS-', 'CONS-')


def is_consumable_invoice_line(line) -> bool:
    """True when an invoice line is a clinical consumable (not dispensed Rx drugs)."""
    if not line or getattr(line, 'is_deleted', False):
        return False
    if getattr(line, 'waived_at', None):
        return False
    sc = getattr(line, 'service_code', None)
    if not sc:
        desc = (getattr(line, 'description', '') or '').casefold()
        return 'consumable' in desc
    cat = (getattr(sc, 'category', '') or '').strip()
    if cat == 'Clinical Consumables':
        return True
    code = (getattr(sc, 'code', '') or '').strip().upper()
    if code in _CONSUMABLE_CODE_EXACT:
        return True
    if any(code.startswith(pfx) for pfx in _CONSUMABLE_CODE_PREFIXES):
        return True
    return False


def _line_billable_amount(line) -> Decimal:
    if getattr(line, 'waived_at', None):
        return D0
    total = getattr(line, 'line_total', None)
    if total is not None and total > 0:
        return Decimal(str(total))
    qty = Decimal(str(getattr(line, 'quantity', 1) or 1))
    unit = Decimal(str(getattr(line, 'unit_price', 0) or 0))
    return (qty * unit).quantize(Decimal('0.01'))


def invoice_consumables_balance(invoice) -> Decimal:
    """Sum billable consumable line totals on an open invoice."""
    if not invoice or getattr(invoice, 'is_deleted', False):
        return D0
    if getattr(invoice, 'status', None) in ('paid', 'cancelled'):
        return D0
    total = D0
    lines = getattr(invoice, 'lines', None)
    if lines is not None:
        for line in lines.filter(is_deleted=False, waived_at__isnull=True):
            if is_consumable_invoice_line(line):
                total += _line_billable_amount(line)
    else:
        from .models import InvoiceLine

        for line in InvoiceLine.objects.filter(
            invoice=invoice, is_deleted=False, waived_at__isnull=True
        ).select_related('service_code'):
            if is_consumable_invoice_line(line):
                total += _line_billable_amount(line)
    return total


def invoice_has_consumable_lines(invoice) -> bool:
    return invoice_consumables_balance(invoice) > 0


def consumables_invoice_label(invoice, *, amount=None) -> str:
    """Human-readable cashier label for an invoice that includes consumables."""
    num = getattr(invoice, 'invoice_number', '') or str(getattr(invoice, 'pk', ''))
    if amount is not None and amount > 0:
        return f'Consumables — Invoice {num}'
    return f'Consumables — Invoice {num}'


def query_open_consumable_lines(patient_ids=None, date_range_start=None, date_range_end=None):
    """
    Open consumable invoice lines on unpaid cash invoices for cashier queues.
    Returns queryset of InvoiceLine ordered by -modified.
    """
    from .models import Invoice, InvoiceLine

    inv_qs = Invoice.all_objects.filter(
        is_deleted=False,
        status__in=('draft', 'issued', 'partially_paid', 'overdue'),
        balance__gt=0,
        payer__payer_type='cash',
    )
    if patient_ids:
        inv_qs = inv_qs.filter(patient_id__in=patient_ids)
    if date_range_start is not None and date_range_end is not None:
        inv_qs = inv_qs.filter(
            Q(modified__gte=date_range_start, modified__lt=date_range_end)
            | Q(issued_at__gte=date_range_start, issued_at__lt=date_range_end)
        )

    qs = InvoiceLine.objects.filter(
        invoice__in=inv_qs,
        is_deleted=False,
        waived_at__isnull=True,
    ).select_related('invoice', 'invoice__patient', 'service_code')

    consumable_pks = []
    for line in qs.iterator(chunk_size=500):
        if is_consumable_invoice_line(line):
            consumable_pks.append(line.pk)
    if not consumable_pks:
        return InvoiceLine.objects.none()
    return InvoiceLine.objects.filter(pk__in=consumable_pks).select_related(
        'invoice', 'invoice__patient', 'service_code'
    ).order_by('-modified')


def build_consumables_cashier_groups(lines_qs, patient_name_filter=''):
    """
    Group open consumable lines by invoice for cashier dashboard / lists.
    Returns list of dicts: patient, patient_name, invoice, lines, total, date_display.
    """
    from collections import OrderedDict

    groups = OrderedDict()
    sn = (patient_name_filter or '').strip().lower()
    for line in lines_qs:
        inv = line.invoice
        patient = getattr(inv, 'patient', None)
        if not patient:
            continue
        if sn:
            fn = (getattr(patient, 'first_name', '') or '').lower()
            ln = (getattr(patient, 'last_name', '') or '').lower()
            mrn = (getattr(patient, 'mrn', '') or '').lower()
            full = f'{fn} {ln}'.strip()
            if sn not in full and sn not in fn and sn not in ln and sn not in mrn:
                continue
        amt = _line_billable_amount(line)
        if amt <= 0:
            continue
        key = inv.pk
        if key not in groups:
            groups[key] = {
                'patient': patient,
                'patient_name': patient.full_name,
                'patient_mrn': patient.mrn,
                'invoice': inv,
                'invoice_id': str(inv.id),
                'invoice_number': inv.invoice_number,
                'lines': [],
                'total': D0,
                'date_display': getattr(inv, 'modified', None) or inv.issued_at,
            }
        groups[key]['lines'].append(line)
        groups[key]['total'] += amt
    return list(groups.values())


def infer_invoice_payment_service_type(invoice) -> str:
    """
    Receipt service_type for a single-invoice payment.
    All consumable lines -> consumables; otherwise other/combined handled by caller.
    """
    if not invoice:
        return 'other'
    from .models import InvoiceLine

    billable = InvoiceLine.objects.filter(
        invoice=invoice, is_deleted=False, waived_at__isnull=True
    ).select_related('service_code')
    lines = [l for l in billable if _line_billable_amount(l) > 0]
    if not lines:
        return 'other'
    if all(is_consumable_invoice_line(l) for l in lines):
        return 'consumables'
    return 'other'

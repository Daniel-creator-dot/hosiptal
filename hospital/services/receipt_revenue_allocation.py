"""
Resolve payment / deposit amounts into revenue stream splits for GL posting.
Uses cashier-facing amounts from receipt service_details (prices / breakdown),
not proportional re-weighting from stale invoice line_total values.
"""
from decimal import Decimal

D0 = Decimal('0.00')

_STREAM_TO_SERVICE_TYPE = {
    'registration': 'registration',
    'consultation': 'consultation',
    'consultation_general': 'consultation',
    'consultation_specialist': 'consultation',
    'lab': 'lab',
    'laboratory': 'lab',
    'pharmacy': 'pharmacy',
    'consumables': 'consumables',
    'imaging': 'imaging',
    'radiology': 'imaging',
    'surgery': 'procedure',
    'admission': 'admission',
    'dental': 'dental',
    'physiotherapy': 'physiotherapy',
    'gynecology': 'gynecology',
    'emergency': 'consultation',
    'psychiatry': 'consultation',
    'other': 'other',
}


def stream_to_service_type(stream_key):
    key = (stream_key or 'other').strip().lower()
    return _STREAM_TO_SERVICE_TYPE.get(
        key, key if key in _STREAM_TO_SERVICE_TYPE.values() else 'other'
    )


def _normalize_cashier_service_type(raw):
    from hospital.views_revenue_monitoring import _SERVICE_DISPLAY, _normalize_service_type

    key = _normalize_service_type(raw)
    if key == 'combined':
        return 'other'
    if key in _SERVICE_DISPLAY:
        return stream_to_service_type(key)
    return stream_to_service_type(key)


def _classify_breakdown_item(bd_item, invoice=None, encounter=None):
    line_id = bd_item.get('line_id')
    if line_id:
        from hospital.models import InvoiceLine
        from hospital.views_revenue_monitoring import _classify_invoice_line_to_stream

        line = (
            InvoiceLine.objects.filter(pk=line_id, is_deleted=False)
            .select_related('service_code', 'invoice__encounter')
            .first()
        )
        if line:
            enc = encounter or getattr(line.invoice, 'encounter', None)
            return _classify_invoice_line_to_stream(line, enc) or 'other'

    desc = (bd_item.get('description') or '').casefold()
    if 'consult' in desc or 'specialist' in desc:
        return 'consultation'
    if any(x in desc for x in ('pharm', 'drug', 'medication', 'tablet', 'capsule', 'prescribe')):
        return 'pharmacy'
    if any(x in desc for x in ('lab', 'laboratory', 'blood', 'fbc')):
        return 'lab'
    if any(x in desc for x in ('x-ray', 'xray', 'scan', 'imaging', 'radiol', 'ultrasound')):
        return 'imaging'
    if any(x in desc for x in ('bed', 'ward', 'admission', 'admit')):
        return 'admission'
    if invoice and encounter is None:
        encounter = getattr(invoice, 'encounter', None)
    return 'other'


def _merge_stream_dict(target, source):
    for key, amt in source.items():
        svc = stream_to_service_type(key)
        target[svc] = target.get(svc, D0) + Decimal(str(amt or 0))


def _finalize_cashier_splits(stream_dict, payment_amount):
    """
    Finalize stream amounts to match payment collected.
    Consultation tariff is recognized in full when possible; remainder goes to other streams.
    """
    payment_amount = Decimal(str(payment_amount or 0))
    if not stream_dict or payment_amount <= 0:
        return []

    consult = stream_dict.get('consultation', D0)
    if consult > 0 and consult <= payment_amount:
        out = {'consultation': consult}
        remainder = payment_amount - consult
        others = {k: v for k, v in stream_dict.items() if k != 'consultation' and v > 0}
        if remainder > 0 and others:
            other_total = sum(others.values(), D0)
            allocated = D0
            items = list(others.items())
            for idx, (svc, part) in enumerate(items):
                if idx == len(items) - 1:
                    share = remainder - allocated
                else:
                    share = (
                        (remainder * part / other_total).quantize(Decimal('0.01'))
                        if other_total > 0
                        else remainder
                    )
                    allocated += share
                if share > 0:
                    out[svc] = out.get(svc, D0) + share
        return [(svc, amt) for svc, amt in out.items() if amt > 0]

    return _scale_stream_dict(stream_dict, payment_amount)


def _scale_stream_dict(stream_dict, payment_amount):
    """Scale stream amounts to payment_amount; last bucket absorbs rounding."""
    payment_amount = Decimal(str(payment_amount or 0))
    if not stream_dict or payment_amount <= 0:
        return []

    total = sum(stream_dict.values(), D0)
    if total <= 0:
        return [('other', payment_amount)]

    if abs(total - payment_amount) <= Decimal('0.02'):
        return [(svc, amt) for svc, amt in stream_dict.items() if amt > 0]

    splits = []
    allocated = D0
    items = list(stream_dict.items())
    for idx, (svc, part) in enumerate(items):
        if idx == len(items) - 1:
            share = payment_amount - allocated
        else:
            share = (payment_amount * part / total).quantize(Decimal('0.01'))
            allocated += share
        if share > 0:
            splits.append((svc, share))
    return splits or [('other', payment_amount)]


def _consultation_tariff_for_line(line, encounter):
    """Standard consultation charge for GL (e.g. 150 GHS), not net after bill discount."""
    if not line or not encounter:
        return None
    try:
        from hospital.utils_billing import get_consultation_price_for_encounter

        tariff = get_consultation_price_for_encounter(encounter)
        if tariff and tariff > 0:
            return Decimal(str(tariff))
    except Exception:
        pass
    qty = Decimal(str(line.quantity or 1))
    unit = Decimal(str(line.unit_price or 0))
    if unit > 0:
        return qty * unit
    return None


def _alloc_from_invoice_display_lines(invoice, cap_amount):
    """
    Split cap_amount across streams using cashier-facing display line amounts.
    Consultation lines use encounter tariff first; remainder goes to other streams.
    """
    from hospital.models import Encounter, InvoiceLine
    from hospital.utils_invoice_line import invoice_line_display_unit_and_total
    from hospital.views_revenue_monitoring import _classify_invoice_line_to_stream

    cap_amount = Decimal(str(cap_amount or 0))
    if not invoice or cap_amount <= 0:
        return {}

    encounter = None
    if getattr(invoice, 'encounter_id', None):
        encounter = (
            Encounter.objects.filter(pk=invoice.encounter_id)
            .select_related('provider__department')
            .first()
        )

    consult_tariff = D0
    other_streams = {}
    other_grand = D0

    lines = InvoiceLine.objects.filter(
        invoice=invoice,
        is_deleted=False,
        waived_at__isnull=True,
    ).select_related('service_code')
    for line in lines:
        _unit, display_amt = invoice_line_display_unit_and_total(line)
        amt = Decimal(str(display_amt or 0))
        if amt <= 0:
            continue
        stream = _classify_invoice_line_to_stream(line, encounter) or 'other'
        if stream == 'consultation' and encounter:
            tariff = _consultation_tariff_for_line(line, encounter)
            if tariff and tariff > 0:
                consult_tariff = max(consult_tariff, tariff)
                continue
        svc = stream_to_service_type(stream)
        other_streams[svc] = other_streams.get(svc, D0) + amt
        other_grand += amt

    result = {}
    if consult_tariff > 0:
        consult_share = min(consult_tariff, cap_amount)
        result['consultation'] = consult_share
        remainder = cap_amount - consult_share
        if remainder > 0 and other_grand > 0:
            allocated = D0
            items = list(other_streams.items())
            for idx, (svc, part) in enumerate(items):
                if idx == len(items) - 1:
                    share = remainder - allocated
                else:
                    share = (remainder * part / other_grand).quantize(Decimal('0.01'))
                    allocated += share
                if share > 0:
                    result[svc] = result.get(svc, D0) + share
        return result

    stream_totals = {}
    grand = D0
    for line in lines:
        _unit, display_amt = invoice_line_display_unit_and_total(line)
        amt = Decimal(str(display_amt or 0))
        if amt <= 0:
            continue
        stream = _classify_invoice_line_to_stream(line, encounter) or 'other'
        svc = stream_to_service_type(stream)
        stream_totals[svc] = stream_totals.get(svc, D0) + amt
        grand += amt

    if grand <= 0:
        return {'other': cap_amount}

    scaled = {}
    allocated = D0
    items = list(stream_totals.items())
    for idx, (svc, part) in enumerate(items):
        if idx == len(items) - 1:
            share = cap_amount - allocated
        else:
            share = (cap_amount * part / grand).quantize(Decimal('0.01'))
            allocated += share
        if share > 0:
            scaled[svc] = scaled.get(svc, D0) + share
    return scaled


def _alloc_from_service_entry(svc):
    """Build stream -> amount dict for one service_details.services[] row."""
    breakdown = svc.get('breakdown') or []
    invoice = None
    raw_type = (svc.get('type') or '').strip().lower()

    if raw_type in ('invoice', 'invoice_line'):
        from hospital.views_revenue_monitoring import _resolve_invoice_for_entry

        invoice = _resolve_invoice_for_entry(svc)

    encounter = getattr(invoice, 'encounter', None) if invoice else None
    merged = {}

    if breakdown:
        for bd in breakdown:
            try:
                amt = Decimal(str(bd.get('amount', 0) or 0))
            except (TypeError, ValueError):
                continue
            if amt <= 0:
                continue
            stream = _classify_breakdown_item(bd, invoice=invoice, encounter=encounter)
            if stream == 'consultation' and encounter:
                line_id = bd.get('line_id')
                if line_id:
                    from hospital.models import InvoiceLine

                    line = InvoiceLine.objects.filter(pk=line_id, is_deleted=False).first()
                    if line:
                        tariff = _consultation_tariff_for_line(line, encounter)
                        if tariff and tariff > 0:
                            amt = tariff
            svc_type = stream_to_service_type(stream)
            merged[svc_type] = merged.get(svc_type, D0) + amt
        if merged:
            return merged

    try:
        price = Decimal(str(svc.get('price', 0) or 0))
    except (TypeError, ValueError):
        price = D0
    if price <= 0:
        return {}

    if raw_type in ('invoice', 'invoice_line') and invoice:
        return _alloc_from_invoice_display_lines(invoice, price)

    stype = _normalize_cashier_service_type(raw_type)
    return {stype: price}


def build_service_details_for_invoice(invoice, amount, service_type=None):
    """Build service_details.services[] with line breakdown for GL revenue split."""
    from hospital.models import InvoiceLine, Encounter
    from hospital.utils_invoice_line import invoice_line_display_unit_and_total

    amount = Decimal(str(amount or 0))
    if not invoice:
        return {'services': []}

    encounter = None
    if getattr(invoice, 'encounter_id', None):
        encounter = Encounter.objects.filter(pk=invoice.encounter_id).first()

    breakdown = []
    lines = InvoiceLine.objects.filter(
        invoice=invoice,
        is_deleted=False,
        waived_at__isnull=True,
    ).select_related('service_code')
    for line in lines:
        _unit, display_amt = invoice_line_display_unit_and_total(line)
        amt = Decimal(str(display_amt or 0))
        from hospital.views_revenue_monitoring import _classify_invoice_line_to_stream

        stream = _classify_invoice_line_to_stream(line, encounter) or 'other'
        if stream == 'consultation' and encounter:
            tariff = _consultation_tariff_for_line(line, encounter)
            if tariff and tariff > 0:
                amt = tariff
        if amt <= 0:
            continue
        from hospital.utils_invoice_line import invoice_line_display_description

        breakdown.append({
            'description': invoice_line_display_description(line),
            'quantity': str(line.quantity),
            'unit_price': str(_unit),
            'amount': str(amt),
            'line_id': str(line.id),
        })

    stype = service_type or 'invoice'
    return {
        'services': [{
            'type': stype,
            'name': f'Invoice {invoice.invoice_number}',
            'price': str(amount),
            'service_id': str(invoice.id),
            'breakdown': breakdown,
        }],
        'invoice_number': invoice.invoice_number,
        'invoice_id': str(invoice.id),
    }


def cashier_revenue_splits_from_receipt(receipt, payment_amount):
    """
    Use cashier-recorded service_details prices/breakdown as source of truth.
    Returns list of (service_type, amount) or None if not applicable.
    """
    if not receipt:
        return None

    details = getattr(receipt, 'service_details', None) or {}
    services = details.get('services') or []
    if not services:
        return None

    payment_amount = Decimal(str(payment_amount or 0))
    if payment_amount <= 0:
        return []

    merged = {}
    for svc in services:
        entry_alloc = _alloc_from_service_entry(svc)
        _merge_stream_dict(merged, entry_alloc)

    if not merged:
        return None

    return _finalize_cashier_splits(merged, payment_amount)


def allocate_payment_to_revenue_accounts(invoice, amount):
    """
    Split a payment amount across revenue service types using invoice display line amounts.
    Returns list of (service_type, amount) tuples summing to amount.
    """
    amount = Decimal(str(amount or 0))
    if amount <= 0:
        return []
    if not invoice:
        return [('other', amount)]

    stream_dict = _alloc_from_invoice_display_lines(invoice, amount)
    if not stream_dict:
        return [('other', amount)]
    if len(stream_dict) == 1:
        only = next(iter(stream_dict.keys()))
        return [(only, amount)]
    return _scale_stream_dict(stream_dict, amount)


def _merge_service_splits(split_lists):
    """Merge multiple (service_type, amount) lists into one."""
    merged = {}
    for splits in split_lists:
        for svc, amt in splits:
            merged[svc] = merged.get(svc, D0) + Decimal(str(amt or 0))
    return [(svc, amt) for svc, amt in merged.items() if amt > 0]


def _splits_from_payment_allocations(txn, receipt, amount):
    """
    When PaymentAllocation rows exist, prefer matching service_details row prices
    per invoice before falling back to invoice display-line split.
    """
    from hospital.models_accounting import PaymentAllocation
    from hospital.views_revenue_monitoring import _resolve_invoice_for_entry

    allocations = list(
        PaymentAllocation.objects.filter(
            payment_transaction=txn,
            is_deleted=False,
        ).select_related('invoice')
    )
    if not allocations:
        return None

    services = []
    if receipt:
        services = (getattr(receipt, 'service_details', None) or {}).get('services') or []

    invoice_to_entry = {}
    for svc in services:
        inv = _resolve_invoice_for_entry(svc)
        if inv:
            invoice_to_entry[str(inv.pk)] = svc

    merged = {}
    for alloc in allocations:
        inv_key = str(alloc.invoice_id)
        entry = invoice_to_entry.get(inv_key)
        if entry:
            _merge_stream_dict(merged, _alloc_from_service_entry(entry))
            continue
        _merge_stream_dict(
            merged,
            _alloc_from_invoice_display_lines(alloc.invoice, alloc.allocated_amount),
        )

    if not merged:
        return None
    return _finalize_cashier_splits(merged, amount)


def revenue_splits_for_transaction(txn, receipt=None):
    """
    Resolve revenue account splits for a payment transaction.
    Priority: cashier service_details → PaymentAllocation + service_details → invoice display lines → service_type.
    """
    amount = txn.amount
    invoice = txn.invoice
    service_type = (receipt.service_type if receipt else 'other') or 'other'

    splits = cashier_revenue_splits_from_receipt(receipt, amount)
    if splits:
        return splits

    splits = _splits_from_payment_allocations(txn, receipt, amount)
    if splits:
        return splits

    if invoice:
        if service_type in ('other', 'combined', 'invoice', 'general'):
            splits = allocate_payment_to_revenue_accounts(invoice, amount)
            if splits:
                return splits
        if service_type not in ('other', 'combined'):
            line_splits = allocate_payment_to_revenue_accounts(invoice, amount)
            if len(line_splits) > 1:
                return line_splits

    return [(service_type, amount)]

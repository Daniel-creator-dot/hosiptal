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
    'sustainability': 'sustainability',
    'sustainability_insurance': 'sustainability',
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


def _peel_sustainability_from_amount(amt, remaining_fee):
    """
    Take Sustainability and Insurance (up to remaining GHS 8) first from a
    consultation-like payment slice — not a proportional fraction of the tariff.

    Proportional peels produced under-8 credits (e.g. 156 → 7.90) and, across
    partial payments, also over-posted 4115 when consultation was re-allocated.
    """
    amt = Decimal(str(amt or 0))
    remaining_fee = Decimal(str(remaining_fee or 0))
    if amt <= 0 or remaining_fee <= 0:
        return D0, amt
    sust = min(remaining_fee, amt).quantize(Decimal('0.01'))
    return sust, amt - sust


def _sustainability_due_for_invoice(invoice):
    """GHS 8 × number of consultation-like lines on the invoice (min one fee if peeling)."""
    from hospital.utils_billing import (
        CONSULTATION_LINE_SERVICE_CODES,
        SUSTAINABILITY_FEE,
        is_consultation_like_charge,
    )

    if invoice is None:
        return SUSTAINABILITY_FEE
    n = 0
    try:
        for line in invoice.lines.filter(
            is_deleted=False, waived_at__isnull=True
        ).select_related('service_code'):
            code = (
                getattr(getattr(line, 'service_code', None), 'code', None) or ''
            ).strip().upper()
            desc = getattr(line, 'description', None) or ''
            if code in CONSULTATION_LINE_SERVICE_CODES or code == 'PHYSIO-SUB':
                n += 1
            elif is_consultation_like_charge(code=code, description=desc):
                n += 1
    except Exception:
        return SUSTAINABILITY_FEE
    if n <= 0:
        return SUSTAINABILITY_FEE
    return (SUSTAINABILITY_FEE * n).quantize(Decimal('0.01'))


def _sustainability_already_posted_for_invoice(invoice):
    """Sum of 4115 credits already posted for this invoice (payments + deposit applies)."""
    if invoice is None:
        return D0
    try:
        from django.db.models import Sum

        from hospital.models_accounting import Account, Transaction
        from hospital.models_accounting_advanced import AdvancedJournalEntry, AdvancedJournalEntryLine
    except Exception:
        return D0

    acc = Account.objects.filter(account_code='4115', is_deleted=False).first()
    if acc is None:
        acc = Account.objects.filter(account_code='4115').first()
    if acc is None:
        return D0

    refs = set(
        Transaction.objects.filter(
            invoice_id=invoice.pk,
            transaction_type='payment_received',
            is_deleted=False,
        ).values_list('transaction_number', flat=True)
    )
    refs.update(
        AdvancedJournalEntry.objects.filter(
            invoice_id=invoice.pk,
            is_deleted=False,
            status='posted',
        ).values_list('reference', flat=True)
    )
    try:
        from hospital.models_patient_deposits import DepositApplication

        for dep_num in DepositApplication.objects.filter(
            invoice_id=invoice.pk,
            is_deleted=False,
        ).values_list('deposit__deposit_number', flat=True):
            if dep_num:
                refs.add(f'DEP-{dep_num}')
    except Exception:
        pass

    refs = {r for r in refs if r}
    if not refs:
        return D0

    total = AdvancedJournalEntryLine.objects.filter(
        account=acc,
        is_deleted=False,
        journal_entry__reference__in=refs,
        journal_entry__is_deleted=False,
        journal_entry__status='posted',
    ).aggregate(s=Sum('credit_amount'))['s']
    return total or D0


_SERVICE_SUSTAINABILITY_PEEL_TYPES = frozenset({
    'lab',
    'lab_test',
    'laboratory',
    'pharmacy',
    'pharmacy_walkin',
    'pharmacy_prescription',
    'medication',
    'imaging',
    'imaging_study',
    'radiology',
    'admission',
    'bed',
    'detainment',
})


def _coalesce_split_amounts(splits):
    merged = {}
    order = []
    for svc, amt in splits:
        amt = Decimal(str(amt or 0))
        if amt <= 0:
            continue
        if svc not in merged:
            order.append(svc)
            merged[svc] = D0
        merged[svc] += amt
    return [(svc, merged[svc]) for svc in order]


def peel_service_sustainability_from_splits(splits, invoice=None):
    """
    Peel the 10% Sustainability and Insurance increment from billed drug / lab / scan / ward
    amounts (billed × 10/110 → GL 4115). Consultations keep the separate GHS 8 peel.
    """
    from hospital.utils_billing import invoice_uses_service_sustainability, service_sustainability_portion

    if not splits:
        return splits
    if not invoice_uses_service_sustainability(invoice):
        return [
            (svc, Decimal(str(amt or 0)))
            for svc, amt in splits
            if Decimal(str(amt or 0)) > 0
        ]

    result = []
    sust_total = D0
    for svc, amt in splits:
        amt = Decimal(str(amt or 0))
        if amt <= 0:
            continue
        key = (svc or '').strip().lower()
        if key == 'sustainability':
            result.append((svc, amt))
            continue
        if key in _SERVICE_SUSTAINABILITY_PEEL_TYPES:
            portion = service_sustainability_portion(amt)
            rest = (amt - portion).quantize(Decimal('0.01'))
            if rest > 0:
                result.append((svc, rest))
            if portion > 0:
                sust_total += portion
            continue
        result.append((svc, amt))
    if sust_total > 0:
        result.append(('sustainability', sust_total.quantize(Decimal('0.01'))))
    return _coalesce_split_amounts(result)


def expand_consultation_with_sustainability(splits, invoice=None):
    """
    Peel Sustainability and Insurance onto GL 4115:

    Consultation-like (fixed GHS 8, not 10%):
    - General OPD: 158 → 150 consultation + 8 sustainability
    - Specialist / gynae (CON002): billed fee includes +8 → peel 8
    - Physio subsequent (PHYSIO-SUB): 158 → 150 physiotherapy + 8 sustainability
    - Antenatal (MAT-ANC): 243 → 235 gynecology + 8 sustainability

    Drugs, lab, scans, and ward/admission fees (billed already include +10%):
    - Peel billed × 10/110 from lab / pharmacy / imaging / admission streams

    Takes the full remaining GHS 8 from the consultation-like slice first (not a
    proportional share). Caps total GHS-8 credits per invoice at 8 × consult lines.
    The 10% service increment is peeled from each payment slice in proportion.
    """
    if not splits:
        return splits

    from hospital.utils_billing import (
        ANC_VISIT,
        GENERAL_CONSULTATION_CASH,
        GENERAL_CONSULTATION_CORPORATE,
        GENERAL_OPD_LINE_SERVICE_CODES,
        GYNAE_SPECIAL,
        PHYSIO_SUBSEQUENT,
        SPECIALIST_CONSULTATION,
        SUSTAINABILITY_FEE,
        get_consultation_line_for_encounter,
        get_consultation_price_for_encounter,
        is_consultation_like_charge,
    )

    peel_consultation = False
    peel_physio_sub = False
    peel_gynecology = False
    consult_tariff = None

    encounter = getattr(invoice, 'encounter', None) if invoice else None
    if encounter is None and invoice and getattr(invoice, 'encounter_id', None):
        try:
            from hospital.models import Encounter
            encounter = Encounter.objects.filter(pk=invoice.encounter_id).first()
        except Exception:
            encounter = None

    line_codes = set()
    if invoice is not None:
        try:
            for line in invoice.lines.filter(is_deleted=False, waived_at__isnull=True).select_related('service_code'):
                code = (getattr(getattr(line, 'service_code', None), 'code', None) or '').strip().upper()
                desc = getattr(line, 'description', None) or ''
                if code:
                    line_codes.add(code)
                if is_consultation_like_charge(code=code, description=desc):
                    peel_consultation = True
        except Exception:
            pass

    if 'PHYSIO-SUB' in line_codes:
        peel_physio_sub = True
    if 'CON002' in line_codes:
        peel_consultation = True
        peel_gynecology = True
    if 'MAT-ANC' in line_codes:
        peel_gynecology = True
        consult_tariff = ANC_VISIT
    if any(c in GENERAL_OPD_LINE_SERVICE_CODES for c in line_codes):
        peel_consultation = True

    if encounter:
        try:
            consult_tariff = get_consultation_price_for_encounter(encounter) or consult_tariff
        except Exception:
            pass
        line = None
        try:
            line = get_consultation_line_for_encounter(encounter)
        except Exception:
            line = None
        code = (
            getattr(getattr(line, 'service_code', None), 'code', None) or ''
        ).strip().upper()
        if code == 'MAT-ANC':
            peel_gynecology = True
            if consult_tariff is None:
                consult_tariff = ANC_VISIT
        elif code in GENERAL_OPD_LINE_SERVICE_CODES or code == 'CON002':
            peel_consultation = True
        elif consult_tariff in (
            GENERAL_CONSULTATION_CASH,
            GENERAL_CONSULTATION_CORPORATE,
            SPECIALIST_CONSULTATION,
            GYNAE_SPECIAL,
            ANC_VISIT,
        ):
            peel_consultation = True
            if consult_tariff == ANC_VISIT or (
                encounter and 'antenatal' in (getattr(encounter, 'encounter_type', None) or '').lower()
            ):
                peel_consultation = False
                peel_gynecology = True
        elif consult_tariff and consult_tariff >= GENERAL_CONSULTATION_CASH:
            enc_type = (getattr(encounter, 'encounter_type', None) or '').strip().lower()
            if enc_type in ('specialist', 'gynae') or code == 'CON002':
                peel_consultation = True
            elif 'antenatal' in enc_type or code == 'MAT-ANC':
                peel_gynecology = True
            elif enc_type:
                if (
                    consult_tariff < Decimal('200.00')
                    or abs(consult_tariff - GENERAL_CONSULTATION_CASH) <= Decimal('0.01')
                    or abs(consult_tariff - GENERAL_CONSULTATION_CORPORATE) <= Decimal('0.01')
                ):
                    peel_consultation = True
    else:
        for svc, amt in splits:
            a = Decimal(str(amt or 0))
            if a <= 0:
                continue
            if svc == 'consultation':
                if (
                    abs(a - GENERAL_CONSULTATION_CASH) <= Decimal('0.01')
                    or abs(a - GENERAL_CONSULTATION_CORPORATE) <= Decimal('0.01')
                    or abs(a - SPECIALIST_CONSULTATION) <= Decimal('0.01')
                    or a >= Decimal('150.00')
                ):
                    peel_consultation = True
                    if consult_tariff is None:
                        consult_tariff = a
            elif svc == 'gynecology' and (
                abs(a - GYNAE_SPECIAL) <= Decimal('0.01')
                or abs(a - ANC_VISIT) <= Decimal('0.01')
                or a >= Decimal('235.00')
            ):
                peel_gynecology = True
                if consult_tariff is None:
                    consult_tariff = a
            elif svc == 'physiotherapy' and abs(a - PHYSIO_SUBSEQUENT) <= Decimal('0.01'):
                peel_physio_sub = True

    if not peel_physio_sub:
        for svc, amt in splits:
            if svc == 'physiotherapy' and abs(Decimal(str(amt or 0)) - PHYSIO_SUBSEQUENT) <= Decimal('0.01'):
                peel_physio_sub = True
                break

    if not peel_consultation and not peel_physio_sub and not peel_gynecology:
        cleaned = [
            (svc, Decimal(str(amt or 0)))
            for svc, amt in splits
            if Decimal(str(amt or 0)) > 0
        ]
        return peel_service_sustainability_from_splits(cleaned, invoice=invoice)

    due = _sustainability_due_for_invoice(invoice)
    already = _sustainability_already_posted_for_invoice(invoice)
    remaining_fee = due - already
    if remaining_fee < 0:
        remaining_fee = D0
    # Never peel more than one fee chunk beyond due (guards bad already-calc)
    if remaining_fee > due:
        remaining_fee = due
    if remaining_fee > SUSTAINABILITY_FEE * 20:
        remaining_fee = due

    result = []
    for svc, amt in splits:
        amt = Decimal(str(amt or 0))
        if amt <= 0:
            continue
        if svc == 'consultation' and peel_consultation:
            sust, consult = _peel_sustainability_from_amount(amt, remaining_fee)
            remaining_fee -= sust
            if consult > 0:
                result.append(('consultation', consult))
            if sust > 0:
                result.append(('sustainability', sust))
            continue
        # Psychiatry stream (before remapping) also carries the sustainability fee
        if svc == 'psychiatry' and peel_consultation:
            sust, psych = _peel_sustainability_from_amount(amt, remaining_fee)
            remaining_fee -= sust
            if psych > 0:
                result.append(('psychiatry', psych))
            if sust > 0:
                result.append(('sustainability', sust))
            continue
        if svc == 'gynecology' and peel_gynecology:
            sust, gyn = _peel_sustainability_from_amount(amt, remaining_fee)
            remaining_fee -= sust
            if gyn > 0:
                result.append(('gynecology', gyn))
            if sust > 0:
                result.append(('sustainability', sust))
            continue
        if svc == 'physiotherapy' and peel_physio_sub:
            sust, phys = _peel_sustainability_from_amount(amt, remaining_fee)
            remaining_fee -= sust
            if phys > 0:
                result.append(('physiotherapy', phys))
            if sust > 0:
                result.append(('sustainability', sust))
            continue
        result.append((svc, amt))
    peeled = result or [(svc, Decimal(str(amt or 0))) for svc, amt in splits]
    return peel_service_sustainability_from_splits(peeled, invoice=invoice)


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
    Always peels GHS 8 Sustainability and Insurance from consultation / physio-subsequent
    when applicable, and peels 10% of billed drugs / lab / scans / ward fees to 4115.
    """
    amount = txn.amount
    invoice = txn.invoice
    service_type = (receipt.service_type if receipt else 'other') or 'other'

    splits = cashier_revenue_splits_from_receipt(receipt, amount)
    if splits:
        return expand_consultation_with_sustainability(splits, invoice=invoice)

    splits = _splits_from_payment_allocations(txn, receipt, amount)
    if splits:
        return expand_consultation_with_sustainability(splits, invoice=invoice)

    if invoice:
        if service_type in ('other', 'combined', 'invoice', 'general'):
            splits = allocate_payment_to_revenue_accounts(invoice, amount)
            if splits:
                return expand_consultation_with_sustainability(splits, invoice=invoice)
        if service_type not in ('other', 'combined'):
            line_splits = allocate_payment_to_revenue_accounts(invoice, amount)
            if len(line_splits) > 1:
                return expand_consultation_with_sustainability(line_splits, invoice=invoice)

    return expand_consultation_with_sustainability([(service_type, amount)], invoice=invoice)

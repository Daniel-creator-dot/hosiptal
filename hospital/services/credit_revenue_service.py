"""
Credit revenue (insurance / corporate) breakdown and matching helpers.
"""
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

D0 = Decimal('0.00')

IRE_AMOUNT_FIELDS = (
    'registration_amount',
    'consultation_amount',
    'laboratory_amount',
    'pharmacy_amount',
    'surgeries_amount',
    'admissions_amount',
    'radiology_amount',
    'dental_amount',
    'physiotherapy_amount',
)

_SERVICE_TO_IRE_FIELD = {
    'registration': 'registration_amount',
    'consultation': 'consultation_amount',
    'lab': 'laboratory_amount',
    'laboratory': 'laboratory_amount',
    'pharmacy': 'pharmacy_amount',
    'procedure': 'surgeries_amount',
    'surgery': 'surgeries_amount',
    'surgeries': 'surgeries_amount',
    'admission': 'admissions_amount',
    'imaging': 'radiology_amount',
    'radiology': 'radiology_amount',
    'dental': 'dental_amount',
    'physiotherapy': 'physiotherapy_amount',
    'consumables': 'consultation_amount',
    'other': 'consultation_amount',
}

IRE_FIELD_TO_REV_TYPE = {
    'registration_amount': 'registration',
    'consultation_amount': 'consultation',
    'laboratory_amount': 'laboratory',
    'pharmacy_amount': 'pharmacy',
    'surgeries_amount': 'surgeries',
    'admissions_amount': 'admissions',
    'radiology_amount': 'radiology',
    'dental_amount': 'dental',
    'physiotherapy_amount': 'physiotherapy',
}

REV_TYPE_TO_ACCOUNT_CODE = {
    'registration': '4100',
    'consultation': '4110',
    'laboratory': '4120',
    'pharmacy': '4130',
    'surgeries': '4140',
    'admissions': '4150',
    'radiology': '4160',
    'dental': '4170',
    'physiotherapy': '4180',
    'consumables': '4190',
}


def resolve_payer_ar_account_code(payer):
    """
    Per-payer AR account code (Account.account_code max_length=20).
    Uses a truncated payer id suffix so UUID payers fit the column.
    """
    raw = str(getattr(payer, 'id', payer)).replace('-', '')
    suffix = raw[:12]
    return f'1200-{suffix}'[:20]


def resolve_payer_ar_account_meta(payer):
    code = resolve_payer_ar_account_code(payer)
    name = f'Accounts Receivable - {getattr(payer, "name", payer)}'
    return code, name


def build_ire_revenue_breakdown(invoice):
    """
    Build InsuranceReceivableEntry department amounts from invoice display lines.
    Returns dict mapping IRE field names to Decimal amounts.
    """
    from hospital.services.receipt_revenue_allocation import _alloc_from_invoice_display_lines

    cap = Decimal(str(invoice.total_amount or 0))
    result = {field: D0 for field in IRE_AMOUNT_FIELDS}

    if cap <= 0:
        return result

    streams = _alloc_from_invoice_display_lines(invoice, cap) or {}
    for svc, amt in streams.items():
        field = _SERVICE_TO_IRE_FIELD.get((svc or 'other').lower(), 'consultation_amount')
        result[field] = result.get(field, D0) + Decimal(str(amt or 0))

    if sum(result.values(), D0) <= 0:
        result['consultation_amount'] = cap

    return result


def prorate_ire_revenue_amounts(ire_entry, credit_amount):
    """
    Prorate IRE department amounts for the outstanding credit portion.
    Returns dict rev_type -> Decimal (e.g. consultation -> 75.00).
    """
    credit_amount = Decimal(str(credit_amount or 0))
    total = Decimal(str(ire_entry.total_amount or 0))
    if credit_amount <= 0:
        return {}

    if total <= 0:
        return {'consultation': credit_amount}

    ratio = credit_amount / total
    buckets = []
    for field in IRE_AMOUNT_FIELDS:
        amt = Decimal(str(getattr(ire_entry, field, 0) or 0))
        if amt > 0:
            rev_type = IRE_FIELD_TO_REV_TYPE[field]
            buckets.append((rev_type, amt))

    if not buckets:
        return {'consultation': credit_amount}

    result = {}
    allocated = D0
    for idx, (rev_type, base_amt) in enumerate(buckets):
        if idx == len(buckets) - 1:
            share = credit_amount - allocated
        else:
            share = (base_amt * ratio).quantize(Decimal('0.01'))
            allocated += share
        if share > 0:
            result[rev_type] = result.get(rev_type, D0) + share

    return result


def credit_revenue_eligible_queryset(backfill_all=False):
    """IRE rows ready for credit revenue matching (48h hold unless backfill_all)."""
    from hospital.models_primecare_accounting import InsuranceReceivableEntry

    qs = InsuranceReceivableEntry.objects.filter(
        is_deleted=False,
        journal_entry__isnull=True,
        status__in=['pending', 'partially_paid'],
    )
    if not backfill_all:
        cutoff_date = timezone.now().date() - timedelta(days=2)
        qs = qs.filter(entry_date__lte=cutoff_date)
    return qs

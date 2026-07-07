"""
Group insurance/corporate receivable subledger lines by payer + billing month.
Supports batch remittance (one bank receipt settling a whole company month).
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from hospital.models import Payer


def month_bounds(month_key: str) -> tuple[date, date]:
    """Parse YYYY-MM into first/last day of that month."""
    year, month = parse_month_key(month_key)
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def parse_month_key(month_key: str) -> tuple[int, int]:
    """Parse YYYY-MM; raises ValueError if invalid."""
    raw = (month_key or '').strip()
    parts = raw.split('-', 1)
    if len(parts) != 2:
        raise ValueError(f'Invalid month key {raw!r} (expected YYYY-MM).')
    try:
        year = int(parts[0])
        month = int(parts[1])
    except ValueError as e:
        raise ValueError(f'Invalid month key {raw!r} (expected YYYY-MM).') from e
    if month < 1 or month > 12:
        raise ValueError(f'Invalid month in {raw!r} (must be 01–12).')
    return year, month


def group_receivable_entries(qs):
    """
    Aggregate InsuranceReceivableEntry rows by payer + calendar month.
    Returns list of dicts sorted newest month first, then payer name.
    """
    rows = (
        qs.annotate(billing_month=TruncMonth('entry_date'))
        .values('payer_id', 'payer__name', 'payer__payer_type', 'billing_month')
        .annotate(
            total_amount=Sum('total_amount'),
            amount_received=Sum('amount_received'),
            amount_rejected=Sum('amount_rejected'),
            withholding_tax=Sum('withholding_tax'),
            outstanding=Sum('outstanding_amount'),
            line_count=Count('id'),
            patient_count=Count('invoice__patient_id', filter=Q(invoice__patient_id__isnull=False), distinct=True),
            open_line_count=Count('id', filter=Q(outstanding_amount__gt=0)),
        )
        .order_by('-billing_month', 'payer__name')
    )
    groups = []
    for row in rows:
        bm = row['billing_month']
        if bm is None:
            continue
        month_date = bm.date() if hasattr(bm, 'date') else bm
        month_key = month_date.isoformat()[:7]
        groups.append(
            {
                'payer_id': row['payer_id'],
                'payer_name': row['payer__name'] or '—',
                'payer_type': row['payer__payer_type'] or '',
                'billing_month': month_date,
                'month_key': month_key,
                'month_label': month_date.strftime('%B %Y'),
                'total_amount': row['total_amount'] or Decimal('0.00'),
                'amount_received': row['amount_received'] or Decimal('0.00'),
                'amount_rejected': row['amount_rejected'] or Decimal('0.00'),
                'withholding_tax': row['withholding_tax'] or Decimal('0.00'),
                'outstanding': row['outstanding'] or Decimal('0.00'),
                'line_count': row['line_count'] or 0,
                'patient_count': row['patient_count'] or 0,
                'open_line_count': row['open_line_count'] or 0,
            }
        )
    return groups


def entries_for_company_month(payer_id, month_key, *, open_only=False):
    from hospital.models_primecare_accounting import InsuranceReceivableEntry

    start, end = month_bounds(month_key)
    qs = (
        InsuranceReceivableEntry.objects.filter(
            payer_id=payer_id,
            entry_date__gte=start,
            entry_date__lte=end,
            is_deleted=False,
        )
        .select_related('payer', 'invoice', 'invoice__patient')
        .order_by('entry_date', 'created')
    )
    if open_only:
        qs = qs.filter(outstanding_amount__gt=0)
    return qs


def _allocate_proportional(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split total across weights; last bucket absorbs rounding."""
    if not weights:
        return []
    if total <= 0:
        return [Decimal('0.00')] * len(weights)
    weight_sum = sum(weights) or Decimal('0')
    if weight_sum <= 0:
        equal = (total / len(weights)).quantize(Decimal('0.01'))
        parts = [equal] * len(weights)
        parts[-1] = total - sum(parts[:-1])
        return parts
    parts = []
    allocated = Decimal('0.00')
    for i, w in enumerate(weights):
        if i == len(weights) - 1:
            parts.append((total - allocated).quantize(Decimal('0.01')))
        else:
            share = (total * w / weight_sum).quantize(Decimal('0.01'))
            parts.append(share)
            allocated += share
    return parts


def apply_payment_to_entry(entry, *, amount_received=Decimal('0'), amount_rejected=Decimal('0'), withholding_tax=Decimal('0')):
    """Update subledger line balances after a remittance allocation."""
    entry.amount_received = (entry.amount_received or Decimal('0')) + amount_received
    entry.amount_rejected = (entry.amount_rejected or Decimal('0')) + amount_rejected
    entry.withholding_tax = (entry.withholding_tax or Decimal('0')) + withholding_tax
    entry.outstanding_amount = max(
        Decimal('0.00'),
        (entry.total_amount or Decimal('0'))
        - entry.amount_received
        - entry.amount_rejected
        - entry.withholding_tax,
    )
    if entry.outstanding_amount <= 0:
        entry.status = 'paid'
    elif entry.amount_received > 0 or entry.amount_rejected > 0 or entry.withholding_tax > 0:
        entry.status = 'partially_paid'
    entry.save(
        update_fields=[
            'amount_received',
            'amount_rejected',
            'withholding_tax',
            'outstanding_amount',
            'status',
            'modified',
        ]
    )


@transaction.atomic
def record_company_month_remittance(
    *,
    user,
    payer,
    month_key: str,
    entry_date,
    bank_account,
    total_amount: Decimal,
    amount_received: Decimal,
    amount_rejected: Decimal,
    withholding_tax: Decimal,
    withholding_tax_rate: Decimal = Decimal('0'),
    payment_reference: str = '',
    notes: str = '',
):
    """
    Record one bank remittance against all open lines for payer + month.
    Creates a single accounting journal entry and updates each subledger line.
    """
    from hospital.models_primecare_accounting import InsurancePaymentReceived

    entries = list(entries_for_company_month(payer.id, month_key, open_only=True))
    if not entries:
        raise ValueError(f'No open receivable lines for {payer.name} in {month_key}.')

    total_outstanding = sum((e.outstanding_amount or Decimal('0')) for e in entries)
    if total_outstanding <= 0:
        raise ValueError('Nothing outstanding to remit for this company/month.')

    if amount_received + amount_rejected + withholding_tax != total_amount:
        raise ValueError('Amount received + rejected + WHT must equal total amount.')

    if total_amount > total_outstanding:
        raise ValueError(
            f'Remittance total GHS {total_amount:.2f} exceeds outstanding '
            f'GHS {total_outstanding:.2f} for this company/month.'
        )

    weights = [e.outstanding_amount or Decimal('0') for e in entries]
    recv_parts = _allocate_proportional(amount_received, weights)
    rej_parts = _allocate_proportional(amount_rejected, weights)
    wht_parts = _allocate_proportional(withholding_tax, weights)

    batch_notes = (
        f'Batch remittance {month_key} — {len(entries)} line(s). '
        f'{notes}'.strip()
    )
    payment = InsurancePaymentReceived.objects.create(
        entry_date=entry_date,
        payer=payer,
        receivable_entry=None,
        total_amount=total_amount,
        amount_received=amount_received,
        amount_rejected=amount_rejected,
        withholding_tax=withholding_tax,
        withholding_tax_rate=withholding_tax_rate,
        bank_account=bank_account,
        payment_reference=payment_reference,
        notes=batch_notes,
        processed_by=user,
    )
    payment.create_accounting_entries(user)

    for entry, recv, rej, wht in zip(entries, recv_parts, rej_parts, wht_parts):
        if recv == 0 and rej == 0 and wht == 0:
            continue
        apply_payment_to_entry(entry, amount_received=recv, amount_rejected=rej, withholding_tax=wht)

    return payment, entries

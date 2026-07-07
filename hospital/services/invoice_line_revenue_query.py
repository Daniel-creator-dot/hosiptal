"""
Shared invoice-line queries for billed (accrual) service revenue reports.

Invoices are scoped by ``issued_at`` date; lines exclude waived rows.
Used by management service revenue and department billed-revenue reports.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from ..models import Invoice, InvoiceLine


def parse_ymd(value, default_date):
    if not value:
        return default_date
    try:
        return timezone.datetime.strptime(value, '%Y-%m-%d').date()
    except Exception:
        return default_date


def invoice_queryset_for_service_revenue(date_from, date_to, include_writeoff_period):
    """
    Invoices whose issued_at date falls in [date_from, date_to].
    Default excludes write-off window (matches Invoice.objects / VisibleManager).
    """
    common = dict(
        is_deleted=False,
        issued_at__date__gte=date_from,
        issued_at__date__lte=date_to,
        total_amount__gt=0,
    )
    if include_writeoff_period:
        return Invoice.all_objects.filter(**common)
    return Invoice.objects.filter(**common)


def service_revenue_line_queryset(
    *,
    date_from,
    date_to,
    include_writeoff_period,
    payer_type=None,
    category_icontains=None,
    search_q=None,
):
    inv_qs = invoice_queryset_for_service_revenue(date_from, date_to, include_writeoff_period)
    qs = InvoiceLine.objects.filter(
        is_deleted=False,
        waived_at__isnull=True,
        invoice__in=inv_qs,
    )
    if payer_type and payer_type != 'all':
        if payer_type == 'insurance':
            qs = qs.filter(
                Q(invoice__payer__payer_type='nhis')
                | Q(invoice__payer__payer_type='private')
                | Q(invoice__payer__payer_type='insurance')
            )
        else:
            qs = qs.filter(invoice__payer__payer_type=payer_type)
    if category_icontains:
        qs = qs.filter(service_code__category__icontains=category_icontains.strip())
    if search_q:
        sq = search_q.strip()
        if sq:
            qs = qs.filter(
                Q(service_code__code__icontains=sq) | Q(service_code__description__icontains=sq)
            )
    return qs


def aggregate_service_rows(qs, min_billed: Decimal | None):
    rows = list(
        qs.values(
            'service_code__code',
            'service_code__description',
            'service_code__category',
        ).annotate(
            line_count=Count('id'),
            qty=Sum('quantity'),
            billed=Sum('line_total'),
        )
    )
    for r in rows:
        if r['billed'] is None:
            r['billed'] = Decimal('0.00')
        else:
            r['billed'] = Decimal(str(r['billed']))
        if r['qty'] is None:
            r['qty'] = Decimal('0.00')
        else:
            r['qty'] = Decimal(str(r['qty']))
    if min_billed is not None and min_billed > 0:
        rows = [r for r in rows if r['billed'] >= min_billed]
    rows.sort(key=lambda x: x['billed'], reverse=True)
    total = sum((r['billed'] for r in rows), Decimal('0.00'))
    for r in rows:
        r['pct'] = (r['billed'] / total * 100) if total > 0 else Decimal('0.00')
    return rows, total


def category_rollup(qs):
    cats = list(
        qs.values('service_code__category')
        .annotate(
            line_count=Count('id'),
            billed=Sum('line_total'),
        )
        .order_by('-billed')
    )
    for c in cats:
        if c['billed'] is None:
            c['billed'] = Decimal('0.00')
        else:
            c['billed'] = Decimal(str(c['billed']))
    return cats

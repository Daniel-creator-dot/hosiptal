"""
Billed revenue by clinical department (invoice lines + payer), complementing cash/receipt views.

Department scoping uses deterministic ServiceCode / prescription rules aligned with
``views_revenue_monitoring._classify_invoice_line_to_stream`` where practical; consultation
uses stream classification for accuracy.
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, Sum

D0 = Decimal('0.00')

DEPARTMENT_KEYS = frozenset({'pharmacy', 'lab', 'imaging', 'consultation'})


def _pharmacy_q() -> Q:
    return (
        Q(prescription_id__isnull=False)
        | Q(service_code__code__istartswith='WALKIN-')
        | Q(service_code__code__istartswith='DRUG-')
        | Q(service_code__code__istartswith='RX-')
        | Q(service_code__code__istartswith='MED-')
        | Q(service_code__code__istartswith='PHARM')
        | Q(service_code__code__istartswith='PHARMA')
        | Q(service_code__code='ADM-CONSUMABLES')
        | Q(service_code__category__icontains='pharm')
        | Q(service_code__category__icontains='drug')
        | Q(service_code__category__icontains='medication')
        | Q(service_code__category__icontains='dispens')
    )


def _lab_q() -> Q:
    q = Q()
    for pfx in (
        'LAB-',
        'LABTEST-',
        'PATH-',
        'BIO-',
        'HEMA-',
        'MIC-',
        'MICRO-',
        'SERO-',
        'IMMUNO-',
    ):
        q |= Q(service_code__code__istartswith=pfx)
    q |= Q(service_code__code__in=['URA001'])
    q |= Q(service_code__category__icontains='laborat')
    q |= Q(service_code__category__icontains='pathology')
    q |= Q(service_code__category__icontains='microbiology')
    q |= Q(service_code__category__icontains='biochemistry')
    q |= Q(service_code__category__icontains='hematology')
    q |= Q(service_code__category__icontains='serology')
    q |= Q(service_code__category__icontains='immunology')
    return q


def _imaging_q() -> Q:
    return (
        Q(service_code__code__istartswith='IMG-')
        | Q(service_code__code__istartswith='IMGCAT-')
        | Q(service_code__code__istartswith='RAD-')
        | Q(service_code__code__istartswith='ECG')
        | Q(service_code__code__istartswith='IMG')
        | Q(service_code__category__icontains='imag')
        | Q(service_code__category__icontains='radiol')
        | Q(service_code__category__icontains='scan')
        | Q(service_code__category__icontains='x-ray')
        | Q(service_code__category__icontains='xray')
    )


def department_line_filter_q(dept: str) -> Q | None:
    """SQL-level filter for pharmacy, lab, imaging. Returns None for consultation (classified in Python)."""
    if dept == 'pharmacy':
        return _pharmacy_q()
    if dept == 'lab':
        return _lab_q()
    if dept == 'imaging':
        return _imaging_q()
    if dept == 'consultation':
        return None
    raise ValueError(f'Unknown dept {dept!r}')


def filter_lines_by_department(qs, dept: str):
    """
    Narrow an InvoiceLine queryset to one clinical department.
    Consultation: keeps rows classified as consultation_general / consultation_specialist.
    """
    if dept not in DEPARTMENT_KEYS:
        raise ValueError(f'Unknown dept {dept!r}')
    q = department_line_filter_q(dept)
    if q is not None:
        return qs.filter(q)

    # Consultation — align with revenue stream classifier (may be slower on large sets).
    from ..views_revenue_monitoring import _classify_invoice_line_to_stream

    keep_ids: list = []
    base = qs.select_related('invoice__encounter__provider__department', 'service_code')
    for line in base.iterator(chunk_size=1500):
        inv = line.invoice
        enc = getattr(inv, 'encounter', None)
        sk = _classify_invoice_line_to_stream(line, enc)
        if sk in ('consultation_general', 'consultation_specialist'):
            keep_ids.append(line.pk)
    if not keep_ids:
        return qs.none()
    return qs.filter(pk__in=keep_ids)


def aggregate_billed_by_payer(qs):
    """
    Sum line_total by invoice payer_type.
    Returns dict with per-payer-type rows, consolidated buckets, totals.
    """
    by_type = list(
        qs.values('invoice__payer__payer_type')
        .annotate(billed=Sum('line_total'), line_count=Count('id'))
        .order_by('-billed')
    )
    by_bucket = {
        'cash': D0,
        'corporate': D0,
        'nhis': D0,
        'private': D0,
        'insurance_other': D0,
        'unknown': D0,
    }
    rows = []
    total_billed = D0
    total_lines = 0
    for r in by_type:
        pt = r['invoice__payer__payer_type'] or ''
        amt = r['billed']
        if amt is None:
            amt = D0
        else:
            amt = Decimal(str(amt))
        n = int(r['line_count'] or 0)
        total_billed += amt
        total_lines += n
        if pt == 'cash':
            by_bucket['cash'] += amt
        elif pt == 'corporate':
            by_bucket['corporate'] += amt
        elif pt == 'nhis':
            by_bucket['nhis'] += amt
        elif pt == 'private':
            by_bucket['private'] += amt
        elif pt == 'insurance':
            by_bucket['insurance_other'] += amt
        else:
            by_bucket['unknown'] += amt
        rows.append(
            {
                'payer_type': pt or '—',
                'billed': amt,
                'line_count': n,
            }
        )

    insurance_all = by_bucket['nhis'] + by_bucket['private'] + by_bucket['insurance_other']

    return {
        'rows': rows,
        'by_bucket': by_bucket,
        'insurance_all': insurance_all,
        'total_billed': total_billed,
        'total_lines': total_lines,
    }


def rollup_service_codes(qs, limit=80):
    """Top service codes by billed amount for department queryset."""
    rows = list(
        qs.values(
            'service_code__code',
            'service_code__description',
            'service_code__category',
        )
        .annotate(line_count=Count('id'), billed=Sum('line_total'))
        .order_by('-billed')[:limit]
    )
    for r in rows:
        if r['billed'] is None:
            r['billed'] = D0
        else:
            r['billed'] = Decimal(str(r['billed']))
    return rows


def build_department_report(
    *,
    date_from,
    date_to,
    include_writeoff_period: bool,
    dept: str,
    payer_type: str | None,
):
    """
    Compose queryset + aggregates for HTML or export.
    payer_type: same semantics as management report (None = all).
    """
    from .invoice_line_revenue_query import service_revenue_line_queryset

    if dept not in DEPARTMENT_KEYS:
        raise ValueError(f'Unknown dept {dept!r}')

    base = service_revenue_line_queryset(
        date_from=date_from,
        date_to=date_to,
        include_writeoff_period=include_writeoff_period,
        payer_type=payer_type if payer_type and payer_type != 'all' else None,
        category_icontains=None,
        search_q=None,
    )
    filtered = filter_lines_by_department(base, dept)
    payer_summary = aggregate_billed_by_payer(filtered)
    top_services = rollup_service_codes(filtered, limit=100)
    return {
        'qs': filtered,
        'payer_summary': payer_summary,
        'top_services': top_services,
    }

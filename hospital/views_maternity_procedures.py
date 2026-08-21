"""
Maternity deliveries & procedures count report.

Counts billed maternity delivery procedures (MAT-DELIVER, MAT-CSECT) by month
so midwifery / admin can see how many deliveries and C-sections occurred.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from .decorators import role_required
from .models import InvoiceLine

REPORT_TZ = ZoneInfo('Africa/Accra')

# Core delivery / obstetric procedures (what we count as "deliveries")
DELIVERY_PROCEDURE_CODES = ('MAT-DELIVER', 'MAT-CSECT')

# Wider maternity activity (visits / care — not counted as a delivery)
MATERNITY_ACTIVITY_CODES = ('MAT-ANC', 'MAT-PNC', 'MAT-MIDWIFE')

CODE_LABELS = {
    'MAT-DELIVER': 'Delivery (normal / vaginal)',
    'MAT-CSECT': 'Caesarean section',
    'MAT-MIDWIFE': 'Midwife care',
    'MAT-ANC': 'Antenatal visit',
    'MAT-PNC': 'Postnatal visit',
}


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _month_end(d: date) -> date:
    if d.month == 12:
        return date(d.year, 12, 31)
    return date(d.year, d.month + 1, 1) - timedelta(days=1)


def _parse_month(raw: str):
    """Parse YYYY-MM into (month_start, month_end) or None."""
    raw = (raw or '').strip()
    if not raw or len(raw) < 7:
        return None
    try:
        y, m = int(raw[:4]), int(raw[5:7])
        start = date(y, m, 1)
        return start, _month_end(start)
    except (ValueError, TypeError):
        return None


def _aware_bounds(start: date, end: date):
    start_dt = timezone.make_aware(datetime.combine(start, time.min), REPORT_TZ)
    end_dt = timezone.make_aware(datetime.combine(end, time.max), REPORT_TZ)
    return start_dt, end_dt


def _delivery_lines_qs(start: date, end: date, codes=None):
    codes = codes or DELIVERY_PROCEDURE_CODES
    start_dt, end_dt = _aware_bounds(start, end)
    return (
        InvoiceLine.objects.filter(
            is_deleted=False,
            waived_at__isnull=True,
            service_code__code__in=codes,
            invoice__is_deleted=False,
        )
        .exclude(invoice__status='cancelled')
        .filter(
            Q(invoice__issued_at__gte=start_dt, invoice__issued_at__lte=end_dt)
            | Q(
                invoice__issued_at__isnull=True,
                created__gte=start_dt,
                created__lte=end_dt,
            )
        )
        .select_related('invoice', 'invoice__patient', 'service_code')
    )


def build_maternity_procedures_report(start: date, end: date):
    """Aggregate delivery procedure counts and related maternity activity for a date range."""
    delivery_qs = _delivery_lines_qs(start, end, DELIVERY_PROCEDURE_CODES)
    activity_qs = _delivery_lines_qs(start, end, MATERNITY_ACTIVITY_CODES)

    by_code = {
        row['service_code__code']: {
            'code': row['service_code__code'],
            'label': CODE_LABELS.get(row['service_code__code'], row['service_code__code']),
            'count': int(row['qty'] or 0),
            'lines': int(row['lines'] or 0),
            'amount': row['amount'] or Decimal('0.00'),
        }
        for row in delivery_qs.values('service_code__code').annotate(
            qty=Sum('quantity'),
            lines=Count('id'),
            amount=Sum('line_total'),
        )
    }

    normal = by_code.get('MAT-DELIVER', {}).get('count', 0)
    csection = by_code.get('MAT-CSECT', {}).get('count', 0)
    total_deliveries = normal + csection
    total_amount = sum((r['amount'] for r in by_code.values()), Decimal('0.00'))

    # Month buckets (for multi-month ranges)
    month_map = defaultdict(lambda: {'deliveries': 0, 'csection': 0, 'normal': 0, 'amount': Decimal('0.00')})
    for line in delivery_qs:
        inv = line.invoice
        dt = getattr(inv, 'issued_at', None) or line.created
        if timezone.is_aware(dt):
            local = dt.astimezone(REPORT_TZ)
        else:
            local = timezone.make_aware(dt, REPORT_TZ).astimezone(REPORT_TZ)
        key = date(local.year, local.month, 1)
        qty = int(line.quantity or 1)
        code = (getattr(line.service_code, 'code', None) or '').upper()
        month_map[key]['deliveries'] += qty
        month_map[key]['amount'] += line.line_total or Decimal('0.00')
        if code == 'MAT-CSECT':
            month_map[key]['csection'] += qty
        else:
            month_map[key]['normal'] += qty

    months = [
        {
            'month': m,
            'label': m.strftime('%B %Y'),
            'deliveries': v['deliveries'],
            'normal': v['normal'],
            'csection': v['csection'],
            'amount': v['amount'],
        }
        for m, v in sorted(month_map.items())
    ]

    activity_by_code = [
        {
            'code': row['service_code__code'],
            'label': CODE_LABELS.get(row['service_code__code'], row['service_code__code']),
            'count': int(row['qty'] or 0),
            'amount': row['amount'] or Decimal('0.00'),
        }
        for row in activity_qs.values('service_code__code').annotate(
            qty=Sum('quantity'),
            amount=Sum('line_total'),
        ).order_by('service_code__code')
    ]

    details = []
    for line in delivery_qs.order_by('-invoice__issued_at', '-created')[:500]:
        patient = getattr(line.invoice, 'patient', None)
        dt = getattr(line.invoice, 'issued_at', None) or line.created
        if dt and timezone.is_aware(dt):
            local = dt.astimezone(REPORT_TZ)
        elif dt:
            local = timezone.make_aware(dt, REPORT_TZ).astimezone(REPORT_TZ)
        else:
            local = None
        code = (getattr(line.service_code, 'code', None) or '').upper()
        details.append({
            'date': local.date() if local else None,
            'datetime': local,
            'patient_name': (patient.full_name if patient else '—'),
            'mrn': getattr(patient, 'mrn', '') or '—',
            'patient_id': getattr(patient, 'id', None),
            'procedure': CODE_LABELS.get(code, line.description or code),
            'code': code,
            'quantity': int(line.quantity or 1),
            'amount': line.line_total or Decimal('0.00'),
            'invoice_number': getattr(line.invoice, 'invoice_number', '') or '—',
        })

    return {
        'date_from': start,
        'date_to': end,
        'total_deliveries': total_deliveries,
        'normal_deliveries': normal,
        'csections': csection,
        'total_amount': total_amount,
        'by_code': sorted(by_code.values(), key=lambda r: r['code']),
        'months': months,
        'activity_by_code': activity_by_code,
        'details': details,
        'detail_count': delivery_qs.count(),
    }


@login_required
@role_required('admin', 'midwife', 'nurse', 'doctor', 'accountant', 'it', 'it_staff', 'manager')
def maternity_procedures_report(request):
    """
    Monthly count of deliveries and related maternity procedures (from billed lines).
    """
    today = timezone.now().astimezone(REPORT_TZ).date()
    month_raw = (request.GET.get('month') or '').strip()
    date_from_raw = (request.GET.get('date_from') or '').strip()
    date_to_raw = (request.GET.get('date_to') or '').strip()

    parsed_month = _parse_month(month_raw)
    if parsed_month:
        start, end = parsed_month
        month_value = start.strftime('%Y-%m')
    elif date_from_raw or date_to_raw:
        start = parse_date(date_from_raw) or _month_start(today)
        end = parse_date(date_to_raw) or _month_end(today)
        if end < start:
            start, end = end, start
        month_value = start.strftime('%Y-%m') if start.month == end.month and start.year == end.year else ''
    else:
        start, end = _month_start(today), _month_end(today)
        month_value = start.strftime('%Y-%m')

    data = build_maternity_procedures_report(start, end)

    export = (request.GET.get('export') or '').strip().lower()
    if export == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="maternity_deliveries_{start}_{end}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(['Date', 'Patient', 'MRN', 'Procedure', 'Code', 'Qty', 'Amount (GHS)', 'Invoice'])
        for row in data['details']:
            writer.writerow([
                row['date'].isoformat() if row['date'] else '',
                row['patient_name'],
                row['mrn'],
                row['procedure'],
                row['code'],
                row['quantity'],
                f"{row['amount']:.2f}",
                row['invoice_number'],
            ])
        return response

    context = {
        **data,
        'month_value': month_value,
        'title': 'Maternity Deliveries & Procedures',
    }
    return render(request, 'hospital/maternity_procedures_report.html', context)

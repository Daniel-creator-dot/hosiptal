"""
Admin Patient Attendance Report.

Canonical grain: Encounter (non-deleted, non-cancelled).
Night shift: 19:00–06:00 Africa/Accra, grouped under the evening start date.
"""
from __future__ import annotations

import csv
import re
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import ExtractHour
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from .decorators import role_required
from .models import Admission, Department, Encounter, Invoice, InvoiceLine, Payer, Staff
from .utils_billing import consolidated_corporate_company_group
from .utils_pagination import get_pagination_html

REPORT_TZ = ZoneInfo('Africa/Accra')
NIGHT_START_HOUR = 19  # inclusive
NIGHT_END_HOUR = 6  # exclusive (night ends at 06:00)

PAYER_TYPE_SHORT = {
    'nhis': 'NHIS',
    'private': 'Insurance',
    'corporate': 'Corporate',
    'cash': 'Cash',
    'insurance': 'Insurance',
    'unknown': 'Unbilled / no payer',
}

INSURANCE_TYPES = set(Payer.INSURANCE_PAYER_TYPES)
PAGE_SIZE = 50
EXPORT_ROW_LIMIT = 10000


def _parse_uuid(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _payer_type_label(ptype):
    key = (ptype or '').lower()
    return PAYER_TYPE_SHORT.get(key, (ptype or '—').replace('_', ' ').title())


def _local_dt(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.astimezone(REPORT_TZ)


def is_night_visit(dt) -> bool:
    local = _local_dt(dt)
    if local is None:
        return False
    hour = local.hour
    return hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR


def night_shift_date(dt):
    """
    Night of D = D 19:00 through (D+1) 06:00.
    Morning hours before 06:00 belong to the previous calendar date's night.
    Daytime visits return None.
    """
    local = _local_dt(dt)
    if local is None or not is_night_visit(local):
        return None
    if local.hour < NIGHT_END_HOUR:
        return (local.date() - timedelta(days=1))
    return local.date()


def _day_bounds(d: date):
    start = datetime.combine(d, time.min, tzinfo=REPORT_TZ)
    end = datetime.combine(d + timedelta(days=1), time.min, tzinfo=REPORT_TZ)
    return start, end


def _resolve_date_range(request):
    today = timezone.now().astimezone(REPORT_TZ).date()
    month_s = (request.GET.get('month') or '').strip()
    date_from_s = (request.GET.get('date_from') or '').strip()
    date_to_s = (request.GET.get('date_to') or '').strip()

    # Prefer explicit From/To when either is provided so a filled Month field
    # does not override a custom multi-month range.
    if date_from_s or date_to_s:
        end = parse_date(date_to_s) or today
        start = parse_date(date_from_s) or end.replace(day=1)
        if start > end:
            start, end = end, start
        return start, end, None

    if month_s and len(month_s) >= 7:
        try:
            year = int(month_s[:4])
            month = int(month_s[5:7])
            start = date(year, month, 1)
            if month == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)
            return start, end, f'{start.strftime("%Y-%m")}'
        except (ValueError, TypeError):
            pass

    start = today.replace(day=1)
    return start, today, start.strftime('%Y-%m')


def _latest_invoice_payer_by_encounter(encounter_ids):
    if not encounter_ids:
        return {}
    rows = (
        Invoice.all_objects.filter(is_deleted=False, encounter_id__in=list(encounter_ids))
        .order_by('encounter_id', '-created')
        .values_list('encounter_id', 'payer_id', 'payer__name', 'payer__payer_type')
    )
    out = {}
    for eid, pid, pname, ptype in rows:
        if eid not in out:
            out[eid] = {
                'id': pid,
                'name': (pname or '').strip() or '—',
                'type': (ptype or '').strip().lower() or 'unknown',
                'source': 'invoice',
            }
    return out


def _resolve_payer_info(encounter, enc_payer_map):
    info = enc_payer_map.get(encounter.pk)
    if info:
        return info
    primary = getattr(encounter.patient, 'primary_insurance', None)
    if primary is not None:
        return {
            'id': primary.pk,
            'name': (primary.name or '').strip() or '—',
            'type': (primary.payer_type or '').strip().lower() or 'unknown',
            'source': 'primary',
        }
    return {
        'id': None,
        'name': 'Unbilled / no payer',
        'type': 'unknown',
        'source': 'none',
    }


def _payer_category(ptype: str) -> str:
    ptype = (ptype or '').lower()
    if ptype == 'cash':
        return 'cash'
    if ptype == 'corporate':
        return 'corporate'
    if ptype in INSURANCE_TYPES:
        return 'insurance'
    if ptype in ('', 'unknown', '—'):
        return 'unbilled'
    return 'other'


def _strip_legacy_payer_suffix(name: str) -> str:
    """Drop trailing 'old' / '(old)' markers used on superseded payer rows."""
    raw = (name or '').strip()
    if not raw:
        return ''
    cleaned = re.sub(r'\s*\(\s*old\s*\)\s*$', '', raw, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+old\s*$', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or raw


def _prefer_payer_mix_label(current: str, candidate: str) -> str:
    """Prefer a human-readable label over ALL-CAPS / truncated duplicates."""
    cur = (current or '').strip()
    cand = (candidate or '').strip()
    if not cur:
        return cand
    if not cand:
        return cur
    cur_scream = cur.isupper() and any(c.isalpha() for c in cur)
    cand_scream = cand.isupper() and any(c.isalpha() for c in cand)
    if cur_scream and not cand_scream:
        return cand
    if cand_scream and not cur_scream:
        return cur
    if len(cand) > len(cur) + 2:
        return cand
    return cur


def _payer_mix_group(name: str, ptype: str | None = None):
    """
    Map a payer label to (group_key, display_name) so alias rows collapse.

    Reuses the corporate bill-pack consolidator (ECG / Anointed / etc.) and
    always groups by the normalized match key so case-only duplicates
    (ACE MEDICAL vs Ace Medical) merge in the payer mix.
    """
    raw = (name or '').strip() or 'Unbilled / no payer'
    cleaned = _strip_legacy_payer_suffix(raw)
    gk, display = consolidated_corporate_company_group(cleaned)
    # Prefer the consolidator's canonical display when it resolved an umbrella.
    if display and display.casefold() != cleaned.casefold():
        label = display
    else:
        label = cleaned or raw
    return gk or cleaned.casefold() or 'n/a', label


def _specialist_line_q():
    """Invoice lines that represent specialist / SP consultation fees."""
    return (
        Q(service_code__code__iexact='CON002')
        | Q(description__icontains='specialist consultation')
        | Q(description__icontains='gynae / special')
        | Q(description__icontains='special consultation')
    )


def _line_amount(line) -> Decimal:
    qty = Decimal(str(line.quantity or 1))
    unit = Decimal(str(line.unit_price or 0))
    total = qty * unit - Decimal(str(line.discount_amount or 0)) + Decimal(str(line.tax_amount or 0))
    if total == 0 and line.line_total is not None:
        return Decimal(str(line.line_total or 0))
    return total


def _specialist_services_breakdown(date_from: date, date_to: date, encounter_ids=None):
    """
    Specialist (SP) consultation amounts for the attendance period.

    Specialist visits are often typed as outpatient but billed as CON002 /
    Specialist Consultation — so this is driven by invoice lines, not
    encounter_type alone.
    """
    start_dt, _ = _day_bounds(date_from)
    _, end_dt = _day_bounds(date_to)
    qs = (
        InvoiceLine.objects.filter(
            is_deleted=False,
            waived_at__isnull=True,
            invoice__is_deleted=False,
            invoice__encounter__isnull=False,
            invoice__encounter__is_deleted=False,
            invoice__encounter__started_at__gte=start_dt,
            invoice__encounter__started_at__lt=end_dt,
        )
        .exclude(invoice__status='cancelled')
        .exclude(invoice__encounter__status='cancelled')
        .filter(_specialist_line_q())
        .select_related(
            'invoice__encounter__provider__user',
            'invoice__encounter__provider__department',
        )
    )
    if encounter_ids is not None:
        qs = qs.filter(invoice__encounter_id__in=list(encounter_ids))

    by_unit = defaultdict(lambda: {'visits': 0, 'amount': Decimal('0.00')})
    by_specialist = defaultdict(lambda: {'visits': 0, 'amount': Decimal('0.00')})
    total_amount = Decimal('0.00')
    total_lines = 0
    encounter_seen = set()

    for line in qs.iterator(chunk_size=500):
        amt = _line_amount(line)
        total_amount += amt
        total_lines += 1
        enc = line.invoice.encounter if line.invoice_id else None
        unit = '—'
        specialist = '—'
        if enc is not None:
            encounter_seen.add(enc.pk)
            provider = enc.provider if enc.provider_id else None
            if provider is not None:
                if provider.department_id and provider.department:
                    unit = provider.department.name or '—'
                if provider.user_id and provider.user:
                    specialist = provider.user.get_full_name() or provider.user.username or '—'
        by_unit[unit]['visits'] += 1
        by_unit[unit]['amount'] += amt
        by_specialist[specialist]['visits'] += 1
        by_specialist[specialist]['amount'] += amt

    def _rows(bucket):
        rows = []
        for label, data in sorted(
            bucket.items(),
            key=lambda x: (-x[1]['amount'], -x[1]['visits'], x[0]),
        ):
            amount = data['amount']
            pct = float(round(100 * amount / total_amount, 1)) if total_amount else 0.0
            rows.append({
                'label': label,
                'visits': data['visits'],
                'amount': amount,
                'amount_display': f'{amount:,.2f}',
                'pct': pct,
            })
        return rows

    return {
        'total_amount': total_amount,
        'total_amount_display': f'{total_amount:,.2f}',
        'total_lines': total_lines,
        'unique_encounters': len(encounter_seen),
        'unit_rows': _rows(by_unit),
        'specialist_rows': _rows(by_specialist),
    }


def _base_encounter_qs(date_from: date, date_to: date):
    start_dt, _ = _day_bounds(date_from)
    _, end_dt = _day_bounds(date_to)
    local_hour = ExtractHour('started_at', tzinfo=REPORT_TZ)
    admission_exists = Admission.objects.filter(
        encounter_id=OuterRef('pk'),
        is_deleted=False,
    )
    return (
        Encounter.objects.filter(
            is_deleted=False,
            started_at__gte=start_dt,
            started_at__lt=end_dt,
        )
        .exclude(status='cancelled')
        .annotate(
            local_hour=local_hour,
            has_admission=Exists(admission_exists),
        )
        .select_related(
            'patient',
            'patient__primary_insurance',
            'provider',
            'provider__user',
            'provider__department',
            'location',
            'admission',
            'admission__ward',
            'admission__ward__department',
        )
    )


def _apply_filters(qs, request, enc_payer_map=None):
    """Apply GET filters. Returns (qs, notes)."""
    notes = []
    shift = (request.GET.get('shift') or '').strip().lower()
    care = (request.GET.get('care') or '').strip().lower()
    encounter_type = (request.GET.get('encounter_type') or '').strip()
    status = (request.GET.get('status') or '').strip()
    department_id = _parse_uuid(request.GET.get('department'))
    clinician_id = _parse_uuid(request.GET.get('clinician'))
    payer_category = (request.GET.get('payer_category') or '').strip().lower()
    payer_id = _parse_uuid(request.GET.get('payer'))
    q = (request.GET.get('q') or '').strip()

    if shift == 'night':
        qs = qs.filter(Q(local_hour__gte=NIGHT_START_HOUR) | Q(local_hour__lt=NIGHT_END_HOUR))
        notes.append('Night visits only (19:00–06:00 Accra)')
    elif shift == 'day':
        qs = qs.filter(local_hour__gte=NIGHT_END_HOUR, local_hour__lt=NIGHT_START_HOUR)
        notes.append('Day visits only (06:00–19:00 Accra)')

    if care == 'inpatient':
        qs = qs.filter(Q(has_admission=True) | Q(encounter_type='inpatient'))
        notes.append('Inpatient / admissions')
    elif care == 'outpatient':
        qs = qs.filter(has_admission=False).exclude(encounter_type='inpatient')
        notes.append('Outpatient / ambulatory')

    if encounter_type:
        qs = qs.filter(encounter_type=encounter_type)
    if status:
        qs = qs.filter(status=status)
    if department_id:
        qs = qs.filter(
            Q(provider__department_id=department_id)
            | Q(admission__ward__department_id=department_id)
        )
    if clinician_id:
        qs = qs.filter(provider_id=clinician_id)
    if q:
        qs = qs.filter(
            Q(patient__mrn__icontains=q)
            | Q(patient__first_name__icontains=q)
            | Q(patient__last_name__icontains=q)
            | Q(patient__middle_name__icontains=q)
        )

    # Payer filters need the payer map (invoice + primary fallback)
    if payer_category or payer_id:
        if enc_payer_map is None:
            enc_payer_map = {}
        id_list = list(qs.values_list('id', flat=True)[:EXPORT_ROW_LIMIT * 2])
        missing = [eid for eid in id_list if eid not in enc_payer_map]
        if missing:
            enc_payer_map.update(_latest_invoice_payer_by_encounter(missing))

        # Lightweight fetch — avoid .only() conflicting with base select_related.
        payer_qs = (
            Encounter.objects.filter(pk__in=id_list)
            .select_related('patient', 'patient__primary_insurance')
        )
        matching_ids = []
        for enc in payer_qs.iterator(chunk_size=500):
            info = _resolve_payer_info(enc, enc_payer_map)
            if payer_id and info.get('id') != payer_id:
                continue
            if payer_category and _payer_category(info.get('type')) != payer_category:
                continue
            matching_ids.append(enc.pk)
        qs = qs.filter(pk__in=matching_ids)
        if payer_category:
            notes.append(f'Payer category: {_payer_type_label(payer_category)}')
        if payer_id:
            notes.append('Filtered by specific payer')

    return qs, notes, enc_payer_map


def _is_inpatient(encounter) -> bool:
    if getattr(encounter, 'has_admission', None) is True:
        return True
    if encounter.encounter_type == 'inpatient':
        return True
    try:
        adm = encounter.admission
        if adm is not None and not getattr(adm, 'is_deleted', False):
            return True
    except Admission.DoesNotExist:
        pass
    return False


def _build_detail_row(encounter, enc_payer_map):
    local = _local_dt(encounter.started_at)
    payer = _resolve_payer_info(encounter, enc_payer_map)
    inpatient = _is_inpatient(encounter)
    dept = None
    if encounter.provider_id and encounter.provider and encounter.provider.department_id:
        dept = encounter.provider.department.name
    ward = None
    admission_status = None
    try:
        adm = encounter.admission
        if adm and not adm.is_deleted:
            ward = adm.ward.name if adm.ward_id and adm.ward else None
            admission_status = adm.status
            if not dept and adm.ward_id and getattr(adm.ward, 'department', None):
                dept = adm.ward.department.name
    except Admission.DoesNotExist:
        pass

    clinician = ''
    if encounter.provider_id and encounter.provider and encounter.provider.user_id:
        clinician = encounter.provider.user.get_full_name() or encounter.provider.user.username

    night_date = night_shift_date(encounter.started_at)
    return {
        'id': encounter.pk,
        'patient_id': encounter.patient_id,
        'started_at': encounter.started_at,
        'started_local': local,
        'started_display': local.strftime('%d %b %Y %H:%M') if local else '—',
        'night_shift_date': night_date,
        'night_shift_display': night_date.strftime('%d %b %Y') if night_date else '—',
        'is_night': bool(night_date),
        'patient_name': encounter.patient.full_name if encounter.patient_id else '—',
        'mrn': encounter.patient.mrn if encounter.patient_id else '—',
        'encounter_type': encounter.encounter_type,
        'encounter_type_display': encounter.get_encounter_type_display(),
        'care_setting': 'Inpatient' if inpatient else 'Outpatient',
        'is_inpatient': inpatient,
        'department': dept or '—',
        'clinician': clinician or '—',
        'payer_name': payer['name'],
        'payer_type': payer['type'],
        'payer_type_label': _payer_type_label(payer['type']),
        'payer_source': payer['source'],
        'payer_category': _payer_category(payer['type']),
        'ward': ward or '—',
        'admission_status': admission_status or '—',
        'status': encounter.status,
        'status_display': encounter.get_status_display(),
    }


def _summarize(rows):
    summary = {
        'total_visits': len(rows),
        'unique_patients': len({r['patient_id'] for r in rows if r.get('patient_id')}),
        'inpatient_visits': sum(1 for r in rows if r['is_inpatient']),
        'outpatient_visits': sum(1 for r in rows if not r['is_inpatient']),
        'night_visits': sum(1 for r in rows if r['is_night']),
        'day_visits': sum(1 for r in rows if not r['is_night']),
        'cash': 0,
        'insurance': 0,
        'corporate': 0,
        'unbilled': 0,
        'other': 0,
    }
    by_month = defaultdict(lambda: {'visits': 0, 'patients': set(), 'night': 0, 'inpatient': 0})
    by_payer_type = defaultdict(int)
    by_payer_group = {}
    by_encounter_type = defaultdict(int)
    by_department = defaultdict(int)
    by_status = defaultdict(int)
    by_care = defaultdict(int)
    by_shift = defaultdict(int)

    for r in rows:
        cat = r['payer_category']
        if cat in summary:
            summary[cat] += 1
        else:
            summary['other'] += 1

        local = r.get('started_local')
        month_key = local.strftime('%Y-%m') if local else 'unknown'
        by_month[month_key]['visits'] += 1
        if r.get('patient_id'):
            by_month[month_key]['patients'].add(r['patient_id'])
        if r['is_night']:
            by_month[month_key]['night'] += 1
        if r['is_inpatient']:
            by_month[month_key]['inpatient'] += 1

        by_payer_type[_payer_type_label(r['payer_type'])] += 1
        gk, label = _payer_mix_group(r.get('payer_name'), r.get('payer_type'))
        if gk not in by_payer_group:
            by_payer_group[gk] = {'label': label, 'count': 0}
        by_payer_group[gk]['count'] += 1
        by_payer_group[gk]['label'] = _prefer_payer_mix_label(
            by_payer_group[gk]['label'], label
        )
        by_encounter_type[r['encounter_type_display']] += 1
        by_department[r['department']] += 1
        by_status[r['status_display']] += 1
        by_care[r['care_setting']] += 1
        by_shift['Night' if r['is_night'] else 'Day'] += 1

    month_rows = []
    for key in sorted(by_month.keys()):
        bucket = by_month[key]
        month_rows.append({
            'month': key,
            'visits': bucket['visits'],
            'unique_patients': len(bucket['patients']),
            'night': bucket['night'],
            'inpatient': bucket['inpatient'],
            'outpatient': bucket['visits'] - bucket['inpatient'],
        })

    total_visits = summary['total_visits'] or 0

    def _sorted_counts(d):
        out = []
        for k, v in sorted(d.items(), key=lambda x: (-x[1], x[0])):
            pct = round(100 * v / total_visits, 1) if total_visits else 0
            out.append({'label': k, 'count': v, 'pct': pct})
        return out

    payer_name_rows = []
    for item in sorted(
        by_payer_group.values(),
        key=lambda x: (-x['count'], x['label']),
    )[:40]:
        pct = round(100 * item['count'] / total_visits, 1) if total_visits else 0
        payer_name_rows.append({
            'label': item['label'],
            'count': item['count'],
            'pct': pct,
        })

    return {
        'summary': summary,
        'month_rows': month_rows,
        'payer_type_rows': _sorted_counts(by_payer_type),
        'payer_name_rows': payer_name_rows,
        'encounter_type_rows': _sorted_counts(by_encounter_type),
        'department_rows': _sorted_counts(by_department)[:40],
        'status_rows': _sorted_counts(by_status),
        'care_rows': _sorted_counts(by_care),
        'shift_rows': _sorted_counts(by_shift),
    }


def _load_report_data(request, for_export=False):
    date_from, date_to, month_value = _resolve_date_range(request)
    qs = _base_encounter_qs(date_from, date_to)

    # Preload payer map for encounters in period (before payer filters)
    period_ids = list(qs.values_list('id', flat=True)[:EXPORT_ROW_LIMIT * 2])
    enc_payer_map = _latest_invoice_payer_by_encounter(period_ids)
    qs, filter_notes, enc_payer_map = _apply_filters(qs, request, enc_payer_map)

    # Cap export/detail materialization
    ordered = qs.order_by('-started_at', '-id')
    total_count = ordered.count()
    if for_export:
        encounters = list(ordered[:EXPORT_ROW_LIMIT])
    else:
        # For summary KPIs we need all matching rows (within safe cap)
        encounters = list(ordered[:EXPORT_ROW_LIMIT])

    if enc_payer_map is None:
        enc_payer_map = {}
    missing = [e.pk for e in encounters if e.pk not in enc_payer_map]
    if missing:
        enc_payer_map.update(_latest_invoice_payer_by_encounter(missing))

    rows = [_build_detail_row(e, enc_payer_map) for e in encounters]
    aggregates = _summarize(rows)
    summary = aggregates['summary']
    period_days = max(1, (date_to - date_from).days + 1)
    total_visits = summary['total_visits']
    summary.update({
        'period_days': period_days,
        'average_daily_visits': round(total_visits / period_days, 1),
        'night_share': round(100 * summary['night_visits'] / total_visits, 1) if total_visits else 0,
        'inpatient_share': round(100 * summary['inpatient_visits'] / total_visits, 1) if total_visits else 0,
        'repeat_visits': max(0, total_visits - summary['unique_patients']),
        'repeat_share': round(
            100 * max(0, total_visits - summary['unique_patients']) / total_visits, 1
        ) if total_visits else 0,
    })

    # Specialist / SP services: amounts & % by unit and clinician (CON002 lines).
    # When detail filters are active, restrict to the same encounter set; otherwise
    # use the full date window so amounts are not truncated by the register cap.
    detail_filters_active = any([
        (request.GET.get('shift') or '').strip(),
        (request.GET.get('care') or '').strip(),
        (request.GET.get('encounter_type') or '').strip(),
        (request.GET.get('status') or '').strip(),
        (request.GET.get('department') or '').strip(),
        (request.GET.get('clinician') or '').strip(),
        (request.GET.get('payer_category') or '').strip(),
        (request.GET.get('payer') or '').strip(),
        (request.GET.get('q') or '').strip(),
    ])
    specialist = _specialist_services_breakdown(
        date_from,
        date_to,
        encounter_ids=[e.pk for e in encounters] if detail_filters_active else None,
    )
    summary['specialist_services_amount'] = specialist['total_amount']
    summary['specialist_services_count'] = specialist['total_lines']
    summary['specialist_services_encounters'] = specialist['unique_encounters']

    departments = Department.objects.filter(is_deleted=False, is_active=True).order_by('name')
    clinicians = (
        Staff.objects.filter(is_deleted=False, is_active=True, profession='doctor')
        .select_related('user')
        .order_by('user__first_name', 'user__last_name')[:300]
    )
    payers = Payer.objects.filter(is_deleted=False).order_by('payer_type', 'name')

    return {
        'date_from': date_from,
        'date_to': date_to,
        'month_value': month_value or date_from.strftime('%Y-%m'),
        'filter_notes': filter_notes,
        'rows': rows,
        'total_count': total_count,
        'truncated': True if total_count > EXPORT_ROW_LIMIT else False,
        'departments': departments,
        'clinicians': clinicians,
        'payers': payers,
        'encounter_types': Encounter.ENCOUNTER_TYPES,
        'status_choices': [c for c in Encounter.STATUS_CHOICES if c[0] != 'cancelled'],
        'filters': {
            'shift': (request.GET.get('shift') or '').strip(),
            'care': (request.GET.get('care') or '').strip(),
            'encounter_type': (request.GET.get('encounter_type') or '').strip(),
            'status': (request.GET.get('status') or '').strip(),
            'department': (request.GET.get('department') or '').strip(),
            'clinician': (request.GET.get('clinician') or '').strip(),
            'payer_category': (request.GET.get('payer_category') or '').strip(),
            'payer': (request.GET.get('payer') or '').strip(),
            'q': (request.GET.get('q') or '').strip(),
            'month': (request.GET.get('month') or '').strip(),
        },
        'specialist_services': specialist,
        'specialist_unit_rows': specialist['unit_rows'],
        'specialist_clinician_rows': specialist['specialist_rows'],
        **aggregates,
    }


def _export_filename(prefix, date_from, date_to, ext):
    return f'{prefix}_{date_from.isoformat()}_{date_to.isoformat()}.{ext}'


def _export_csv(data):
    buffer = BytesIO()
    # utf-8-sig for Excel
    import io
    text = io.StringIO()
    writer = csv.writer(text)
    s = data['summary']
    writer.writerow(['Patient Attendance Report'])
    writer.writerow(['Period', f"{data['date_from']} to {data['date_to']}"])
    writer.writerow(['Timezone', 'Africa/Accra'])
    writer.writerow(['Night window', '19:00 – 06:00 (grouped by night start date)'])
    writer.writerow([])
    writer.writerow(['Summary'])
    for label, key in [
        ('Total visits', 'total_visits'),
        ('Unique patients', 'unique_patients'),
        ('Inpatient visits', 'inpatient_visits'),
        ('Outpatient visits', 'outpatient_visits'),
        ('Night visits', 'night_visits'),
        ('Day visits', 'day_visits'),
        ('Cash', 'cash'),
        ('Insurance / NHIS', 'insurance'),
        ('Corporate', 'corporate'),
        ('Unbilled / no payer', 'unbilled'),
    ]:
        writer.writerow([label, s.get(key, 0)])
    writer.writerow([])
    writer.writerow(['Month-to-month'])
    writer.writerow(['Month', 'Visits', 'Unique patients', 'Night', 'Inpatient', 'Outpatient'])
    for m in data['month_rows']:
        writer.writerow([m['month'], m['visits'], m['unique_patients'], m['night'], m['inpatient'], m['outpatient']])
    writer.writerow([])
    writer.writerow(['Payer mix (consolidated)'])
    writer.writerow(['Payer', 'Visits', '% of visits'])
    for item in data['payer_name_rows']:
        writer.writerow([item['label'], item['count'], item.get('pct', 0)])
    writer.writerow([])
    sp = data.get('specialist_services') or {}
    writer.writerow(['Specialist / SP services'])
    writer.writerow(['Total billed (GHS)', sp.get('total_amount_display', '0.00')])
    writer.writerow(['Lines', sp.get('total_lines', 0)])
    writer.writerow(['Visits with SP fee', sp.get('unique_encounters', 0)])
    writer.writerow([])
    writer.writerow(['By unit / department'])
    writer.writerow(['Unit', 'Lines', 'Amount (GHS)', '% of SP'])
    for item in data.get('specialist_unit_rows') or []:
        writer.writerow([item['label'], item['visits'], item['amount_display'], item.get('pct', 0)])
    writer.writerow([])
    writer.writerow(['By specialist / clinician'])
    writer.writerow(['Specialist', 'Lines', 'Amount (GHS)', '% of SP'])
    for item in data.get('specialist_clinician_rows') or []:
        writer.writerow([item['label'], item['visits'], item['amount_display'], item.get('pct', 0)])
    writer.writerow([])
    writer.writerow([
        'Arrival (Accra)', 'Night of', 'Shift', 'MRN', 'Patient', 'Visit type',
        'Care setting', 'Department', 'Clinician', 'Payer', 'Payer type',
        'Payer source', 'Ward', 'Admission status', 'Status',
    ])
    for r in data['rows']:
        writer.writerow([
            r['started_display'],
            r['night_shift_display'],
            'Night' if r['is_night'] else 'Day',
            r['mrn'],
            r['patient_name'],
            r['encounter_type_display'],
            r['care_setting'],
            r['department'],
            r['clinician'],
            r['payer_name'],
            r['payer_type_label'],
            r['payer_source'],
            r['ward'],
            r['admission_status'],
            r['status_display'],
        ])
    content = '\ufeff' + text.getvalue()
    response = HttpResponse(content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="{_export_filename("patient_attendance", data["date_from"], data["date_to"], "csv")}"'
    )
    return response


def _export_excel(data):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return HttpResponse('openpyxl is required for Excel export.', status=500)

    wb = Workbook()
    header_fill = PatternFill('solid', fgColor='1F4E79')
    header_font = Font(color='FFFFFF', bold=True)
    title_font = Font(size=16, bold=True, color='1F4E79')
    section_font = Font(size=12, bold=True)
    thin = Border(
        left=Side(style='thin', color='D0D7DE'),
        right=Side(style='thin', color='D0D7DE'),
        top=Side(style='thin', color='D0D7DE'),
        bottom=Side(style='thin', color='D0D7DE'),
    )
    kpi_fill = PatternFill('solid', fgColor='E8F1FB')

    # Summary sheet
    ws = wb.active
    ws.title = 'Summary'
    ws.merge_cells('A1:D1')
    ws['A1'] = 'Patient Attendance Report'
    ws['A1'].font = title_font
    ws['A2'] = f"Period: {data['date_from']} to {data['date_to']} (Africa/Accra)"
    ws['A3'] = 'Night window: 19:00–06:00, grouped by night start date'
    if data.get('filter_notes'):
        ws['A4'] = 'Filters: ' + '; '.join(data['filter_notes'])

    row = 6
    ws.cell(row=row, column=1, value='KPI').font = Font(bold=True)
    ws.cell(row=row, column=2, value='Value').font = Font(bold=True)
    for col in (1, 2):
        ws.cell(row=row, column=col).fill = header_fill
        ws.cell(row=row, column=col).font = header_font
    row += 1
    s = data['summary']
    for label, key in [
        ('Total visits', 'total_visits'),
        ('Unique patients', 'unique_patients'),
        ('Inpatient visits', 'inpatient_visits'),
        ('Outpatient visits', 'outpatient_visits'),
        ('Night visits', 'night_visits'),
        ('Day visits', 'day_visits'),
        ('Cash', 'cash'),
        ('Insurance / NHIS', 'insurance'),
        ('Corporate', 'corporate'),
        ('Unbilled / no payer', 'unbilled'),
    ]:
        ws.cell(row=row, column=1, value=label).fill = kpi_fill
        ws.cell(row=row, column=2, value=s.get(key, 0))
        for col in (1, 2):
            ws.cell(row=row, column=col).border = thin
        row += 1

    row += 2
    ws.cell(row=row, column=1, value='Month-to-month').font = section_font
    row += 1
    headers = ['Month', 'Visits', 'Unique patients', 'Night', 'Inpatient', 'Outpatient']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin
    row += 1
    for m in data['month_rows']:
        vals = [m['month'], m['visits'], m['unique_patients'], m['night'], m['inpatient'], m['outpatient']]
        for col, val in enumerate(vals, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.border = thin
        row += 1

    def _write_breakdown(title, rows_data, start_row):
        r = start_row
        ws.cell(row=r, column=1, value=title).font = section_font
        r += 1
        for col, h in enumerate(['Category', 'Visits'], 1):
            cell = ws.cell(row=r, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = thin
        r += 1
        for item in rows_data:
            ws.cell(row=r, column=1, value=item['label']).border = thin
            ws.cell(row=r, column=2, value=item['count']).border = thin
            r += 1
        return r + 2

    row += 2
    row = _write_breakdown('By shift', data['shift_rows'], row)
    row = _write_breakdown('By care setting', data['care_rows'], row)
    row = _write_breakdown('By payer type', data['payer_type_rows'], row)
    row = _write_breakdown('By visit type', data['encounter_type_rows'], row)

    for col_idx in range(1, 7):
        ws.column_dimensions[get_column_letter(col_idx)].width = 18

    # Detail sheet
    wd = wb.create_sheet('Detailed register')
    detail_headers = [
        'Arrival (Accra)', 'Night of', 'Shift', 'MRN', 'Patient', 'Visit type',
        'Care setting', 'Department', 'Clinician', 'Payer', 'Payer type',
        'Payer source', 'Ward', 'Admission status', 'Status',
    ]
    for col, h in enumerate(detail_headers, 1):
        cell = wd.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(wrap_text=True)
        cell.border = thin
    for i, r in enumerate(data['rows'], start=2):
        vals = [
            r['started_display'], r['night_shift_display'],
            'Night' if r['is_night'] else 'Day',
            r['mrn'], r['patient_name'], r['encounter_type_display'],
            r['care_setting'], r['department'], r['clinician'],
            r['payer_name'], r['payer_type_label'], r['payer_source'],
            r['ward'], r['admission_status'], r['status_display'],
        ]
        for col, val in enumerate(vals, 1):
            cell = wd.cell(row=i, column=col, value=val)
            cell.border = thin
    for col_idx in range(1, len(detail_headers) + 1):
        wd.column_dimensions[get_column_letter(col_idx)].width = 16
    wd.auto_filter.ref = f'A1:{get_column_letter(len(detail_headers))}{max(1, len(data["rows"]) + 1)}'
    wd.freeze_panes = 'A2'

    # Payer sheet (consolidated aliases + share %)
    wp = wb.create_sheet('Payer mix')
    for col, h in enumerate(['Payer', 'Visits', '% of visits'], 1):
        cell = wp.cell(row=1, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
    for i, item in enumerate(data['payer_name_rows'], start=2):
        wp.cell(row=i, column=1, value=item['label'])
        wp.cell(row=i, column=2, value=item['count'])
        wp.cell(row=i, column=3, value=item.get('pct', 0))
    wp.column_dimensions['A'].width = 36
    wp.column_dimensions['B'].width = 12
    wp.column_dimensions['C'].width = 14

    # Specialist / SP services
    ws_sp = wb.create_sheet('Specialist services')
    sp = data.get('specialist_services') or {}
    ws_sp['A1'] = 'Specialist / SP services'
    ws_sp['A1'].font = title_font
    ws_sp['A2'] = (
        f"Total billed: GHS {sp.get('total_amount_display', '0.00')} · "
        f"{sp.get('total_lines', 0)} lines · {sp.get('unique_encounters', 0)} visits"
    )
    row = 4
    ws_sp.cell(row=row, column=1, value='By unit / department').font = section_font
    row += 1
    for col, h in enumerate(['Unit', 'Lines', 'Amount (GHS)', '% of SP'], 1):
        cell = ws_sp.cell(row=row, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin
    row += 1
    for item in data.get('specialist_unit_rows') or []:
        vals = [item['label'], item['visits'], float(item['amount']), item.get('pct', 0)]
        for col, val in enumerate(vals, 1):
            cell = ws_sp.cell(row=row, column=col, value=val)
            cell.border = thin
        row += 1
    row += 2
    ws_sp.cell(row=row, column=1, value='By specialist / clinician').font = section_font
    row += 1
    for col, h in enumerate(['Specialist', 'Lines', 'Amount (GHS)', '% of SP'], 1):
        cell = ws_sp.cell(row=row, column=col, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = thin
    row += 1
    for item in data.get('specialist_clinician_rows') or []:
        vals = [item['label'], item['visits'], float(item['amount']), item.get('pct', 0)]
        for col, val in enumerate(vals, 1):
            cell = ws_sp.cell(row=row, column=col, value=val)
            cell.border = thin
        row += 1
    for col_idx, width in enumerate([28, 12, 16, 12], 1):
        ws_sp.column_dimensions[get_column_letter(col_idx)].width = width

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = (
        f'attachment; filename="{_export_filename("patient_attendance", data["date_from"], data["date_to"], "xlsx")}"'
    )
    return response


def _export_pdf(data):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        return HttpResponse('ReportLab is required for PDF export.', status=500)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=0.4 * inch,
        rightMargin=0.4 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.4 * inch,
        title='Patient Attendance Report',
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'AttTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1F4E79'),
        alignment=TA_CENTER, spaceAfter=6,
    )
    sub_style = ParagraphStyle(
        'AttSub', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=colors.HexColor('#475569'),
    )
    section_style = ParagraphStyle(
        'AttSec', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#1F4E79'), spaceBefore=10, spaceAfter=6,
    )
    cell_style = ParagraphStyle('AttCell', parent=styles['Normal'], fontSize=7, leading=9)

    story = []
    story.append(Paragraph('Patient Attendance Report', title_style))
    story.append(Paragraph(
        f"Period: {data['date_from']} to {data['date_to']} · Timezone: Africa/Accra · "
        f"Night: 19:00–06:00 (grouped by night start date)",
        sub_style,
    ))
    if data.get('filter_notes'):
        story.append(Paragraph('Filters: ' + '; '.join(data['filter_notes']), sub_style))
    story.append(Spacer(1, 8))

    s = data['summary']
    kpi_data = [
        ['Visits', 'Unique patients', 'Inpatient', 'Outpatient', 'Night', 'Day', 'Cash', 'Insurance', 'Corporate', 'Unbilled'],
        [
            str(s['total_visits']), str(s['unique_patients']), str(s['inpatient_visits']),
            str(s['outpatient_visits']), str(s['night_visits']), str(s['day_visits']),
            str(s['cash']), str(s['insurance']), str(s['corporate']), str(s['unbilled']),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[1.05 * inch] * 10)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#E8F1FB')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#94A3B8')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(kpi_table)

    if data['month_rows']:
        story.append(Paragraph('Month-to-month attendance', section_style))
        month_data = [['Month', 'Visits', 'Unique patients', 'Night', 'Inpatient', 'Outpatient']]
        for m in data['month_rows']:
            month_data.append([
                m['month'], str(m['visits']), str(m['unique_patients']),
                str(m['night']), str(m['inpatient']), str(m['outpatient']),
            ])
        mt = Table(month_data, colWidths=[1.4 * inch] * 6)
        mt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ]))
        story.append(mt)

    story.append(Paragraph('Detailed attendance register', section_style))
    headers = ['Arrival', 'Night of', 'Shift', 'MRN', 'Patient', 'Type', 'Care', 'Dept', 'Payer', 'Status']
    table_data = [headers]
    # Keep PDF readable — first 500 detail rows
    for r in data['rows'][:500]:
        table_data.append([
            Paragraph(r['started_display'], cell_style),
            Paragraph(r['night_shift_display'], cell_style),
            'Night' if r['is_night'] else 'Day',
            Paragraph(str(r['mrn']), cell_style),
            Paragraph(r['patient_name'][:28], cell_style),
            Paragraph(r['encounter_type_display'][:16], cell_style),
            r['care_setting'][:3],
            Paragraph((r['department'] or '—')[:14], cell_style),
            Paragraph((r['payer_name'] or '—')[:18], cell_style),
            r['status_display'][:10],
        ])
    col_widths = [1.15 * inch, 0.85 * inch, 0.5 * inch, 0.85 * inch, 1.35 * inch,
                  0.9 * inch, 0.55 * inch, 0.9 * inch, 1.1 * inch, 0.7 * inch]
    detail = Table(table_data, colWidths=col_widths, repeatRows=1)
    detail.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F5F9')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(detail)
    if len(data['rows']) > 500:
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"Showing first 500 of {len(data['rows'])} rows. Export Excel/CSV for the full register.",
            sub_style,
        ))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{_export_filename("patient_attendance", data["date_from"], data["date_to"], "pdf")}"'
    )
    return response


@login_required
@role_required('admin', 'it', 'it_staff')
def patient_attendance_report(request):
    export = (request.GET.get('export') or '').strip().lower()
    data = _load_report_data(request, for_export=bool(export))

    if export == 'csv':
        return _export_csv(data)
    if export in ('xlsx', 'excel'):
        return _export_excel(data)
    if export == 'pdf':
        return _export_pdf(data)

    paginator = Paginator(data['rows'], PAGE_SIZE)
    page_number = request.GET.get('page') or 1
    page_obj = paginator.get_page(page_number)
    pagination_html = get_pagination_html(request, page_obj)

    export_qs = request.GET.copy()
    export_qs.pop('export', None)
    export_qs.pop('page', None)

    context = {
        'title': 'Patient Attendance Report',
        'date_from': data['date_from'],
        'date_to': data['date_to'],
        'month_value': data['month_value'],
        'filter_notes': data['filter_notes'],
        'summary': data['summary'],
        'month_rows': data['month_rows'],
        'payer_type_rows': data['payer_type_rows'],
        'payer_name_rows': data['payer_name_rows'],
        'encounter_type_rows': data['encounter_type_rows'],
        'department_rows': data['department_rows'],
        'status_rows': data['status_rows'],
        'care_rows': data['care_rows'],
        'shift_rows': data['shift_rows'],
        'specialist_services': data['specialist_services'],
        'specialist_unit_rows': data['specialist_unit_rows'],
        'specialist_clinician_rows': data['specialist_clinician_rows'],
        'page_obj': page_obj,
        'detail_rows': page_obj.object_list,
        'pagination_html': pagination_html,
        'total_count': data['total_count'],
        'truncated': data['truncated'],
        'departments': data['departments'],
        'clinicians': data['clinicians'],
        'payers': data['payers'],
        'encounter_types': data['encounter_types'],
        'status_choices': data['status_choices'],
        'filters': data['filters'],
        'querystring': export_qs.urlencode(),
    }
    return render(request, 'hospital/patient_attendance_report.html', context)

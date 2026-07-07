"""
Medical analytics for Django admin users: diagnosis mix, visit frequency, payer & enrollment filters.
"""
import uuid
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Encounter, Invoice, Payer
from .models_advanced import Diagnosis
from .models_diagnosis import DiagnosisCode
from .models_enterprise_billing import CorporateAccount, CorporateEmployee

PAYER_TYPE_SHORT = {
    'nhis': 'NHIS',
    'private': 'Insurance',
    'corporate': 'Corporate',
    'cash': 'Cash',
    'insurance': 'Insurance',
}

# Short, evidence-aligned prevention themes by ICD category (education / wellness planning).
PREVENTION_BY_CATEGORY = {
    'infectious': 'Promote vaccination where available, hand hygiene, food and water safety, and rapid isolation/treatment of communicable illness.',
    'neoplasms': 'Encourage age-appropriate screening, smoking cessation, and early evaluation of persistent symptoms.',
    'blood': 'Address nutrition (e.g. iron, B12), malaria prevention where relevant, and prompt work-up of anemia or bleeding.',
    'endocrine': 'Lifestyle counselling (diet, activity), metabolic screening for at-risk staff, and medication adherence support for diabetes and hypertension.',
    'mental': 'Stress management, employee assistance, sleep hygiene, and destigmatising access to counselling.',
    'nervous': 'Head injury prevention (safety), migraine triggers, and urgent care pathways for focal neurological symptoms.',
    'eye': 'UV protection, diabetes and hypertension control, and periodic vision checks for screen-intensive roles.',
    'ear': 'Hearing protection in noisy environments and prompt treatment of chronic ear infections.',
    'circulatory': 'BP and lipids screening, smoking cessation, diet, activity, and adherence to cardiac medications.',
    'respiratory': 'Smoking cessation, flu and pneumococcal vaccination where indicated, and dust/fume controls at work.',
    'digestive': 'Safe food handling, moderation of alcohol, hydration, and evaluation of chronic GI symptoms.',
    'skin': 'Sun protection, occupational dermatitis prevention, and hygiene education for common skin infections.',
    'musculoskeletal': 'Ergonomics, lifting training, stretching breaks, and early physio for back and neck pain.',
    'genitourinary': 'STI prevention, hydration, and screening for UTI/diabetes in recurrent cases.',
    'pregnancy': 'Prenatal care linkage, iron/folate, and workplace accommodations for pregnant employees.',
    'perinatal': 'Neonatal danger-sign education for parents and timely postnatal follow-up.',
    'congenital': 'Genetic counselling where appropriate and coordinated specialist follow-up.',
    'symptoms': 'Clarify recurring “undiagnosed” symptoms with targeted work-ups and health coaching.',
    'injury': 'Workplace safety, road safety, and first-aid readiness; review near-miss incidents.',
    'external': 'Safety audits and protective equipment to reduce preventable external causes.',
    'other': 'General wellness: sleep, nutrition, activity, and periodic health checks.',
}


def _admin_site_access(request):
    from .admin import _primecare_admin_has_permission

    return _primecare_admin_has_permission(request)


def _parse_uuid(raw):
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _latest_invoice_payer_by_encounter(encounter_ids):
    """Latest non-deleted invoice per encounter (by created desc)."""
    if not encounter_ids:
        return {}
    eids = list(encounter_ids)
    rows = (
        Invoice.all_objects.filter(is_deleted=False, encounter_id__in=eids)
        .order_by('encounter_id', '-created')
        .values_list('encounter_id', 'payer_id', 'payer__name', 'payer__payer_type')
    )
    out = {}
    for eid, pid, pname, ptype in rows:
        if eid not in out:
            out[eid] = {'id': pid, 'name': (pname or '').strip() or '—', 'type': (ptype or '').strip() or '—'}
    return out


def _corporate_enrollment_patient_ids(corporate_account_id):
    if not corporate_account_id:
        return None
    return CorporateEmployee.objects.filter(
        corporate_account_id=corporate_account_id,
        is_active=True,
        is_deleted=False,
    ).values_list('patient_id', flat=True)


def _parse_org_param(request):
    """
    org=payer:<uuid> — visits billed to that Payer (latest invoice on encounter in period).
    org=ca:<uuid>     — patients with active CorporateEmployee for that CorporateAccount.
    Legacy: corporate_account=<uuid> treated as ca:<uuid>.
    """
    raw = (request.GET.get('org') or '').strip()
    if raw.startswith('payer:') and len(raw) > 6:
        u = _parse_uuid(raw[6:])
        return ('payer', u) if u else (None, None)
    if raw.startswith('ca:') and len(raw) > 3:
        u = _parse_uuid(raw[3:])
        return ('ca', u) if u else (None, None)
    legacy = (request.GET.get('corporate_account') or '').strip()
    if legacy:
        u = _parse_uuid(legacy)
        if u:
            return ('ca', u)
    return (None, None)


def _payer_type_label(ptype):
    return PAYER_TYPE_SHORT.get((ptype or '').lower(), (ptype or '—').replace('_', ' ').title())


def _build_org_choices(selected_kind, selected_uuid):
    """Dropdown: billing payers + corporate enrollment accounts."""
    choices = []

    # Include inactive payers so historical NHIS / corporate names still appear in the list
    payers = (
        Payer.objects.filter(is_deleted=False)
        .exclude(payer_type='cash')
        .order_by('payer_type', 'name')
    )
    for p in payers:
        val = f'payer:{p.pk}'
        label = f"{p.name} ({_payer_type_label(p.payer_type)})"
        choices.append(
            {
                'value': val,
                'label': label,
                'group': 'Billing payer (NHIS, insurance, corporate on invoice)',
                'selected': selected_kind == 'payer' and selected_uuid and p.pk == selected_uuid,
            }
        )

    for c in CorporateAccount.objects.filter(is_deleted=False).order_by('company_name'):
        val = f'ca:{c.pk}'
        suffix = '' if getattr(c, 'is_active', True) else ' — inactive'
        choices.append(
            {
                'value': val,
                'label': f"{c.company_name} (employee enrollment){suffix}",
                'group': 'Corporate account (HR enrollment, not always same as invoice payer)',
                'selected': selected_kind == 'ca' and selected_uuid and c.pk == selected_uuid,
            }
        )

    return choices


def _payer_scheme_mix(encounter_ids, enc_payer_map, diag_qs):
    """
    Aggregate visits, diagnosis rows, and distinct patients by billing payer
    for encounters in period (using latest invoice payer).
    """
    visits_by = defaultdict(int)
    for eid in encounter_ids:
        info = enc_payer_map.get(eid)
        if not info:
            key = (None, 'Unbilled / no invoice', 'unknown')
        else:
            key = (info['id'], info['name'], info['type'])
        visits_by[key] += 1

    dx_by = defaultdict(lambda: {'dx': 0, 'patients': set()})
    for row in diag_qs.values('encounter_id', 'patient_id'):
        eid = row['encounter_id']
        info = enc_payer_map.get(eid)
        if not info:
            key = (None, 'Unbilled / no invoice', 'unknown')
        else:
            key = (info['id'], info['name'], info['type'])
        dx_by[key]['dx'] += 1
        if row.get('patient_id'):
            dx_by[key]['patients'].add(row['patient_id'])

    rows = []
    all_keys = set(visits_by.keys()) | set(dx_by.keys())
    for key in all_keys:
        pid, pname, ptype = key
        rows.append(
            {
                'payer_id': pid,
                'name': pname,
                'payer_type': ptype,
                'type_label': _payer_type_label(ptype) if ptype != 'unknown' else '—',
                'visits': visits_by.get(key, 0),
                'diagnoses': dx_by[key]['dx'],
                'patients': len(dx_by[key]['patients']),
            }
        )
    rows.sort(key=lambda r: (-r['diagnoses'], -r['visits'], r['name'] or ''))
    return rows[:50]


@login_required
def admin_medical_analytics_report(request):
    if not _admin_site_access(request):
        raise PermissionDenied

    today = timezone.now().date()
    date_to_s = request.GET.get('date_to') or ''
    date_from_s = request.GET.get('date_from') or ''
    end = parse_date(date_to_s) or today
    start = parse_date(date_from_s) or (end - timedelta(days=89))
    if start > end:
        start, end = end, start

    org_kind, org_uuid = _parse_org_param(request)

    encounter_ids_period = list(
        Encounter.objects.filter(
            is_deleted=False,
            started_at__date__gte=start,
            started_at__date__lte=end,
        ).values_list('id', flat=True)
    )
    enc_payer_map = _latest_invoice_payer_by_encounter(encounter_ids_period)

    encounter_filter_ids = None
    patient_filter_ids = None
    selected_payer = None
    selected_company = None
    filter_description = 'All schemes — volume table uses the latest invoice on each visit in this period.'

    if org_kind == 'payer' and org_uuid:
        selected_payer = Payer.objects.filter(pk=org_uuid, is_deleted=False).first()
        encounter_filter_ids = {
            eid for eid, info in enc_payer_map.items() if info['id'] == org_uuid
        }
        filter_description = (
            f'Visits billed to payer “{selected_payer.name}” ({_payer_type_label(selected_payer.payer_type)}) '
            f'— using latest invoice per encounter in the date range.'
        )
    elif org_kind == 'ca' and org_uuid:
        selected_company = CorporateAccount.objects.filter(pk=org_uuid, is_deleted=False).first()
        patient_filter_ids = list(_corporate_enrollment_patient_ids(org_uuid) or [])
        filter_description = (
            f'Patients with active enrollment under corporate account '
            f'“{selected_company.company_name if selected_company else org_uuid}”.'
        )

    diag_base = Diagnosis.objects.filter(
        is_deleted=False,
        diagnosis_date__date__gte=start,
        diagnosis_date__date__lte=end,
    )
    enc_base = Encounter.objects.filter(
        is_deleted=False,
        started_at__date__gte=start,
        started_at__date__lte=end,
    )

    if encounter_filter_ids is not None:
        diag_base = diag_base.filter(encounter_id__in=encounter_filter_ids)
        enc_base = enc_base.filter(id__in=encounter_filter_ids)
    elif patient_filter_ids is not None:
        if not patient_filter_ids:
            diag_base = diag_base.none()
            enc_base = enc_base.none()
        else:
            diag_base = diag_base.filter(patient_id__in=patient_filter_ids)
            enc_base = enc_base.filter(patient_id__in=patient_filter_ids)

    total_diagnoses = diag_base.count()
    distinct_patients_dx = diag_base.values('patient_id').distinct().count()

    top_diagnoses = list(
        diag_base.values(
            'diagnosis_code_id',
            'diagnosis_code__short_description',
            'diagnosis_code__description',
            'diagnosis',
            'icd10_code',
            'diagnosis_code__code',
            'diagnosis_code__category',
        )
        .annotate(
            diag_count=Count('id'),
            patient_count=Count('patient_id', distinct=True),
        )
        .order_by('-diag_count')[:35]
    )

    for row in top_diagnoses:
        name = (row.get('diagnosis_code__short_description') or '').strip()
        if not name:
            name = (row.get('diagnosis_code__description') or '').strip()
        if not name:
            name = (row.get('diagnosis') or '').strip() or '—'
        code = (row.get('diagnosis_code__code') or row.get('icd10_code') or '').strip()
        row['display_name'] = name
        row['display_code'] = code
        row['pct'] = round(100.0 * row['diag_count'] / total_diagnoses, 1) if total_diagnoses else 0.0

    total_enc_in_filter = enc_base.count()

    top_visitors = list(
        enc_base.values(
            'patient_id',
            'patient__mrn',
            'patient__first_name',
            'patient__last_name',
            'patient__middle_name',
        )
        .annotate(visit_count=Count('id'))
        .order_by('-visit_count')[:25]
    )

    for row in top_visitors:
        fn = row.get('patient__first_name') or ''
        mn = (row.get('patient__middle_name') or '').strip()
        ln = row.get('patient__last_name') or ''
        row['full_name'] = ' '.join(p for p in (fn, mn, ln) if p).strip() or '—'
        row['patient_pk'] = row.get('patient_id')
        row['visit_pct'] = (
            round(100.0 * row['visit_count'] / total_enc_in_filter, 1) if total_enc_in_filter else 0.0
        )

    category_rows = list(
        diag_base.exclude(diagnosis_code__isnull=True)
        .values('diagnosis_code__category')
        .annotate(c=Count('id'))
        .order_by('-c')
    )

    uncoded_count = diag_base.filter(diagnosis_code__isnull=True).count()

    prevention_items = []
    for cr in category_rows:
        cat = cr.get('diagnosis_code__category') or ''
        if not cat:
            continue
        label = dict(DiagnosisCode.CATEGORY_CHOICES).get(cat, cat.replace('_', ' ').title())
        prevention_items.append(
            {
                'category_key': cat,
                'category_label': label,
                'count': cr['c'],
                'pct': round(100.0 * cr['c'] / total_diagnoses, 1) if total_diagnoses else 0.0,
                'hint': PREVENTION_BY_CATEGORY.get(cat, PREVENTION_BY_CATEGORY['other']),
            }
        )

    # Full-period mix (only meaningful when not narrowed by org — still useful to compare)
    diag_for_mix = Diagnosis.objects.filter(
        is_deleted=False,
        diagnosis_date__date__gte=start,
        diagnosis_date__date__lte=end,
        encounter_id__in=encounter_ids_period,
    )
    payer_mix_rows = _payer_scheme_mix(encounter_ids_period, enc_payer_map, diag_for_mix)

    type_totals = defaultdict(lambda: {'dx': 0, 'visits': 0})
    for r in payer_mix_rows:
        pt = (r['payer_type'] or 'unknown').lower()
        type_totals[pt]['dx'] += r['diagnoses']
        type_totals[pt]['visits'] += r['visits']
    payer_type_summary = [
        {
            'type': pt,
            'label': _payer_type_label(pt),
            'diagnoses': data['dx'],
            'visits': data['visits'],
        }
        for pt, data in sorted(type_totals.items(), key=lambda x: -x[1]['dx'])
    ]

    org_choices = _build_org_choices(org_kind, org_uuid)
    current_org_value = ''
    if org_kind == 'payer' and org_uuid:
        current_org_value = f'payer:{org_uuid}'
    elif org_kind == 'ca' and org_uuid:
        current_org_value = f'ca:{org_uuid}'

    context = {
        'title': 'Medical analytics report',
        'date_from': start,
        'date_to': end,
        'org_value': current_org_value,
        'filter_description': filter_description,
        'selected_payer': selected_payer,
        'selected_company': selected_company,
        'org_choices': org_choices,
        # Hospital-wide scheme mix for the period (hidden when a single org is selected to avoid confusion)
        'payer_mix_rows': payer_mix_rows if not (org_kind and org_uuid) else [],
        'payer_type_summary': payer_type_summary if not (org_kind and org_uuid) else [],
        'total_diagnoses': total_diagnoses,
        'distinct_patients_dx': distinct_patients_dx,
        'total_encounters': total_enc_in_filter,
        'top_diagnoses': top_diagnoses,
        'top_visitors': top_visitors,
        'prevention_items': prevention_items[:12],
        'uncoded_count': uncoded_count,
        'org_filtered': bool(org_kind and org_uuid),
    }
    return render(request, 'hospital/admin_medical_analytics_report.html', context)

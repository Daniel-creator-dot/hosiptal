"""
Canonical InsuranceClaimItem rows for lists and KPIs.

- One row per invoice line (newest by created, id).
- Orphan rows (no invoice_line): one per exact snapshot on an invoice, or per
  encounter-less snapshot (newest wins). Uses NOT EXISTS so PostgreSQL does not
  need MAX(uuid).

Run ``manage.py dedupe_insurance_claim_items --apply`` to soft-delete duplicates
in the database (including normalized-description orphan clusters).
"""
from collections import defaultdict
from datetime import date

from django.apps import apps
from django.db.models import Exists, OuterRef, Q, Subquery


CLAIM_GROUP_BUILD_CAP = 3000


def visit_bucket_key_for_claim(claim_item):
    """Group claim lines into one visit (combined bill) per invoice or encounter."""
    if claim_item.invoice_id:
        return ('inv', claim_item.invoice_id)
    if claim_item.encounter_id:
        return ('enc', claim_item.encounter_id, claim_item.service_date)
    return ('solo', claim_item.id)


def _patient_ids_matching_claim_search(query):
    """Patients whose name/MRN/insurance fields match — used to show all visit lines."""
    if not (query or '').strip():
        return []
    Patient = apps.get_model('hospital', 'Patient')
    q = query.strip()
    return list(
        Patient.objects.filter(is_deleted=False)
        .filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(mrn__icontains=q)
            | Q(insurance_id__icontains=q)
            | Q(insurance_member_id__icontains=q)
            | Q(insurance_policy_number__icontains=q)
        )
        .values_list('pk', flat=True)[:250]
    )


def apply_insurance_claim_item_filters(qs, get_params):
    """
    Apply shared GET filters (q, status, payer, date_from, date_to, encounter).
    When q matches a patient name/MRN, return every claim line for that patient.
    """
    query = (get_params.get('q') or '').strip()
    status_filter = (get_params.get('status') or '').strip()
    payer_filter = (get_params.get('payer') or '').strip()
    date_from = (get_params.get('date_from') or '').strip()
    date_to = (get_params.get('date_to') or '').strip()
    encounter_filter = (get_params.get('encounter') or '').strip()

    if query:
        patient_ids = _patient_ids_matching_claim_search(query)
        line_q = (
            Q(patient_insurance_id__icontains=query)
            | Q(service_description__icontains=query)
            | Q(claim_reference__icontains=query)
        )
        if patient_ids:
            qs = qs.filter(Q(patient_id__in=patient_ids) | line_q)
        else:
            qs = qs.filter(line_q)

    if status_filter:
        qs = qs.filter(claim_status=status_filter)

    if payer_filter:
        qs = qs.filter(payer_id=payer_filter)

    if encounter_filter:
        qs = qs.filter(encounter_id=encounter_filter)

    if date_from:
        try:
            from datetime import datetime

            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            qs = qs.filter(service_date__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            from datetime import datetime

            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            qs = qs.filter(service_date__lte=date_to_obj)
        except ValueError:
            pass

    return qs


def rollup_insurance_claim_status(items):
    """Single status label when a visit group has mixed line statuses."""
    statuses = [i.claim_status for i in items]
    if len(set(statuses)) == 1:
        return statuses[0]
    if 'pending' in statuses:
        return 'pending'
    if 'rejected' in statuses:
        return 'rejected'
    if 'reversed' in statuses:
        return 'reversed'
    for s in ('submitted', 'processing', 'approved', 'partially_paid', 'paid'):
        if s in statuses:
            return s
    return statuses[0]


def batch_insurance_plan_names_for_patients(patient_ids):
    """Active insurance plan name per patient (for claims officer tables)."""
    if not patient_ids:
        return {}
    try:
        PatientInsurance = apps.get_model('hospital', 'PatientInsurance')
    except LookupError:
        return {}
    out = {}
    rows = (
        PatientInsurance.objects.filter(
            patient_id__in=patient_ids,
            status='active',
            is_deleted=False,
            insurance_plan__isnull=False,
        )
        .select_related('insurance_plan')
        .order_by('patient_id', '-is_primary', '-effective_date', '-created')
    )
    for pi in rows:
        if pi.patient_id in out:
            continue
        plan = getattr(pi.insurance_plan, 'plan_name', None) or ''
        if plan.strip():
            out[pi.patient_id] = plan.strip()
    return out


def build_claim_encounter_groups(claim_items, *, plan_by_patient=None):
    """
    Group claim items by visit (invoice / encounter) for claims-officer UI.
    plan_by_patient: optional dict patient_id -> plan name.
    """
    plan_by_patient = plan_by_patient or {}
    buckets = defaultdict(list)
    for item in claim_items:
        buckets[visit_bucket_key_for_claim(item)].append(item)

    InsuranceClaimItem = apps.get_model('hospital', 'InsuranceClaimItem')
    status_labels = dict(InsuranceClaimItem.CLAIM_STATUS_CHOICES)

    groups = []
    for _key, items in buckets.items():
        items.sort(key=lambda x: (x.service_date or date.min, x.pk), reverse=True)
        first = items[0]
        patient = first.patient
        pid = patient.pk if patient else None
        billed = sum((i.billed_amount or 0 for i in items), 0)
        paid = sum((i.paid_amount or 0 for i in items), 0)
        rolled = rollup_insurance_claim_status(items)
        enc = first.encounter
        visit_label = first.service_date
        if enc and getattr(enc, 'started_at', None):
            visit_label = enc.started_at.date()
        groups.append(
            {
                'patient': patient,
                'payer': first.payer,
                'encounter': enc,
                'invoice': first.invoice,
                'service_date': first.service_date,
                'visit_date': visit_label,
                'insurance_id': (first.patient_insurance_id or '').strip(),
                'plan_name': plan_by_patient.get(pid, '') if pid else '',
                'items': items,
                'item_count': len(items),
                'billed_total': billed,
                'paid_total': paid,
                'claim_status': rolled,
                'claim_status_label': status_labels.get(
                    rolled, rolled.replace('_', ' ').title()
                ),
            }
        )
    groups.sort(
        key=lambda g: (g['visit_date'] or date.min, g['service_date'] or date.min),
        reverse=True,
    )
    return groups


def build_claim_patient_groups(encounter_groups):
    """
    Nest visit (invoice/encounter) groups under each patient for claims-officer UI.
    """
    InsuranceClaimItem = apps.get_model('hospital', 'InsuranceClaimItem')
    status_labels = dict(InsuranceClaimItem.CLAIM_STATUS_CHOICES)

    buckets = defaultdict(list)
    for group in encounter_groups:
        patient = group.get('patient')
        pid = patient.pk if patient else None
        buckets[pid].append(group)

    patient_groups = []
    for pid, visits in buckets.items():
        visits.sort(
            key=lambda g: (g['visit_date'] or date.min, g['service_date'] or date.min),
            reverse=True,
        )
        first_visit = visits[0]
        patient = first_visit['patient']
        billed = sum((v['billed_total'] or 0 for v in visits), 0)
        paid = sum((v['paid_total'] or 0 for v in visits), 0)
        item_count = sum(v['item_count'] for v in visits)
        all_items = [line for v in visits for line in v['items']]
        rolled = rollup_insurance_claim_status(all_items)
        payer_ids = {v['payer'].pk for v in visits if v.get('payer')}
        payer = first_visit['payer']
        payer_label = payer.name if payer and len(payer_ids) <= 1 else 'Multiple payers'
        latest_visit = max(
            (g['visit_date'] or g['service_date'] or date.min for g in visits),
            default=date.min,
        )
        patient_groups.append(
            {
                'patient': patient,
                'insurance_id': (first_visit.get('insurance_id') or '').strip(),
                'plan_name': first_visit.get('plan_name') or '',
                'payer': payer,
                'payer_label': payer_label,
                'visits': visits,
                'visit_count': len(visits),
                'item_count': item_count,
                'billed_total': billed,
                'paid_total': paid,
                'claim_status': rolled,
                'claim_status_label': status_labels.get(
                    rolled, rolled.replace('_', ' ').title()
                ),
                'latest_visit_date': latest_visit,
            }
        )

    patient_groups.sort(key=lambda g: g['latest_visit_date'] or date.min, reverse=True)
    return patient_groups


def paginate_claim_encounter_groups(filtered_qs, *, per_page, page_number):
    """
    Build encounter-group pages from a filtered claim-item queryset.
    Returns (page_obj, groups_truncated: bool).
    """
    from django.core.paginator import Paginator

    total = filtered_qs.count()
    truncated = total > CLAIM_GROUP_BUILD_CAP
    cap = CLAIM_GROUP_BUILD_CAP if truncated else total
    item_pks = list(
        filtered_qs.order_by('-service_date', '-created').values_list('pk', flat=True)[:cap]
    )
    if not item_pks:
        empty = Paginator([], per_page).get_page(page_number)
        return empty, truncated

    InsuranceClaimItem = apps.get_model('hospital', 'InsuranceClaimItem')
    items = list(
        InsuranceClaimItem.objects.filter(pk__in=item_pks)
        .select_related('patient', 'payer', 'invoice', 'encounter', 'service_code')
        .order_by('-service_date', '-created')
    )
    patient_ids = list({i.patient_id for i in items if i.patient_id})
    plan_map = batch_insurance_plan_names_for_patients(patient_ids)
    groups = build_claim_encounter_groups(items, plan_by_patient=plan_map)
    return Paginator(groups, per_page).get_page(page_number), truncated


def paginate_claim_patient_groups(filtered_qs, *, per_page, page_number):
    """
    Build patient-group pages (each patient nests visit groups and line items).
    Returns (page_obj, groups_truncated: bool).
    """
    from django.core.paginator import Paginator

    total = filtered_qs.count()
    truncated = total > CLAIM_GROUP_BUILD_CAP
    cap = CLAIM_GROUP_BUILD_CAP if truncated else total
    item_pks = list(
        filtered_qs.order_by('-service_date', '-created').values_list('pk', flat=True)[:cap]
    )
    if not item_pks:
        empty = Paginator([], per_page).get_page(page_number)
        return empty, truncated

    InsuranceClaimItem = apps.get_model('hospital', 'InsuranceClaimItem')
    items = list(
        InsuranceClaimItem.objects.filter(pk__in=item_pks)
        .select_related('patient', 'payer', 'invoice', 'encounter', 'service_code')
        .order_by('-service_date', '-created')
    )
    patient_ids = list({i.patient_id for i in items if i.patient_id})
    plan_map = batch_insurance_plan_names_for_patients(patient_ids)
    visit_groups = build_claim_encounter_groups(items, plan_by_patient=plan_map)
    patient_groups = build_claim_patient_groups(visit_groups)
    return Paginator(patient_groups, per_page).get_page(page_number), truncated


def insurance_claim_item_deduped_q():
    """
    Rows that should appear in UI aggregates and claim lists.
    """
    InsuranceClaimItem = apps.get_model('hospital', 'InsuranceClaimItem')

    latest_with_line = InsuranceClaimItem.objects.filter(
        invoice_line_id=OuterRef('invoice_line_id'),
        is_deleted=False,
    ).order_by('-created', '-id').values('id')[:1]

    newer_orphan_on_invoice = InsuranceClaimItem.objects.filter(
        is_deleted=False,
        invoice_line_id__isnull=True,
        invoice_id=OuterRef('invoice_id'),
        patient_id=OuterRef('patient_id'),
        payer_id=OuterRef('payer_id'),
        service_date=OuterRef('service_date'),
        billed_amount=OuterRef('billed_amount'),
        service_description=OuterRef('service_description'),
    ).exclude(pk=OuterRef('pk')).filter(
        Q(created__gt=OuterRef('created'))
        | Q(created=OuterRef('created'), pk__gt=OuterRef('pk'))
    )

    newer_orphan_no_invoice = InsuranceClaimItem.objects.filter(
        is_deleted=False,
        invoice_line_id__isnull=True,
        invoice_id__isnull=True,
        patient_id=OuterRef('patient_id'),
        payer_id=OuterRef('payer_id'),
        service_date=OuterRef('service_date'),
        billed_amount=OuterRef('billed_amount'),
        service_description=OuterRef('service_description'),
    ).exclude(pk=OuterRef('pk')).filter(
        Q(created__gt=OuterRef('created'))
        | Q(created=OuterRef('created'), pk__gt=OuterRef('pk'))
    )

    return (
        Q(invoice_line_id__isnull=False) & Q(id=Subquery(latest_with_line))
    ) | (
        Q(invoice_line_id__isnull=True, invoice_id__isnull=False)
        & ~Exists(newer_orphan_on_invoice)
    ) | (
        Q(invoice_line_id__isnull=True, invoice_id__isnull=True)
        & ~Exists(newer_orphan_no_invoice)
    )

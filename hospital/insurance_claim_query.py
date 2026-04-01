"""
Canonical InsuranceClaimItem rows for lists and KPIs.

- One row per invoice line (newest by created, id).
- Orphan rows (no invoice_line): one per exact snapshot on an invoice, or per
  encounter-less snapshot (newest wins). Uses NOT EXISTS so PostgreSQL does not
  need MAX(uuid).

Run ``manage.py dedupe_insurance_claim_items --apply`` to soft-delete duplicates
in the database (including normalized-description orphan clusters).
"""
from django.apps import apps
from django.db.models import Exists, OuterRef, Q, Subquery


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

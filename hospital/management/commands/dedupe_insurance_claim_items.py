"""
Soft-delete duplicate InsuranceClaimItem rows:
- Per invoice_line (newest wins).
- Orphan rows on an invoice: same normalized snapshot (date, amount, description).
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count
from hospital.models_insurance import InsuranceClaimItem


def _norm_desc(s):
    if not s:
        return ''
    return str(s).strip().lower()[:500]


class Command(BaseCommand):
    help = 'Soft-delete duplicate insurance claim items (dry-run unless --apply).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Perform soft-delete (is_deleted=True). Without this, only report.',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        total = 0

        dup_line_ids = (
            InsuranceClaimItem.objects.filter(is_deleted=False, invoice_line_id__isnull=False)
            .values('invoice_line_id')
            .annotate(c=Count('id'))
            .filter(c__gt=1)
            .values_list('invoice_line_id', flat=True)
        )
        for lid in dup_line_ids:
            qs = InsuranceClaimItem.objects.filter(
                is_deleted=False,
                invoice_line_id=lid,
            ).order_by('-created', '-id')
            keep = qs.first()
            if not keep:
                continue
            dup_qs = qs.exclude(pk=keep.pk)
            cnt = dup_qs.count()
            self.stdout.write(
                f'invoice_line_id={lid}: soft-delete {cnt} duplicate(s), keep pk={keep.pk}'
            )
            total += cnt
            if apply:
                dup_qs.update(is_deleted=True)

        inv_ids = (
            InsuranceClaimItem.objects.filter(
                is_deleted=False,
                invoice_line_id__isnull=True,
                invoice_id__isnull=False,
            )
            .values('invoice_id')
            .annotate(c=Count('id'))
            .filter(c__gt=1)
            .values_list('invoice_id', flat=True)
        )
        for inv_id in inv_ids:
            orphans = list(
                InsuranceClaimItem.objects.filter(
                    is_deleted=False,
                    invoice_line_id__isnull=True,
                    invoice_id=inv_id,
                ).order_by('-created', '-id')
            )
            by_key = defaultdict(list)
            for c in orphans:
                key = (
                    c.patient_id,
                    c.payer_id,
                    c.service_date,
                    str(c.billed_amount or 0),
                    _norm_desc(c.service_description),
                    c.service_code_id,
                )
                by_key[key].append(c)
            for _key, lst in by_key.items():
                if len(lst) <= 1:
                    continue
                keep = lst[0]
                dup_qs = InsuranceClaimItem.objects.filter(pk__in=[x.pk for x in lst[1:]])
                cnt = dup_qs.count()
                self.stdout.write(
                    f'invoice_id={inv_id} orphan snapshot: soft-delete {cnt} duplicate(s), keep pk={keep.pk}'
                )
                total += cnt
                if apply:
                    dup_qs.update(is_deleted=True)

        solo_invoices = (
            InsuranceClaimItem.objects.filter(
                is_deleted=False,
                invoice_line_id__isnull=True,
                invoice_id__isnull=True,
            )
            .values(
                'patient_id',
                'payer_id',
                'encounter_id',
                'service_date',
                'billed_amount',
                'service_description',
                'service_code_id',
            )
            .annotate(c=Count('id'))
            .filter(c__gt=1)
        )
        for g in solo_invoices:
            nd = _norm_desc(g['service_description'])
            qs = (
                InsuranceClaimItem.objects.filter(
                    is_deleted=False,
                    invoice_line_id__isnull=True,
                    invoice_id__isnull=True,
                    patient_id=g['patient_id'],
                    payer_id=g['payer_id'],
                    encounter_id=g['encounter_id'],
                    service_date=g['service_date'],
                    billed_amount=g['billed_amount'],
                    service_description=g['service_description'],
                ).order_by('-created', '-id')
            )
            keep = qs.first()
            if not keep:
                continue
            dup_qs = qs.exclude(pk=keep.pk)
            cnt = dup_qs.count()
            snap = _norm_desc(g['service_description'])
            snap_short = (snap[:40] + '…') if len(snap) > 40 else snap
            self.stdout.write(
                f'No-invoice orphan snapshot ({snap_short}): soft-delete {cnt} duplicate(s), keep pk={keep.pk}'
            )
            total += cnt
            if apply:
                dup_qs.update(is_deleted=True)

        if apply:
            self.stdout.write(self.style.SUCCESS(f'Done. Soft-deleted {total} duplicate claim item row(s).'))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'Dry-run: would soft-delete {total} duplicate row(s). Re-run with --apply to execute.'
                )
            )

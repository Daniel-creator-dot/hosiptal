"""
Backfill COGS journal entries for pharmacy stock deductions missing GL posting.
Uses stored cogs_amount on log, or drug.cost_price × quantity as fallback estimate.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from hospital.models_payment_verification import PharmacyStockDeductionLog
from hospital.services.inventory_gl_service import post_inventory_cogs_gl


class Command(BaseCommand):
    help = 'Backfill pharmacy COGS GL entries for PharmacyStockDeductionLog rows'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be posted without creating journals',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='Max logs to process (default 500)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        qs = PharmacyStockDeductionLog.objects.filter(
            is_deleted=False,
            gl_journal_entry__isnull=True,
        ).select_related('drug').order_by('created')[:limit]

        posted = 0
        skipped = 0
        for log in qs:
            amount = log.cogs_amount
            if not amount or amount <= 0:
                drug = log.drug
                unit = Decimal(str(getattr(drug, 'cost_price', 0) or 0))
                amount = (unit * Decimal(log.quantity or 0)).quantize(Decimal('0.01'))
            if amount <= 0:
                skipped += 1
                continue
            ref = f'COGS-PHARM-{log.pk}'
            if dry_run:
                self.stdout.write(
                    f'Would post GHS {amount} for {log.source_type} {log.source_id} ({ref})'
                )
                posted += 1
                continue
            if not log.cogs_amount or log.cogs_amount <= 0:
                log.cogs_amount = amount
                log.save(update_fields=['cogs_amount', 'modified'])
            result = post_inventory_cogs_gl(
                category_key='pharmacy',
                amount=amount,
                reference=ref,
                description=(
                    f'Backfill pharmacy COGS — {getattr(log.drug, "name", "drug")} '
                    f'×{log.quantity} ({log.source_type})'
                ),
                deduction_log=log,
                entry_date=log.created.date() if log.created else timezone.now().date(),
            )
            if result.get('posted') or result.get('already_posted'):
                posted += 1
            else:
                skipped += 1

        mode = 'DRY RUN' if dry_run else 'LIVE'
        self.stdout.write(
            self.style.SUCCESS(f'{mode}: processed {posted} posted/would-post, {skipped} skipped')
        )

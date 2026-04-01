"""
Management command to fix duplicate Revenue and wrong Dr Cash/Cr Revenue
for deposit payments, and to deduplicate by transaction reference.

- Transactions with payment_received + payment_method='deposit' should NOT have
  Dr Cash / Cr Revenue (that was double posting). DepositApplication signal
  already posts Dr Patient Deposits / Cr Revenue. This command voids those
  incorrect JEs and marks the duplicate Revenue.
- Optionally deduplicates: for the same transaction reference, keeps one
  Revenue/JE set and voids the rest.

Usage:
  python manage.py fix_accounting_payment_duplicates
  python manage.py fix_accounting_payment_duplicates --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from decimal import Decimal
from collections import defaultdict


class Command(BaseCommand):
    help = (
        'Void duplicate Revenue and wrong Dr Cash/Cr Revenue for deposit payments; '
        'deduplicate by transaction reference.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--dedupe-only',
            action='store_true',
            help='Only deduplicate by reference; do not fix deposit-as-cash',
        )
        parser.add_argument(
            '--deposit-only',
            action='store_true',
            help='Only fix deposit payment entries; do not deduplicate by reference',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        dedupe_only = options['dedupe_only']
        deposit_only = options['deposit_only']

        from hospital.models_accounting import Transaction
        from hospital.models_accounting_advanced import (
            Revenue,
            AdvancedJournalEntry,
            AdvancedGeneralLedger,
        )

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('FIX ACCOUNTING PAYMENT DUPLICATES'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        if dry_run:
            self.stdout.write(self.style.WARNING('\n*** DRY RUN MODE ***\n'))

        stats = {'jes_voided': 0, 'revenue_marked': 0, 'dedupe_voided': 0}

        # ----- 1. Fix deposit payments (wrong Dr Cash / Cr Revenue) -----
        if not dedupe_only:
            self.stdout.write('\n1. Finding deposit payments with incorrect Cash/Revenue posting...')
            deposit_txns = Transaction.objects.filter(
                transaction_type='payment_received',
                payment_method='deposit',
                is_deleted=False,
            )
            refs = list(deposit_txns.values_list('transaction_number', flat=True))
            if not refs:
                self.stdout.write('   No deposit payment transactions found.')
            else:
                # Revenue created by payment signal used reference=transaction_number
                wrong_revenues = Revenue.objects.filter(
                    reference__in=refs,
                    journal_entry__isnull=False,
                ).select_related('journal_entry')
                count = wrong_revenues.count()
                self.stdout.write(f'   Found {count} Revenue entries linked to deposit payments (to correct).')
                for rev in wrong_revenues:
                    je = rev.journal_entry
                    if not je or je.status == 'void':
                        continue
                    self.stdout.write(
                        f'   Reference {rev.reference} amount {rev.amount} '
                        f'JE {je.entry_number} (status={je.status})'
                    )
                    if not dry_run:
                        with db_transaction.atomic():
                            je.void()
                            rev.amount = Decimal('0.00')
                            rev.description = (rev.description or '') + ' [VOIDED - duplicate deposit-as-cash posting]'
                            rev.journal_entry = None
                            rev.save(update_fields=['amount', 'description', 'journal_entry'])
                            stats['jes_voided'] += 1
                            stats['revenue_marked'] += 1
                    else:
                        self.stdout.write(self.style.WARNING(f'      Would void JE {je.entry_number} and zero Revenue {rev.revenue_number}'))
                        stats['jes_voided'] += 1
                        stats['revenue_marked'] += 1

        # ----- 2. Deduplicate by transaction reference (keep one, void rest) -----
        if not deposit_only:
            self.stdout.write('\n2. Finding duplicate Revenue/JE by same reference...')
            # Group Revenue by reference (e.g. transaction_number)
            by_ref = defaultdict(list)
            qs = Revenue.objects.filter(
                reference__isnull=False,
            ).exclude(reference='').select_related('journal_entry')
            for rev in qs:
                if rev.journal_entry_id and rev.journal_entry.status != 'void':
                    by_ref[rev.reference].append(rev)
            duplicates = {ref: revs for ref, revs in by_ref.items() if len(revs) > 1}
            self.stdout.write(f'   Found {len(duplicates)} reference groups with duplicate Revenue (keeping one per group).')
            for ref, revs in list(duplicates.items())[:50]:
                # Keep oldest (by revenue id or created)
                revs_sorted = sorted(revs, key=lambda r: (r.created, r.pk))
                keep = revs_sorted[0]
                to_void = revs_sorted[1:]
                self.stdout.write(f'   Reference {ref}: keeping Revenue {keep.revenue_number} (id={keep.pk}), voiding {len(to_void)} duplicate(s).')
                for rev in to_void:
                    je = rev.journal_entry
                    if not je or je.status == 'void':
                        continue
                    if not dry_run:
                        with db_transaction.atomic():
                            je.void()
                            rev.amount = Decimal('0.00')
                            rev.description = (rev.description or '') + ' [VOIDED - duplicate by reference]'
                            rev.journal_entry = None
                            rev.save(update_fields=['amount', 'description', 'journal_entry'])
                            stats['dedupe_voided'] += 1
                    else:
                        self.stdout.write(self.style.WARNING(f'      Would void JE {je.entry_number} and Revenue {rev.revenue_number}'))
                        stats['dedupe_voided'] += 1
            if len(duplicates) > 50:
                self.stdout.write(f'   ... and {len(duplicates) - 50} more groups (run without --dry-run to fix all).')

        # ----- Summary -----
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('SUMMARY')
        self.stdout.write('=' * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING('\nThis was a DRY RUN. Run without --dry-run to apply.'))
        self.stdout.write(f'  JEs voided (deposit fix): {stats["jes_voided"]}')
        self.stdout.write(f'  Revenue rows corrected (deposit): {stats["revenue_marked"]}')
        self.stdout.write(f'  Duplicate Revenue/JE voided (by reference): {stats["dedupe_voided"]}')
        if not dry_run and (stats['jes_voided'] or stats['revenue_marked'] or stats['dedupe_voided']):
            self.stdout.write(self.style.SUCCESS('\nTrial balance and revenue reports should now exclude these corrected entries.'))

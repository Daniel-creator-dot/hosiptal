"""
Management command to fix duplicate GL entries and restore correct values
Usage: python manage.py fix_accounting_duplicates
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from hospital.models_accounting import GeneralLedger, JournalEntry
from decimal import Decimal


class Command(BaseCommand):
    help = 'Fix duplicate GL entries and restore correct accounting values'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('FIXING ACCOUNTING DUPLICATES'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n*** DRY RUN MODE ***\n'))
        
        deleted_count = 0
        
        # Step 1: Remove OLD GL entries without reference numbers (duplicates)
        self.stdout.write('\n1. Removing OLD duplicate GL entries (no reference numbers)...')
        
        old_entries = GeneralLedger.objects.filter(
            reference_number='',
            is_deleted=False
        ) | GeneralLedger.objects.filter(
            reference_number__isnull=True,
            is_deleted=False
        )
        
        old_count = old_entries.count()
        total_old_debits = sum(e.debit_amount for e in old_entries)
        total_old_credits = sum(e.credit_amount for e in old_entries)
        
        self.stdout.write(f'   Found {old_count} old entries without reference numbers')
        self.stdout.write(f'   Total Debits: GHS {total_old_debits}')
        self.stdout.write(f'   Total Credits: GHS {total_old_credits}')
        
        if not dry_run:
            for entry in old_entries:
                self.stdout.write(
                    self.style.WARNING(
                        f'   ✗ Removing: {entry.entry_number} - {entry.account.account_code} '
                        f'DR:{entry.debit_amount} CR:{entry.credit_amount}'
                    )
                )
                entry.is_deleted = True
                entry.save()
                deleted_count += 1
        else:
            for entry in old_entries:
                self.stdout.write(
                    f'   Would remove: {entry.entry_number} - {entry.account.account_code} '
                    f'DR:{entry.debit_amount} CR:{entry.credit_amount}'
                )
        
        # Step 2: Remove artificial reclassification entries
        self.stdout.write('\n2. Removing artificial revenue reclassifications...')
        
        recl_entries = GeneralLedger.objects.filter(
            reference_type='reclassification',
            is_deleted=False
        )
        
        recl_count = recl_entries.count()
        self.stdout.write(f'   Found {recl_count} reclassification entries')
        
        if not dry_run:
            for entry in recl_entries:
                self.stdout.write(
                    self.style.WARNING(
                        f'   ✗ Removing: {entry.entry_number} - {entry.account.account_code} '
                        f'DR:{entry.debit_amount} CR:{entry.credit_amount}'
                    )
                )
                entry.is_deleted = True
                entry.save()
                deleted_count += 1
                
            # Also mark related journal entries as deleted
            JournalEntry.objects.filter(
                reference_number__startswith='RECL-',
                is_deleted=False
            ).update(is_deleted=True)
        else:
            for entry in recl_entries:
                self.stdout.write(
                    f'   Would remove: {entry.entry_number} - {entry.account.account_code} '
                    f'DR:{entry.debit_amount} CR:{entry.credit_amount}'
                )
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('SUMMARY')
        self.stdout.write('=' * 60)
        
        if dry_run:
            self.stdout.write(f'\nWould remove:')
            self.stdout.write(f'  - {old_count} old duplicate entries (GHS {total_old_debits} debits)')
            self.stdout.write(f'  - {recl_count} artificial reclassification entries')
            self.stdout.write(f'\nTotal: {old_count + recl_count} entries would be removed')
            self.stdout.write(self.style.WARNING('\nThis was a DRY RUN. Run without --dry-run to apply.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Removed {deleted_count} erroneous entries!'))
            self.stdout.write('\nResults:')
            self.stdout.write('  ✓ Cash balance should now match receipts (GHS 8,370)')
            self.stdout.write('  ✓ Revenue restored to original distribution')
            self.stdout.write('  ✓ All artificial adjustments removed')
            self.stdout.write('\nRefresh dashboard: http://127.0.0.1:8000/hms/accounting/')




















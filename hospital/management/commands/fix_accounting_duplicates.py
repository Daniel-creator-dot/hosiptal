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
        
        # Step 2: Find and remove duplicate entries with same reference number
        self.stdout.write('\n2. Checking for duplicate entries with same reference number...')
        
        from collections import defaultdict
        from django.db.models import Q
        
        # Group entries by reference number, account, and amount
        duplicate_groups = defaultdict(list)
        
        entries_with_ref = GeneralLedger.objects.filter(
            ~Q(reference_number=''),
            reference_number__isnull=False,
            is_deleted=False
        )
        
        for entry in entries_with_ref:
            # Create a key based on reference_number, account, and amount
            key = (entry.reference_number, entry.account_id, entry.debit_amount, entry.credit_amount)
            duplicate_groups[key].append(entry)
        
        # Find groups with more than one entry (duplicates)
        duplicates = {key: entries for key, entries in duplicate_groups.items() if len(entries) > 1}
        
        dup_count = sum(len(entries) - 1 for entries in duplicates.values())  # Keep one, remove rest
        self.stdout.write(f'   Found {len(duplicates)} groups with {dup_count} duplicate entries')
        
        if duplicates:
            for (ref_num, acc_id, debit, credit), entries in list(duplicates.items())[:20]:  # Show first 20
                account = entries[0].account
                self.stdout.write(
                    f'\n   Reference: {ref_num}, Account: {account.account_code} - {account.account_name}'
                )
                self.stdout.write(f'   Amount: DR {debit} / CR {credit}')
                self.stdout.write(f'   Found {len(entries)} entries (keeping oldest, removing {len(entries) - 1})')
                
                # Sort by created date, keep the oldest
                sorted_entries = sorted(entries, key=lambda e: e.created)
                keep_entry = sorted_entries[0]
                remove_entries = sorted_entries[1:]
                
                if not dry_run:
                    for entry in remove_entries:
                        self.stdout.write(
                            self.style.WARNING(
                                f'   ✗ Removing duplicate: {entry.entry_number} (created: {entry.created})'
                            )
                        )
                        entry.is_deleted = True
                        entry.save()
                        deleted_count += 1
                else:
                    for entry in remove_entries:
                        self.stdout.write(
                            f'   Would remove: {entry.entry_number} (created: {entry.created})'
                        )
                    self.stdout.write(
                        f'   Would keep: {keep_entry.entry_number} (created: {keep_entry.created})'
                    )
        
        # Step 3: Remove artificial reclassification entries
        self.stdout.write('\n3. Removing artificial revenue reclassifications...')
        
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
            self.stdout.write(f'  - {dup_count} duplicate entries with same reference')
            self.stdout.write(f'  - {recl_count} artificial reclassification entries')
            self.stdout.write(f'\nTotal: {old_count + dup_count + recl_count} entries would be removed')
            self.stdout.write(self.style.WARNING('\nThis was a DRY RUN. Run without --dry-run to apply.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Removed {deleted_count} erroneous entries!'))
            self.stdout.write('\nResults:')
            self.stdout.write('  ✓ Removed duplicate entries')
            self.stdout.write('  ✓ Revenue figures should now be correct')
            self.stdout.write('  ✓ All artificial adjustments removed')
            self.stdout.write('\nRefresh trial balance to see corrected figures!')


























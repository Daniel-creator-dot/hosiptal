"""
Management command to sync payment receipts to accounting (General Ledger)
Usage: python manage.py sync_receipts_to_accounting
"""

from django.core.management.base import BaseCommand
from hospital.models_accounting import PaymentReceipt, GeneralLedger, JournalEntry
from hospital.services.accounting_sync_service import AccountingSyncService


class Command(BaseCommand):
    help = 'Sync payment receipts to accounting system (retroactive fix)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually syncing',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sync even if already synced',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('SYNCING PAYMENT RECEIPTS TO ACCOUNTING'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # Get all payment receipts
        receipts = PaymentReceipt.objects.filter(is_deleted=False).order_by('receipt_date')
        total_receipts = receipts.count()
        
        self.stdout.write(f'\nFound {total_receipts} payment receipts')
        
        synced_count = 0
        skipped_count = 0
        error_count = 0
        
        for receipt in receipts:
            # Check if already synced (has GL entries with this receipt number)
            existing_gl = GeneralLedger.objects.filter(
                reference_number=receipt.receipt_number,
                is_deleted=False
            ).count()
            
            if existing_gl > 0 and not force:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ⊘ Skipped {receipt.receipt_number} - Already synced ({existing_gl} GL entries)')
                )
                continue
            
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Would sync {receipt.receipt_number} - GHS {receipt.amount_paid}')
                )
                synced_count += 1
                continue
            
            # Sync to accounting
            try:
                # Determine service type - default to general for now
                # You can enhance this logic later based on your invoice structure
                service_type = 'general'
                
                result = AccountingSyncService.sync_payment_to_accounting(
                    payment_receipt=receipt,
                    service_type=service_type
                )
                
                if result['success']:
                    synced_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Synced {receipt.receipt_number} - GHS {receipt.amount_paid} ({service_type})'
                        )
                    )
                else:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ✗ Error {receipt.receipt_number}: {result.get("error", "Unknown error")}'
                        )
                    )
            
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Exception {receipt.receipt_number}: {str(e)}')
                )
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        if dry_run:
            self.stdout.write(self.style.SUCCESS('DRY RUN SUMMARY'))
        else:
            self.stdout.write(self.style.SUCCESS('SYNC SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Total receipts: {total_receipts}')
        self.stdout.write(self.style.SUCCESS(f'Synced: {synced_count}'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'Skipped (already synced): {skipped_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {error_count}'))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('This was a DRY RUN. No changes were made.'))
            self.stdout.write('To actually sync, run without --dry-run flag')
        else:
            self.stdout.write(self.style.SUCCESS('✅ Sync complete!'))
            self.stdout.write('')
            self.stdout.write('Check the results:')
            self.stdout.write('  - Dashboard: http://127.0.0.1:8000/hms/accounting/')
            self.stdout.write('  - General Ledger: http://127.0.0.1:8000/hms/accounting/ledger/')
            self.stdout.write('  - Financial Statements: http://127.0.0.1:8000/hms/accounting/financial-statement/')


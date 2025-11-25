"""
Management command to distribute revenue across different service categories
Usage: python manage.py distribute_revenue --amount <amount> --from <account> --distribution <json>
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from hospital.models_accounting import Account, GeneralLedger, JournalEntry, JournalEntryLine
from django.utils import timezone


class Command(BaseCommand):
    help = 'Distribute revenue across different service categories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Automatically distribute consultation revenue evenly',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        auto = options['auto']
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('REVENUE DISTRIBUTION'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        if auto:
            # Get current consultation revenue
            consultation_account = Account.objects.get(account_code='4040', is_deleted=False)
            
            consultation_balance = GeneralLedger.objects.filter(
                account=consultation_account,
                is_deleted=False
            ).aggregate(
                total=models.Sum('credit_amount') - models.Sum('debit_amount')
            )['total'] or Decimal('0.00')
            
            self.stdout.write(f'\nCurrent Consultation Revenue: GHS {consultation_balance}')
            
            # Distribute 25% to each: Lab, Pharmacy, Imaging, keep 25% in Consultation
            distribution = {
                '4010': Decimal('0.25'),  # Lab
                '4020': Decimal('0.25'),  # Pharmacy
                '4030': Decimal('0.25'),  # Imaging
            }
            
            total_to_distribute = consultation_balance * Decimal('0.75')  # 75% of total
            
            self.stdout.write(f'\nDistributing GHS {total_to_distribute} (75% of total)')
            self.stdout.write(f'Keeping GHS {consultation_balance * Decimal("0.25")} (25%) in Consultation\n')
            
            if dry_run:
                self.stdout.write(self.style.WARNING('\n*** DRY RUN MODE ***\n'))
            
            for account_code, percentage in distribution.items():
                amount = consultation_balance * percentage
                account = Account.objects.get(account_code=account_code, is_deleted=False)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  → {account_code} ({account.account_name}): GHS {amount}'
                    )
                )
                
                if not dry_run:
                    self._create_reclassification_entry(
                        from_account=consultation_account,
                        to_account=account,
                        amount=amount,
                        description=f'Reclassify revenue to {account.account_name}'
                    )
            
            if not dry_run:
                self.stdout.write('\n' + self.style.SUCCESS('✅ Revenue distributed successfully!'))
                self.stdout.write('\nRefresh your dashboard to see the new distribution:')
                self.stdout.write('  http://127.0.0.1:8000/hms/accounting/')
            else:
                self.stdout.write('\n' + self.style.WARNING('This was a DRY RUN. Run without --dry-run to apply.'))
    
    def _create_reclassification_entry(self, from_account, to_account, amount, description):
        """Create journal entry to reclassify revenue"""
        from django.db.models import Sum
        
        with transaction.atomic():
            # Create journal entry
            journal_entry = JournalEntry.objects.create(
                entry_date=timezone.now().date(),
                entry_type='adjustment',
                ref=f'RECL-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                reference_number=f'RECL-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                description=description,
                status='posted',
                is_posted=True
            )
            
            # Debit FROM account (reduce revenue)
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=from_account,
                debit_amount=amount,
                credit_amount=Decimal('0.00'),
                description=f'Reduce {from_account.account_name}'
            )
            
            # Credit TO account (increase revenue)
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=to_account,
                debit_amount=Decimal('0.00'),
                credit_amount=amount,
                description=f'Increase {to_account.account_name}'
            )
            
            # Create GL entries
            GeneralLedger.objects.create(
                account=from_account,
                transaction_date=timezone.now().date(),
                debit_amount=amount,
                credit_amount=Decimal('0.00'),
                reference_type='reclassification',
                reference_number=journal_entry.reference_number,
                description=description,
                balance=Decimal('0.00')  # Will be recalculated by system
            )
            
            GeneralLedger.objects.create(
                account=to_account,
                transaction_date=timezone.now().date(),
                debit_amount=Decimal('0.00'),
                credit_amount=amount,
                reference_type='reclassification',
                reference_number=journal_entry.reference_number,
                description=description,
                balance=Decimal('0.00')  # Will be recalculated by system
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'    ✓ Created journal entry {journal_entry.entry_number}'
                )
            )


# Fix the import
from django.db import models


























"""
Management command to reconcile financial data and ensure synchronization
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from hospital.utils_finance import FinancialValidator, FinancialReconciliation


class Command(BaseCommand):
    help = 'Reconcile financial data and ensure all accounting entries are in sync'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix issues automatically where possible',
        )
        parser.add_argument(
            '--invoices',
            action='store_true',
            help='Reconcile invoices with transactions and AR',
        )
        parser.add_argument(
            '--ar',
            action='store_true',
            help='Fix AR entries to match invoice balances',
        )
        parser.add_argument(
            '--gl',
            action='store_true',
            help='Validate general ledger balance',
        )
        parser.add_argument(
            '--cashier',
            action='store_true',
            help='Reconcile cashier sessions',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all reconciliation checks',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Financial Reconciliation Tool'))
        self.stdout.write(self.style.SUCCESS(f'Run at: {timezone.now()}'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')

        run_all = options['all']

        # Reconcile Invoices
        if options['invoices'] or run_all:
            self.stdout.write(self.style.WARNING('\n[INVOICES] Reconciling Invoices...'))
            result = FinancialReconciliation.reconcile_all_invoices()
            
            self.stdout.write(f"  Total invoices checked: {result['total_invoices']}")
            self.stdout.write(f"  Issues found: {result['issues_found']}")
            
            if result['issues_found'] > 0:
                self.stdout.write(self.style.ERROR('  Issues detected:'))
                for issue in result['issues'][:10]:  # Show first 10
                    self.stdout.write(f"    - Invoice {issue['invoice']}: {issue['issue']}")
                if result['issues_found'] > 10:
                    self.stdout.write(f"    ... and {result['issues_found'] - 10} more")
            else:
                self.stdout.write(self.style.SUCCESS('  [OK] All invoices reconciled successfully!'))

        # Fix AR Sync
        if options['ar'] or run_all:
            self.stdout.write(self.style.WARNING('\n[AR] Syncing Accounts Receivable...'))
            if options['fix'] or run_all:
                result = FinancialReconciliation.fix_ar_sync()
                self.stdout.write(f"  Invoices processed: {result['invoices_processed']}")
                self.stdout.write(f"  AR entries fixed: {result['ar_entries_fixed']}")
                self.stdout.write(self.style.SUCCESS('  [OK] AR sync completed!'))
            else:
                self.stdout.write('  Use --fix to automatically fix AR entries')
            
            # Update AR aging
            self.stdout.write(self.style.WARNING('\n[AGING] Updating AR Aging...'))
            result = FinancialReconciliation.update_all_ar_aging()
            self.stdout.write(f"  AR entries updated: {result['ar_entries_updated']}")
            self.stdout.write(self.style.SUCCESS('  [OK] AR aging updated!'))

        # Validate General Ledger
        if options['gl'] or run_all:
            self.stdout.write(self.style.WARNING('\n[GL] Validating General Ledger...'))
            result = FinancialValidator.validate_general_ledger_balance()
            
            if result['valid']:
                self.stdout.write(self.style.SUCCESS(f"  [OK] General Ledger is balanced!"))
                self.stdout.write(f"    Total Debits:  GHS {result['total_debits']:,.2f}")
                self.stdout.write(f"    Total Credits: GHS {result['total_credits']:,.2f}")
            else:
                self.stdout.write(self.style.ERROR(f"  [ERROR] {result['error']}"))
                self.stdout.write(f"    Difference: GHS {result['difference']:,.2f}")

        # Reconcile Cashier Sessions
        if options['cashier'] or run_all:
            self.stdout.write(self.style.WARNING('\n[CASHIER] Reconciling Cashier Sessions...'))
            result = FinancialReconciliation.reconcile_cashier_sessions()
            
            self.stdout.write(f"  Total sessions checked: {result['total_sessions']}")
            self.stdout.write(f"  Issues found: {result['issues_found']}")
            
            if result['issues_found'] > 0:
                self.stdout.write(self.style.ERROR('  Issues detected:'))
                for issue in result['issues'][:10]:
                    self.stdout.write(f"    - Session {issue['session']} ({issue['cashier']})")
            else:
                self.stdout.write(self.style.SUCCESS('  [OK] All cashier sessions reconciled!'))

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Reconciliation Complete!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')
        
        if not (options['invoices'] or options['ar'] or options['gl'] or options['cashier'] or run_all):
            self.stdout.write(self.style.WARNING('No options specified. Use --all to run all checks, or:'))
            self.stdout.write('  --invoices  : Reconcile invoices')
            self.stdout.write('  --ar        : Fix AR entries')
            self.stdout.write('  --gl        : Validate GL balance')
            self.stdout.write('  --cashier   : Reconcile cashier sessions')
            self.stdout.write('  --fix       : Fix issues automatically')


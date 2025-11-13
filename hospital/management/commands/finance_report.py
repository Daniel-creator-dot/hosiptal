"""
Management command to generate financial reports
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from hospital.utils_finance import FinancialReports


class Command(BaseCommand):
    help = 'Generate financial reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--revenue',
            action='store_true',
            help='Generate revenue summary',
        )
        parser.add_argument(
            '--ar-aging',
            action='store_true',
            help='Generate AR aging report',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for reports (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for reports (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Generate all reports',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Financial Reports'))
        self.stdout.write(self.style.SUCCESS(f'Generated at: {timezone.now()}'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')

        # Parse dates
        start_date = None
        end_date = None
        
        if options['start_date']:
            try:
                start_date = date.fromisoformat(options['start_date'])
            except ValueError:
                self.stdout.write(self.style.ERROR(f'Invalid start date: {options["start_date"]}'))
                return
        
        if options['end_date']:
            try:
                end_date = date.fromisoformat(options['end_date'])
            except ValueError:
                self.stdout.write(self.style.ERROR(f'Invalid end date: {options["end_date"]}'))
                return
        
        # Default to current month
        if not start_date:
            start_date = date.today().replace(day=1)
        if not end_date:
            end_date = date.today()

        run_all = options['all']

        # Revenue Summary
        if options['revenue'] or run_all:
            self.stdout.write(self.style.WARNING('\n[REVENUE] Revenue Summary'))
            self.stdout.write(f'Period: {start_date} to {end_date}')
            self.stdout.write('-' * 70)
            
            result = FinancialReports.revenue_summary(start_date, end_date)
            
            self.stdout.write('\nRevenue by Account:')
            for account_name, amount in result['revenue_by_account'].items():
                if amount > 0:
                    self.stdout.write(f'  {account_name:<40} GHS {amount:>15,.2f}')
            
            self.stdout.write('-' * 70)
            self.stdout.write(self.style.SUCCESS(f'{"Total Revenue":<40} GHS {result["total_revenue"]:>15,.2f}'))

        # AR Aging Report
        if options['ar_aging'] or run_all:
            self.stdout.write(self.style.WARNING('\n\n[AR AGING] Accounts Receivable Aging Report'))
            self.stdout.write(f'As of: {date.today()}')
            self.stdout.write('-' * 70)
            
            result = FinancialReports.ar_aging_summary()
            
            self.stdout.write('\nAging Summary:')
            self.stdout.write(f'  {"Current (0-30 days)":<40} GHS {result["summary"]["current"]:>15,.2f}')
            self.stdout.write(f'  {"31-60 days":<40} GHS {result["summary"]["31-60"]:>15,.2f}')
            self.stdout.write(f'  {"61-90 days":<40} GHS {result["summary"]["61-90"]:>15,.2f}')
            self.stdout.write(f'  {"Over 90 days":<40} GHS {result["summary"]["90+"]:>15,.2f}')
            
            self.stdout.write('-' * 70)
            self.stdout.write(self.style.SUCCESS(f'{"Total Outstanding":<40} GHS {result["total_outstanding"]:>15,.2f}'))
            self.stdout.write(f'\nTotal Invoices Outstanding: {result["total_invoices"]}')
            
            # Calculate percentage by aging bucket
            if result["total_outstanding"] > 0:
                self.stdout.write('\nPercentage by Aging Bucket:')
                for bucket, amount in result["summary"].items():
                    percentage = (amount / result["total_outstanding"]) * 100
                    self.stdout.write(f'  {bucket:<40} {percentage:>14.1f}%')

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Report Generation Complete!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')
        
        if not (options['revenue'] or options['ar_aging'] or run_all):
            self.stdout.write(self.style.WARNING('No options specified. Use --all to generate all reports, or:'))
            self.stdout.write('  --revenue   : Revenue summary')
            self.stdout.write('  --ar-aging  : AR aging report')
            self.stdout.write('  --start-date YYYY-MM-DD : Start date')
            self.stdout.write('  --end-date YYYY-MM-DD   : End date')


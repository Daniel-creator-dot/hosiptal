"""
Management command to generate monthly statements for corporate accounts
Run this on the 1st of each month
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from hospital.services.monthly_billing_service import monthly_billing_service


class Command(BaseCommand):
    help = 'Generate monthly statements for all corporate accounts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=str,
            help='Billing month in YYYY-MM format (default: last month)',
        )
        parser.add_argument(
            '--send',
            action='store_true',
            help='Send statements via email after generation',
        )

    def handle(self, *args, **kwargs):
        billing_month_str = kwargs.get('month')
        send_statements = kwargs.get('send', False)
        
        self.stdout.write(self.style.SUCCESS('\n📄 Monthly Statement Generation\n'))
        
        # Determine billing month
        if billing_month_str:
            try:
                from datetime import datetime
                billing_month = datetime.strptime(billing_month_str, '%Y-%m').date()
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(
                        '❌ Invalid month format. Use YYYY-MM (e.g., 2025-11)'
                    )
                )
                return
        else:
            # Default to last month
            today = timezone.now().date()
            last_month_end = today.replace(day=1) - timedelta(days=1)
            billing_month = last_month_end
        
        period_start = billing_month.replace(day=1)
        period_end = billing_month
        
        self.stdout.write(
            f'📅 Billing Period: {period_start} to {period_end}\n'
        )
        
        # Generate statements
        try:
            results = monthly_billing_service.generate_all_monthly_statements(billing_month)
            
            self.stdout.write(self.style.SUCCESS('\n📊 Generation Results:\n'))
            self.stdout.write(f'   Total Accounts: {results["total_accounts"]}')
            self.stdout.write(
                self.style.SUCCESS(f'   ✅ Successful: {results["successful"]}')
            )
            
            if results['skipped'] > 0:
                self.stdout.write(
                    self.style.WARNING(f'   ⚠️ Skipped: {results["skipped"]} (no charges)')
                )
            
            if results['failed'] > 0:
                self.stdout.write(
                    self.style.ERROR(f'   ❌ Failed: {results["failed"]}')
                )
                self.stdout.write('\nErrors:')
                for error in results['errors']:
                    self.stdout.write(self.style.ERROR(f'   - {error}'))
            
            # Display generated statements
            if results['statements']:
                self.stdout.write(self.style.SUCCESS('\n📄 Statements Generated:\n'))
                for stmt in results['statements']:
                    self.stdout.write(
                        f'   {stmt.statement_number} - '
                        f'{stmt.corporate_account.company_name} - '
                        f'GHS {stmt.closing_balance:,.2f}'
                    )
            
            # Send statements if requested
            if send_statements and results['statements']:
                self.stdout.write(self.style.SUCCESS('\n📧 Sending Statements...\n'))
                send_results = monthly_billing_service.send_statements(
                    results['statements'],
                    via='email'
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   ✅ Sent: {send_results["sent"]}/{send_results["total"]}'
                    )
                )
                if send_results['failed'] > 0:
                    self.stdout.write(
                        self.style.ERROR(f'   ❌ Failed: {send_results["failed"]}')
                    )
            
            self.stdout.write(self.style.SUCCESS('\n✅ Monthly billing complete!\n'))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Error: {str(e)}\n')
            )
            raise

























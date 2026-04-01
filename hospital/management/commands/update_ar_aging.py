"""
Management command to calculate and update AR aging snapshot
Run this daily to track accounts receivable aging
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from hospital.models_enterprise_billing import ARAgingSnapshot, MonthlyStatement, CorporateAccount
from hospital.models import Invoice
from datetime import timedelta


class Command(BaseCommand):
    help = 'Calculate and update AR aging snapshot'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\n📊 AR Aging Analysis\n'))
        
        today = timezone.now().date()
        
        # Check if snapshot already exists for today
        existing = ARAgingSnapshot.objects.filter(snapshot_date=today).first()
        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️ AR snapshot already exists for {today}. Deleting and recreating...'
                )
            )
            existing.delete()
        
        # Initialize buckets
        current_0_30 = Decimal('0.00')
        days_31_60 = Decimal('0.00')
        days_61_90 = Decimal('0.00')
        days_91_120 = Decimal('0.00')
        days_over_120 = Decimal('0.00')
        
        cash_outstanding = Decimal('0.00')
        corporate_outstanding = Decimal('0.00')
        insurance_outstanding = Decimal('0.00')
        
        total_accounts = 0
        overdue_accounts = 0
        
        # Calculate from outstanding invoices
        invoices = Invoice.objects.filter(
            balance__gt=0,
            status__in=['issued', 'partially_paid', 'overdue'],
            is_deleted=False
        ).select_related('payer')
        
        self.stdout.write(f'📝 Analyzing {invoices.count()} outstanding invoices...\n')
        
        for invoice in invoices:
            age_days = (today - invoice.issued_at.date()).days
            balance = invoice.balance
            
            # Age buckets
            if age_days <= 30:
                current_0_30 += balance
            elif age_days <= 60:
                days_31_60 += balance
                overdue_accounts += 1
            elif age_days <= 90:
                days_61_90 += balance
                overdue_accounts += 1
            elif age_days <= 120:
                days_91_120 += balance
                overdue_accounts += 1
            else:
                days_over_120 += balance
                overdue_accounts += 1
            
            # Payer type
            if invoice.payer:
                if invoice.payer.payer_type == 'corporate':
                    corporate_outstanding += balance
                elif invoice.payer.payer_type in ('insurance', 'private', 'nhis'):
                    insurance_outstanding += balance
                else:
                    cash_outstanding += balance
            else:
                cash_outstanding += balance
            
            total_accounts += 1
        
        # Add corporate account balances
        corporate_accounts = CorporateAccount.objects.filter(
            current_balance__gt=0,
            is_deleted=False
        )
        
        for account in corporate_accounts:
            corporate_outstanding += account.current_balance
        
        # Calculate total
        total_outstanding = (
            current_0_30 + days_31_60 + days_61_90 + 
            days_91_120 + days_over_120
        )
        
        # Create snapshot
        snapshot = ARAgingSnapshot.objects.create(
            snapshot_date=today,
            current_0_30=current_0_30,
            days_31_60=days_31_60,
            days_61_90=days_61_90,
            days_91_120=days_91_120,
            days_over_120=days_over_120,
            total_outstanding=total_outstanding,
            cash_outstanding=cash_outstanding,
            corporate_outstanding=corporate_outstanding,
            insurance_outstanding=insurance_outstanding,
            total_accounts=total_accounts,
            overdue_accounts=overdue_accounts
        )
        
        # Display results
        self.stdout.write(self.style.SUCCESS('\n✅ AR Aging Snapshot Created\n'))
        self.stdout.write(f'Date: {today}\n')
        self.stdout.write(f'\n📊 Age Analysis:')
        self.stdout.write(f'   Current (0-30 days):  GHS {current_0_30:>12,.2f} ({self._percentage(current_0_30, total_outstanding):>5.1f}%)')
        self.stdout.write(f'   31-60 days:           GHS {days_31_60:>12,.2f} ({self._percentage(days_31_60, total_outstanding):>5.1f}%)')
        self.stdout.write(f'   61-90 days:           GHS {days_61_90:>12,.2f} ({self._percentage(days_61_90, total_outstanding):>5.1f}%)')
        self.stdout.write(f'   91-120 days:          GHS {days_91_120:>12,.2f} ({self._percentage(days_91_120, total_outstanding):>5.1f}%)')
        self.stdout.write(f'   Over 120 days:        GHS {days_over_120:>12,.2f} ({self._percentage(days_over_120, total_outstanding):>5.1f}%)')
        self.stdout.write(f'   {"─" * 60}')
        self.stdout.write(f'   TOTAL OUTSTANDING:    GHS {total_outstanding:>12,.2f}\n')
        
        self.stdout.write(f'\n💼 By Payer Type:')
        self.stdout.write(f'   Cash:      GHS {cash_outstanding:>12,.2f} ({self._percentage(cash_outstanding, total_outstanding):>5.1f}%)')
        self.stdout.write(f'   Corporate: GHS {corporate_outstanding:>12,.2f} ({self._percentage(corporate_outstanding, total_outstanding):>5.1f}%)')
        self.stdout.write(f'   Insurance: GHS {insurance_outstanding:>12,.2f} ({self._percentage(insurance_outstanding, total_outstanding):>5.1f}%)\n')
        
        self.stdout.write(f'\n📈 Summary:')
        self.stdout.write(f'   Total Accounts: {total_accounts}')
        self.stdout.write(f'   Overdue Accounts: {overdue_accounts}')
        self.stdout.write(f'   Overdue Percentage: {snapshot.overdue_percentage:.1f}%\n')
        
        # Recommendations
        if snapshot.overdue_percentage > 30:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️ WARNING: High overdue percentage! Consider:'
                )
            )
            self.stdout.write('   - Send payment reminders')
            self.stdout.write('   - Review credit policies')
            self.stdout.write('   - Initiate collection procedures\n')
        
        self.stdout.write(self.style.SUCCESS('✅ AR aging update complete!\n'))
    
    def _percentage(self, amount, total):
        """Calculate percentage"""
        if total > 0:
            return (amount / total) * 100
        return 0

























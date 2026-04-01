"""
Sync All Existing Data to Accounting
One-time sync of all existing invoices, payments, etc. to accounting system
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Invoice, Patient
from hospital.models_accounting import Transaction, Account
from hospital.models_accounting_advanced import (
    Revenue, RevenueCategory, AdvancedAccountsReceivable,
    AdvancedJournalEntry, AdvancedJournalEntryLine, Journal
)
from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone


def sync_all_invoices():
    """Sync all invoices to AR"""
    print("="*70)
    print("SYNCING INVOICES TO ACCOUNTS RECEIVABLE")
    print("="*70)
    print()
    
    invoices = Invoice.objects.filter(
        is_deleted=False,
        status__in=['issued', 'partially_paid', 'overdue']
    )
    
    count = 0
    total_amount = Decimal('0.00')
    
    for invoice in invoices:
        try:
            ar, created = AdvancedAccountsReceivable.objects.get_or_create(
                invoice=invoice,
                defaults={
                    'patient': invoice.patient,
                    'invoice_amount': invoice.total_amount,
                    'amount_paid': invoice.total_amount - invoice.balance,
                    'balance_due': invoice.balance,
                    'due_date': invoice.due_at.date() if invoice.due_at else (timezone.now().date() + timezone.timedelta(days=30)),
                }
            )
            
            if created:
                count += 1
                total_amount += invoice.balance
                print(f"  [OK] {invoice.invoice_number}: ${invoice.balance}")
        
        except Exception as e:
            print(f"  [ERROR] {invoice.invoice_number}: {e}")
    
    print()
    print(f"SYNCED: {count} invoices")
    print(f"TOTAL AR: ${total_amount}")
    print()


def sync_all_payments():
    """Sync all payments to revenue"""
    print("="*70)
    print("SYNCING PAYMENTS TO REVENUE")
    print("="*70)
    print()
    
    # Get accounts
    try:
        cash_account = Account.objects.get(account_code='1000')
        revenue_account = Account.objects.get(account_code='4000')
    except Account.DoesNotExist:
        print("[ERROR] Default accounts not found. Run setup_accounting_simple.py first")
        return
    
    # Get category
    revenue_category, _ = RevenueCategory.objects.get_or_create(
        code='REV-PATIENT',
        defaults={'name': 'Patient Services', 'account': revenue_account}
    )
    
    # Get all payment transactions
    payments = Transaction.objects.filter(
        transaction_type='payment_received'
    ).select_related('patient', 'invoice', 'processed_by')
    
    count = 0
    total_amount = Decimal('0.00')
    
    # Check which are already synced
    existing_refs = set(Revenue.objects.values_list('reference', flat=True))
    
    for payment in payments:
        # Skip if already synced
        if payment.transaction_number in existing_refs:
            continue
        
        try:
            with db_transaction.atomic():
                # Create revenue
                revenue = Revenue.objects.create(
                    revenue_date=payment.transaction_date.date() if hasattr(payment.transaction_date, 'date') else payment.transaction_date,
                    category=revenue_category,
                    description=f"Payment from {payment.patient.full_name if payment.patient else 'Patient'}",
                    amount=payment.amount,
                    patient=payment.patient,
                    invoice=payment.invoice,
                    payment_method=payment.payment_method,
                    reference=payment.transaction_number,
                    recorded_by=payment.processed_by,
                )
                
                count += 1
                total_amount += payment.amount
                print(f"  [OK] {payment.transaction_number}: ${payment.amount}")
        
        except Exception as e:
            print(f"  [ERROR] {payment.transaction_number}: {e}")
    
    print()
    print(f"SYNCED: {count} payments")
    print(f"TOTAL REVENUE: ${total_amount}")
    print()


def create_summary():
    """Show summary of what's synced"""
    print("="*70)
    print("SYNC SUMMARY")
    print("="*70)
    print()
    
    # Count everything
    try:
        print("INVOICES & AR:")
        total_invoices = Invoice.objects.filter(is_deleted=False).count()
        total_ar = AdvancedAccountsReceivable.objects.count()
        print(f"  Total Invoices: {total_invoices}")
        print(f"  AR Entries: {total_ar}")
        print(f"  Sync Rate: {round((total_ar/max(total_invoices,1))*100, 1)}%")
        
        print()
        print("PAYMENTS & REVENUE:")
        total_payments = Transaction.objects.filter(transaction_type='payment_received').count()
        total_revenue = Revenue.objects.count()
        print(f"  Total Payments: {total_payments}")
        print(f"  Revenue Entries: {total_revenue}")
        print(f"  Sync Rate: {round((total_revenue/max(total_payments,1))*100, 1)}%")
        
        print()
        print("JOURNAL ENTRIES:")
        total_je = AdvancedJournalEntry.objects.count()
        posted_je = AdvancedJournalEntry.objects.filter(status='posted').count()
        print(f"  Total JE: {total_je}")
        print(f"  Posted: {posted_je}")
        
        print()
        print("ACCOUNTS:")
        print(f"  Chart of Accounts: {Account.objects.count()}")
        print(f"  Revenue Categories: {RevenueCategory.objects.count()}")
        
        # Financial summary
        from django.db.models import Sum
        print()
        print("FINANCIAL SUMMARY:")
        total_rev = Revenue.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_ar_balance = AdvancedAccountsReceivable.objects.aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
        print(f"  Total Revenue Recorded: ${total_rev}")
        print(f"  Total AR Outstanding: ${total_ar_balance}")
    
    except Exception as e:
        print(f"Error generating summary: {e}")
    
    print()
    print("="*70)


def main():
    print()
    print("="*70)
    print("SYNC ALL DATA TO ACCOUNTING SYSTEM")
    print("="*70)
    print()
    print("This will sync:")
    print("  - All invoices to Accounts Receivable")
    print("  - All payments to Revenue entries")
    print("  - Create audit trail")
    print()
    
    confirm = input("Continue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Cancelled.")
        return
    
    print()
    
    # Sync invoices
    sync_all_invoices()
    
    # Sync payments
    sync_all_payments()
    
    # Show summary
    create_summary()
    
    print("="*70)
    print("SYNC COMPLETE!")
    print("="*70)
    print()
    print("Next steps:")
    print("1. Restart server to activate signals")
    print("2. Visit: http://127.0.0.1:8000/hms/accounting/")
    print("3. See real financial data!")
    print()
    print("From now on, all new payments will AUTO-SYNC to accounting!")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


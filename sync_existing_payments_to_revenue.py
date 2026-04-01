"""
Sync All Existing Payments to Revenue
Retroactively sync all historical payments to accounting system
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Transaction, Account
from hospital.models_accounting_advanced import (
    Revenue, RevenueCategory, AdvancedAccountsReceivable,
    AdvancedJournalEntry, AdvancedJournalEntryLine, Journal,
    ReceiptVoucher
)
from decimal import Decimal
from django.db import transaction as db_transaction
from django.db.models import Sum


def sync_all_payments():
    print("="*70)
    print("SYNCING ALL EXISTING PAYMENTS TO ACCOUNTING")
    print("="*70)
    print()
    
    # Get all payment transactions
    all_payments = Transaction.objects.filter(
        transaction_type='payment_received'
    ).select_related('patient', 'invoice', 'processed_by').order_by('transaction_date')
    
    total_payments = all_payments.count()
    total_amount = all_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    print(f"Found {total_payments} payments totaling ${total_amount}")
    print()
    
    # Get existing revenue entries to avoid duplicates
    existing_refs = set(Revenue.objects.values_list('reference', flat=True))
    print(f"Already synced: {len(existing_refs)} payments")
    print()
    
    # Filter payments that haven't been synced
    payments_to_sync = [p for p in all_payments if p.transaction_number not in existing_refs]
    
    print(f"Need to sync: {len(payments_to_sync)} payments")
    print()
    
    if len(payments_to_sync) == 0:
        print("[INFO] All payments already synced!")
        print()
        print_summary()
        return
    
    # Get required accounts
    try:
        cash_account = Account.objects.get(account_code='1000')
        revenue_account = Account.objects.get(account_code='4000')
    except Account.DoesNotExist as e:
        print(f"[ERROR] Required accounts not found: {e}")
        print("Run: python setup_accounting_system.py")
        return
    
    # Get revenue category
    revenue_category, _ = RevenueCategory.objects.get_or_create(
        code='REV-PATIENT',
        defaults={'name': 'Patient Services', 'account': revenue_account}
    )
    
    # Get journal
    journal = Journal.objects.filter(journal_type='receipt').first()
    if not journal:
        print("[INFO] Creating Receipt Journal...")
        journal = Journal.objects.create(
            code='RJ',
            name='Receipt Journal',
            journal_type='receipt',
        )
    
    # Sync each payment
    synced_count = 0
    synced_amount = Decimal('0.00')
    errors = []
    
    for i, payment in enumerate(payments_to_sync, 1):
        try:
            with db_transaction.atomic():
                # Create revenue
                revenue = Revenue.objects.create(
                    revenue_date=payment.transaction_date.date() if hasattr(payment.transaction_date, 'date') else payment.transaction_date,
                    category=revenue_category,
                    description=f"Payment from {payment.patient.full_name if payment.patient else 'Patient'} - {payment.transaction_number}",
                    amount=payment.amount,
                    patient=payment.patient,
                    invoice=payment.invoice,
                    payment_method=payment.payment_method,
                    reference=payment.transaction_number,
                    recorded_by=payment.processed_by,
                )
                
                # Create receipt voucher
                receipt = ReceiptVoucher.objects.create(
                    receipt_date=revenue.revenue_date,
                    received_from=payment.patient.full_name if payment.patient else 'Patient',
                    patient=payment.patient,
                    amount=payment.amount,
                    payment_method=payment.payment_method,
                    description=revenue.description,
                    reference=payment.transaction_number,
                    status='issued',
                    revenue_account=revenue_account,
                    cash_account=cash_account,
                    invoice=payment.invoice,
                    received_by=payment.processed_by,
                )
                
                # Create journal entry
                je = AdvancedJournalEntry.objects.create(
                    journal=journal,
                    entry_date=revenue.revenue_date,
                    description=revenue.description,
                    reference=payment.transaction_number,
                    status='draft',
                    total_debit=payment.amount,
                    total_credit=payment.amount,
                    created_by=payment.processed_by,
                    invoice=payment.invoice,
                )
                
                # Dr: Cash
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=1,
                    account=cash_account,
                    description="Cash received",
                    debit_amount=payment.amount,
                    credit_amount=Decimal('0.00'),
                    patient=payment.patient,
                )
                
                # Cr: Revenue
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=2,
                    account=revenue_account,
                    description="Patient services revenue",
                    debit_amount=Decimal('0.00'),
                    credit_amount=payment.amount,
                    patient=payment.patient,
                )
                
                # Post to GL
                je.post(payment.processed_by)
                
                # Link to revenue
                revenue.journal_entry = je
                revenue.receipt_voucher = receipt
                revenue.save()
                
                receipt.journal_entry = je
                receipt.save()
                
                # Update AR if linked to invoice
                if payment.invoice:
                    try:
                        ar = AdvancedAccountsReceivable.objects.get(invoice=payment.invoice)
                        ar.amount_paid += payment.amount
                        ar.save()
                    except AdvancedAccountsReceivable.DoesNotExist:
                        # Create AR if it doesn't exist
                        AdvancedAccountsReceivable.objects.create(
                            invoice=payment.invoice,
                            patient=payment.patient,
                            invoice_amount=payment.invoice.total_amount,
                            amount_paid=payment.amount,
                            balance_due=payment.invoice.balance,
                            due_date=payment.invoice.due_at.date() if payment.invoice.due_at else payment.invoice.created.date(),
                        )
                
                synced_count += 1
                synced_amount += payment.amount
                
                # Progress indicator
                if i % 10 == 0 or i == len(payments_to_sync):
                    print(f"  Progress: {i}/{len(payments_to_sync)} payments synced...")
        
        except Exception as e:
            errors.append((payment.transaction_number, str(e)))
            print(f"  [ERROR] {payment.transaction_number}: {e}")
    
    print()
    print("="*70)
    print("SYNC COMPLETE!")
    print("="*70)
    print()
    print(f"Successfully synced: {synced_count} payments")
    print(f"Total amount: ${synced_amount}")
    print(f"Errors: {len(errors)}")
    print()
    
    if errors:
        print("ERRORS:")
        for ref, error in errors[:10]:  # Show first 10 errors
            print(f"  {ref}: {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more errors")
        print()
    
    print_summary()


def print_summary():
    """Print current accounting summary"""
    from django.db.models import Sum
    
    print("="*70)
    print("CURRENT ACCOUNTING DATA")
    print("="*70)
    print()
    
    # Transactions
    total_txns = Transaction.objects.filter(transaction_type='payment_received').count()
    total_txn_amount = Transaction.objects.filter(transaction_type='payment_received').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    print(f"PAYMENT TRANSACTIONS: {total_txns} (${total_txn_amount})")
    
    # Revenue
    total_revenue = Revenue.objects.count()
    total_revenue_amount = Revenue.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    print(f"REVENUE ENTRIES: {total_revenue} (${total_revenue_amount})")
    
    # Journal Entries
    total_je = AdvancedJournalEntry.objects.count()
    posted_je = AdvancedJournalEntry.objects.filter(status='posted').count()
    print(f"JOURNAL ENTRIES: {total_je} (Posted: {posted_je})")
    
    # Receipt Vouchers
    total_receipts = ReceiptVoucher.objects.count()
    print(f"RECEIPT VOUCHERS: {total_receipts}")
    
    # AR
    total_ar = AdvancedAccountsReceivable.objects.count()
    total_ar_balance = AdvancedAccountsReceivable.objects.aggregate(total=Sum('balance_due'))['total'] or Decimal('0.00')
    print(f"ACCOUNTS RECEIVABLE: {total_ar} invoices (Balance: ${total_ar_balance})")
    
    print()
    
    # Sync rate
    sync_rate = round((total_revenue / max(total_txns, 1)) * 100, 1) if total_txns > 0 else 0
    print(f"SYNC RATE: {sync_rate}%")
    
    if sync_rate >= 100:
        print()
        print("[SUCCESS] ALL PAYMENTS SYNCED TO ACCOUNTING!")
        print()
        print("View your data:")
        print("  - http://127.0.0.1:8000/hms/accounting/")
        print("  - http://127.0.0.1:8000/admin/ (Revenues, Journal Entries)")
    elif sync_rate > 0:
        print()
        print("[INFO] Partial sync complete. From now on, new payments auto-sync!")
    else:
        print()
        print("[INFO] No payments synced yet. Run this script to sync.")
    
    print()
    print("="*70)


def main():
    print()
    print("This will sync ALL existing payments to the accounting system.")
    print()
    
    try:
        sync_all_payments()
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("="*70)
    print("DONE!")
    print("="*70)
    print()
    print("Next: Visit http://127.0.0.1:8000/hms/accounting/")
    print("See all your revenue data!")
    print()


if __name__ == '__main__':
    main()





















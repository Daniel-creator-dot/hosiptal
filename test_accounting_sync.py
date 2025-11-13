"""
Test Accounting Sync
Create a test payment and verify it syncs to accounting
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient, Invoice
from hospital.models_accounting import Transaction, Account
from hospital.models_accounting_advanced import Revenue, AdvancedAccountsReceivable, AdvancedJournalEntry
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone


def test_payment_sync():
    print("="*70)
    print("TESTING PAYMENT TO ACCOUNTING SYNC")
    print("="*70)
    print()
    
    # Get or create test patient
    patient = Patient.objects.filter(is_deleted=False).first()
    if not patient:
        print("[ERROR] No patients found")
        return
    
    print(f"Using patient: {patient.full_name}")
    
    # Get or create test invoice
    invoice = Invoice.objects.filter(patient=patient, is_deleted=False).first()
    if not invoice:
        print("[INFO] Creating test invoice...")
        invoice = Invoice.objects.create(
            patient=patient,
            total_amount=Decimal('100.00'),
            balance=Decimal('100.00'),
            status='issued',
        )
    
    print(f"Using invoice: {invoice.invoice_number} (Balance: ${invoice.balance})")
    
    # Get admin user
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.first()
    
    # Count before
    revenue_count_before = Revenue.objects.count()
    je_count_before = AdvancedJournalEntry.objects.count()
    ar_count_before = AdvancedAccountsReceivable.objects.count()
    
    print()
    print("BEFORE:")
    print(f"  Revenue entries: {revenue_count_before}")
    print(f"  Journal entries: {je_count_before}")
    print(f"  AR entries: {ar_count_before}")
    
    # Create a test payment
    print()
    print("Creating test payment of $50.00...")
    
    try:
        transaction = Transaction.objects.create(
            transaction_type='payment_received',
            invoice=invoice,
            patient=patient,
            amount=Decimal('50.00'),
            payment_method='cash',
            reference_number='TEST-001',
            processed_by=user,
        )
        
        print(f"[OK] Transaction created: {transaction.transaction_number}")
    
    except Exception as e:
        print(f"[ERROR] Transaction creation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Count after
    revenue_count_after = Revenue.objects.count()
    je_count_after = AdvancedJournalEntry.objects.count()
    ar_count_after = AdvancedAccountsReceivable.objects.count()
    
    print()
    print("AFTER:")
    print(f"  Revenue entries: {revenue_count_after}")
    print(f"  Journal entries: {je_count_after}")
    print(f"  AR entries: {ar_count_after}")
    
    # Check sync results
    print()
    print("SYNC RESULTS:")
    if revenue_count_after > revenue_count_before:
        print("  [OK] Revenue entry created automatically!")
        latest_revenue = Revenue.objects.latest('created')
        print(f"     Revenue: ${latest_revenue.amount} - {latest_revenue.description}")
    else:
        print("  [FAIL] Revenue NOT auto-created")
        print("     Signal may not be working")
    
    if je_count_after > je_count_before:
        print("  [OK] Journal entry created automatically!")
        latest_je = AdvancedJournalEntry.objects.latest('created')
        print(f"     Entry: {latest_je.entry_number} - Dr:${latest_je.total_debit} Cr:${latest_je.total_credit}")
    else:
        print("  [FAIL] Journal entry NOT auto-created")
    
    if ar_count_after > ar_count_before:
        print("  [OK] AR entry created automatically!")
    else:
        print("  [INFO] AR not created (may already exist for invoice)")
    
    # Check accounts exist
    print()
    print("CHECKING REQUIRED ACCOUNTS:")
    try:
        cash_account = Account.objects.get(account_code='1000')
        print(f"  [OK] Cash Account: {cash_account.account_name}")
    except Account.DoesNotExist:
        print("  [ERROR] Cash Account (1000) not found - CREATING NOW...")
        Account.objects.create(
            account_code='1000',
            account_name='Cash on Hand',
            account_type='asset'
        )
    
    try:
        revenue_account = Account.objects.get(account_code='4000')
        print(f"  [OK] Revenue Account: {revenue_account.account_name}")
    except Account.DoesNotExist:
        print("  [ERROR] Revenue Account (4000) not found - CREATING NOW...")
        Account.objects.create(
            account_code='4000',
            account_name='Patient Services Revenue',
            account_type='revenue'
        )
    
    print()
    print("="*70)
    print("TEST COMPLETE!")
    print("="*70)
    print()
    
    if revenue_count_after > revenue_count_before:
        print("[SUCCESS] AUTO-SYNC IS WORKING!")
        print()
        print("Check these in Admin:")
        print("  - Admin - Revenues")
        print("  - Admin - Advanced Journal Entries")
        print("  - Admin - Receipt Vouchers")
    else:
        print("[FAIL] AUTO-SYNC NOT WORKING")
        print()
        print("Possible issues:")
        print("  1. Signals not registered (server not restarted)")
        print("  2. Required accounts don't exist")
        print("  3. Error in signal handler")
        print()
        print("Solution:")
        print("  1. Restart server: python manage.py runserver")
        print("  2. Run test again")


if __name__ == '__main__':
    try:
        test_payment_sync()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


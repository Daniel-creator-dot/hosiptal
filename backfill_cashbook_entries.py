#!/usr/bin/env python
"""Backfill cashbook entries from existing payments"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from hospital.models_accounting import Transaction, PaymentReceipt
from hospital.models_accounting_advanced import Cashbook, Account

print("=" * 80)
print("BACKFILLING CASHBOOK ENTRIES FROM EXISTING PAYMENTS")
print("=" * 80)
print()

# Get or create cash account
cash_account, _ = Account.objects.get_or_create(
    account_code='1000',
    defaults={
        'account_name': 'Cash on Hand',
        'account_type': 'asset',
        'is_active': True,
    }
)

# Get all payment transactions
transactions = Transaction.objects.filter(
    transaction_type='payment_received',
    is_deleted=False
).order_by('transaction_date')

print(f"Found {transactions.count()} payment transactions")
print()

created_count = 0
skipped_count = 0

with transaction.atomic():
    for trans in transactions:
        # Check if cashbook entry already exists
        existing = Cashbook.objects.filter(
            reference=trans.transaction_number,
            is_deleted=False
        ).first()
        
        if existing:
            skipped_count += 1
            continue
        
        # Create cashbook entry
        try:
            cashbook_entry = Cashbook.objects.create(
                entry_type='receipt',
                entry_date=trans.transaction_date.date() if hasattr(trans.transaction_date, 'date') else trans.transaction_date,
                amount=trans.amount,
                payee_or_payer=trans.patient.full_name if trans.patient else 'Unknown',
                description=f"Payment received: {trans.transaction_number}",
                reference=trans.transaction_number,
                payment_method=trans.payment_method or 'cash',
                patient=trans.patient,
                invoice=trans.invoice,
                cash_account=cash_account,
                status='pending',
                created_by=trans.processed_by,
            )
            created_count += 1
            
            if created_count % 100 == 0:
                print(f"   Created {created_count} entries...")
                
        except Exception as e:
            print(f"   ⚠️  Error creating entry for {trans.transaction_number}: {e}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Created: {created_count} cashbook entries")
print(f"Skipped: {skipped_count} (already exist)")
print()

# Verify
total_cashbook = Cashbook.objects.filter(is_deleted=False).count()
print(f"Total cashbook entries: {total_cashbook}")
print()
print("✅ Backfill complete!")
print()
print("From now on, cashbook entries will be created automatically")
print("when payments are received.")









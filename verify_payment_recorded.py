#!/usr/bin/env python
"""Verify payment was recorded"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Invoice
from hospital.models_accounting import PaymentReceipt, Transaction
from hospital.models_accounting_advanced import Revenue

inv = Invoice.objects.filter(invoice_number='INV20251200001').first()
if inv:
    print(f"Invoice: {inv.invoice_number}")
    print(f"Total: GHS {inv.total_amount}, Balance: GHS {inv.balance}, Status: {inv.status}")
    print(f"Lines: {inv.lines.count()}")
    for line in inv.lines.all():
        print(f"  - {line.description}: GHS {line.line_total}")
    print()
    
    receipts = PaymentReceipt.objects.filter(invoice=inv)
    print(f"Receipts: {receipts.count()}")
    for r in receipts:
        print(f"  - {r.receipt_number}: GHS {r.amount_paid} ({r.payment_method}) - Date: {r.receipt_date}")
    print()
    
    transactions = Transaction.objects.filter(invoice=inv)
    print(f"Transactions: {transactions.count()}")
    for t in transactions:
        print(f"  - {t.transaction_number}: GHS {t.amount} ({t.payment_method}) - Date: {t.transaction_date}")
    print()
    
    revenues = Revenue.objects.filter(invoice=inv)
    print(f"Revenue: {revenues.count()}")
    for rev in revenues:
        print(f"  - {rev.revenue_number}: GHS {rev.amount} ({rev.payment_method}) - Ref: {rev.reference}")
else:
    print("Invoice not found")









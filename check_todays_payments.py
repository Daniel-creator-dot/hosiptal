#!/usr/bin/env python
"""Check for today's payments, especially discharge payments"""
import os
import sys
import django

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from hospital.models_accounting import PaymentReceipt, Transaction
from hospital.models import Invoice, Admission, Encounter
from hospital.models_accounting_advanced import Revenue

today = timezone.now().date()
print("=" * 80)
print(f"CHECKING PAYMENTS FOR TODAY: {today}")
print("=" * 80)
print()

# Check PaymentReceipts
print("1. PAYMENT RECEIPTS TODAY:")
receipts = PaymentReceipt.objects.filter(
    receipt_date__date=today,
    is_deleted=False
).select_related('patient', 'invoice')
print(f"   Found: {receipts.count()} receipts")
for r in receipts:
    patient_name = r.patient.full_name if r.patient else "No Patient"
    invoice_num = r.invoice.invoice_number if r.invoice else "No Invoice"
    print(f"   - {r.receipt_number}: {patient_name} - GHS {r.amount_paid} ({r.payment_method}) - Invoice: {invoice_num}")
print()

# Check Transactions
print("2. TRANSACTIONS TODAY:")
transactions = Transaction.objects.filter(
    transaction_date=today,
    transaction_type='payment_received',
    is_deleted=False
).select_related('patient', 'invoice')
print(f"   Found: {transactions.count()} transactions")
for t in transactions:
    patient_name = t.patient.full_name if t.patient else "No Patient"
    invoice_num = t.invoice.invoice_number if t.invoice else "No Invoice"
    print(f"   - {t.transaction_number}: {patient_name} - GHS {t.amount} ({t.payment_method}) - Invoice: {invoice_num}")
print()

# Check Paid Invoices
print("3. PAID INVOICES TODAY:")
invoices = Invoice.objects.filter(
    issued_at__date=today,
    status__in=['paid', 'partially_paid'],
    is_deleted=False
).select_related('patient')
print(f"   Found: {invoices.count()} paid invoices")
for inv in invoices:
    paid_amount = inv.total_amount - inv.balance
    print(f"   - {inv.invoice_number}: {inv.patient.full_name} - GHS {paid_amount} paid (Total: GHS {inv.total_amount}, Balance: GHS {inv.balance}) - Status: {inv.status}")
print()

# Check Discharges Today
print("4. DISCHARGES TODAY:")
discharges = Admission.objects.filter(
    discharge_date__date=today,
    is_deleted=False
).select_related('encounter', 'encounter__patient', 'ward', 'bed')
print(f"   Found: {discharges.count()} discharges")
for d in discharges:
    patient_name = d.encounter.patient.full_name if d.encounter and d.encounter.patient else "No Patient"
    print(f"   - {patient_name} - Discharged: {d.discharge_date}")
    if d.encounter:
        # Check for invoices for this encounter
        encounter_invoices = Invoice.objects.filter(
            encounter=d.encounter,
            is_deleted=False
        ).select_related('patient')
        print(f"     Encounter ID: {d.encounter.id}")
        print(f"     Invoices: {encounter_invoices.count()}")
        for inv in encounter_invoices:
            paid_amount = inv.total_amount - inv.balance
            print(f"       - {inv.invoice_number}: GHS {paid_amount} paid (Total: GHS {inv.total_amount}, Balance: GHS {inv.balance}) - Status: {inv.status}")
            
            # Check for receipts for this invoice
            invoice_receipts = PaymentReceipt.objects.filter(
                invoice=inv,
                is_deleted=False
            )
            print(f"         Receipts: {invoice_receipts.count()}")
            for rec in invoice_receipts:
                print(f"           - {rec.receipt_number}: GHS {rec.amount_paid} ({rec.payment_method}) - Date: {rec.receipt_date}")
            
            # Check for transactions for this invoice
            invoice_transactions = Transaction.objects.filter(
                invoice=inv,
                is_deleted=False
            )
            print(f"         Transactions: {invoice_transactions.count()}")
            for trans in invoice_transactions:
                print(f"           - {trans.transaction_number}: GHS {trans.amount} ({trans.payment_method}) - Date: {trans.transaction_date}")
print()

# Check Revenue entries
print("5. REVENUE ENTRIES TODAY:")
revenues = Revenue.objects.filter(
    revenue_date=today,
    is_deleted=False
).select_related('patient', 'invoice', 'category')
print(f"   Found: {revenues.count()} revenue entries")
for rev in revenues:
    patient_name = rev.patient.full_name if rev.patient else "No Patient"
    invoice_num = rev.invoice.invoice_number if rev.invoice else "No Invoice"
    print(f"   - {rev.revenue_number}: {patient_name} - GHS {rev.amount} ({rev.payment_method}) - Invoice: {invoice_num} - Ref: {rev.reference}")
print()

# Check for cash payments specifically
print("6. CASH PAYMENTS TODAY:")
cash_receipts = receipts.filter(payment_method='cash')
cash_transactions = transactions.filter(payment_method='cash')
print(f"   Cash Receipts: {cash_receipts.count()}")
print(f"   Cash Transactions: {cash_transactions.count()}")
print()

# Summary
print("=" * 80)
print("SUMMARY:")
print(f"   Total Receipts: {receipts.count()}")
print(f"   Total Transactions: {transactions.count()}")
print(f"   Total Paid Invoices: {invoices.count()}")
print(f"   Total Discharges: {discharges.count()}")
print(f"   Total Revenue Entries: {revenues.count()}")
print("=" * 80)


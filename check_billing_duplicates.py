#!/usr/bin/env python
"""Check for duplicate billing entries"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db.models import Count, Q
from hospital.models import Invoice, InvoiceLine
from hospital.models_workflow import Bill
from decimal import Decimal

print("=" * 80)
print("CHECKING FOR BILLING DUPLICATES")
print("=" * 80)
print()

# 1. Check for duplicate invoice numbers
print("1. CHECKING DUPLICATE INVOICE NUMBERS:")
duplicate_invoices = Invoice.objects.values('invoice_number').annotate(
    count=Count('id')
).filter(count__gt=1, is_deleted=False)

if duplicate_invoices.exists():
    print(f"   ❌ Found {duplicate_invoices.count()} duplicate invoice numbers:")
    for dup in duplicate_invoices:
        invoices = Invoice.objects.filter(
            invoice_number=dup['invoice_number'],
            is_deleted=False
        )
        print(f"      Invoice Number: {dup['invoice_number']} ({dup['count']} duplicates)")
        for inv in invoices:
            print(f"        - ID: {inv.id}, Patient: {inv.patient.full_name}, Amount: GHS {inv.total_amount}, Status: {inv.status}")
else:
    print("   ✅ No duplicate invoice numbers found")
print()

# 2. Check for duplicate bills (same patient, encounter, same date)
print("2. CHECKING DUPLICATE BILLS:")
duplicate_bills = Bill.objects.values(
    'patient', 'encounter', 'bill_type', 'issued_at__date'
).annotate(
    count=Count('id')
).filter(count__gt=1, is_deleted=False)

if duplicate_bills.exists():
    print(f"   ❌ Found {duplicate_bills.count()} sets of duplicate bills:")
    for dup in duplicate_bills:
        bills = Bill.objects.filter(
            patient_id=dup['patient'],
            encounter_id=dup['encounter'],
            bill_type=dup['bill_type'],
            issued_at__date=dup['issued_at__date'],
            is_deleted=False
        )
        print(f"      Patient ID: {dup['patient']}, Encounter: {dup['encounter']}, Type: {dup['bill_type']}, Date: {dup['issued_at__date']} ({dup['count']} duplicates)")
        for bill in bills:
            print(f"        - Bill: {bill.bill_number}, Amount: GHS {bill.total_amount}, Status: {bill.status}")
else:
    print("   ✅ No duplicate bills found")
print()

# 3. Check for duplicate invoice lines (same invoice, same service, same price)
print("3. CHECKING DUPLICATE INVOICE LINES:")
duplicate_lines = InvoiceLine.objects.values(
    'invoice', 'service_code', 'unit_price', 'quantity'
).annotate(
    count=Count('id')
).filter(count__gt=1, is_deleted=False)

if duplicate_lines.exists():
    print(f"   ❌ Found {duplicate_lines.count()} sets of duplicate invoice lines:")
    for dup in duplicate_lines:
        lines = InvoiceLine.objects.filter(
            invoice_id=dup['invoice'],
            service_code_id=dup['service_code'],
            unit_price=dup['unit_price'],
            quantity=dup['quantity'],
            is_deleted=False
        )
        invoice = Invoice.objects.get(id=dup['invoice'])
        print(f"      Invoice: {invoice.invoice_number}, Service: {dup['service_code']}, Price: GHS {dup['unit_price']}, Qty: {dup['quantity']} ({dup['count']} duplicates)")
        for line in lines:
            print(f"        - Line ID: {line.id}, Description: {line.description[:50]}")
else:
    print("   ✅ No duplicate invoice lines found")
print()

# 4. Check for multiple invoices for same encounter
print("4. CHECKING MULTIPLE INVOICES FOR SAME ENCOUNTER:")
encounter_invoices = Invoice.objects.values('encounter').annotate(
    count=Count('id')
).filter(count__gt=1, encounter__isnull=False, is_deleted=False)

if encounter_invoices.exists():
    print(f"   ⚠️  Found {encounter_invoices.count()} encounters with multiple invoices:")
    for enc in encounter_invoices:
        invoices = Invoice.objects.filter(
            encounter_id=enc['encounter'],
            is_deleted=False
        )
        from hospital.models import Encounter
        encounter = Encounter.objects.get(id=enc['encounter'])
        print(f"      Encounter ID: {enc['encounter']}, Patient: {encounter.patient.full_name} ({enc['count']} invoices)")
        for inv in invoices:
            print(f"        - Invoice: {inv.invoice_number}, Amount: GHS {inv.total_amount}, Status: {inv.status}, Date: {inv.issued_at}")
else:
    print("   ✅ No encounters with multiple invoices found")
print()

# 5. Check for invoices with same patient and same date
print("5. CHECKING DUPLICATE INVOICES (SAME PATIENT, SAME DATE):")
patient_date_invoices = Invoice.objects.values(
    'patient', 'issued_at__date'
).annotate(
    count=Count('id')
).filter(count__gt=1, is_deleted=False)

if patient_date_invoices.exists():
    print(f"   ⚠️  Found {patient_date_invoices.count()} sets of invoices (same patient, same date):")
    for dup in patient_date_invoices:
        invoices = Invoice.objects.filter(
            patient_id=dup['patient'],
            issued_at__date=dup['issued_at__date'],
            is_deleted=False
        )
        from hospital.models import Patient
        patient = Patient.objects.get(id=dup['patient'])
        print(f"      Patient: {patient.full_name}, Date: {dup['issued_at__date']} ({dup['count']} invoices)")
        for inv in invoices:
            print(f"        - Invoice: {inv.invoice_number}, Amount: GHS {inv.total_amount}, Status: {inv.status}, Encounter: {inv.encounter.id if inv.encounter else 'None'}")
else:
    print("   ✅ No duplicate invoices (same patient, same date) found")
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
total_issues = (
    duplicate_invoices.count() +
    duplicate_bills.count() +
    duplicate_lines.count()
)
if total_issues > 0:
    print(f"❌ Found {total_issues} types of duplicate issues that need fixing")
    print()
    print("To fix duplicates, run:")
    print("  docker exec chm-web-1 python /app/fix_billing_duplicates.py")
else:
    print("✅ No critical duplicate billing entries found!")
    print("   (Some multiple invoices per encounter may be legitimate)")









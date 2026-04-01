#!/usr/bin/env python
"""Detailed check for billing duplicates"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db.models import Count, Q, Sum
from hospital.models import Invoice, InvoiceLine, ServiceCode
from hospital.models_workflow import Bill
from decimal import Decimal

print("=" * 80)
print("DETAILED BILLING DUPLICATE CHECK")
print("=" * 80)
print()

issues_found = []

# 1. Check for invoices with duplicate invoice lines (same service code, same price, same quantity)
print("1. CHECKING INVOICES WITH DUPLICATE LINES:")
invoices_with_duplicates = []
for invoice in Invoice.objects.filter(is_deleted=False):
    lines = InvoiceLine.objects.filter(invoice=invoice, is_deleted=False)
    seen = {}
    duplicates = []
    
    for line in lines:
        key = (line.service_code_id, line.unit_price, line.quantity, line.description[:50])
        if key in seen:
            duplicates.append((seen[key], line))
        else:
            seen[key] = line
    
    if duplicates:
        invoices_with_duplicates.append((invoice, duplicates))
        issues_found.append(f"Invoice {invoice.invoice_number} has duplicate lines")

if invoices_with_duplicates:
    print(f"   ❌ Found {len(invoices_with_duplicates)} invoices with duplicate lines:")
    for invoice, dups in invoices_with_duplicates:
        print(f"      Invoice: {invoice.invoice_number} - {invoice.patient.full_name}")
        for orig, dup in dups:
            print(f"        - Duplicate: Service {orig.service_code_id}, Price: GHS {orig.unit_price}, Qty: {orig.quantity}")
            print(f"          Original Line ID: {orig.id}, Duplicate Line ID: {dup.id}")
else:
    print("   ✅ No invoices with duplicate lines found")
print()

# 2. Check for bills with same bill number (should be unique)
print("2. CHECKING DUPLICATE BILL NUMBERS:")
duplicate_bill_numbers = Bill.objects.values('bill_number').annotate(
    count=Count('id')
).filter(count__gt=1, is_deleted=False)

if duplicate_bill_numbers.exists():
    print(f"   ❌ Found {duplicate_bill_numbers.count()} duplicate bill numbers:")
    for dup in duplicate_bill_numbers:
        bills = Bill.objects.filter(bill_number=dup['bill_number'], is_deleted=False)
        print(f"      Bill Number: {dup['bill_number']} ({dup['count']} duplicates)")
        for bill in bills:
            print(f"        - ID: {bill.id}, Patient: {bill.patient.full_name}, Amount: GHS {bill.total_amount}")
        issues_found.append(f"Duplicate bill number: {dup['bill_number']}")
else:
    print("   ✅ No duplicate bill numbers found")
print()

# 3. Check for invoices with zero or negative amounts
print("3. CHECKING INVOICES WITH INVALID AMOUNTS:")
invalid_invoices = Invoice.objects.filter(
    Q(total_amount__lte=0) | Q(balance__lt=0),
    is_deleted=False
)
if invalid_invoices.exists():
    print(f"   ⚠️  Found {invalid_invoices.count()} invoices with invalid amounts:")
    for inv in invalid_invoices[:10]:
        print(f"      Invoice: {inv.invoice_number}, Total: GHS {inv.total_amount}, Balance: GHS {inv.balance}")
    issues_found.append(f"{invalid_invoices.count()} invoices with invalid amounts")
else:
    print("   ✅ No invoices with invalid amounts found")
print()

# 4. Check for invoice lines with zero or negative amounts
print("4. CHECKING INVOICE LINES WITH INVALID AMOUNTS:")
invalid_lines = InvoiceLine.objects.filter(
    Q(line_total__lte=0) | Q(unit_price__lt=0) | Q(quantity__lte=0),
    is_deleted=False
)
if invalid_lines.exists():
    print(f"   ⚠️  Found {invalid_lines.count()} invoice lines with invalid amounts:")
    for line in invalid_lines[:10]:
        print(f"      Line ID: {line.id}, Invoice: {line.invoice.invoice_number}, Total: GHS {line.line_total}")
    issues_found.append(f"{invalid_lines.count()} invoice lines with invalid amounts")
else:
    print("   ✅ No invoice lines with invalid amounts found")
print()

# 5. Check for bills with same invoice (should be one bill per invoice ideally)
print("5. CHECKING MULTIPLE BILLS FOR SAME INVOICE:")
invoice_bills = Bill.objects.values('invoice').annotate(
    count=Count('id')
).filter(count__gt=1, invoice__isnull=False, is_deleted=False)

if invoice_bills.exists():
    print(f"   ⚠️  Found {invoice_bills.count()} invoices with multiple bills:")
    for ib in invoice_bills:
        bills = Bill.objects.filter(invoice_id=ib['invoice'], is_deleted=False)
        invoice = Invoice.objects.get(id=ib['invoice'])
        print(f"      Invoice: {invoice.invoice_number} ({ib['count']} bills)")
        for bill in bills:
            print(f"        - Bill: {bill.bill_number}, Amount: GHS {bill.total_amount}, Status: {bill.status}")
else:
    print("   ✅ No invoices with multiple bills found")
print()

# 6. Check for orphaned invoice lines (invoice doesn't exist)
print("6. CHECKING ORPHANED INVOICE LINES:")
orphaned_lines = InvoiceLine.objects.filter(
    invoice__isnull=True
).count()
if orphaned_lines > 0:
    print(f"   ⚠️  Found {orphaned_lines} orphaned invoice lines (no invoice)")
    issues_found.append(f"{orphaned_lines} orphaned invoice lines")
else:
    print("   ✅ No orphaned invoice lines found")
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
if issues_found:
    print(f"❌ Found {len(issues_found)} issues:")
    for issue in issues_found:
        print(f"   - {issue}")
    print()
    print("To fix these issues, run:")
    print("  docker exec chm-web-1 python /app/fix_billing_duplicates.py")
else:
    print("✅ No billing duplicate issues found!")
    print("   All billing entries are clean and properly structured.")









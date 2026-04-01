#!/usr/bin/env python
"""Fix billing duplicates"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from django.db.models import Count
from hospital.models import Invoice, InvoiceLine
from hospital.models_workflow import Bill
from decimal import Decimal

print("=" * 80)
print("FIXING BILLING DUPLICATES")
print("=" * 80)
print()

fixed_count = 0

# 1. Fix duplicate invoice lines
print("1. FIXING DUPLICATE INVOICE LINES:")
with transaction.atomic():
    invoices = Invoice.objects.filter(is_deleted=False)
    for invoice in invoices:
        lines = InvoiceLine.objects.filter(invoice=invoice, is_deleted=False).order_by('id')
        seen = {}
        duplicates_to_delete = []
        
        for line in lines:
            # Create a key based on service, price, quantity, and description
            key = (
                line.service_code_id,
                line.unit_price,
                line.quantity,
                line.description[:100] if line.description else ''
            )
            
            if key in seen:
                # This is a duplicate - mark for deletion
                duplicates_to_delete.append(line)
            else:
                seen[key] = line
        
        if duplicates_to_delete:
            print(f"   Invoice {invoice.invoice_number}: Found {len(duplicates_to_delete)} duplicate lines")
            for dup in duplicates_to_delete:
                print(f"      Deleting duplicate line ID {dup.id}: {dup.description[:50]}")
                dup.is_deleted = True
                dup.save()
                fixed_count += 1
            
            # Recalculate invoice totals
            invoice.calculate_totals()
            invoice.save()
            print(f"      Updated invoice total: GHS {invoice.total_amount}")

if fixed_count == 0:
    print("   ✅ No duplicate invoice lines to fix")
print()

# 2. Fix duplicate bills (keep the most recent, delete older ones)
print("2. FIXING DUPLICATE BILLS:")
with transaction.atomic():
    duplicate_bills = Bill.objects.values(
        'patient', 'encounter', 'bill_type', 'issued_at__date'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1, is_deleted=False)
    
    for dup in duplicate_bills:
        bills = Bill.objects.filter(
            patient_id=dup['patient'],
            encounter_id=dup['encounter'],
            bill_type=dup['bill_type'],
            issued_at__date=dup['issued_at__date'],
            is_deleted=False
        ).order_by('-issued_at')
        
        # Keep the most recent, delete others
        keep_bill = bills.first()
        delete_bills = bills[1:]
        
        print(f"   Patient ID {dup['patient']}, Encounter {dup['encounter']}: Keeping bill {keep_bill.bill_number}")
        for bill in delete_bills:
            print(f"      Deleting duplicate bill {bill.bill_number}")
            bill.is_deleted = True
            bill.save()
            fixed_count += 1

if fixed_count == 0:
    print("   ✅ No duplicate bills to fix")
print()

# 3. Fix invoices with invalid amounts
print("3. FIXING INVOICES WITH INVALID AMOUNTS:")
with transaction.atomic():
    invalid_invoices = Invoice.objects.filter(
        total_amount__lte=0,
        is_deleted=False
    )
    
    for inv in invalid_invoices:
        # Recalculate from lines
        inv.calculate_totals()
        if inv.total_amount <= 0:
            # If still invalid, mark as cancelled
            inv.status = 'cancelled'
            print(f"   Invoice {inv.invoice_number}: Marked as cancelled (invalid amount)")
        else:
            print(f"   Invoice {inv.invoice_number}: Recalculated to GHS {inv.total_amount}")
        inv.save()
        fixed_count += 1

if invalid_invoices.count() == 0:
    print("   ✅ No invoices with invalid amounts to fix")
print()

# 4. Fix invoice lines with invalid amounts
print("4. FIXING INVOICE LINES WITH INVALID AMOUNTS:")
with transaction.atomic():
    invalid_lines = InvoiceLine.objects.filter(
        Q(line_total__lte=0) | Q(unit_price__lt=0) | Q(quantity__lte=0),
        is_deleted=False
    )
    
    for line in invalid_lines:
        if line.quantity <= 0:
            line.quantity = 1
        if line.unit_price < 0:
            line.unit_price = abs(line.unit_price)
        line.line_total = line.quantity * line.unit_price
        line.save()
        print(f"   Fixed line ID {line.id}: Qty={line.quantity}, Price=GHS {line.unit_price}, Total=GHS {line.line_total}")
        fixed_count += 1
        
        # Update parent invoice
        line.invoice.calculate_totals()
        line.invoice.save()

if invalid_lines.count() == 0:
    print("   ✅ No invoice lines with invalid amounts to fix")
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
if fixed_count > 0:
    print(f"✅ Fixed {fixed_count} duplicate/invalid billing entries")
else:
    print("✅ No duplicates or invalid entries found - billing is clean!")









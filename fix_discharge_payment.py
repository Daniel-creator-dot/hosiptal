#!/usr/bin/env python
"""Fix discharge payment - add bed charges and record payment"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.utils import timezone
from django.db import transaction as db_transaction
from datetime import date
from decimal import Decimal
from hospital.models import Admission, Invoice, InvoiceLine, Payer, ServiceCode
from hospital.models_accounting import PaymentReceipt, Transaction
from hospital.models_accounting_advanced import Revenue, RevenueCategory, ReceiptVoucher, AdvancedJournalEntry, AdvancedJournalEntryLine, Journal, Account
from hospital.services.bed_billing_service import BedBillingService
from django.contrib.auth.models import User

today = timezone.now().date()
amount = Decimal('960.00')
payment_method = 'cash'

# Find today's discharge
discharge = Admission.objects.filter(
    discharge_date__date=today,
    is_deleted=False
).select_related('encounter', 'encounter__patient', 'ward', 'bed').first()

if not discharge:
    print("ERROR: No discharge found for today")
    sys.exit(1)

patient = discharge.encounter.patient if discharge.encounter else None
encounter = discharge.encounter

if not patient:
    print("ERROR: No patient found")
    sys.exit(1)

print(f"Patient: {patient.full_name}")
print(f"Amount: GHS {amount}")
print()

# Get or create invoice
invoice = Invoice.objects.filter(
    encounter=encounter,
    is_deleted=False
).first()

if not invoice:
    payer = patient.primary_insurance or Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
    if not payer:
        payer = Payer.objects.create(name='Cash', payer_type='cash', is_active=True)
    
    invoice = Invoice.objects.create(
        patient=patient,
        encounter=encounter,
        payer=payer,
        status='issued',
        issued_at=timezone.now()
    )
    print(f"Created invoice: {invoice.invoice_number}")

# Calculate bed charges
admission_date = discharge.created if hasattr(discharge, 'created') else discharge.discharge_date
if admission_date and discharge.discharge_date:
    if hasattr(admission_date, 'date'):
        admission_date_only = admission_date.date()
    else:
        admission_date_only = admission_date
    
    if hasattr(discharge.discharge_date, 'date'):
        discharge_date_only = discharge.discharge_date.date()
    else:
        discharge_date_only = discharge.discharge_date
    
    days = (discharge_date_only - admission_date_only).days + 1
    if days < 1:
        days = 1
else:
    days = 1

daily_rate = BedBillingService._get_daily_rate(discharge)
bed_charge = Decimal(str(days)) * daily_rate

print(f"Bed charges: {days} days @ GHS {daily_rate}/day = GHS {bed_charge}")
print()

with db_transaction.atomic():
    # Add bed charges if not already added
    if invoice.lines.count() == 0:
        bed_service_code, _ = ServiceCode.objects.get_or_create(
            code='BED-CHARGE',
            defaults={
                'description': 'Bed Charges - Accommodation',
                'category': 'accommodation',
                'is_active': True
            }
        )
        
        InvoiceLine.objects.create(
            invoice=invoice,
            service_code=bed_service_code,
            description=f"Bed Charges - {discharge.ward.name if discharge.ward else 'Ward'} - {days} days @ GHS {daily_rate}/day",
            quantity=days,
            unit_price=daily_rate,
            line_total=bed_charge
        )
        
        invoice.calculate_totals()
        invoice.save()
        print(f"Added bed charges to invoice")
    
    # Record payment
    admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    
    # Create Transaction
    transaction = Transaction.objects.create(
        transaction_type='payment_received',
        invoice=invoice,
        patient=patient,
        amount=amount,
        payment_method=payment_method,
        processed_by=admin_user,
        transaction_date=timezone.now(),
        notes=f'Discharge payment - {patient.full_name}'
    )
    print(f"Created transaction: {transaction.transaction_number}")
    
    # Create PaymentReceipt
    receipt = PaymentReceipt.objects.create(
        transaction=transaction,
        invoice=invoice,
        patient=patient,
        amount_paid=amount,
        payment_method=payment_method,
        received_by=admin_user,
        receipt_date=timezone.now(),
        notes=f'Discharge payment - {patient.full_name}'
    )
    print(f"Created receipt: {receipt.receipt_number}")
    
    # Update invoice
    invoice.balance = invoice.balance - amount
    if invoice.balance <= 0:
        invoice.status = 'paid'
    else:
        invoice.status = 'partially_paid'
    invoice.save()
    print(f"Updated invoice: Balance = GHS {invoice.balance}, Status = {invoice.status}")

print()
print("=" * 80)
print("PAYMENT RECORDED SUCCESSFULLY!")
print("=" * 80)
print(f"Receipt: {receipt.receipt_number}")
print(f"Transaction: {transaction.transaction_number}")
print(f"Invoice: {invoice.invoice_number}")
print(f"Amount: GHS {amount}")
print()
print("The payment is now visible in:")
print("  - Revenue Report: /hms/accounting/revenue-report/")
print("  - Payment Receipts: /admin/hospital/paymentreceipt/")
print("=" * 80)









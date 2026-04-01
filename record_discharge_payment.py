#!/usr/bin/env python
"""Record missing discharge payment"""
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
from hospital.models import Admission, Invoice, InvoiceLine, Payer, Encounter, ServiceCode
from hospital.models_accounting import PaymentReceipt, Transaction
from hospital.models_accounting_advanced import Revenue, RevenueCategory, ReceiptVoucher, AdvancedJournalEntry, AdvancedJournalEntryLine, Journal, AdvancedGeneralLedger, Account
from django.contrib.auth.models import User

if len(sys.argv) < 3:
    print("Usage: python record_discharge_payment.py <amount> <payment_method>")
    print("Example: python record_discharge_payment.py 500.00 cash")
    sys.exit(1)

amount = Decimal(sys.argv[1])
payment_method = sys.argv[2].lower()

if payment_method not in ['cash', 'mobile_money', 'card', 'bank_transfer', 'cheque']:
    print(f"Warning: Payment method '{payment_method}' may not be standard")
    print("Using 'cash' as default")
    payment_method = 'cash'

today = timezone.now().date()

print("=" * 80)
print("RECORDING DISCHARGE PAYMENT")
print("=" * 80)
print(f"Amount: GHS {amount}")
print(f"Payment Method: {payment_method}")
print()

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
    print("ERROR: No patient found for discharge")
    sys.exit(1)

print(f"Patient: {patient.full_name}")
print(f"Encounter: {encounter.id if encounter else 'None'}")
print()

# Get or create payer
payer = patient.primary_insurance
if not payer:
    payer = Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
if not payer:
    payer = Payer.objects.create(
        name='Cash',
        payer_type='cash',
        is_active=True
    )

# Get or create invoice
invoice = None
if encounter:
    invoice = Invoice.objects.filter(
        encounter=encounter,
        is_deleted=False
    ).first()

if not invoice:
    print("Creating invoice for discharge...")
    invoice = Invoice.objects.create(
        patient=patient,
        encounter=encounter,
        payer=payer,
        status='issued',
        issued_at=timezone.now()
    )
    print(f"  Created invoice: {invoice.invoice_number}")
    
    # Add bed charges if available
    from hospital.services.bed_billing_service import BedBillingService
    
    # Calculate days
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
    
    # Get daily rate
    daily_rate = BedBillingService._get_daily_rate(discharge)
    bed_charge = Decimal(str(days)) * daily_rate
    
    # Get or create service code for bed charges
    bed_service_code, _ = ServiceCode.objects.get_or_create(
        code='BED-CHARGE',
        defaults={
            'description': 'Bed Charges - Accommodation',
            'category': 'accommodation',
            'is_active': True
        }
    )
    
    # Add invoice line
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
    print(f"  Added bed charges: GHS {bed_charge} ({days} days @ GHS {daily_rate}/day)")
else:
    print(f"Using existing invoice: {invoice.invoice_number}")

# Get admin user for processing
admin_user = User.objects.filter(is_superuser=True).first()
if not admin_user:
    admin_user = User.objects.first()

print()
print("Recording payment...")

with db_transaction.atomic():
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
    print(f"  Created transaction: {transaction.transaction_number}")
    
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
    print(f"  Created receipt: {receipt.receipt_number}")
    
    # Update invoice
    invoice.balance = invoice.balance - amount
    if invoice.balance <= 0:
        invoice.status = 'paid'
    else:
        invoice.status = 'partially_paid'
    invoice.save()
    print(f"  Updated invoice balance: GHS {invoice.balance}")
    
    # Get or create accounts
    cash_account, _ = Account.objects.get_or_create(
        account_code='1000',
        defaults={
            'account_name': 'Cash on Hand',
            'account_type': 'asset',
            'is_active': True
        }
    )
    
    revenue_account, _ = Account.objects.get_or_create(
        account_code='4000',
        defaults={
            'account_name': 'Patient Services Revenue',
            'account_type': 'revenue',
            'is_active': True
        }
    )
    
    revenue_category, _ = RevenueCategory.objects.get_or_create(
        code='REV-PATIENT',
        defaults={
            'name': 'Patient Services',
            'account': revenue_account
        }
    )
    
    # Create Revenue entry
    revenue = Revenue.objects.create(
        revenue_date=today,
        category=revenue_category,
        description=f'Discharge payment: {patient.full_name} - {receipt.receipt_number}',
        amount=amount,
        patient=patient,
        invoice=invoice,
        payment_method=payment_method,
        reference=receipt.receipt_number,
        recorded_by=admin_user,
    )
    print(f"  Created revenue entry: {revenue.revenue_number}")
    
    # Create Receipt Voucher
    receipt_voucher = ReceiptVoucher.objects.create(
        receipt_date=today,
        received_from=patient.full_name,
        patient=patient,
        amount=amount,
        payment_method=payment_method,
        description=revenue.description,
        reference=receipt.receipt_number,
        status='issued',
        revenue_account=revenue_account,
        cash_account=cash_account,
        invoice=invoice,
        received_by=admin_user,
    )
    print(f"  Created receipt voucher: {receipt_voucher.receipt_number}")
    
    # Check if journal entry already exists (created by auto-sync)
    journal_entry = revenue.journal_entry if hasattr(revenue, 'journal_entry') and revenue.journal_entry else None
    
    if not journal_entry:
        # Create Journal Entry if not already created by auto-sync
        journal, _ = Journal.objects.get_or_create(
            code='RJ',
            defaults={
                'name': 'Receipt Journal',
                'journal_type': 'receipt'
            }
        )
        
        # Check field name - try reference first
        try:
            journal_entry = AdvancedJournalEntry.objects.create(
                journal=journal,
                entry_date=today,
                description=revenue.description,
                reference=receipt.receipt_number,
                status='draft',
                posted_by=admin_user,
            )
        except TypeError:
            # Try with reference_number if reference doesn't work
            journal_entry = AdvancedJournalEntry.objects.create(
                journal=journal,
                entry_date=today,
                description=revenue.description,
                status='draft',
                posted_by=admin_user,
            )
        
        # Create Journal Entry Lines
        AdvancedJournalEntryLine.objects.create(
            journal_entry=journal_entry,
            line_number=1,
            account=cash_account,
            description='Payment received',
            debit_amount=amount,
            credit_amount=Decimal('0.00'),
        )
        
        AdvancedJournalEntryLine.objects.create(
            journal_entry=journal_entry,
            line_number=2,
            account=revenue_account,
            description='Revenue from patient services',
            debit_amount=Decimal('0.00'),
            credit_amount=amount,
        )
        
        # Post journal entry
        journal_entry.post(user=admin_user)
        print(f"  Created and posted journal entry: {journal_entry.entry_number if hasattr(journal_entry, 'entry_number') else 'N/A'}")
    else:
        print(f"  Journal entry already exists (created by auto-sync): {journal_entry.entry_number if hasattr(journal_entry, 'entry_number') else 'N/A'}")

print()
print("=" * 80)
print("PAYMENT RECORDED SUCCESSFULLY!")
print("=" * 80)
print(f"Receipt Number: {receipt.receipt_number}")
print(f"Transaction Number: {transaction.transaction_number}")
print(f"Invoice Number: {invoice.invoice_number}")
print(f"Amount: GHS {amount}")
print()
print("Payment is now visible in:")
print("  - Revenue Report: /hms/accounting/revenue-report/")
print("  - Payment Receipts: /admin/hospital/paymentreceipt/")
print("  - Transactions: /admin/hospital/transaction/")
print("  - Revenue: /admin/hospital/revenue/")
print("=" * 80)


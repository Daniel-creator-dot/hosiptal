#!/usr/bin/env python
"""Find and fix missing discharge payment"""
import os
import sys
import django

sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.utils import timezone
from datetime import date
from decimal import Decimal
from hospital.models import Admission, Invoice, InvoiceLine, Payer, Encounter
from hospital.models_accounting import PaymentReceipt, Transaction
from hospital.models_accounting_advanced import Revenue, RevenueCategory, ReceiptVoucher, AdvancedJournalEntry, AdvancedJournalEntryLine, Journal, AdvancedGeneralLedger, Account

today = timezone.now().date()

print("=" * 80)
print("FINDING MISSING DISCHARGE PAYMENT")
print("=" * 80)
print()

# Find today's discharge
discharge = Admission.objects.filter(
    discharge_date__date=today,
    is_deleted=False
).select_related('encounter', 'encounter__patient', 'ward', 'bed').first()

if not discharge:
    print("No discharge found for today")
    sys.exit(1)

patient = discharge.encounter.patient if discharge.encounter else None
encounter = discharge.encounter

print(f"DISCHARGE FOUND:")
print(f"  Patient: {patient.full_name if patient else 'No Patient'}")
print(f"  Discharge Date: {discharge.discharge_date}")
print(f"  Encounter ID: {encounter.id if encounter else 'None'}")
print(f"  Ward: {discharge.ward.name if discharge.ward else 'None'}")
print(f"  Bed: {discharge.bed.bed_number if discharge.bed else 'None'}")
print()

# Check for invoices
invoices = Invoice.objects.filter(
    encounter=encounter,
    is_deleted=False
) if encounter else Invoice.objects.none()

print(f"INVOICES FOR THIS ENCOUNTER: {invoices.count()}")
for inv in invoices:
    print(f"  - {inv.invoice_number}: GHS {inv.total_amount} (Balance: GHS {inv.balance}, Status: {inv.status})")
print()

# Check if bed charges were calculated
from hospital.services.bed_billing_service import BedBillingService

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

# Get daily rate
daily_rate = BedBillingService._get_daily_rate(discharge)
total_charge = Decimal(str(days)) * daily_rate

print("BED CHARGES:")
print(f"  Days: {days}")
print(f"  Daily Rate: GHS {daily_rate}")
print(f"  Total Charge: GHS {total_charge}")
print()

# Ask user for payment amount
print("=" * 80)
print("PAYMENT INFORMATION NEEDED:")
print("=" * 80)
print(f"Patient: {patient.full_name if patient else 'Unknown'}")
print(f"Expected Charge: GHS {total_charge}")
print()
print("Please provide:")
print("  1. Amount paid (in GHS)")
print("  2. Payment method (cash/mobile_money/card/bank_transfer)")
print()
print("To record the payment, run:")
print("  docker exec chm-web-1 python /app/record_discharge_payment.py <amount> <payment_method>")
print("=" * 80)


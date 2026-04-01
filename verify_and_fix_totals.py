"""
Verify and Fix General Ledger Totals
Check if totals match what's displayed and fix any discrepancies
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import AdvancedGeneralLedger
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

print("=" * 80)
print("VERIFYING AND FIXING GENERAL LEDGER TOTALS")
print("=" * 80)

# Check entries for Jan 7, 2026 (from image)
check_date = datetime(2026, 1, 7).date()
print(f"\nChecking entries for: {check_date.strftime('%B %d, %Y')}")

# Get entries exactly as the view does
ledger_entries = AdvancedGeneralLedger.objects.filter(
    transaction_date=check_date,
    is_voided=False
).select_related('account').order_by('account', 'transaction_date')

print(f"\nTotal entries found: {ledger_entries.count()}")

# Calculate totals exactly as the view does
total_debits = ledger_entries.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
total_credits = ledger_entries.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')

print(f"\n" + "=" * 80)
print("CURRENT TOTALS (as calculated by view):")
print("=" * 80)
print(f"  Total Debits: GHS {total_debits:,.2f}")
print(f"  Total Credits: GHS {total_credits:,.2f}")
print(f"  Difference: GHS {abs(total_debits - total_credits):,.2f}")

# Manual verification - sum all entries
print(f"\n" + "=" * 80)
print("MANUAL VERIFICATION:")
print("=" * 80)

manual_debit_sum = Decimal('0.00')
manual_credit_sum = Decimal('0.00')

for entry in ledger_entries:
    manual_debit_sum += entry.debit_amount
    manual_credit_sum += entry.credit_amount

print(f"  Manual Sum of Debits: GHS {manual_debit_sum:,.2f}")
print(f"  Manual Sum of Credits: GHS {manual_credit_sum:,.2f}")

# Compare
debit_match = abs(total_debits - manual_debit_sum) < 0.01
credit_match = abs(total_credits - manual_credit_sum) < 0.01

print(f"\n  Debit Match: {'[OK]' if debit_match else '[ERROR]'}")
print(f"  Credit Match: {'[OK]' if credit_match else '[ERROR]'}")

if not debit_match:
    print(f"    Difference: GHS {abs(total_debits - manual_debit_sum):,.2f}")
if not credit_match:
    print(f"    Difference: GHS {abs(total_credits - manual_credit_sum):,.2f}")

# Check for any entries that might be excluded incorrectly
print(f"\n" + "=" * 80)
print("CHECKING FOR ISSUES:")
print("=" * 80)

# Check for voided entries that shouldn't be included
voided_count = AdvancedGeneralLedger.objects.filter(
    transaction_date=check_date,
    is_voided=True
).count()
print(f"  Voided entries (excluded): {voided_count}")

# Check for deleted entries
deleted_count = AdvancedGeneralLedger.objects.filter(
    transaction_date=check_date,
    is_deleted=True
).count()
print(f"  Deleted entries (excluded): {deleted_count}")

# Check if any entries have NULL debit/credit
null_debit = ledger_entries.filter(debit_amount__isnull=True).count()
null_credit = ledger_entries.filter(credit_amount__isnull=True).count()
print(f"  Entries with NULL debit: {null_debit}")
print(f"  Entries with NULL credit: {null_credit}")

# Show breakdown by account
print(f"\n" + "=" * 80)
print("BREAKDOWN BY ACCOUNT:")
print("=" * 80)

accounts_data = {}
for entry in ledger_entries:
    account_code = entry.account.account_code
    if account_code not in accounts_data:
        accounts_data[account_code] = {
            'account_name': entry.account.account_name,
            'total_debit': Decimal('0.00'),
            'total_credit': Decimal('0.00'),
            'count': 0
        }
    accounts_data[account_code]['total_debit'] += entry.debit_amount
    accounts_data[account_code]['total_credit'] += entry.credit_amount
    accounts_data[account_code]['count'] += 1

for account_code, data in sorted(accounts_data.items()):
    print(f"\n{account_code} - {data['account_name']}:")
    print(f"  Entries: {data['count']}")
    print(f"  Total Debit: GHS {data['total_debit']:,.2f}")
    print(f"  Total Credit: GHS {data['total_credit']:,.2f}")

# Verify sum of account totals matches overall totals
account_debit_sum = sum(data['total_debit'] for data in accounts_data.values())
account_credit_sum = sum(data['total_credit'] for data in accounts_data.values())

print(f"\n" + "=" * 80)
print("ACCOUNT TOTALS VERIFICATION:")
print("=" * 80)
print(f"  Sum of Account Debits: GHS {account_debit_sum:,.2f}")
print(f"  Sum of Account Credits: GHS {account_credit_sum:,.2f}")
print(f"  Matches Overall Debits: {'[OK]' if abs(account_debit_sum - total_debits) < 0.01 else '[ERROR]'}")
print(f"  Matches Overall Credits: {'[OK]' if abs(account_credit_sum - total_credits) < 0.01 else '[ERROR]'}")

# Expected totals from image
expected_debit = Decimal('918301.31')
expected_credit = Decimal('0.00')

print(f"\n" + "=" * 80)
print("COMPARISON WITH EXPECTED TOTALS (from image):")
print("=" * 80)
print(f"  Expected Debit: GHS {expected_debit:,.2f}")
print(f"  Actual Debit: GHS {total_debits:,.2f}")
print(f"  Match: {'[OK]' if abs(total_debits - expected_debit) < 0.01 else '[ERROR]'}")

print(f"  Expected Credit: GHS {expected_credit:,.2f}")
print(f"  Actual Credit: GHS {total_credits:,.2f}")
print(f"  Match: {'[OK]' if abs(total_credits - expected_credit) < 0.01 else '[ERROR]'}")

if abs(total_debits - expected_debit) > 0.01 or abs(total_credits - expected_credit) > 0.01:
    print(f"\n[WARN] Totals don't match expected values!")
    print(f"  Difference in Debit: GHS {abs(total_debits - expected_debit):,.2f}")
    print(f"  Difference in Credit: GHS {abs(total_credits - expected_credit):,.2f}")
else:
    print(f"\n[OK] All totals match expected values!")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)

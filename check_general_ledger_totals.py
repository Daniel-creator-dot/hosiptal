"""
Check General Ledger Totals - Verify Calculations
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting_advanced import AdvancedGeneralLedger
from django.db.models import Sum
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

print("=" * 80)
print("CHECKING GENERAL LEDGER TOTALS")
print("=" * 80)

# Get date range (default to this month)
today = timezone.now().date()
start_date = today.replace(day=1)
end_date = today

# Or use specific date from image (Jan 7, 2026)
check_date = datetime(2026, 1, 7).date()
print(f"\nChecking entries for: {check_date.strftime('%B %d, %Y')}")

# Get all entries for this date
ledger_entries = AdvancedGeneralLedger.objects.filter(
    transaction_date=check_date,
    is_voided=False
).select_related('account').order_by('account', 'transaction_date')

print(f"\nTotal entries found: {ledger_entries.count()}")

# Calculate totals
total_debits = ledger_entries.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
total_credits = ledger_entries.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')

print(f"\n" + "=" * 80)
print("TOTALS:")
print("=" * 80)
print(f"  Total Debits: GHS {total_debits:,.2f}")
print(f"  Total Credits: GHS {total_credits:,.2f}")
print(f"  Difference: GHS {abs(total_debits - total_credits):,.2f}")

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
            'entries': [],
            'total_debit': Decimal('0.00'),
            'total_credit': Decimal('0.00'),
        }
    
    accounts_data[account_code]['entries'].append(entry)
    accounts_data[account_code]['total_debit'] += entry.debit_amount
    accounts_data[account_code]['total_credit'] += entry.credit_amount

for account_code, data in sorted(accounts_data.items()):
    print(f"\n{account_code} - {data['account_name']}:")
    print(f"  Entries: {len(data['entries'])}")
    print(f"  Total Debit: GHS {data['total_debit']:,.2f}")
    print(f"  Total Credit: GHS {data['total_credit']:,.2f}")
    
    # Show individual entries
    for entry in data['entries'][:5]:  # Show first 5
        balance_display = entry.debit_amount if entry.debit_amount > 0 else entry.credit_amount
        print(f"    - {entry.description[:50]}: Debit GHS {entry.debit_amount:,.2f}, Balance GHS {balance_display:,.2f}")
    if len(data['entries']) > 5:
        print(f"    ... and {len(data['entries']) - 5} more entries")

# Verify arithmetic
print(f"\n" + "=" * 80)
print("VERIFICATION:")
print("=" * 80)

# Manual sum of all debits
manual_debit_sum = sum(entry.debit_amount for entry in ledger_entries)
print(f"  Manual Sum of Debits: GHS {manual_debit_sum:,.2f}")
print(f"  Database Aggregate: GHS {total_debits:,.2f}")
print(f"  Match: {'[OK]' if abs(manual_debit_sum - total_debits) < 0.01 else '[ERROR]'}")

# Manual sum of all credits
manual_credit_sum = sum(entry.credit_amount for entry in ledger_entries)
print(f"  Manual Sum of Credits: GHS {manual_credit_sum:,.2f}")
print(f"  Database Aggregate: GHS {total_credits:,.2f}")
print(f"  Match: {'[OK]' if abs(manual_credit_sum - total_credits) < 0.01 else '[ERROR]'}")

print("\n" + "=" * 80)
print("CHECK COMPLETE")
print("=" * 80)

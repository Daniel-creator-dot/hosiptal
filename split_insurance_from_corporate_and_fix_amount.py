"""
Split Insurance companies from Corporate accounts
Keep only insurance in 1201, move corporate to separate account
Target: ~GHS 600,834.40 for insurance
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account
from django.db import transaction
from decimal import Decimal

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("SPLIT INSURANCE FROM CORPORATE")
print("Keep only Insurance in 1201")
print("Target: ~GHS 600,834.40")
print("=" * 80)

# Insurance company keywords
insurance_keywords = [
    'insurance', 'health insurance', 'medical insurance', 'health',
    'glico', 'metropolitan', 'nationwide', 'premier', 'equity',
    'cosmopolitan', 'apex', 'acacia', 'ace medical', 'gab health'
]

# Corporate keywords (non-insurance)
corporate_keywords = [
    'electricity', 'electrical', 'company limited', 'ltd', 'limited',
    'university', 'church', 'bank', 'motors', 'logistics', 'supply',
    'football', 'fc', 'olympics', 'calbank'
]

acc_1201 = Account.objects.filter(account_code='1201', is_deleted=False).first()
if not acc_1201:
    print("  [ERROR] Account 1201 not found!")
    exit(1)

print(f"\n1. Analyzing entries in account 1201...")
print("-" * 80)

if HAS_ADVANCED:
    entries = AdvancedGeneralLedger.objects.filter(
        account=acc_1201,
        is_voided=False,
        is_deleted=False
    ).order_by('transaction_date', 'created', 'id')
    
    insurance_entries = []
    corporate_entries = []
    insurance_total = Decimal('0.00')
    corporate_total = Decimal('0.00')
    
    for entry in entries:
        desc_lower = entry.description.lower()
        is_insurance = False
        is_corporate = False
        
        # Check if insurance
        for keyword in insurance_keywords:
            if keyword.lower() in desc_lower:
                is_insurance = True
                break
        
        # Check if corporate
        if not is_insurance:
            for keyword in corporate_keywords:
                if keyword.lower() in desc_lower:
                    is_corporate = True
                    break
        
        if is_insurance:
            insurance_entries.append(entry)
            insurance_total += entry.debit_amount
        elif is_corporate:
            corporate_entries.append(entry)
            corporate_total += entry.debit_amount
        else:
            # Unknown - check description more carefully
            print(f"  [UNKNOWN] {entry.description[:50]}")
            # Default to insurance if has "Accounts Receivable"
            if 'accounts receivable' in desc_lower:
                insurance_entries.append(entry)
                insurance_total += entry.debit_amount
            else:
                corporate_entries.append(entry)
                corporate_total += entry.debit_amount
    
    print(f"\n  Insurance entries: {len(insurance_entries)}")
    print(f"  Insurance total: GHS {insurance_total:,.2f}")
    print(f"\n  Corporate entries: {len(corporate_entries)}")
    print(f"  Corporate total: GHS {corporate_total:,.2f}")
    
    # Show insurance entries
    print(f"\n  Insurance companies:")
    for entry in insurance_entries:
        print(f"    - {entry.description}: GHS {entry.debit_amount:,.2f}")
    
    # Show corporate entries
    print(f"\n  Corporate accounts:")
    for entry in corporate_entries:
        print(f"    - {entry.description}: GHS {entry.debit_amount:,.2f}")
    
    # Check if insurance total matches target
    target = Decimal('600834.40')
    print(f"\n2. Comparing to target...")
    print("-" * 80)
    print(f"  Insurance total: GHS {insurance_total:,.2f}")
    print(f"  Target: GHS {target:,.2f}")
    print(f"  Difference: GHS {abs(insurance_total - target):,.2f}")
    
    if abs(insurance_total - target) < Decimal('10000'):
        print(f"  [OK] Insurance total is close to target!")
    else:
        print(f"  [NOTE] Insurance total differs from target")
    
    # Move corporate entries to account 1200 (or create new)
    if corporate_entries:
        print(f"\n3. Moving corporate entries to account 1200...")
        print("-" * 80)
        
        acc_1200, created = Account.objects.get_or_create(
            account_code='1200',
            defaults={
                'account_name': 'Corporate Accounts Receivable',
                'account_type': 'asset',
                'is_active': True,
            }
        )
        
        if not created:
            acc_1200.account_name = 'Corporate Accounts Receivable'
            acc_1200.save()
        
        moved_count = 0
        with transaction.atomic():
            for entry in corporate_entries:
                entry.account = acc_1200
                entry.save()
                moved_count += 1
        
        print(f"  [OK] Moved {moved_count} corporate entries to account 1200")
        
        # Verify 1201 now only has insurance
        remaining_1201 = AdvancedGeneralLedger.objects.filter(
            account=acc_1201,
            is_voided=False,
            is_deleted=False
        )
        remaining_debits = sum(e.debit_amount for e in remaining_1201)
        remaining_credits = sum(e.credit_amount for e in remaining_1201)
        new_balance = remaining_debits - remaining_credits
        
        print(f"\n4. Final balances...")
        print("-" * 80)
        print(f"  Account 1201 (Insurance): GHS {new_balance:,.2f} ({remaining_1201.count()} entries)")
        
        corporate_1200 = AdvancedGeneralLedger.objects.filter(
            account=acc_1200,
            is_voided=False,
            is_deleted=False
        )
        corp_debits = sum(e.debit_amount for e in corporate_1200)
        corp_credits = sum(e.credit_amount for e in corporate_1200)
        corp_balance = corp_debits - corp_credits
        print(f"  Account 1200 (Corporate): GHS {corp_balance:,.2f} ({corporate_1200.count()} entries)")

print("\n" + "=" * 80)
print("SPLIT COMPLETE")
print("=" * 80)

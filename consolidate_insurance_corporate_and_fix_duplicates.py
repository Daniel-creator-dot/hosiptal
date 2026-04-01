"""
Consolidate Insurance and Corporate accounts into one (1201)
Check for duplicates in GL and Trial Balance
Fix all issues
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_accounting import Account, GeneralLedger
from django.db import transaction
from django.db.models import Sum, Q
from decimal import Decimal
from collections import defaultdict

# Try to import AdvancedGeneralLedger
try:
    from hospital.models_accounting_advanced import AdvancedGeneralLedger
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False

print("=" * 80)
print("CONSOLIDATE INSURANCE & CORPORATE ACCOUNTS")
print("Check for Duplicates and Fix")
print("=" * 80)

# Step 1: Find all insurance and corporate accounts
print("\n1. Finding all Insurance and Corporate accounts...")
print("-" * 80)

# Find accounts with insurance/corporate in name or code starting with 12xx
insurance_accounts = Account.objects.filter(
    Q(account_name__icontains='insurance') |
    Q(account_name__icontains='corporate') |
    Q(account_name__icontains='receivable') |
    Q(account_code__startswith='12')
).filter(is_deleted=False).distinct()

print(f"  Found {insurance_accounts.count()} insurance/corporate accounts:")
for acc in insurance_accounts:
    print(f"    - {acc.account_code}: {acc.account_name} ({acc.account_type})")

# Step 2: Get or create main Insurance Receivables account (1201)
print("\n2. Setting up main Insurance Receivables account (1201)...")
print("-" * 80)

main_account, created = Account.objects.get_or_create(
    account_code='1201',
    defaults={
        'account_name': 'Insurance Receivables',
        'account_type': 'asset',
        'is_active': True,
    }
)

if not created:
    main_account.account_name = 'Insurance Receivables'
    main_account.account_type = 'asset'
    main_account.is_active = True
    main_account.save()

print(f"  [OK] Main account: {main_account.account_code} - {main_account.account_name}")

# Step 3: Collect all entries from insurance/corporate accounts
print("\n3. Collecting all entries from insurance/corporate accounts...")
print("-" * 80)

all_entries = []
total_debits = Decimal('0.00')
total_credits = Decimal('0.00')

# From GeneralLedger
for account in insurance_accounts:
    gl_entries = GeneralLedger.objects.filter(account=account, is_deleted=False)
    for entry in gl_entries:
        all_entries.append({
            'source': 'GeneralLedger',
            'entry': entry,
            'account': account,
            'debit': entry.debit_amount,
            'credit': entry.credit_amount,
            'date': entry.transaction_date,
            'ref': entry.reference_number,
            'desc': entry.description,
        })
        total_debits += entry.debit_amount
        total_credits += entry.credit_amount

# From AdvancedGeneralLedger
if HAS_ADVANCED:
    for account in insurance_accounts:
        adv_entries = AdvancedGeneralLedger.objects.filter(
            account=account,
            is_voided=False,
            is_deleted=False
        )
        for entry in adv_entries:
            all_entries.append({
                'source': 'AdvancedGeneralLedger',
                'entry': entry,
                'account': account,
                'debit': entry.debit_amount,
                'credit': entry.credit_amount,
                'date': entry.transaction_date,
                'ref': getattr(entry.journal_entry, 'reference_number', '') if hasattr(entry, 'journal_entry') and entry.journal_entry else '',
                'desc': entry.description,
            })
            total_debits += entry.debit_amount
            total_credits += entry.credit_amount

print(f"  Found {len(all_entries)} total entries")
print(f"  Total Debits: GHS {total_debits:,.2f}")
print(f"  Total Credits: GHS {total_credits:,.2f}")
print(f"  Net Balance: GHS {total_debits - total_credits:,.2f}")

# Step 4: Check for duplicates
print("\n4. Checking for duplicates...")
print("-" * 80)

# Group by reference number, date, and amount
duplicate_groups = defaultdict(list)
for entry_data in all_entries:
    key = (
        entry_data['ref'] or 'NO_REF',
        entry_data['date'],
        entry_data['debit'],
        entry_data['credit']
    )
    duplicate_groups[key].append(entry_data)

duplicates_found = []
for key, entries in duplicate_groups.items():
    if len(entries) > 1:
        duplicates_found.append(entries)
        print(f"  [DUPLICATE] Found {len(entries)} entries with:")
        print(f"    Ref: {key[0]}, Date: {key[1]}, DR: {key[2]}, CR: {key[3]}")

if not duplicates_found:
    print("  [OK] No duplicates found")
else:
    print(f"  [WARNING] Found {len(duplicates_found)} duplicate groups")

# Step 5: Consolidate to main account (1201)
print("\n5. Consolidating all entries to account 1201...")
print("-" * 80)

# Get existing entries for 1201
existing_1201_gl = GeneralLedger.objects.filter(account=main_account, is_deleted=False)
existing_1201_adv = []
if HAS_ADVANCED:
    existing_1201_adv = list(AdvancedGeneralLedger.objects.filter(
        account=main_account,
        is_voided=False,
        is_deleted=False
    ))

print(f"  Current 1201 entries: GL={existing_1201_gl.count()}, Adv={len(existing_1201_adv)}")

# Calculate what should be in 1201
expected_balance = total_debits - total_credits  # Asset account
print(f"  Expected balance for 1201: GHS {expected_balance:,.2f}")

# Step 6: Move entries from other accounts to 1201 (mark old as deleted, create new in 1201)
print("\n6. Moving entries to account 1201...")
print("-" * 80)

moved_count = 0
with transaction.atomic():
    # Process GeneralLedger entries
    for entry_data in all_entries:
        if entry_data['source'] == 'GeneralLedger':
            entry = entry_data['entry']
            if entry.account.account_code != '1201':
                # Mark old entry as deleted
                entry.is_deleted = True
                entry.save()
                
                # Create new entry in 1201 (if not duplicate)
                # Check if this exact entry already exists in 1201
                existing = GeneralLedger.objects.filter(
                    account=main_account,
                    transaction_date=entry.transaction_date,
                    reference_number=entry.reference_number,
                    debit_amount=entry.debit_amount,
                    credit_amount=entry.credit_amount,
                    is_deleted=False
                ).first()
                
                if not existing:
                    GeneralLedger.objects.create(
                        account=main_account,
                        transaction_date=entry.transaction_date,
                        reference_number=entry.reference_number,
                        reference_type=entry.reference_type,
                        reference_id=entry.reference_id,
                        description=entry.description,
                        debit_amount=entry.debit_amount,
                        credit_amount=entry.credit_amount,
                        entered_by=entry.entered_by,
                    )
                    moved_count += 1

    # Process AdvancedGeneralLedger entries
    if HAS_ADVANCED:
        for entry_data in all_entries:
            if entry_data['source'] == 'AdvancedGeneralLedger':
                entry = entry_data['entry']
                if entry.account.account_code != '1201':
                    # Mark old entry as voided/deleted
                    entry.is_voided = True
                    entry.is_deleted = True
                    entry.save()
                    
                    # Create new entry in 1201 (if not duplicate)
                    ref_num = getattr(entry.journal_entry, 'reference_number', '') if hasattr(entry, 'journal_entry') and entry.journal_entry else ''
                    existing = AdvancedGeneralLedger.objects.filter(
                        account=main_account,
                        transaction_date=entry.transaction_date,
                        description=entry.description,
                        debit_amount=entry.debit_amount,
                        credit_amount=entry.credit_amount,
                        is_voided=False,
                        is_deleted=False
                    ).first()
                    
                    if not existing and entry.journal_entry:
                        AdvancedGeneralLedger.objects.create(
                            journal_entry=entry.journal_entry,
                            journal_entry_line=entry.journal_entry_line,
                            account=main_account,
                            cost_center=entry.cost_center,
                            transaction_date=entry.transaction_date,
                            posting_date=entry.posting_date,
                            description=entry.description,
                            debit_amount=entry.debit_amount,
                            credit_amount=entry.credit_amount,
                            fiscal_year=entry.fiscal_year,
                            accounting_period=entry.accounting_period,
                        )
                        moved_count += 1

print(f"  [OK] Moved {moved_count} entries to account 1201")

# Step 7: Remove duplicates from 1201
print("\n7. Removing duplicates from account 1201...")
print("-" * 80)

duplicates_removed = 0
with transaction.atomic():
    # Check GeneralLedger duplicates
    gl_entries_1201 = GeneralLedger.objects.filter(account=main_account, is_deleted=False)
    seen = set()
    for entry in gl_entries_1201.order_by('transaction_date', 'created', 'id'):
        key = (entry.transaction_date, entry.reference_number, entry.debit_amount, entry.credit_amount)
        if key in seen:
            entry.is_deleted = True
            entry.save()
            duplicates_removed += 1
        else:
            seen.add(key)
    
    # Check AdvancedGeneralLedger duplicates
    if HAS_ADVANCED:
        adv_entries_1201 = AdvancedGeneralLedger.objects.filter(
            account=main_account,
            is_voided=False,
            is_deleted=False
        )
        seen = set()
        for entry in adv_entries_1201.order_by('transaction_date', 'created', 'id'):
            ref = getattr(entry.journal_entry, 'reference_number', '') if hasattr(entry, 'journal_entry') and entry.journal_entry else ''
            key = (entry.transaction_date, ref, entry.debit_amount, entry.credit_amount)
            if key in seen:
                entry.is_voided = True
                entry.is_deleted = True
                entry.save()
                duplicates_removed += 1
            else:
                seen.add(key)

print(f"  [OK] Removed {duplicates_removed} duplicate entries")

# Step 8: Recalculate balance for 1201
print("\n8. Recalculating balance for account 1201...")
print("-" * 80)

if HAS_ADVANCED:
    adv_entries = AdvancedGeneralLedger.objects.filter(
        account=main_account,
        is_voided=False,
        is_deleted=False
    )
    adv_debits = adv_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
    adv_credits = adv_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
else:
    adv_debits = Decimal('0.00')
    adv_credits = Decimal('0.00')

gl_entries = GeneralLedger.objects.filter(account=main_account, is_deleted=False)
gl_debits = gl_entries.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
gl_credits = gl_entries.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')

total_debits = gl_debits + adv_debits
total_credits = gl_credits + adv_credits
final_balance = total_debits - total_credits

print(f"  GeneralLedger: {gl_entries.count()} entries")
print(f"    Debits: GHS {gl_debits:,.2f}, Credits: GHS {gl_credits:,.2f}")
if HAS_ADVANCED:
    print(f"  AdvancedGeneralLedger: {adv_entries.count()} entries")
    print(f"    Debits: GHS {adv_debits:,.2f}, Credits: GHS {adv_credits:,.2f}")
print(f"  Final Balance: GHS {final_balance:,.2f}")

print("\n" + "=" * 80)
print("CONSOLIDATION COMPLETE")
print("=" * 80)
print(f"\nSummary:")
print(f"  - Insurance/Corporate accounts found: {insurance_accounts.count()}")
print(f"  - Entries moved to 1201: {moved_count}")
print(f"  - Duplicates removed: {duplicates_removed}")
print(f"  - Final balance (1201): GHS {final_balance:,.2f}")
print(f"\n[OK] All insurance and corporate accounts consolidated to 1201!")

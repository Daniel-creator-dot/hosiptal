"""
Populate Creditors and Debtors from JERRY.xlsx
- Debtors = Insurance Companies (create as Payers with payer_type='private')
- Creditors = Suppliers (create as Suppliers, NOT as insurance)
"""
import os
import sys
import django
from decimal import Decimal
from datetime import date, timedelta
import json

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import transaction
from django.utils import timezone
from hospital.models import Payer
from hospital.models_missing_features import Supplier
from hospital.models_accounting_advanced import AccountsPayable, Account, AdvancedJournalEntry, AdvancedJournalEntryLine, Journal

def get_or_create_account(account_code, account_name, account_type):
    """Get or create an account"""
    account, created = Account.objects.get_or_create(
        account_code=account_code,
        defaults={
            'account_name': account_name,
            'account_type': account_type,
            'is_active': True,
        }
    )
    return account, created

def get_or_create_journal(code, name, journal_type):
    """Get or create a journal"""
    journal, created = Journal.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'journal_type': journal_type,
        }
    )
    return journal, created

@transaction.atomic
def populate_debtors(debtors_data):
    """
    Populate debtors (Insurance Companies)
    - Create/update Payer records with payer_type='private'
    - Create InsuranceReceivableEntry records
    """
    print("\n" + "="*80)
    print("POPULATING DEBTORS (INSURANCE COMPANIES)")
    print("="*80)
    
    # Get or create Insurance Receivable account
    ar_account, _ = get_or_create_account(
        '1201',
        'Insurance Receivables',
        'asset'
    )
    
    # Get or create Sales Journal
    sales_journal, _ = get_or_create_journal(
        'SALES',
        'Sales Journal',
        'sales'
    )
    
    created_payers = 0
    updated_payers = 0
    created_receivables = 0
    
    for debtor in debtors_data:
        if debtor['name'].upper() == 'TOTAL':
            continue
            
        company_name = debtor['name'].strip()
        balance = Decimal(str(abs(debtor['balance'])))
        
        if balance <= 0:
            continue
        
        # Create or get Payer (Insurance Company)
        payer, created = Payer.objects.get_or_create(
            name=company_name,
            defaults={
                'payer_type': 'private',  # Private Insurance
                'is_active': True,
            }
        )
        
        if created:
            created_payers += 1
            print(f"[OK] Created Payer: {company_name} (payer_type='private')")
        else:
            # Update existing payer to ensure it's insurance type
            if payer.payer_type not in ['private', 'nhis']:
                payer.payer_type = 'private'
                payer.is_active = True
                payer.save()
                updated_payers += 1
                print(f"[UPDATE] Updated Payer: {company_name} -> payer_type='private'")
        
        # Check if journal entry already exists for this payer
        payer_ar_account_code = f'1201-{payer.id}'
        existing_je = AdvancedJournalEntry.objects.filter(
            reference__icontains=company_name[:20],
            entry_date=date(2025, 12, 31)
        ).first()
        
        if not existing_je:
            # Create journal entry directly (opening balance)
            try:
                je = AdvancedJournalEntry.objects.create(
                    journal=sales_journal,
                    entry_date=date(2025, 12, 31),
                    posting_date=date(2025, 12, 31),
                    reference=f"IR-{payer.name[:20]}",
                    description=f"Insurance Receivable - {company_name}",
                    status='posted',
                    posted_by=None,
                )
                
                # Get or create AR account for this specific payer
                payer_ar_account, _ = get_or_create_account(
                    payer_ar_account_code,
                    f'Accounts Receivable - {payer.name}',
                    'asset'
                )
                
                # Get revenue account (Pharmacy Revenue)
                revenue_account, _ = get_or_create_account(
                    '4130',
                    'Pharmacy Revenue',
                    'revenue'
                )
                
                # Debit: Accounts Receivable
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=1,
                    account=payer_ar_account,
                    description=f"AR - {company_name}",
                    debit_amount=balance,
                    credit_amount=0,
                )
                
                # Credit: Revenue
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=2,
                    account=revenue_account,
                    description=f"Revenue - {company_name}",
                    debit_amount=0,
                    credit_amount=balance,
                )
                
                je.total_debit = balance
                je.total_credit = balance
                je.save()
                
                created_receivables += 1
                print(f"  [CREATED] Receivable Entry: {company_name} = GHS {balance:,.2f}")
                print(f"    [OK] Created Journal Entry: JE-{je.id}")
            except Exception as e:
                print(f"    [WARNING] Journal Entry creation failed: {e}")
        else:
            print(f"  [SKIP] Journal Entry already exists: {company_name} = GHS {balance:,.2f}")
    
    print(f"\nSummary:")
    print(f"  Created Payers: {created_payers}")
    print(f"  Updated Payers: {updated_payers}")
    print(f"  Created Receivables: {created_receivables}")

@transaction.atomic
def populate_creditors(creditors_data):
    """
    Populate creditors (Suppliers)
    - Create/update Supplier records (NOT Payers)
    - Create AccountsPayable records
    """
    print("\n" + "="*80)
    print("POPULATING CREDITORS (SUPPLIERS)")
    print("="*80)
    
    # Get or create Accounts Payable account
    ap_account, _ = get_or_create_account(
        '3000',
        'Accounts Payable',
        'liability'
    )
    
    # Get or create Purchases account
    purchases_account, _ = get_or_create_account(
        '5100',
        'Purchases',
        'expense'
    )
    
    # Get or create Purchase Journal
    purchase_journal, _ = get_or_create_journal(
        'PURCHASE',
        'Purchase Journal',
        'purchase'
    )
    
    created_suppliers = 0
    updated_suppliers = 0
    created_payables = 0
    
    for creditor in creditors_data:
        if creditor['name'].upper() == 'TOTAL':
            continue
            
        supplier_name = creditor['name'].strip()
        balance = Decimal(str(abs(creditor['balance'])))  # Use absolute value (creditors are negative)
        
        if balance <= 0:
            continue
        
        # Create or get Supplier (NOT a Payer!)
        supplier, created = Supplier.objects.get_or_create(
            name=supplier_name,
            defaults={
                'is_active': True,
            }
        )
        
        if created:
            created_suppliers += 1
            print(f"[OK] Created Supplier: {supplier_name}")
        else:
            supplier.is_active = True
            supplier.save()
            updated_suppliers += 1
            print(f"[UPDATE] Updated Supplier: {supplier_name}")
        
        # Check if Accounts Payable already exists for this supplier
        existing_ap = AccountsPayable.objects.filter(
            vendor_name=supplier_name,
            balance_due=balance,
            amount_paid=0
        ).first()
        
        if not existing_ap:
            # Generate bill number
            from datetime import datetime
            bill_prefix = "AP"
            year_month = datetime.now().strftime('%Y%m')
            ap_count = AccountsPayable.objects.filter(
                bill_number__startswith=f"{bill_prefix}{year_month}"
            ).count()
            bill_number = f"{bill_prefix}{year_month}{ap_count + 1:05d}"
            
            # Create Accounts Payable
            ap = AccountsPayable.objects.create(
                bill_number=bill_number,
                vendor_name=supplier_name,
                vendor_invoice=f"INV-{supplier_name[:20]}-{year_month}",
                bill_date=date(2025, 12, 31),  # As per Excel date
                due_date=date(2025, 12, 31) + timedelta(days=30),  # 30 days payment terms
                amount=balance,
                amount_paid=Decimal('0.00'),
                balance_due=balance,
                description=f"Opening Balance - {supplier_name}",
                supply_type='goods',  # Default to goods
            )
            created_payables += 1
            print(f"  [CREATED] Accounts Payable: {supplier_name} = GHS {balance:,.2f}")
            
            # Create journal entry
            try:
                je = AdvancedJournalEntry.objects.create(
                    journal=purchase_journal,
                    entry_date=date(2025, 12, 31),
                    posting_date=date(2025, 12, 31),
                    reference=f"AP-{supplier_name[:20]}",
                    description=f"Accounts Payable - {supplier_name}",
                    status='posted',
                    posted_by=None,
                )
                
                # Get or create AP account for this specific supplier
                supplier_ap_account, _ = get_or_create_account(
                    f'3000-{supplier.id}',
                    f'Accounts Payable - {supplier.name}',
                    'liability'
                )
                
                # Debit: Purchases (Expense)
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=1,
                    account=purchases_account,
                    description=f"Purchases - {supplier_name}",
                    debit_amount=balance,
                    credit_amount=0,
                )
                
                # Credit: Accounts Payable (Liability)
                AdvancedJournalEntryLine.objects.create(
                    journal_entry=je,
                    line_number=2,
                    account=supplier_ap_account,
                    description=f"AP - {supplier_name}",
                    debit_amount=0,
                    credit_amount=balance,
                )
                
                je.total_debit = balance
                je.total_credit = balance
                je.save()
                
                ap.journal_entry = je
                ap.save()
                
                print(f"    [OK] Created Journal Entry: JE-{je.id}")
            except Exception as e:
                print(f"    [WARNING] Journal Entry creation failed: {e}")
        else:
            print(f"  [SKIP] Accounts Payable already exists: {supplier_name} = GHS {balance:,.2f}")
    
    print(f"\nSummary:")
    print(f"  Created Suppliers: {created_suppliers}")
    print(f"  Updated Suppliers: {updated_suppliers}")
    print(f"  Created Accounts Payable: {created_payables}")

def main():
    """Main function"""
    print("\n" + "="*80)
    print("POPULATING CREDITORS AND DEBTORS FROM JERRY.XLSX")
    print("="*80)
    
    # Load data from JSON file
    try:
        with open('jerry_extracted_data.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ Error: jerry_extracted_data.json not found!")
        print("   Please run extract_jerry_data.py first")
        return
    
    debtors = [d for d in data['debtors'] if d['name'].upper() != 'TOTAL']
    creditors = [c for c in data['creditors'] if c['name'].upper() != 'TOTAL']
    
    print(f"\nData Summary:")
    print(f"  Debtors (Insurance): {len(debtors)}")
    print(f"  Creditors (Suppliers): {len(creditors)}")
    
    # Confirm before proceeding (skip if running non-interactively)
    import sys
    if sys.stdin.isatty():
        response = input("\nWARNING: This will create/update Payers, Suppliers, and accounting entries. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled by user")
            return
    else:
        print("\nWARNING: Running non-interactively. Proceeding with population...")
    
    # Populate debtors (insurance companies)
    populate_debtors(debtors)
    
    # Populate creditors (suppliers)
    populate_creditors(creditors)
    
    print("\n" + "="*80)
    print("POPULATION COMPLETE!")
    print("="*80)
    print("\nNext Steps:")
    print("  1. Review the created Payers (Insurance Companies)")
    print("  2. Review the created Suppliers")
    print("  3. Review the Insurance Receivable Entries")
    print("  4. Review the Accounts Payable entries")
    print("  5. Verify journal entries in the accounting system")

if __name__ == '__main__':
    main()


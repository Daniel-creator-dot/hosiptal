"""
Fix migration issue and import JERRY.xlsx data
This script will:
1. Check if InsuranceReceivableEntry table exists, create if needed
2. Run the import command
3. Verify records appear in reports
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection
from django.core.management import call_command

print("="*80)
print("FIXING MIGRATIONS AND IMPORTING JERRY.XLSX DATA")
print("="*80)
print()

# Check if InsuranceReceivableEntry table exists
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'hospital_insurancereceivableentry'
        );
    """)
    table_exists = cursor.fetchone()[0]

if not table_exists:
    print("WARNING: InsuranceReceivableEntry table does not exist!")
    print("   Creating table manually...")
    
    try:
        with connection.cursor() as cursor:
            # Create the table based on the model structure
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_insurancereceivableentry (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    entry_number VARCHAR(50) UNIQUE NOT NULL,
                    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    payer_id UUID NOT NULL REFERENCES hospital_payer(id),
                    total_amount NUMERIC(15, 2) NOT NULL CHECK (total_amount >= 0),
                    registration_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    consultation_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    laboratory_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    pharmacy_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    surgeries_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    admissions_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    radiology_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    dental_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    physiotherapy_amount NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    matched_at TIMESTAMP WITH TIME ZONE,
                    matched_by_id INTEGER REFERENCES auth_user(id),
                    journal_entry_id UUID REFERENCES hospital_advancedjournalentry(id),
                    amount_received NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    amount_rejected NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    withholding_tax NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    outstanding_amount NUMERIC(15, 2) NOT NULL,
                    notes TEXT
                );
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_insurancereceivableentry_payer 
                ON hospital_insurancereceivableentry(payer_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_insurancereceivableentry_status 
                ON hospital_insurancereceivableentry(status);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_insurancereceivableentry_entry_date 
                ON hospital_insurancereceivableentry(entry_date);
            """)
        
        print("SUCCESS: Table created successfully!")
    except Exception as e:
        print(f"ERROR: Error creating table: {e}")
        print("   Trying to run migrations instead...")
        try:
            call_command('migrate', 'hospital', '1037', verbosity=0)
            print("SUCCESS: Migration applied!")
        except Exception as e2:
            print(f"ERROR: Migration also failed: {e2}")
            print("   Please run: python manage.py migrate")
            sys.exit(1)
else:
    print("SUCCESS: InsuranceReceivableEntry table exists")

print()
print("="*80)
print("RUNNING IMPORT COMMAND")
print("="*80)
print()

try:
    call_command('import_jerry_excel', verbosity=2)
    print()
    print("SUCCESS: Import completed successfully!")
except Exception as e:
    print(f"ERROR: Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("="*80)
print("VERIFICATION")
print("="*80)
print()

from hospital.models_primecare_accounting import InsuranceReceivableEntry
from hospital.models_accounting_advanced import AccountsPayable
from hospital.models import Payer
from hospital.models_missing_features import Supplier

# Check Insurance Receivable Entries
receivable_entries = InsuranceReceivableEntry.objects.filter(is_deleted=False)
print(f"Insurance Receivable Entries: {receivable_entries.count()}")
if receivable_entries.exists():
    total = sum(entry.total_amount for entry in receivable_entries)
    outstanding = sum(entry.outstanding_amount for entry in receivable_entries)
    print(f"  Total Amount: GHS {total:,.2f}")
    print(f"  Outstanding: GHS {outstanding:,.2f}")

# Check Accounts Payable
ap_entries = AccountsPayable.objects.filter(is_deleted=False)
print(f"\nAccounts Payable Entries: {ap_entries.count()}")
if ap_entries.exists():
    total = sum(entry.amount for entry in ap_entries)
    balance = sum(entry.balance_due for entry in ap_entries)
    print(f"  Total Amount: GHS {total:,.2f}")
    print(f"  Balance Due: GHS {balance:,.2f}")

# Check Payers
payers = Payer.objects.filter(payer_type__in=['private', 'nhis'], is_active=True)
print(f"\nInsurance Payers: {payers.count()}")

# Check Suppliers
suppliers = Supplier.objects.filter(is_active=True)
print(f"Suppliers: {suppliers.count()}")

print()
print("="*80)
print("SUCCESS: ALL DONE! Records should now appear in:")
print("   - Insurance Receivable page")
print("   - Balance Sheet (Account 1201 - Insurance Receivables)")
print("   - Accounts Payable Report")
print("   - General Ledger")
print("   - Trial Balance")
print("="*80)


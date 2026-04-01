"""
Create missing PrimeCare accounting tables if they don't exist
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.db import connection

print("="*80)
print("CREATING MISSING PRIMECARE ACCOUNTING TABLES")
print("="*80)
print()

# Check and create InsurancePaymentReceived table
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'hospital_insurancepaymentreceived'
        );
    """)
    table_exists = cursor.fetchone()[0]

if not table_exists:
    print("WARNING: InsurancePaymentReceived table does not exist!")
    print("   Creating table manually...")
    
    try:
        with connection.cursor() as cursor:
            # Create the table based on the model structure
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_insurancepaymentreceived (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    entry_number VARCHAR(50) UNIQUE NOT NULL,
                    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    payer_id UUID NOT NULL REFERENCES hospital_payer(id),
                    receivable_entry_id UUID REFERENCES hospital_insurancereceivableentry(id),
                    total_amount NUMERIC(15, 2) NOT NULL CHECK (total_amount >= 0),
                    amount_received NUMERIC(15, 2) NOT NULL CHECK (amount_received >= 0),
                    amount_rejected NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    withholding_tax NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    withholding_tax_rate NUMERIC(5, 2) NOT NULL DEFAULT 0,
                    bank_account_id UUID REFERENCES hospital_bankaccount(id),
                    payment_reference VARCHAR(100),
                    journal_entry_id UUID REFERENCES hospital_advancedjournalentry(id),
                    processed_by_id INTEGER REFERENCES auth_user(id),
                    notes TEXT
                );
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_insurancepaymentreceived_payer 
                ON hospital_insurancepaymentreceived(payer_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_insurancepaymentreceived_entry_date 
                ON hospital_insurancepaymentreceived(entry_date);
            """)
        
        print("SUCCESS: InsurancePaymentReceived table created successfully!")
    except Exception as e:
        print(f"ERROR: Error creating table: {e}")
        print("   Trying to run migrations instead...")
        try:
            from django.core.management import call_command
            call_command('migrate', 'hospital', '1037', verbosity=0)
            print("SUCCESS: Migration applied!")
        except Exception as e2:
            print(f"ERROR: Migration also failed: {e2}")
            print("   Please run: python manage.py migrate")
            sys.exit(1)
else:
    print("SUCCESS: InsurancePaymentReceived table exists")

# Check and create UndepositedFunds table
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'hospital_undepositedfunds'
        );
    """)
    table_exists = cursor.fetchone()[0]

if not table_exists:
    print("WARNING: UndepositedFunds table does not exist!")
    print("   Creating table manually...")
    
    try:
        with connection.cursor() as cursor:
            # Create the table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hospital_undepositedfunds (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    created TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    modified TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                    entry_number VARCHAR(50) UNIQUE NOT NULL,
                    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    amount NUMERIC(15, 2) NOT NULL CHECK (amount >= 0),
                    description TEXT,
                    matched BOOLEAN NOT NULL DEFAULT FALSE,
                    matched_at TIMESTAMP WITH TIME ZONE,
                    matched_by_id INTEGER REFERENCES auth_user(id),
                    journal_entry_id UUID REFERENCES hospital_advancedjournalentry(id)
                );
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_undepositedfunds_entry_date 
                ON hospital_undepositedfunds(entry_date);
            """)
        
        print("SUCCESS: UndepositedFunds table created successfully!")
    except Exception as e:
        print(f"ERROR: Error creating table: {e}")
else:
    print("SUCCESS: UndepositedFunds table exists")

print()
print("="*80)
print("SUCCESS: All PrimeCare accounting tables checked/created!")
print("="*80)


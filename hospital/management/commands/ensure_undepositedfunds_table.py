"""
Create hospital_undepositedfunds and hospital_insurancereceivableentry tables if they don't exist.
Fixes: ProgrammingError when deleting User in admin (Django tries to SET_NULL on matched_by_id).

Run on server: python manage.py ensure_undepositedfunds_table
Or via Docker: docker-compose exec web python manage.py ensure_undepositedfunds_table
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Create PrimeCare accounting tables if missing (fixes User delete error)'

    def handle(self, *args, **options):
        created = []

        with connection.cursor() as cursor:
            # 1. hospital_undepositedfunds
            cursor.execute("""
                SELECT EXISTS (SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'hospital_undepositedfunds');
            """)
            if not cursor.fetchone()[0]:
                self.stdout.write('Creating hospital_undepositedfunds...')
                cursor.execute("""
                    CREATE TABLE hospital_undepositedfunds (
                        id UUID PRIMARY KEY,
                        created TIMESTAMP WITH TIME ZONE NOT NULL,
                        modified TIMESTAMP WITH TIME ZONE NOT NULL,
                        is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                        entry_number VARCHAR(50) UNIQUE NOT NULL,
                        entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
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
                        matched_at TIMESTAMP WITH TIME ZONE NULL,
                        matched_by_id INTEGER NULL REFERENCES auth_user(id) ON DELETE SET NULL,
                        journal_entry_id UUID NULL,
                        bank_account_id UUID NULL,
                        deposit_date DATE NULL,
                        deposit_reference VARCHAR(100) NOT NULL DEFAULT '',
                        notes TEXT NOT NULL DEFAULT ''
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS hospital_undepositedfunds_entry_date_idx ON hospital_undepositedfunds (entry_date DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS hospital_undepositedfunds_status_idx ON hospital_undepositedfunds (status);")
                created.append('hospital_undepositedfunds')

            # 2. hospital_insurancereceivableentry (requires hospital_payer)
            cursor.execute("""
                SELECT EXISTS (SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'hospital_insurancereceivableentry');
            """)
            if not cursor.fetchone()[0]:
                cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'hospital_payer');")
                if cursor.fetchone()[0]:
                    self.stdout.write('Creating hospital_insurancereceivableentry...')
                    cursor.execute("""
                        CREATE TABLE hospital_insurancereceivableentry (
                            id UUID PRIMARY KEY,
                            created TIMESTAMP WITH TIME ZONE NOT NULL,
                            modified TIMESTAMP WITH TIME ZONE NOT NULL,
                            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                            entry_number VARCHAR(50) UNIQUE NOT NULL,
                            entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
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
                            matched_at TIMESTAMP WITH TIME ZONE NULL,
                            matched_by_id INTEGER NULL REFERENCES auth_user(id) ON DELETE SET NULL,
                            journal_entry_id UUID NULL,
                            payer_id UUID NOT NULL REFERENCES hospital_payer(id) ON DELETE RESTRICT,
                            amount_received NUMERIC(15, 2) NOT NULL DEFAULT 0,
                            amount_rejected NUMERIC(15, 2) NOT NULL DEFAULT 0,
                            withholding_tax NUMERIC(15, 2) NOT NULL DEFAULT 0,
                            outstanding_amount NUMERIC(15, 2) NOT NULL,
                            notes TEXT NOT NULL DEFAULT ''
                        );
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS hospital_insurancereceivableentry_entry_date_idx ON hospital_insurancereceivableentry (entry_date DESC);")
                    created.append('hospital_insurancereceivableentry')
                else:
                    self.stdout.write(self.style.WARNING('Skipped hospital_insurancereceivableentry: hospital_payer table not found. Run: python manage.py migrate'))

            # 3. hospital_insurancepaymentreceived (requires bank_account, payer, insurancereceivableentry)
            cursor.execute("""
                SELECT EXISTS (SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'hospital_insurancepaymentreceived');
            """)
            if not cursor.fetchone()[0]:
                for t in ['hospital_bankaccount', 'hospital_payer', 'hospital_insurancereceivableentry']:
                    cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s);", [t])
                    if not cursor.fetchone()[0]:
                        self.stdout.write(self.style.WARNING(f'Skipped hospital_insurancepaymentreceived: {t} not found.'))
                        break
                else:
                    self.stdout.write('Creating hospital_insurancepaymentreceived...')
                    cursor.execute("""
                        CREATE TABLE hospital_insurancepaymentreceived (
                            id UUID PRIMARY KEY,
                            created TIMESTAMP WITH TIME ZONE NOT NULL,
                            modified TIMESTAMP WITH TIME ZONE NOT NULL,
                            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
                            entry_number VARCHAR(50) UNIQUE NOT NULL,
                            entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
                            total_amount NUMERIC(15, 2) NOT NULL CHECK (total_amount >= 0),
                            amount_received NUMERIC(15, 2) NOT NULL CHECK (amount_received >= 0),
                            amount_rejected NUMERIC(15, 2) NOT NULL DEFAULT 0,
                            withholding_tax NUMERIC(15, 2) NOT NULL DEFAULT 0,
                            withholding_tax_rate NUMERIC(5, 2) NOT NULL DEFAULT 0,
                            payment_reference VARCHAR(100) NOT NULL DEFAULT '',
                            notes TEXT NOT NULL DEFAULT '',
                            bank_account_id UUID NOT NULL REFERENCES hospital_bankaccount(id) ON DELETE RESTRICT,
                            journal_entry_id UUID NULL,
                            payer_id UUID NOT NULL REFERENCES hospital_payer(id) ON DELETE RESTRICT,
                            processed_by_id INTEGER NULL REFERENCES auth_user(id) ON DELETE SET NULL,
                            receivable_entry_id UUID NULL REFERENCES hospital_insurancereceivableentry(id) ON DELETE CASCADE
                        );
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS hospital_insurancepaymentreceived_entry_date_idx ON hospital_insurancepaymentreceived (entry_date DESC);")
                    created.append('hospital_insurancepaymentreceived')

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created: {", ".join(created)}'))
        else:
            self.stdout.write(self.style.SUCCESS('All tables already exist.'))

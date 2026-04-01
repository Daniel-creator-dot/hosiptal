# Ensure hospital_undepositedfunds table exists (fixes User delete error when table was never created)

from django.db import migrations, connection


def ensure_undepositedfunds_table(apps, schema_editor):
    """Create hospital_undepositedfunds table if it doesn't exist"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'hospital_undepositedfunds'
            );
        """)
        if cursor.fetchone()[0]:
            return  # Table exists, nothing to do

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hospital_undepositedfunds (
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
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS hospital_undepositedfunds_entry_date_idx 
            ON hospital_undepositedfunds (entry_date DESC);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS hospital_undepositedfunds_status_idx 
            ON hospital_undepositedfunds (status);
        """)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1085_add_lab_imaging_result_attachments'),
    ]

    operations = [
        migrations.RunPython(ensure_undepositedfunds_table, noop),
    ]

# Generated manually for duplicate prevention
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hospital', '1042_remove_batchrecall_completed_by_and_more'),
    ]

    operations = [
        # Safe index creation: Only create if they don't exist
        migrations.RunSQL(
            sql="""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'patient_name_dob_idx') THEN
                        CREATE INDEX patient_name_dob_idx ON hospital_patient(first_name, last_name, date_of_birth);
                    END IF;
                END $$;
            """,
            reverse_sql="DROP INDEX IF EXISTS patient_name_dob_idx;",
        ),
        migrations.RunSQL(
            sql="""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'patient_name_phone_idx') THEN
                        CREATE INDEX patient_name_phone_idx ON hospital_patient(first_name, last_name, phone_number);
                    END IF;
                END $$;
            """,
            reverse_sql="DROP INDEX IF EXISTS patient_name_phone_idx;",
        ),
        migrations.RunSQL(
            sql="""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'patient_email_idx') THEN
                        CREATE INDEX patient_email_idx ON hospital_patient(email);
                    END IF;
                END $$;
            """,
            reverse_sql="DROP INDEX IF EXISTS patient_email_idx;",
        ),
        migrations.RunSQL(
            sql="""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'patient_national_id_idx') THEN
                        CREATE INDEX patient_national_id_idx ON hospital_patient(national_id);
                    END IF;
                END $$;
            """,
            reverse_sql="DROP INDEX IF EXISTS patient_national_id_idx;",
        ),
        migrations.RunSQL(
            sql="""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'patient_phone_idx') THEN
                        CREATE INDEX patient_phone_idx ON hospital_patient(phone_number);
                    END IF;
                END $$;
            """,
            reverse_sql="DROP INDEX IF EXISTS patient_phone_idx;",
        ),
    ]


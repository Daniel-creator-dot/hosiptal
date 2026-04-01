"""
Add unique constraint to prevent duplicate patients at database level
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Add unique constraint to prevent duplicate patients'

    def handle(self, *args, **options):
        self.stdout.write('Adding unique constraints to prevent duplicate patients...')
        
        with connection.cursor() as cursor:
            try:
                # Add unique constraint on first_name + last_name + phone_number (normalized)
                # This is a partial unique index that only applies to non-deleted patients
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS patient_unique_name_phone_idx 
                    ON hospital_patient (LOWER(first_name), LOWER(last_name), 
                    REGEXP_REPLACE(phone_number, '[^0-9]', '', 'g'))
                    WHERE is_deleted = false;
                """)
                self.stdout.write(self.style.SUCCESS('✅ Added unique constraint on name + phone'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Could not add name+phone constraint: {e}'))
            
            try:
                # Add unique constraint on email (if provided)
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS patient_unique_email_idx 
                    ON hospital_patient (LOWER(email))
                    WHERE is_deleted = false AND email IS NOT NULL AND email != '';
                """)
                self.stdout.write(self.style.SUCCESS('✅ Added unique constraint on email'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Could not add email constraint: {e}'))
        
        self.stdout.write(self.style.SUCCESS('Unique constraints added successfully!'))







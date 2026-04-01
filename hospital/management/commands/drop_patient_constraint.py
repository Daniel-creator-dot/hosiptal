"""
Drop the unique constraint on patient that's blocking legitimate registrations
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Drop unique constraint on patient that blocks legitimate registrations'

    def handle(self, *args, **options):
        self.stdout.write('Dropping unique constraint on patient...')
        
        with connection.cursor() as cursor:
            try:
                # Drop the constraint if it exists
                cursor.execute("""
                    ALTER TABLE hospital_patient 
                    DROP CONSTRAINT IF EXISTS uniq_patient_name_phone_dob_active;
                """)
                self.stdout.write(self.style.SUCCESS('✅ Dropped unique constraint'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Could not drop constraint: {e}'))
        
        self.stdout.write(self.style.SUCCESS('Constraint removal completed!'))

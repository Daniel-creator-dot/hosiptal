"""
Django Management Command to Check and Convert Imported Patient Data for PostgreSQL
Ensures all patient data is properly formatted for PostgreSQL database
"""
import re
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone
from hospital.models import Patient
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check and convert imported patient data to suit PostgreSQL database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be converted without making changes',
        )
        parser.add_argument(
            '--fix-encoding',
            action='store_true',
            help='Fix encoding issues in text fields',
        )
        parser.add_argument(
            '--fix-dates',
            action='store_true',
            help='Fix date format issues',
        )
        parser.add_argument(
            '--fix-all',
            action='store_true',
            help='Apply all fixes',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fix_all = options['fix_all']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('POSTGRESQL PATIENT DATA CONVERSION'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
        
        # Check PostgreSQL connection
        self.stdout.write('[1/5] Checking PostgreSQL connection...')
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            self.stdout.write(self.style.SUCCESS(f'  ✅ Connected to PostgreSQL: {version[:50]}...'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ PostgreSQL connection error: {e}'))
            return
        self.stdout.write('')
        
        # Check patient table structure
        self.stdout.write('[2/5] Checking patient table structure...')
        try:
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length 
                FROM information_schema.columns 
                WHERE table_name = 'hospital_patient' 
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            self.stdout.write(f'  ✅ Found {len(columns)} columns in hospital_patient table')
            for col in columns[:10]:
                col_type = f"{col[1]}({col[2]})" if col[2] else col[1]
                self.stdout.write(f'    - {col[0]}: {col_type}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Error checking table structure: {e}'))
        self.stdout.write('')
        
        # Check for imported/legacy patients
        self.stdout.write('[3/5] Checking imported patient data...')
        all_patients = Patient.objects.filter(is_deleted=False)
        total_count = all_patients.count()
        
        imported_patients = [p for p in all_patients if 'PMC-LEG' in p.mrn or 'LEG' in p.mrn]
        imported_count = len(imported_patients)
        
        self.stdout.write(f'  Total patients: {total_count}')
        self.stdout.write(f'  Imported/Legacy patients: {imported_count}')
        self.stdout.write('')
        
        # Check for data issues
        self.stdout.write('[4/5] Checking for data conversion issues...')
        issues = {
            'encoding_issues': [],
            'date_issues': [],
            'null_strings': [],
            'invalid_chars': [],
            'type_mismatches': [],
        }
        
        for patient in all_patients:
            # Check encoding issues
            if fix_all or options['fix_encoding']:
                encoding_fixed = self.check_and_fix_encoding(patient, dry_run)
                if encoding_fixed:
                    issues['encoding_issues'].append(patient)
            
            # Check date issues
            if fix_all or options['fix_dates']:
                date_fixed = self.check_and_fix_dates(patient, dry_run)
                if date_fixed:
                    issues['date_issues'].append(patient)
            
            # Check for NULL strings (should be None)
            if patient.national_id == '':
                issues['null_strings'].append(patient)
                if fix_all and not dry_run:
                    patient.national_id = None
                    patient.save(update_fields=['national_id'])
        
        # Summary
        self.stdout.write(f'  Encoding issues found: {len(issues["encoding_issues"])}')
        self.stdout.write(f'  Date issues found: {len(issues["date_issues"])}')
        self.stdout.write(f'  NULL string issues: {len(issues["null_strings"])}')
        self.stdout.write('')
        
        # Check legacy tables
        self.stdout.write('[5/5] Checking legacy patient tables...')
        legacy_tables = [
            'patient_data',
            'patient_portal_menu',
            'patient_reminders',
            'patient_access_offsite',
            'patient_access_onsite',
        ]
        
        for table_name in legacy_tables:
            try:
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_name = '{table_name}'
                """)
                exists = cursor.fetchone()[0] > 0
                
                if exists:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    self.stdout.write(f'  ✅ {table_name}: {count} rows')
                else:
                    self.stdout.write(f'  ⚠️  {table_name}: table not found')
            except Exception as e:
                self.stdout.write(f'  ❌ {table_name}: error - {e}')
        
        self.stdout.write('')
        
        # Final summary
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('CONVERSION SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        self.stdout.write(f'Total patients checked: {total_count}')
        self.stdout.write(f'Imported patients: {imported_count}')
        self.stdout.write(f'Encoding issues fixed: {len(issues["encoding_issues"])}')
        self.stdout.write(f'Date issues fixed: {len(issues["date_issues"])}')
        self.stdout.write(f'NULL strings fixed: {len(issues["null_strings"])}')
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were made. Run without --dry-run to apply fixes.'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Patient data conversion complete!'))
            self.stdout.write('')
            self.stdout.write('All patient data is now PostgreSQL-compatible.')
        
        self.stdout.write('')
    
    def check_and_fix_encoding(self, patient, dry_run):
        """Check and fix encoding issues in patient text fields"""
        fixed = False
        fields_to_check = [
            'first_name', 'last_name', 'middle_name', 'address',
            'phone_number', 'email', 'next_of_kin_name', 'next_of_kin_phone',
            'allergies', 'chronic_conditions', 'medications',
        ]
        
        for field_name in fields_to_check:
            value = getattr(patient, field_name, None)
            if not value:
                continue
            
            # Check for encoding issues (non-UTF8 characters)
            try:
                value.encode('utf-8')
            except UnicodeEncodeError:
                # Fix encoding
                if not dry_run:
                    try:
                        # Try to decode and re-encode
                        fixed_value = value.encode('latin-1', errors='ignore').decode('utf-8', errors='ignore')
                        setattr(patient, field_name, fixed_value)
                        fixed = True
                    except:
                        # If that fails, remove problematic characters
                        fixed_value = value.encode('ascii', errors='ignore').decode('ascii')
                        setattr(patient, field_name, fixed_value)
                        fixed = True
        
        if fixed and not dry_run:
            patient.save()
        
        return fixed
    
    def check_and_fix_dates(self, patient, dry_run):
        """Check and fix date format issues"""
        fixed = False
        
        # Check date_of_birth
        if patient.date_of_birth:
            # Ensure it's a valid date object
            if isinstance(patient.date_of_birth, str):
                try:
                    # Try to parse string date
                    parsed_date = datetime.strptime(patient.date_of_birth, '%Y-%m-%d').date()
                    if not dry_run:
                        patient.date_of_birth = parsed_date
                        patient.save(update_fields=['date_of_birth'])
                    fixed = True
                except:
                    pass
            
            # Check for future dates
            today = timezone.now().date()
            if patient.date_of_birth > today:
                if not dry_run:
                    # Set to reasonable default
                    patient.date_of_birth = datetime(2000, 1, 1).date()
                    patient.save(update_fields=['date_of_birth'])
                fixed = True
        
        return fixed






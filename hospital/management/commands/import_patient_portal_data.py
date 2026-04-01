"""
Django Management Command to Import Patient Portal Data
Imports patient_portal_menu, patient_reminders, patient_access_offsite, patient_access_onsite
and creates Patient records with QR codes
"""
import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.contrib.auth import get_user_model
from hospital.models import Patient, PatientQRCode
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Import patient portal data and create Patient records with QR codes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-dir',
            type=str,
            default='f:\\',
            help='Directory containing SQL files'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )
        parser.add_argument(
            '--create-patients',
            action='store_true',
            default=True,
            help='Create Patient records for PIDs found in access tables'
        )
    
    def handle(self, *args, **options):
        sql_dir = options['sql_dir']
        dry_run = options['dry_run']
        create_patients = options['create_patients']
        
        if not os.path.exists(sql_dir):
            raise CommandError(f'SQL directory does not exist: {sql_dir}')
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('PATIENT PORTAL DATA IMPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
            self.stdout.write('')
        
        # Files to import
        sql_files = {
            'patient_portal_menu': os.path.join(sql_dir, 'patient_portal_menu.sql'),
            'patient_reminders': os.path.join(sql_dir, 'patient_reminders.sql'),
            'patient_access_offsite': os.path.join(sql_dir, 'patient_access_offsite.sql'),
            'patient_access_onsite': os.path.join(sql_dir, 'patient_access_onsite.sql'),
        }
        
        # Step 1: Import table structures and data
        self.stdout.write(self.style.SUCCESS('[1/3] Importing table structures and data...'))
        imported_tables = []
        rows_imported = 0
        
        for table_name, file_path in sql_files.items():
            if not os.path.exists(file_path):
                self.stdout.write(self.style.WARNING(f'  ⚠️  File not found: {file_path}'))
                continue
            
            try:
                result = self.import_table_structure(file_path, dry_run, table_name)
                if result:
                    imported_tables.append(table_name)
                    # Try to import data if INSERT statements exist
                    rows = self.import_table_data(file_path, dry_run, table_name)
                    rows_imported += rows
                    if rows > 0:
                        self.stdout.write(self.style.SUCCESS(f'  ✅ {table_name} (structure + {rows} rows)'))
                    else:
                        self.stdout.write(self.style.SUCCESS(f'  ✅ {table_name} (structure only)'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ❌ {table_name}: {str(e)}'))
        
        self.stdout.write(f'  Total rows imported: {rows_imported}')
        self.stdout.write('')
        
        # Step 2: Extract patient IDs from access tables
        self.stdout.write(self.style.SUCCESS('[2/3] Extracting patient IDs from access tables...'))
        patient_ids = set()
        
        if not dry_run:
            cursor = connection.cursor()
            
            # Get PIDs from patient_access_offsite
            try:
                cursor.execute("SELECT DISTINCT pid FROM patient_access_offsite WHERE pid IS NOT NULL")
                offsite_pids = [row[0] for row in cursor.fetchall()]
                patient_ids.update(offsite_pids)
                self.stdout.write(f'  Found {len(offsite_pids)} PIDs in patient_access_offsite')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠️  Could not read patient_access_offsite: {e}'))
            
            # Get PIDs from patient_access_onsite
            try:
                cursor.execute("SELECT DISTINCT pid FROM patient_access_onsite WHERE pid IS NOT NULL")
                onsite_pids = [row[0] for row in cursor.fetchall()]
                patient_ids.update(onsite_pids)
                self.stdout.write(f'  Found {len(onsite_pids)} PIDs in patient_access_onsite')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠️  Could not read patient_access_onsite: {e}'))
            
            # Get PIDs from patient_reminders
            try:
                cursor.execute("SELECT DISTINCT pid FROM patient_reminders WHERE pid IS NOT NULL")
                reminder_pids = [row[0] for row in cursor.fetchall()]
                patient_ids.update(reminder_pids)
                self.stdout.write(f'  Found {len(reminder_pids)} PIDs in patient_reminders')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠️  Could not read patient_reminders: {e}'))
            
            self.stdout.write(f'  Total unique PIDs found: {len(patient_ids)}')
        else:
            self.stdout.write('  [DRY RUN] Would extract PIDs from access tables')
            patient_ids = {1, 2, 3}  # Sample for dry run
        
        self.stdout.write('')
        
        # Step 3: Create Patient records and QR codes
        if create_patients and patient_ids:
            self.stdout.write(self.style.SUCCESS('[3/3] Creating Patient records with QR codes...'))
            
            created_count = 0
            updated_count = 0
            qr_created_count = 0
            skipped_count = 0
            
            for pid in sorted(patient_ids):
                try:
                    # Check if patient already exists with this PID as MRN
                    mrn = f"PMC-LEG-{str(pid).zfill(6)}"
                    existing_patient = Patient.objects.filter(mrn=mrn, is_deleted=False).first()
                    
                    if existing_patient:
                        # Patient exists, ensure QR code
                        if not dry_run:
                            qr_profile, created = PatientQRCode.objects.get_or_create(
                                patient=existing_patient
                            )
                            if created or not qr_profile.qr_code_image:
                                qr_profile.refresh_qr(force_token=True)
                                qr_created_count += 1
                            updated_count += 1
                        else:
                            self.stdout.write(f'  [DRY RUN] Would update patient: {mrn}')
                        continue
                    
                    # Create new patient - CHECK FOR DUPLICATES FIRST
                    if not dry_run:
                        with transaction.atomic():
                            # CRITICAL: Check for duplicate MRN before creating
                            existing = Patient.objects.filter(mrn=mrn, is_deleted=False).first()
                            if existing:
                                self.stdout.write(f'  ⚠️ Skipping duplicate MRN: {mrn} (already exists)')
                                skipped_count += 1
                                continue
                            
                            # Create patient with minimal data
                            patient = Patient.objects.create(
                                mrn=mrn,
                                first_name=f"Patient",
                                last_name=f"PID-{pid}",
                                date_of_birth=datetime(2000, 1, 1).date(),
                                gender='M',
                                phone_number='',
                                address='',
                            )
                            
                            # QR code will be created automatically by signal
                            # But let's ensure it exists
                            qr_profile, qr_created = PatientQRCode.objects.get_or_create(
                                patient=patient
                            )
                            if qr_created or not qr_profile.qr_code_image:
                                qr_profile.refresh_qr(force_token=True)
                                qr_created_count += 1
                            
                            created_count += 1
                            
                            if created_count % 10 == 0:
                                self.stdout.write(f'  Progress: {created_count} patients created...')
                    else:
                        self.stdout.write(f'  [DRY RUN] Would create patient: {mrn}')
                        created_count += 1
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Error creating patient for PID {pid}: {str(e)}'))
                    skipped_count += 1
                    continue
            
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(f'  Tables imported: {len(imported_tables)}')
            self.stdout.write(f'  Unique PIDs found: {len(patient_ids)}')
            self.stdout.write(f'  Patients created: {created_count}')
            self.stdout.write(f'  Patients updated: {updated_count}')
            self.stdout.write(f'  QR codes generated: {qr_created_count}')
            self.stdout.write(f'  Skipped: {skipped_count}')
            self.stdout.write('')
            
            if not dry_run:
                self.stdout.write(self.style.SUCCESS('✅ All patients now have QR codes!'))
                self.stdout.write('')
                self.stdout.write('Next steps:')
                self.stdout.write('  1. Update patient details (names, DOB, etc.) from patient_data if available')
                self.stdout.write('  2. View QR codes at: /hms/patients/<id>/qr-card/')
        else:
            self.stdout.write('[3/3] Skipping patient creation (--no-create-patients or no PIDs found)')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Import completed!'))
    
    def import_table_structure(self, file_path, dry_run, table_name):
        """Import table structure from SQL file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            sql_content = f.read()
        
        # Remove DROP TABLE if it exists (we'll handle it separately)
        sql_content = re.sub(r'DROP TABLE.*?;', '', sql_content, flags=re.IGNORECASE)
        
        # Extract CREATE TABLE statement
        create_match = re.search(r'CREATE TABLE.*?;', sql_content, re.DOTALL | re.IGNORECASE)
        if not create_match:
            return False
        
        create_statement = create_match.group(0)
        
        # Convert MySQL syntax to PostgreSQL if needed
        create_statement = self.convert_mysql_to_postgresql(create_statement, table_name)
        
        if dry_run:
            self.stdout.write(f'  [DRY RUN] Would create table: {table_name}')
            return True
        
        # Execute CREATE TABLE
        cursor = connection.cursor()
        try:
            # Drop table if exists (PostgreSQL syntax)
            cursor.execute(f'DROP TABLE IF EXISTS {table_name} CASCADE;')
            
            # Create table
            cursor.execute(create_statement)
            return True
        except Exception as e:
            # Table might already exist or have different structure
            if 'already exists' in str(e).lower():
                self.stdout.write(f'  ⚠️  Table {table_name} already exists, skipping')
                return True
            raise
    
    def convert_mysql_to_postgresql(self, sql, table_name):
        """Convert MySQL CREATE TABLE syntax to PostgreSQL"""
        # Remove MySQL-specific syntax
        sql = sql.replace('`', '"')  # Backticks to double quotes
        sql = sql.replace('ENGINE=InnoDB', '')
        sql = sql.replace('DEFAULT CHARSET=latin1', '')
        sql = sql.replace('AUTO_INCREMENT', 'SERIAL')
        sql = sql.replace('tinyint(1)', 'BOOLEAN')
        sql = sql.replace('tinyint(2)', 'SMALLINT')
        sql = sql.replace('tinyint(4)', 'SMALLINT')
        sql = sql.replace('int(11)', 'INTEGER')
        sql = sql.replace('bigint(20)', 'BIGINT')
        sql = sql.replace('smallint(4)', 'SMALLINT')
        sql = sql.replace('varchar(100)', 'VARCHAR(100)')
        sql = sql.replace('varchar(40)', 'VARCHAR(40)')
        sql = sql.replace('varchar(31)', 'VARCHAR(31)')
        sql = sql.replace('varchar(20)', 'VARCHAR(20)')
        sql = sql.replace('COMMENT', '--')
        
        # Remove trailing commas before closing parenthesis
        sql = re.sub(r',\s*\)', ')', sql)
        
        return sql
    
    def import_table_data(self, file_path, dry_run, table_name):
        """Import INSERT data from SQL file if present"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            sql_content = f.read()
        
        # Find all INSERT statements
        insert_pattern = r'INSERT INTO\s+(?:`)?' + re.escape(table_name) + r'(?:`)?\s+.*?VALUES\s*\((.*?)\);'
        matches = re.findall(insert_pattern, sql_content, re.DOTALL | re.IGNORECASE)
        
        if not matches:
            return 0
        
        if dry_run:
            return len(matches)
        
        cursor = connection.cursor()
        rows_inserted = 0
        
        for match in matches:
            try:
                # Parse values (simplified - handles basic cases)
                values = self.parse_sql_values(match)
                
                # Build INSERT statement for PostgreSQL
                placeholders = ','.join(['%s'] * len(values))
                insert_sql = f'INSERT INTO {table_name} VALUES ({placeholders})'
                
                cursor.execute(insert_sql, values)
                rows_inserted += 1
            except Exception as e:
                # Skip problematic rows
                logger.warning(f'Error inserting row into {table_name}: {e}')
                continue
        
        if rows_inserted > 0:
            connection.commit()
        
        return rows_inserted
    
    def parse_sql_values(self, values_str):
        """Parse SQL VALUES string into a list"""
        import csv
        from io import StringIO
        
        # Clean up the string
        values_str = values_str.strip()
        
        # Handle NULL values
        values_str = re.sub(r'\bNULL\b', 'None', values_str, flags=re.IGNORECASE)
        
        # Use csv reader to handle quoted strings properly
        reader = csv.reader(StringIO(values_str), delimiter=',', quotechar="'")
        try:
            values = list(reader)[0]
            # Convert 'None' strings back to None
            values = [None if v.strip() == 'None' else v.strip().strip("'\"") for v in values]
            return values
        except:
            # Fallback to simple split
            values = [v.strip().strip('"').strip("'") for v in values_str.split(',')]
            values = [None if v.upper() == 'NULL' else v for v in values]
            return values


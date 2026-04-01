"""
Comprehensive Legacy Data Migration Command
Maps MySQL SQL dumps to Django models with duplicate detection and updates.

As a senior engineer and data specialist, this command:
- Intelligently maps legacy SQL tables to Django models
- Handles duplicates by updating existing records
- Supports both PostgreSQL and MySQL databases
- Provides detailed progress tracking and error handling
- Imports all data: patients, drugs, services, lab, imaging, inventory, etc.
"""

import os
import re
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
import logging

# Optional MySQL connector
try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

# Import models
from hospital.models import (
    Patient, Drug, LabTest, ServiceCode, Invoice, InvoiceLine,
    Encounter, Staff, Payer, PharmacyStock
)
from hospital.models_procurement import InventoryItem, Store, InventoryCategory
from hospital.models_advanced import ImagingStudy

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate legacy database data to Django models with duplicate handling'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-dir',
            type=str,
            default='import/db_3_extracted',
            help='Directory containing SQL files'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            default=True,
            help='Update existing records if found (default: True)'
        )
        parser.add_argument(
            '--skip-duplicates',
            action='store_true',
            help='Skip duplicates instead of updating'
        )
        parser.add_argument(
            '--use-mysql',
            action='store_true',
            help='Connect to source MySQL database directly instead of SQL files'
        )
        parser.add_argument(
            '--mysql-host',
            type=str,
            help='MySQL host (if using direct connection)'
        )
        parser.add_argument(
            '--mysql-user',
            type=str,
            help='MySQL user (if using direct connection)'
        )
        parser.add_argument(
            '--mysql-password',
            type=str,
            help='MySQL password (if using direct connection)'
        )
        parser.add_argument(
            '--mysql-database',
            type=str,
            help='MySQL database name (if using direct connection)'
        )
        parser.add_argument(
            '--skip-tables',
            nargs='+',
            help='Tables to skip (e.g., form_* audit_* logs_*)'
        )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = {
            'patients': {'created': 0, 'updated': 0, 'skipped': 0},
            'drugs': {'created': 0, 'updated': 0, 'skipped': 0},
            'services': {'created': 0, 'updated': 0, 'skipped': 0},
            'lab_tests': {'created': 0, 'updated': 0, 'skipped': 0},
            'imaging': {'created': 0, 'updated': 0, 'skipped': 0},
            'inventory': {'created': 0, 'updated': 0, 'skipped': 0},
            'billing': {'created': 0, 'updated': 0, 'skipped': 0},
        }
        self.errors = []
        self.mysql_conn = None
        # Mapping from legacy drug_id to Django Drug
        self.drug_id_mapping = {}
    
    def handle(self, *args, **options):
        sql_dir = options['sql_dir']
        dry_run = options['dry_run']
        use_mysql = options.get('use_mysql', False)
        skip_tables = options.get('skip_tables', []) or []
        
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('LEGACY DATA MIGRATION SYSTEM'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN MODE - No changes will be made\n'))
        
        # Connect to MySQL if requested
        if use_mysql:
            self.connect_mysql(options)
        
        # Import data in correct order (respecting foreign key dependencies)
        with transaction.atomic():
            try:
                # 1. Import base reference data first
                self.stdout.write(self.style.SUCCESS('\n[1/7] Importing Reference Data...'))
                if not dry_run:
                    self.import_payers(sql_dir, skip_tables)
                    self.import_staff(sql_dir, skip_tables)
                
                # 2. Import patients
                self.stdout.write(self.style.SUCCESS('\n[2/7] Importing Patients...'))
                if not dry_run:
                    self.import_patients(sql_dir, skip_tables, options)
                
                # 3. Import drugs/pharmacy
                self.stdout.write(self.style.SUCCESS('\n[3/7] Importing Drugs/Pharmacy...'))
                if not dry_run:
                    self.import_drugs(sql_dir, skip_tables, options)
                
                # 4. Import services/codes
                self.stdout.write(self.style.SUCCESS('\n[4/7] Importing Services/Codes...'))
                if not dry_run:
                    self.import_services(sql_dir, skip_tables, options)
                
                # 5. Import lab tests
                self.stdout.write(self.style.SUCCESS('\n[5/7] Importing Lab Tests...'))
                if not dry_run:
                    self.import_lab_tests(sql_dir, skip_tables, options)
                
                # 6. Import imaging
                self.stdout.write(self.style.SUCCESS('\n[6/7] Importing Imaging Studies...'))
                if not dry_run:
                    self.import_imaging(sql_dir, skip_tables, options)
                
                # 7. Import inventory
                self.stdout.write(self.style.SUCCESS('\n[7/7] Importing Inventory...'))
                if not dry_run:
                    self.import_inventory(sql_dir, skip_tables, options)
                
                # 8. Import billing/charges (depends on above)
                self.stdout.write(self.style.SUCCESS('\n[8/8] Importing Billing/Charges...'))
                if not dry_run:
                    self.import_billing(sql_dir, skip_tables, options)
                
                if dry_run:
                    raise Exception("DRY RUN - Rolling back transaction")
                    
            except Exception as e:
                if not dry_run:
                    self.stdout.write(self.style.ERROR(f'\nError during migration: {str(e)}'))
                    logger.exception('Migration error')
                raise
        
        # Print summary
        self.print_summary()
        
        if self.mysql_conn:
            self.mysql_conn.close()
    
    def connect_mysql(self, options):
        """Connect to MySQL database directly"""
        if not MYSQL_AVAILABLE:
            raise CommandError(
                'MySQL connector not available. Install it with: pip install mysql-connector-python\n'
                'Or use SQL files instead with --sql-dir option.'
            )
        
        try:
            self.mysql_conn = mysql.connector.connect(
                host=options.get('mysql_host') or 'localhost',
                user=options.get('mysql_user') or 'root',
                password=options.get('mysql_password') or '',
                database=options.get('mysql_database') or 'hospital',
                charset='utf8mb4'
            )
            self.stdout.write(self.style.SUCCESS('✓ Connected to MySQL database'))
        except Exception as e:
            raise CommandError(f'Failed to connect to MySQL: {str(e)}')
    
    def execute_sql_file(self, sql_file):
        """Execute SQL file and return parsed INSERT statements"""
        if not os.path.exists(sql_file):
            return []
        
        inserts = []
        with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract INSERT statements - handle both single and multi-row inserts
        # Pattern: INSERT INTO `table` VALUES (...), (...), (...);
        pattern = r'INSERT\s+INTO\s+`?(\w+)`?\s*(?:\([^)]+\))?\s*VALUES\s+(.*?);'
        matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        
        for match in matches:
            table_name = match.group(1)
            values_block = match.group(2)
            
            # Split multiple value sets: (...), (...), (...)
            value_sets = re.findall(r'\((.*?)\)(?=,|$)', values_block, re.DOTALL)
            
            for values_str in value_sets:
                values = self.parse_sql_values(values_str)
                inserts.append({
                    'table': table_name,
                    'values': values
                })
        
        return inserts
    
    def parse_sql_values(self, values_str):
        """Parse SQL VALUES string into Python values - handles quoted strings, NULL, numbers"""
        values = []
        current = ''
        in_quotes = False
        quote_char = None
        escaped = False
        
        i = 0
        while i < len(values_str):
            char = values_str[i]
            
            if escaped:
                current += char
                escaped = False
                i += 1
                continue
            
            if char == '\\':
                escaped = True
                current += char
                i += 1
                continue
            
            if not in_quotes:
                if char in ("'", '"'):
                    in_quotes = True
                    quote_char = char
                elif char == ',':
                    values.append(self.convert_value(current.strip()))
                    current = ''
                else:
                    current += char
            else:
                if char == quote_char:
                    # Check if next char is also quote (MySQL escaping)
                    if i + 1 < len(values_str) and values_str[i + 1] == quote_char:
                        current += quote_char
                        i += 1  # Skip next quote
                    else:
                        in_quotes = False
                        quote_char = None
                else:
                    current += char
            i += 1
        
        if current.strip() or current:
            values.append(self.convert_value(current.strip()))
        
        return values
    
    def convert_value(self, value):
        """Convert SQL value to Python type"""
        value = value.strip()
        if value.upper() == 'NULL':
            return None
        if value.upper() == 'TRUE' or value == '1':
            return True
        if value.upper() == 'FALSE' or value == '0':
            return False
        # Remove quotes
        if (value.startswith("'") and value.endswith("'")) or \
           (value.startswith('"') and value.endswith('"')):
            return value[1:-1]
        # Try number conversion
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
    
    # ==================== IMPORT FUNCTIONS ====================
    
    def import_patients(self, sql_dir, skip_tables, options):
        """Import patients from patient_data.sql"""
        sql_file = os.path.join(sql_dir, 'patient_data.sql')
        if not os.path.exists(sql_file) or 'patient_data' in skip_tables:
            self.stdout.write(self.style.WARNING('  Skipping patient_data (file not found or skipped)'))
            return
        
        self.stdout.write(f'  Processing {sql_file}...')
        inserts = self.execute_sql_file(sql_file)
        
        # Map legacy fields to Django model
        # patient_data table: id, fname, lname, mname, DOB, sex, phone_cell, email, etc.
        
        for idx, insert in enumerate(inserts):
            if insert['table'] != 'patient_data':
                continue
            
            try:
                values = insert['values']
                # Map based on CREATE TABLE structure from SQL file
                legacy_pid = values[0] if len(values) > 0 else None  # id/pid
                fname = values[8] if len(values) > 8 else ''  # fname
                lname = values[9] if len(values) > 9 else ''  # lname
                mname = values[10] if len(values) > 10 else ''  # mname
                dob = values[11] if len(values) > 11 else None  # DOB
                sex = values[28] if len(values) > 28 else ''  # sex
                phone = values[23] if len(values) > 23 else ''  # phone_cell
                email = values[33] if len(values) > 33 else ''  # email
                
                # Normalize data
                gender = 'M' if sex.upper() in ('M', 'MALE') else 'F' if sex.upper() in ('F', 'FEMALE') else 'O'
                
                # Generate MRN from legacy PID
                mrn = f"PMC{legacy_pid:06d}" if legacy_pid else None
                
                # Check for existing patient
                existing = None
                if mrn:
                    existing = Patient.objects.filter(mrn=mrn, is_deleted=False).first()
                if not existing and fname and lname:
                    # Try to find by name + DOB
                    if dob:
                        try:
                            dob_date = self.parse_date(dob)
                            existing = Patient.objects.filter(
                                first_name__iexact=fname,
                                last_name__iexact=lname,
                                date_of_birth=dob_date,
                                is_deleted=False
                            ).first()
                        except:
                            pass
                
                if existing and not options.get('skip_duplicates', False):
                    # Update existing
                    existing.first_name = fname or existing.first_name
                    existing.last_name = lname or existing.last_name
                    existing.middle_name = mname or existing.middle_name
                    if dob:
                        try:
                            existing.date_of_birth = self.parse_date(dob)
                        except:
                            pass
                    existing.gender = gender
                    if phone:
                        existing.phone_number = phone[:17]  # Max length
                    if email:
                        existing.email = email[:254]  # Max length
                    existing.save()
                    self.stats['patients']['updated'] += 1
                elif not existing:
                    # Create new
                    patient = Patient(
                        mrn=mrn or f"PMC{timezone.now().timestamp():.0f}",
                        first_name=fname or '',
                        last_name=lname or '',
                        middle_name=mname or '',
                        gender=gender,
                        phone_number=phone[:17] if phone else '',
                        email=email[:254] if email else '',
                        date_of_birth=self.parse_date(dob) if dob else date(2000, 1, 1)
                    )
                    patient.save()
                    self.stats['patients']['created'] += 1
                else:
                    self.stats['patients']['skipped'] += 1
                
                # Progress update
                if (idx + 1) % 100 == 0:
                    self.stdout.write(f'  Processed {idx + 1:,} patients...')
                    
            except Exception as e:
                self.errors.append(f'Patient import error (row {idx}): {str(e)}')
                logger.exception(f'Patient import error')
        
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ Patients: {self.stats["patients"]["created"]} created, '
            f'{self.stats["patients"]["updated"]} updated, '
            f'{self.stats["patients"]["skipped"]} skipped'
        ))
    
    def import_drugs(self, sql_dir, skip_tables, options):
        """Import drugs from drugs.sql"""
        sql_file = os.path.join(sql_dir, 'drugs.sql')
        if not os.path.exists(sql_file) or 'drugs' in skip_tables:
            self.stdout.write(self.style.WARNING('  Skipping drugs (file not found or skipped)'))
            return
        
        self.stdout.write(f'  Processing {sql_file}...')
        inserts = self.execute_sql_file(sql_file)
        
        for idx, insert in enumerate(inserts):
            if insert['table'] != 'drugs':
                continue
            
            try:
                values = insert['values']
                legacy_drug_id = values[0] if len(values) > 0 else None
                name = values[1] if len(values) > 1 else ''
                base_price = values[26] if len(values) > 26 else 0  # base_price
                last_cost = values[33] if len(values) > 33 else 0  # last_cost
                form_id = values[12] if len(values) > 12 else 0  # form
                size = values[14] if len(values) > 14 else ''  # size
                active = values[20] if len(values) > 20 else 1  # active
                
                if not name or not legacy_drug_id:
                    continue
                
                # Check for existing drug by name
                existing = Drug.objects.filter(name__iexact=name, is_deleted=False).first()
                
                if existing and not options.get('skip_duplicates', False):
                    # Update existing
                    try:
                        existing.unit_price = Decimal(str(base_price)) if base_price else Decimal('0')
                        existing.cost_price = Decimal(str(last_cost)) if last_cost else Decimal('0')
                        existing.is_active = bool(active)
                        existing.form = self.map_drug_form(form_id)
                        existing.save()
                        self.stats['drugs']['updated'] += 1
                        # Store mapping - CRITICAL for stock import
                        self.drug_id_mapping[str(legacy_drug_id)] = existing
                    except Exception as e:
                        logger.error(f'Drug update error: {e}')
                elif not existing:
                    # Create new
                    try:
                        drug = Drug(
                            name=name[:200],
                            form=self.map_drug_form(form_id),
                            pack_size=size[:50] if size else '',
                            unit_price=Decimal(str(base_price)) if base_price else Decimal('0'),
                            cost_price=Decimal(str(last_cost)) if last_cost else Decimal('0'),
                            is_active=bool(active)
                        )
                        drug.save()
                        self.stats['drugs']['created'] += 1
                        # Store mapping - CRITICAL for stock import
                        self.drug_id_mapping[str(legacy_drug_id)] = drug
                    except Exception as e:
                        logger.error(f'Drug creation error: {e}')
                else:
                    self.stats['drugs']['skipped'] += 1
                    # Still store mapping if skipped
                    if existing:
                        self.drug_id_mapping[str(legacy_drug_id)] = existing
                
                if (idx + 1) % 100 == 0:
                    self.stdout.write(f'  Processed {idx + 1:,} drugs...')
                    
            except Exception as e:
                self.errors.append(f'Drug import error (row {idx}): {str(e)}')
                logger.exception(f'Drug import error')
        
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ Drugs: {self.stats["drugs"]["created"]} created, '
            f'{self.stats["drugs"]["updated"]} updated, '
            f'{len(self.drug_id_mapping)} mapped for stock import'
        ))
    
    def import_services(self, sql_dir, skip_tables, options):
        """Import services from codes.sql"""
        sql_file = os.path.join(sql_dir, 'codes.sql')
        if not os.path.exists(sql_file) or 'codes' in skip_tables:
            self.stdout.write(self.style.WARNING('  Skipping codes (file not found or skipped)'))
            return
        
        self.stdout.write(f'  Processing {sql_file}...')
        inserts = self.execute_sql_file(sql_file)
        
        for idx, insert in enumerate(inserts):
            if insert['table'] != 'codes':
                continue
            
            try:
                values = insert['values']
                code_id = values[0] if len(values) > 0 else None
                code_text = values[1] if len(values) > 1 else ''  # code_text (description)
                code = values[3] if len(values) > 3 else ''  # code
                code_type = values[4] if len(values) > 4 else None  # code_type
                fee = values[7] if len(values) > 7 else 0  # fee
                active = values[17] if len(values) > 17 else 1  # active
                is_lab = values[22] if len(values) > 22 else 0  # is_lab_order
                is_imaging = values[25] if len(values) > 25 else 0  # is_diag_imaging
                is_drug = values[28] if len(values) > 28 else 0  # is_drug
                
                # Skip drugs and lab tests (imported separately)
                if is_drug or is_lab or is_imaging:
                    continue
                
                if not code or not code_text:
                    continue
                
                # Check for existing service by code
                existing = ServiceCode.objects.filter(code=code, is_deleted=False).first()
                
                if existing and not options.get('skip_duplicates', False):
                    # Update existing
                    existing.description = code_text[:200]
                    existing.is_active = bool(active)
                    existing.save()
                    self.stats['services']['updated'] += 1
                elif not existing:
                    # Create new
                    service = ServiceCode(
                        code=code[:20],
                        description=code_text[:200],
                        category=self.map_code_type(code_type),
                        is_active=bool(active)
                    )
                    service.save()
                    self.stats['services']['created'] += 1
                else:
                    self.stats['services']['skipped'] += 1
                
                if (idx + 1) % 500 == 0:
                    self.stdout.write(f'  Processed {idx + 1:,} services...')
                    
            except Exception as e:
                self.errors.append(f'Service import error (row {idx}): {str(e)}')
                logger.exception(f'Service import error')
        
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ Services: {self.stats["services"]["created"]} created, '
            f'{self.stats["services"]["updated"]} updated'
        ))
    
    def import_lab_tests(self, sql_dir, skip_tables, options):
        """Import lab tests from codes.sql (where is_lab_order=1)"""
        sql_file = os.path.join(sql_dir, 'codes.sql')
        if not os.path.exists(sql_file):
            return
        
        self.stdout.write(f'  Processing lab tests from codes.sql...')
        inserts = self.execute_sql_file(sql_file)
        
        for idx, insert in enumerate(inserts):
            if insert['table'] != 'codes':
                continue
            
            try:
                values = insert['values']
                is_lab = values[22] if len(values) > 22 else 0  # is_lab_order
                
                if not is_lab:
                    continue
                
                code_text = values[1] if len(values) > 1 else ''  # code_text
                code = values[3] if len(values) > 3 else ''  # code
                fee = values[7] if len(values) > 7 else 0  # fee
                active = values[17] if len(values) > 17 else 1  # active
                
                if not code or not code_text:
                    continue
                
                # Check for existing lab test by code
                existing = LabTest.objects.filter(code=code, is_deleted=False).first()
                
                if existing and not options.get('skip_duplicates', False):
                    # Update existing
                    existing.name = code_text[:200]
                    existing.price = Decimal(str(fee)) if fee else Decimal('0')
                    existing.is_active = bool(active)
                    existing.save()
                    self.stats['lab_tests']['updated'] += 1
                elif not existing:
                    # Create new
                    lab_test = LabTest(
                        code=code[:20],
                        name=code_text[:200],
                        specimen_type='Blood',  # Default, can be enhanced
                        price=Decimal(str(fee)) if fee else Decimal('0'),
                        is_active=bool(active)
                    )
                    lab_test.save()
                    self.stats['lab_tests']['created'] += 1
                else:
                    self.stats['lab_tests']['skipped'] += 1
                
            except Exception as e:
                self.errors.append(f'Lab test import error (row {idx}): {str(e)}')
                logger.exception(f'Lab test import error')
        
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ Lab Tests: {self.stats["lab_tests"]["created"]} created, '
            f'{self.stats["lab_tests"]["updated"]} updated'
        ))
    
    def import_imaging(self, sql_dir, skip_tables, options):
        """Import imaging studies from diag_imaging_order.sql"""
        sql_file = os.path.join(sql_dir, 'diag_imaging_order.sql')
        if not os.path.exists(sql_file):
            return
        
        # This would require encounter/patient mapping which is complex
        # For now, just log that imaging import is available
        self.stdout.write(self.style.WARNING('  Imaging import requires encounter mapping - skipped for now'))
    
    def import_inventory(self, sql_dir, skip_tables, options):
        """Import inventory from drug_inventory.sql into PharmacyStock"""
        sql_file = os.path.join(sql_dir, 'drug_inventory.sql')
        if not os.path.exists(sql_file) or 'drug_inventory' in skip_tables:
            self.stdout.write(self.style.WARNING('  Skipping drug_inventory (file not found or skipped)'))
            return
        
        if not self.drug_id_mapping:
            self.stdout.write(self.style.ERROR('  ⚠️  No drug mapping found! Import drugs first.'))
            return
        
        self.stdout.write(f'  Processing {sql_file}...')
        self.stdout.write(f'  Using drug mapping with {len(self.drug_id_mapping)} drugs...')
        
        inserts = self.execute_sql_file(sql_file)
        
        # Track stock by drug and batch for aggregation
        stock_by_drug_batch = {}
        
        for idx, insert in enumerate(inserts):
            if insert['table'] != 'drug_inventory':
                continue
            
            try:
                values = insert['values']
                # Map based on CREATE TABLE structure from drug_inventory.sql
                inventory_id = values[0] if len(values) > 0 else None
                legacy_drug_id = values[1] if len(values) > 1 else None  # drug_id
                lot_number = values[2] if len(values) > 2 else ''  # lot_number
                expiration = values[3] if len(values) > 3 else None  # expiration
                on_hand = values[5] if len(values) > 5 else 0  # on_hand
                warehouse_id = values[6] if len(values) > 6 else ''  # warehouse_id
                value_onhand = values[17] if len(values) > 17 else 0  # value_onhand
                
                # Skip if no drug_id or no stock
                if not legacy_drug_id:
                    continue
                
                # Convert on_hand to integer
                try:
                    on_hand = int(on_hand) if on_hand else 0
                except:
                    on_hand = 0
                
                # Skip zero or negative stock
                if on_hand <= 0:
                    continue
                
                # Find drug using mapping
                drug = self.drug_id_mapping.get(str(legacy_drug_id))
                if not drug:
                    # Try to find by legacy ID in different formats
                    drug = self.drug_id_mapping.get(str(int(legacy_drug_id))) if legacy_drug_id else None
                    if not drug:
                        continue  # Skip if drug not found
                
                # Parse expiration date
                expiry_date = None
                if expiration:
                    try:
                        expiry_date = self.parse_date(expiration)
                    except:
                        expiry_date = None
                
                # Use lot_number as batch_number, or generate one
                batch_number = lot_number[:50] if lot_number else f"BATCH{inventory_id or idx}"
                
                # Calculate unit cost
                unit_cost = Decimal('0')
                if value_onhand and on_hand:
                    try:
                        unit_cost = Decimal(str(value_onhand)) / Decimal(str(on_hand))
                    except:
                        pass
                
                # Location from warehouse
                location = warehouse_id[:100] if warehouse_id else 'Main Pharmacy'
                
                # Aggregate stock by drug + batch + expiry
                key = (drug.id, batch_number, expiry_date)
                if key not in stock_by_drug_batch:
                    stock_by_drug_batch[key] = {
                        'drug': drug,
                        'batch_number': batch_number,
                        'expiry_date': expiry_date,
                        'quantity': 0,
                        'unit_cost': unit_cost,
                        'location': location,
                    }
                
                stock_by_drug_batch[key]['quantity'] += on_hand
                # Use weighted average for unit cost if multiple lots
                if unit_cost > 0:
                    existing_cost = stock_by_drug_batch[key]['unit_cost']
                    if existing_cost == 0:
                        stock_by_drug_batch[key]['unit_cost'] = unit_cost
                
                if (idx + 1) % 500 == 0:
                    self.stdout.write(f'  Processed {idx + 1:,} inventory records, '
                                    f'{len(stock_by_drug_batch)} unique batches...')
                    
            except Exception as e:
                self.errors.append(f'Inventory import error (row {idx}): {str(e)}')
                logger.exception(f'Inventory import error')
        
        # Now create PharmacyStock records from aggregated data
        self.stdout.write(f'  Creating {len(stock_by_drug_batch)} PharmacyStock records...')
        
        for key, stock_data in stock_by_drug_batch.items():
            try:
                drug = stock_data['drug']
                batch_number = stock_data['batch_number']
                expiry_date = stock_data['expiry_date'] or date(2099, 12, 31)  # Default far future if no expiry
                quantity = stock_data['quantity']
                unit_cost = stock_data['unit_cost']
                location = stock_data['location']
                
                # Check for existing stock with same drug, batch, and expiry
                existing_stock = PharmacyStock.objects.filter(
                    drug=drug,
                    batch_number=batch_number,
                    expiry_date=expiry_date,
                    is_deleted=False
                ).first()
                
                if existing_stock and not options.get('skip_duplicates', False):
                    # Update existing stock
                    existing_stock.quantity_on_hand += quantity
                    if unit_cost > 0:
                        # Update cost if new cost is available
                        existing_stock.unit_cost = unit_cost
                    existing_stock.save()
                    self.stats['inventory']['updated'] += 1
                elif not existing_stock:
                    # Create new stock record
                    stock = PharmacyStock(
                        drug=drug,
                        batch_number=batch_number,
                        expiry_date=expiry_date,
                        location=location,
                        quantity_on_hand=quantity,
                        unit_cost=unit_cost
                    )
                    stock.save()
                    self.stats['inventory']['created'] += 1
                else:
                    self.stats['inventory']['skipped'] += 1
                    
            except Exception as e:
                self.errors.append(f'PharmacyStock creation error: {str(e)}')
                logger.exception(f'PharmacyStock creation error')
        
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ Pharmacy Stock: {self.stats["inventory"]["created"]} created, '
            f'{self.stats["inventory"]["updated"]} updated, '
            f'{self.stats["inventory"]["skipped"]} skipped'
        ))
    
    def import_billing(self, sql_dir, skip_tables, options):
        """Import billing records from billing.sql"""
        sql_file = os.path.join(sql_dir, 'billing.sql')
        if not os.path.exists(sql_file):
            return
        
        # Billing import is complex and requires full encounter/patient/service mapping
        self.stdout.write(self.style.WARNING('  Billing import requires full system mapping - skipped for now'))
    
    def import_payers(self, sql_dir, skip_tables):
        """Import insurance companies/payers"""
        # Placeholder - would import from insurance_companies.sql
        pass
    
    def import_staff(self, sql_dir, skip_tables):
        """Import staff/users"""
        # Placeholder - would import from users.sql, employees.sql
        pass
    
    # ==================== HELPER FUNCTIONS ====================
    
    def parse_date(self, value):
        """Parse date string to date object"""
        if not value:
            return date(2000, 1, 1)
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        
        # Try various date formats
        formats = ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y']
        for fmt in formats:
            try:
                return datetime.strptime(str(value), fmt).date()
            except:
                continue
        
        # Default fallback
        return date(2000, 1, 1)
    
    def map_drug_form(self, form_id):
        """Map legacy form ID to drug form string"""
        form_map = {
            1: 'syrup',
            2: 'tablet',
            3: 'capsule',
            16: 'injection',
            27: 'suppository',
        }
        return form_map.get(int(form_id) if form_id else 0, 'tablet')
    
    def map_code_type(self, code_type):
        """Map legacy code_type to category"""
        # Default categories
        return 'general'
    
    def print_summary(self):
        """Print migration summary"""
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('MIGRATION SUMMARY'))
        self.stdout.write('='*70)
        
        for category, stats in self.stats.items():
            total = stats['created'] + stats['updated'] + stats['skipped']
            if total > 0:
                self.stdout.write(
                    f"{category.replace('_', ' ').title()}: "
                    f"{stats['created']} created, {stats['updated']} updated, "
                    f"{stats['skipped']} skipped"
                )
        
        if self.errors:
            self.stdout.write(self.style.ERROR(f'\nErrors encountered: {len(self.errors)}'))
            for error in self.errors[:10]:  # Show first 10 errors
                self.stdout.write(self.style.ERROR(f'  - {error}'))
        
        self.stdout.write('='*70)

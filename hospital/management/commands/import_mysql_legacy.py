"""
Django Management Command to Import Legacy Data from MySQL (db_2)
Imports: Patients, Encounters, Diagnoses, Prescriptions, Lab Results, Notes
"""
import os
import sys
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connections
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal
import pymysql

from hospital.models import (
    Patient, Encounter, Prescription, LabResult, Order, LabTest, Drug, Staff
)


class Command(BaseCommand):
    help = 'Import legacy data from MySQL db_2 container (patients, encounters, diagnoses, prescriptions, lab results, notes)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually importing data'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of records to import (for testing)'
        )
        parser.add_argument(
            '--patients-only',
            action='store_true',
            help='Import only patients'
        )
        parser.add_argument(
            '--encounters-only',
            action='store_true',
            help='Import only encounters'
        )
    
    def get_mysql_connection(self):
        """Connect to MySQL db_2 container - tries multiple connection methods"""
        hosts = ['localhost', '127.0.0.1', 'db_2']  # Try localhost first, then Docker service name
        port = 3306
        user = 'legacy_user'
        password = 'legacy_password'
        database = 'legacy_db'
        
        last_error = None
        for host in hosts:
            try:
                self.stdout.write(f'  Trying to connect to MySQL at {host}:{port}...')
                conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=10
                )
                # Test connection
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                cursor.close()
                self.stdout.write(f'  [OK] Connected to MySQL at {host}:{port}')
                return conn
            except Exception as e:
                last_error = e
                self.stdout.write(f'  [WARN] Failed to connect to {host}:{port} - {e}')
                continue
        
        raise CommandError(f'Failed to connect to MySQL after trying all hosts. Last error: {last_error}')
    
    def normalize_phone(self, phone):
        """Normalize phone number to Django format"""
        if not phone:
            return ''
        phone = str(phone).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if phone.startswith('0') and len(phone) == 10:
            phone = '+233' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+233' + phone
        return phone[:17]  # Max length
    
    def normalize_gender(self, sex):
        """Normalize gender: M/F/O"""
        if not sex:
            return 'M'
        sex = str(sex).upper().strip()
        if sex in ['M', 'MALE']:
            return 'M'
        elif sex in ['F', 'FEMALE']:
            return 'F'
        return 'O'
    
    def parse_date(self, date_str):
        """Parse date string safely"""
        if not date_str:
            return date(2000, 1, 1)
        if isinstance(date_str, date):
            return date_str
        if isinstance(date_str, datetime):
            return date_str.date()
        try:
            return datetime.strptime(str(date_str), '%Y-%m-%d').date()
        except:
            try:
                return datetime.strptime(str(date_str), '%Y/%m/%d').date()
            except:
                return date(2000, 1, 1)
    
    def parse_datetime(self, dt_str):
        """Parse datetime string safely"""
        if not dt_str:
            return timezone.now()
        if isinstance(dt_str, datetime):
            return timezone.make_aware(dt_str) if timezone.is_naive(dt_str) else dt_str
        try:
            dt = datetime.strptime(str(dt_str), '%Y-%m-%d %H:%M:%S')
            return timezone.make_aware(dt)
        except:
            try:
                dt = datetime.strptime(str(dt_str), '%Y-%m-%d')
                return timezone.make_aware(dt)
            except:
                return timezone.now()
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        patients_only = options['patients_only']
        encounters_only = options['encounters_only']
        
        self.stdout.write('')
        self.stdout.write('=' * 70)
        self.stdout.write('MySQL Legacy Data Import')
        self.stdout.write('=' * 70)
        self.stdout.write(f'Dry Run: {dry_run}')
        self.stdout.write(f'Limit: {limit}')
        self.stdout.write('=' * 70)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
        
        try:
            mysql_conn = self.get_mysql_connection()
            self.stdout.write(self.style.SUCCESS('[OK] Connected to MySQL db_2'))
            
            # Import patients first (required for other imports)
            if not encounters_only:
                patient_map = self.import_patients(mysql_conn, dry_run, limit)
                self.stdout.write(f'[OK] Imported {len(patient_map)} patients')
            else:
                # Build patient map from existing Django patients
                patient_map = {p.mrn: p for p in Patient.objects.filter(is_deleted=False)}
                self.stdout.write(f'[OK] Using {len(patient_map)} existing patients')
            
            # Import encounters
            if not patients_only:
                encounter_map = self.import_encounters(mysql_conn, patient_map, dry_run, limit)
                self.stdout.write(f'[OK] Imported {len(encounter_map)} encounters')
                
                # Import related data
                if not encounters_only:
                    self.import_diagnoses(mysql_conn, patient_map, encounter_map, dry_run, limit)
                    self.import_prescriptions(mysql_conn, patient_map, encounter_map, dry_run, limit)
                    self.import_lab_results(mysql_conn, patient_map, encounter_map, dry_run, limit)
                    self.import_notes(mysql_conn, patient_map, encounter_map, dry_run, limit)
            
            mysql_conn.close()
            self.stdout.write(self.style.SUCCESS('\n[OK] Import completed successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n[ERROR] Import failed: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
            raise CommandError(f'Import failed: {e}')
    
    def import_patients(self, mysql_conn, dry_run, limit):
        """Import patients from patient_data table"""
        patient_map = {}
        cursor = mysql_conn.cursor()
        
        query = "SELECT * FROM patient_data WHERE pid > 0"
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        self.stdout.write(f'\nImporting {len(rows)} patients...')
        
        for idx, row in enumerate(rows, 1):
            try:
                # Map MySQL fields to Django Patient model
                first_name = (row.get('fname') or '').strip()[:100]
                last_name = (row.get('lname') or '').strip()[:100]
                middle_name = (row.get('mname') or '').strip()[:100]
                
                if not first_name and not last_name:
                    continue
                
                # Generate MRN from pid
                pid = row.get('pid', 0)
                mrn = f"MRN{pid:06d}"
                
                # Check if patient already exists
                existing = Patient.objects.filter(mrn=mrn, is_deleted=False).first()
                if existing:
                    patient_map[pid] = existing
                    if idx % 100 == 0:
                        self.stdout.write(f'  Processed {idx}/{len(rows)} (existing: {existing.mrn})')
                    continue
                
                if dry_run:
                    patient_map[pid] = None
                    continue
                
                # Create patient
                patient = Patient.objects.create(
                    mrn=mrn,
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    date_of_birth=self.parse_date(row.get('DOB')),
                    gender=self.normalize_gender(row.get('sex')),
                    phone_number=self.normalize_phone(row.get('phone_cell') or row.get('phone_home') or row.get('phone_contact')),
                    email=(row.get('email') or row.get('email_direct') or '').strip()[:254],
                    address=f"{row.get('street', '')} {row.get('city', '')} {row.get('state', '')}".strip()[:500],
                    national_id=(row.get('ss') or row.get('drivers_license') or '').strip()[:20],
                )
                
                patient_map[pid] = patient
                
                if idx % 100 == 0:
                    self.stdout.write(f'  Imported {idx}/{len(rows)} patients')
                    
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Error importing patient {pid}: {e}'))
                continue
        
        cursor.close()
        return patient_map
    
    def import_encounters(self, mysql_conn, patient_map, dry_run, limit):
        """Import encounters from form_encounter table"""
        encounter_map = {}
        cursor = mysql_conn.cursor()
        
        # Try multiple possible table names
        tables = ['form_encounter', 'external_encounters', 'issue_encounter']
        query = None
        
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                result = cursor.fetchone()
                if result and result.get('cnt', 0) > 0:
                    query = f"SELECT * FROM {table}"
                    if limit:
                        query += f" LIMIT {limit}"
                    break
            except:
                continue
        
        if not query:
            self.stdout.write(self.style.WARNING('No encounter table found'))
            return encounter_map
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        self.stdout.write(f'\nImporting {len(rows)} encounters...')
        
        for idx, row in enumerate(rows, 1):
            try:
                # Get patient ID from row (could be pid, patient_id, etc.)
                pid = row.get('pid') or row.get('patient_id') or 0
                patient = patient_map.get(pid)
                
                if not patient:
                    continue
                
                # Map encounter type
                encounter_type_map = {
                    'outpatient': 'outpatient',
                    'inpatient': 'inpatient',
                    'emergency': 'er',
                    'er': 'er',
                    'surgery': 'surgery',
                }
                enc_type = encounter_type_map.get(
                    (row.get('encounter_type') or row.get('type') or 'outpatient').lower(),
                    'outpatient'
                )
                
                # Get dates
                started_at = self.parse_datetime(row.get('date') or row.get('encounter_date') or row.get('started_at'))
                ended_at = None
                if row.get('end_date') or row.get('ended_at'):
                    ended_at = self.parse_datetime(row.get('end_date') or row.get('ended_at'))
                
                # Get chief complaint
                chief_complaint = (row.get('chief_complaint') or row.get('complaint') or 'Legacy encounter').strip()[:500]
                
                if dry_run:
                    encounter_map[row.get('id')] = None
                    continue
                
                # Create encounter
                encounter = Encounter.objects.create(
                    patient=patient,
                    encounter_type=enc_type,
                    status='completed' if ended_at else 'active',
                    started_at=started_at,
                    ended_at=ended_at,
                    chief_complaint=chief_complaint,
                    diagnosis=(row.get('diagnosis') or '').strip()[:500],
                    notes=(row.get('notes') or '').strip()[:1000],
                )
                
                encounter_map[row.get('id')] = encounter
                
                if idx % 100 == 0:
                    self.stdout.write(f'  Imported {idx}/{len(rows)} encounters')
                    
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Error importing encounter: {e}'))
                continue
        
        cursor.close()
        return encounter_map
    
    def import_diagnoses(self, mysql_conn, patient_map, encounter_map, dry_run, limit):
        """Import diagnoses from various diagnosis tables"""
        cursor = mysql_conn.cursor()
        
        # Try multiple diagnosis table names
        tables = ['form_diagnosis', 'visit_diagnosis', 'admission_diagnosis', 'form_consultation_differential_diagnosis']
        
        total_imported = 0
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                result = cursor.fetchone()
                if not result or result.get('cnt', 0) == 0:
                    continue
                
                query = f"SELECT * FROM {table}"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                self.stdout.write(f'\nImporting {len(rows)} diagnoses from {table}...')
                
                for row in rows:
                    try:
                        pid = row.get('pid') or row.get('patient_id') or 0
                        patient = patient_map.get(pid)
                        if not patient:
                            continue
                        
                        diagnosis_text = (row.get('diagnosis') or row.get('diagnosis_code') or row.get('code') or '').strip()
                        if not diagnosis_text:
                            continue
                        
                        # Get encounter if available
                        encounter = None
                        if row.get('encounter_id'):
                            encounter = encounter_map.get(row.get('encounter_id'))
                        
                        if dry_run:
                            total_imported += 1
                            continue
                        
                        # Store diagnosis in encounter notes or create MedicalRecord
                        if encounter:
                            if diagnosis_text not in encounter.diagnosis:
                                encounter.diagnosis = f"{encounter.diagnosis}\n{diagnosis_text}".strip()
                                encounter.save(update_fields=['diagnosis', 'modified'])
                        else:
                            # Store in patient's first encounter or create a note
                            first_encounter = patient.encounters.filter(is_deleted=False).first()
                            if first_encounter:
                                first_encounter.diagnosis = f"{first_encounter.diagnosis}\n{diagnosis_text}".strip()
                                first_encounter.save(update_fields=['diagnosis', 'modified'])
                        
                        total_imported += 1
                        
                    except Exception as e:
                        continue
                        
            except Exception as e:
                continue
        
        cursor.close()
        self.stdout.write(f'[OK] Imported {total_imported} diagnoses')
    
    def import_prescriptions(self, mysql_conn, patient_map, encounter_map, dry_run, limit):
        """Import prescriptions"""
        cursor = mysql_conn.cursor()
        
        tables = ['prescriptions', 'form_consultation_prescriptions', 'admission_prescriptions']
        
        total_imported = 0
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                result = cursor.fetchone()
                if not result or result.get('cnt', 0) == 0:
                    continue
                
                query = f"SELECT * FROM {table}"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                self.stdout.write(f'\nImporting {len(rows)} prescriptions from {table}...')
                
                for row in rows:
                    try:
                        pid = row.get('pid') or row.get('patient_id') or 0
                        patient = patient_map.get(pid)
                        if not patient:
                            continue
                        
                        # Get or create encounter
                        encounter_id = row.get('encounter_id') or row.get('visit_id')
                        encounter = encounter_map.get(encounter_id) if encounter_id else None
                        
                        if not encounter:
                            encounter = patient.encounters.filter(is_deleted=False).order_by('-started_at').first()
                            if not encounter:
                                continue
                        
                        # Get drug name
                        drug_name = (row.get('drug') or row.get('drug_name') or row.get('medication') or '').strip()
                        if not drug_name:
                            continue
                        
                        # Get or create drug
                        drug, _ = Drug.objects.get_or_create(
                            name=drug_name[:200],
                            defaults={
                                'strength': (row.get('strength') or 'N/A')[:50],
                                'form': (row.get('form') or 'tablet')[:50],
                                'pack_size': '1',
                            }
                        )
                        
                        # Get or create order
                        order, _ = Order.objects.get_or_create(
                            encounter=encounter,
                            order_type='medication',
                            defaults={
                                'status': 'completed',
                                'ordered_at': self.parse_datetime(row.get('date') or row.get('created')),
                            }
                        )
                        
                        if dry_run:
                            total_imported += 1
                            continue
                        
                        # Create prescription
                        Prescription.objects.create(
                            order=order,
                            drug=drug,
                            quantity=int(row.get('quantity', 1) or 1),
                            dose=(row.get('dose') or 'As directed')[:100],
                            route=(row.get('route') or 'oral')[:50],
                            frequency=(row.get('frequency') or 'daily')[:50],
                            duration=(row.get('duration') or '7 days')[:50],
                            instructions=(row.get('instructions') or '')[:500],
                            prescribed_by=encounter.provider or Staff.objects.filter(is_deleted=False).first(),
                        )
                        
                        total_imported += 1
                        
                    except Exception as e:
                        continue
                        
            except Exception as e:
                continue
        
        cursor.close()
        self.stdout.write(f'[OK] Imported {total_imported} prescriptions')
    
    def import_lab_results(self, mysql_conn, patient_map, encounter_map, dry_run, limit):
        """Import lab results"""
        cursor = mysql_conn.cursor()
        
        tables = ['lab_result', 'lab_report', 'form_consultation_laboratory', 'form_track_anything_results']
        
        total_imported = 0
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                result = cursor.fetchone()
                if not result or result.get('cnt', 0) == 0:
                    continue
                
                query = f"SELECT * FROM {table}"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                self.stdout.write(f'\nImporting {len(rows)} lab results from {table}...')
                
                for row in rows:
                    try:
                        pid = row.get('pid') or row.get('patient_id') or 0
                        patient = patient_map.get(pid)
                        if not patient:
                            continue
                        
                        # Get or create encounter
                        encounter_id = row.get('encounter_id') or row.get('visit_id')
                        encounter = encounter_map.get(encounter_id) if encounter_id else None
                        
                        if not encounter:
                            encounter = patient.encounters.filter(is_deleted=False).order_by('-started_at').first()
                            if not encounter:
                                continue
                        
                        # Get test name
                        test_name = (row.get('test_name') or row.get('test') or row.get('lab_test') or '').strip()
                        if not test_name:
                            continue
                        
                        # Get or create lab test
                        test, _ = LabTest.objects.get_or_create(
                            name=test_name[:200],
                            defaults={
                                'category': 'other',
                                'price': Decimal('0.00'),
                            }
                        )
                        
                        # Get or create order
                        order, _ = Order.objects.get_or_create(
                            encounter=encounter,
                            order_type='lab',
                            defaults={
                                'status': 'completed',
                                'ordered_at': self.parse_datetime(row.get('date') or row.get('created')),
                            }
                        )
                        
                        if dry_run:
                            total_imported += 1
                            continue
                        
                        # Check for duplicate before creating
                        existing_result = LabResult.objects.filter(
                            order=order,
                            test=test,
                            is_deleted=False
                        ).first()
                        
                        if not existing_result:
                            # Create lab result
                            LabResult.objects.create(
                                order=order,
                                test=test,
                                status='completed',
                                value=(row.get('result') or row.get('value') or '')[:100],
                                units=(row.get('units') or '')[:20],
                                range_low=(row.get('range_low') or '')[:20],
                                range_high=(row.get('range_high') or '')[:20],
                                is_abnormal=bool(row.get('is_abnormal') or False),
                                notes=(row.get('notes') or '')[:500],
                                verified_at=self.parse_datetime(row.get('verified_at') or row.get('date')),
                            )
                        
                        total_imported += 1
                        
                    except Exception as e:
                        continue
                        
            except Exception as e:
                continue
        
        cursor.close()
        self.stdout.write(f'[OK] Imported {total_imported} lab results')
    
    def import_notes(self, mysql_conn, patient_map, encounter_map, dry_run, limit):
        """Import clinical notes"""
        cursor = mysql_conn.cursor()
        
        tables = ['notes', 'form_note', 'form_nurse_note', 'form_consultation', 'admission_notes']
        
        total_imported = 0
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                result = cursor.fetchone()
                if not result or result.get('cnt', 0) == 0:
                    continue
                
                query = f"SELECT * FROM {table}"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                self.stdout.write(f'\nImporting {len(rows)} notes from {table}...')
                
                for row in rows:
                    try:
                        pid = row.get('pid') or row.get('patient_id') or 0
                        patient = patient_map.get(pid)
                        if not patient:
                            continue
                        
                        # Get or create encounter
                        encounter_id = row.get('encounter_id') or row.get('visit_id')
                        encounter = encounter_map.get(encounter_id) if encounter_id else None
                        
                        if not encounter:
                            encounter = patient.encounters.filter(is_deleted=False).order_by('-started_at').first()
                            if not encounter:
                                continue
                        
                        # Get note text
                        note_text = (
                            row.get('note') or row.get('notes') or row.get('note_text') or 
                            row.get('content') or row.get('body') or ''
                        ).strip()
                        
                        if not note_text:
                            continue
                        
                        if dry_run:
                            total_imported += 1
                            continue
                        
                        # Add note to encounter
                        if note_text:
                            existing_notes = encounter.notes or ''
                            timestamp = self.parse_datetime(row.get('date') or row.get('created'))
                            new_note = f"\n\n[{timestamp.strftime('%Y-%m-%d %H:%M')}] {note_text}"
                            encounter.notes = (existing_notes + new_note).strip()[:2000]
                            encounter.save(update_fields=['notes', 'modified'])
                        
                        total_imported += 1
                        
                    except Exception as e:
                        continue
                        
            except Exception as e:
                continue
        
        cursor.close()
        self.stdout.write(f'[OK] Imported {total_imported} notes')

















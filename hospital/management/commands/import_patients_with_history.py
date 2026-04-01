"""
Import all patients with their history from legacy database files
Checks for duplicates using multiple criteria to prevent duplicate imports
"""
import os
import re
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from hospital.models import Patient, Encounter, Staff, Payer
from hospital.models_workflow import PatientFlowStage


class Command(BaseCommand):
    help = 'Import all patients with their history from patient_data.sql and form_encounter.sql files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--patient-file',
            type=str,
            default='import/patient_data.sql',
            help='Path to patient_data.sql file'
        )
        parser.add_argument(
            '--encounter-file',
            type=str,
            default='import/form_encounter.sql',
            help='Path to form_encounter.sql file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of patients to process per batch'
        )
        parser.add_argument(
            '--skip-encounters',
            action='store_true',
            help='Skip importing encounters (only import patients)'
        )

    def normalize_phone(self, phone):
        """Normalize phone number to consistent format"""
        if not phone:
            return ''
        phone = str(phone).strip()
        # Skip if phone is just "0" or empty
        if phone == '0' or phone == '':
            return ''
        # Remove common separators
        phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')
        # Normalize Ghana numbers: 024 -> 23324, 050 -> 23350
        if phone.startswith('0') and len(phone) == 10:
            phone = '233' + phone[1:]
        # Must have at least 9 digits to be valid
        if len(phone) < 9:
            return ''
        return phone

    def parse_date(self, date_str):
        """Parse date string, handling various formats and invalid dates"""
        if not date_str or date_str.strip() == '' or date_str == '0000-00-00' or date_str == '0000-00-00 00:00:00':
            return None
        try:
            # Try various date formats
            for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%d-%m-%Y']:
                try:
                    return datetime.strptime(date_str.strip()[:10], fmt).date()
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def parse_datetime(self, datetime_str):
        """Parse datetime string"""
        if not datetime_str or datetime_str.strip() == '' or datetime_str == '0000-00-00 00:00:00':
            return None
        try:
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m-%d %H:%M']:
                try:
                    return datetime.strptime(datetime_str.strip()[:19], fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def parse_values_line(self, line):
        """Parse INSERT INTO table VALUES line"""
        # Extract values between VALUES( and );
        values_start = line.find('VALUES(')
        if values_start == -1:
            return None
        
        values_end = line.rfind(');')
        if values_end == -1:
            values_end = len(line)
        
        values_str = line[values_start + 6:values_end].strip()
        
        # Parse quoted values, handling commas inside quotes
        parts = []
        current = ''
        in_quotes = False
        i = 0
        while i < len(values_str):
            char = values_str[i]
            if char == '"':
                if i > 0 and values_str[i-1] == '\\':
                    current += char
                else:
                    in_quotes = not in_quotes
                    current += char
            elif char == ',' and not in_quotes:
                parts.append(current.strip().strip('"'))
                current = ''
            else:
                current += char
            i += 1
        if current:
            parts.append(current.strip().strip('"'))
        
        return parts

    def check_duplicate_patient(self, patient_data):
        """Check for duplicate patient using multiple criteria"""
        first_name = patient_data.get('fname', '').strip()
        last_name = patient_data.get('lname', '').strip()
        middle_name = patient_data.get('mname', '').strip()
        phone = patient_data.get('phone_cell') or patient_data.get('phone_home') or patient_data.get('phone_contact') or ''
        email = patient_data.get('email', '').strip()
        national_id = patient_data.get('ss', '').strip()  # Social Security = National ID
        pubpid = patient_data.get('pubpid', '').strip()  # Public Patient ID = MRN
        dob = self.parse_date(patient_data.get('DOB', ''))
        
        # Normalize phone
        normalized_phone = self.normalize_phone(phone)
        
        # Build duplicate check queries
        queries = Q()
        
        # 1. Check by MRN (pubpid or pmc_mrn)
        if pubpid:
            queries |= Q(mrn__iexact=pubpid)
        
        # 2. Check by National ID
        if national_id:
            queries |= Q(national_id=national_id)
        
        # 3. Check by email (if provided)
        if email:
            queries |= Q(email__iexact=email)
        
        # 4. Check by name + phone + DOB (only if phone is valid)
        if first_name and last_name and normalized_phone and len(normalized_phone) >= 9 and dob:
            queries |= Q(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                phone_number__icontains=normalized_phone[-9:],  # Last 9 digits
                date_of_birth=dob
            )
        
        # 5. Check by name + DOB (when phone is missing)
        if first_name and last_name and dob and not normalized_phone:
            queries |= Q(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                date_of_birth=dob,
                phone_number=''  # Match empty phone
            )
        
        # 6. Check by name + phone (more lenient, only if phone is valid)
        if first_name and last_name and normalized_phone and len(normalized_phone) >= 9:
            queries |= Q(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                phone_number__icontains=normalized_phone[-9:]  # Last 9 digits
            )
        
        if queries:
            existing = Patient.objects.filter(queries, is_deleted=False).first()
            if existing:
                return existing
        
        return None

    def import_patient(self, patient_data, legacy_pid_map):
        """Import a single patient record"""
        # Map legacy fields to new model fields
        first_name = patient_data.get('fname', '').strip()
        last_name = patient_data.get('lname', '').strip()
        middle_name = patient_data.get('mname', '').strip()
        
        # Skip if no name
        if not first_name and not last_name:
            return None, 'Skipped: No name'
        
        # Check for duplicate
        existing = self.check_duplicate_patient(patient_data)
        if existing:
            legacy_pid_map[patient_data.get('pid', '')] = existing
            return existing, 'Duplicate: Exists as MRN ' + existing.mrn
        
        # Get phone (prefer cell, then home, then contact)
        phone = patient_data.get('phone_cell') or patient_data.get('phone_home') or patient_data.get('phone_contact') or ''
        normalized_phone = self.normalize_phone(phone)
        
        # Parse dates
        dob = self.parse_date(patient_data.get('DOB', ''))
        if not dob:
            dob = timezone.now().date() - timezone.timedelta(days=365*30)  # Default to 30 years ago
        
        # Map gender
        sex = patient_data.get('sex', '').upper()
        gender = 'M' if sex.startswith('M') else 'F' if sex.startswith('F') else 'M'
        
        # Build address
        street = patient_data.get('street', '').strip()
        city = patient_data.get('city', '').strip()
        state = patient_data.get('state', '').strip()
        postal_code = patient_data.get('postal_code', '').strip()
        country_code = patient_data.get('country_code', '').strip()
        address_parts = [p for p in [street, city, state, postal_code, country_code] if p]
        address = ', '.join(address_parts) if address_parts else ''
        
        # Get MRN (prefer pubpid, fallback to auto-generated)
        mrn = patient_data.get('pubpid', '').strip()
        if not mrn:
            mrn = None  # Will be auto-generated
        
        # Create patient
        patient = Patient(
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            date_of_birth=dob,
            gender=gender,
            phone_number=normalized_phone if normalized_phone else '',
            email=patient_data.get('email', '').strip(),
            address=address,
            national_id=patient_data.get('ss', '').strip() or None,
            mrn=mrn,
            # Insurance info
            insurance_company=patient_data.get('insurance_name', '').strip() or '',
            insurance_id=patient_data.get('policy_number', '').strip() or '',
            # Emergency contact
            next_of_kin_name=patient_data.get('guardiansname', '').strip() or patient_data.get('mothersname', '').strip() or '',
            next_of_kin_phone=self.normalize_phone(patient_data.get('guardianphone', '')) or '',
            next_of_kin_relationship=patient_data.get('guardianrelationship', '').strip() or patient_data.get('contact_relationship', '').strip() or '',
        )
        
        # Save patient (will auto-generate MRN if needed)
        try:
            patient.save()
            legacy_pid_map[patient_data.get('pid', '')] = patient
            return patient, 'Imported'
        except Exception as e:
            # If save failed (likely duplicate constraint), rollback and check again
            from django.db import transaction
            transaction.rollback()
            
            # Check if duplicate exists (might have been created by another process)
            try:
                existing = self.check_duplicate_patient(patient_data)
                if existing:
                    legacy_pid_map[patient_data.get('pid', '')] = existing
                    return existing, 'Duplicate: Exists as MRN ' + existing.mrn
            except Exception:
                pass
            
            return None, f'Error: {str(e)}'

    def import_encounter(self, encounter_data, legacy_pid_map):
        """Import a single encounter record"""
        legacy_pid = encounter_data.get('pid', '')
        if not legacy_pid:
            return None, 'Skipped: No patient ID'
        
        # Get patient from map
        patient = legacy_pid_map.get(legacy_pid)
        if not patient:
            return None, f'Skipped: Patient {legacy_pid} not found'
        
        # Parse encounter date
        encounter_date = self.parse_datetime(encounter_data.get('date', ''))
        if not encounter_date:
            return None, 'Skipped: No encounter date'
        
        # Map encounter type (pc_catid: 5=outpatient, 9=emergency, 11=inpatient)
        pc_catid = encounter_data.get('pc_catid', '5')
        encounter_type_map = {
            '5': 'outpatient',
            '9': 'er',
            '11': 'inpatient',
            '18': 'surgery',
        }
        encounter_type = encounter_type_map.get(str(pc_catid), 'outpatient')
        
        # Map pricelevel to payer
        pricelevel = encounter_data.get('pricelevel', 'cash').lower()
        payer = None
        if pricelevel not in ['cash', '']:
            payer, _ = Payer.objects.get_or_create(
                name=pricelevel.title(),
                defaults={
                    'payer_type': 'insurance' if pricelevel not in ['corp', 'corporate'] else 'corporate',
                    'is_active': True
                }
            )
        
        # Determine status (enable=1 means active)
        enable = encounter_data.get('enable', '1')
        status = 'active' if str(enable) == '1' else 'completed'
        
        # Check for duplicate encounter (same patient, same date/time)
        existing = Encounter.objects.filter(
            patient=patient,
            started_at=encounter_date,
            is_deleted=False
        ).first()
        
        if existing:
            return existing, 'Duplicate encounter'
        
        # Create encounter
        encounter = Encounter(
            patient=patient,
            encounter_type=encounter_type,
            status=status,
            started_at=encounter_date,
            chief_complaint=encounter_data.get('reason', '').strip() or 'Visit',
            diagnosis=encounter_data.get('diagnosis', '').strip() or '',
            notes=encounter_data.get('billing_note', '').strip() or '',
        )
        
        try:
            encounter.save()
            return encounter, 'Imported'
        except Exception as e:
            return None, f'Error: {str(e)}'

    def handle(self, *args, **options):
        patient_file = options['patient_file']
        encounter_file = options['encounter_file']
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        skip_encounters = options['skip_encounters']
        
        if not os.path.exists(patient_file):
            self.stdout.write(self.style.ERROR(f'Patient file not found: {patient_file}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Reading patients from: {patient_file}'))
        if not skip_encounters and os.path.exists(encounter_file):
            self.stdout.write(self.style.SUCCESS(f'Reading encounters from: {encounter_file}'))
        
        stats = {
            'patients_processed': 0,
            'patients_imported': 0,
            'patients_duplicate': 0,
            'patients_skipped': 0,
            'patients_errors': 0,
            'encounters_processed': 0,
            'encounters_imported': 0,
            'encounters_duplicate': 0,
            'encounters_skipped': 0,
            'encounters_errors': 0,
        }
        
        # Map legacy PID to new Patient objects
        legacy_pid_map = {}
        
        # Import patients
        with open(patient_file, 'r', encoding='utf-8', errors='ignore') as f:
            batch = []
            for line_num, line in enumerate(f, 1):
                if line_num % 10000 == 0:
                    self.stdout.write(f'Reading line {line_num}...')
                
                if 'INSERT INTO patient_data VALUES' not in line:
                    continue
                
                parts = self.parse_values_line(line)
                if not parts or len(parts) < 50:
                    continue
                
                # Map fields based on CREATE TABLE structure
                patient_data = {
                    'id': parts[0] if len(parts) > 0 else '',
                    'pid': parts[46] if len(parts) > 46 else '',  # pid field
                    'fname': parts[8] if len(parts) > 8 else '',
                    'lname': parts[9] if len(parts) > 9 else '',
                    'mname': parts[10] if len(parts) > 10 else '',
                    'DOB': parts[11] if len(parts) > 11 else '',
                    'street': parts[12] if len(parts) > 12 else '',
                    'postal_code': parts[13] if len(parts) > 13 else '',
                    'city': parts[14] if len(parts) > 14 else '',
                    'state': parts[15] if len(parts) > 15 else '',
                    'country_code': parts[16] if len(parts) > 16 else '',
                    'drivers_license': parts[17] if len(parts) > 17 else '',
                    'ss': parts[18] if len(parts) > 18 else '',  # National ID
                    'phone_home': parts[20] if len(parts) > 20 else '',
                    'phone_biz': parts[21] if len(parts) > 21 else '',
                    'phone_contact': parts[22] if len(parts) > 22 else '',
                    'phone_cell': parts[23] if len(parts) > 23 else '',
                    'sex': parts[28] if len(parts) > 28 else '',
                    'email': parts[33] if len(parts) > 33 else '',
                    'email_direct': parts[34] if len(parts) > 34 else '',
                    'pubpid': parts[46] if len(parts) > 46 else '',  # Public Patient ID
                    'guardiansname': parts[67] if len(parts) > 67 else '',
                    'guardianphone': parts[91] if len(parts) > 91 else '',
                    'guardianrelationship': parts[84] if len(parts) > 84 else '',
                    'mothersname': parts[66] if len(parts) > 66 else '',
                    'contact_relationship': parts[26] if len(parts) > 26 else '',
                    'date': parts[27] if len(parts) > 27 else '',
                    'pricelevel': parts[96] if len(parts) > 96 else '',
                    'insurance_name': parts[41] if len(parts) > 41 else '',
                    'policy_number': parts[42] if len(parts) > 42 else '',
                }
                
                batch.append(patient_data)
                
                if len(batch) >= batch_size:
                    if not dry_run:
                        # Process each patient individually to handle errors better
                        for pd in batch:
                            stats['patients_processed'] += 1
                            try:
                                with transaction.atomic():
                                    patient, message = self.import_patient(pd, legacy_pid_map)
                                    if patient:
                                        if 'Duplicate' in message:
                                            stats['patients_duplicate'] += 1
                                        elif 'Imported' in message:
                                            stats['patients_imported'] += 1
                                        else:
                                            stats['patients_skipped'] += 1
                                    else:
                                        stats['patients_errors'] += 1
                                        if stats['patients_errors'] <= 10:
                                            self.stdout.write(self.style.WARNING(f'  Error importing {pd.get("fname", "")} {pd.get("lname", "")}: {message}'))
                            except Exception as e:
                                stats['patients_errors'] += 1
                                if stats['patients_errors'] <= 10:
                                    self.stdout.write(self.style.WARNING(f'  Exception importing {pd.get("fname", "")} {pd.get("lname", "")}: {str(e)}'))
                    else:
                        # Dry run - just check for duplicates and build map
                        for pd in batch:
                            stats['patients_processed'] += 1
                            existing = self.check_duplicate_patient(pd)
                            if existing:
                                stats['patients_duplicate'] += 1
                                legacy_pid_map[pd.get('pid', '')] = existing
                            else:
                                stats['patients_imported'] += 1
                                # In dry run, create a dummy entry so encounters can be counted
                                legacy_pid_map[pd.get('pid', '')] = 'DRY_RUN'
                    
                    batch = []
                    
                    # Progress update
                    if stats['patients_processed'] % 1000 == 0:
                        self.stdout.write(f'Processed {stats["patients_processed"]} patients...')
            
            # Process remaining batch
            if batch:
                if not dry_run:
                    # Process each patient individually to handle errors better
                    for pd in batch:
                        stats['patients_processed'] += 1
                        try:
                            with transaction.atomic():
                                patient, message = self.import_patient(pd, legacy_pid_map)
                                if patient:
                                    if 'Duplicate' in message:
                                        stats['patients_duplicate'] += 1
                                    elif 'Imported' in message:
                                        stats['patients_imported'] += 1
                                    else:
                                        stats['patients_skipped'] += 1
                                else:
                                    stats['patients_errors'] += 1
                        except Exception as e:
                            stats['patients_errors'] += 1
                            if stats['patients_errors'] <= 10:
                                self.stdout.write(self.style.WARNING(f'  Exception importing {pd.get("fname", "")} {pd.get("lname", "")}: {str(e)}'))
                else:
                    for pd in batch:
                        stats['patients_processed'] += 1
                        existing = self.check_duplicate_patient(pd)
                        if existing:
                            stats['patients_duplicate'] += 1
                            legacy_pid_map[pd.get('pid', '')] = existing
                        else:
                            stats['patients_imported'] += 1
                            legacy_pid_map[pd.get('pid', '')] = 'DRY_RUN'
        
        # Import encounters
        if not skip_encounters and os.path.exists(encounter_file):
            self.stdout.write(self.style.SUCCESS(f'\nImporting encounters from: {encounter_file}'))
            
            with open(encounter_file, 'r', encoding='utf-8', errors='ignore') as f:
                batch = []
                for line_num, line in enumerate(f, 1):
                    if line_num % 10000 == 0:
                        self.stdout.write(f'Reading encounter line {line_num}...')
                    
                    if 'INSERT INTO form_encounter VALUES' not in line:
                        continue
                    
                    parts = self.parse_values_line(line)
                    if not parts or len(parts) < 20:
                        continue
                    
                    # Map fields based on CREATE TABLE structure
                    encounter_data = {
                        'id': parts[0] if len(parts) > 0 else '',
                        'date': parts[1] if len(parts) > 1 else '',
                        'reason': parts[2] if len(parts) > 2 else '',
                        'facility': parts[3] if len(parts) > 3 else '',
                        'facility_id': parts[4] if len(parts) > 4 else '',
                        'pid': parts[5] if len(parts) > 5 else '',  # Patient ID
                        'encounter': parts[6] if len(parts) > 6 else '',
                        'onset_date': parts[7] if len(parts) > 7 else '',
                        'sensitivity': parts[8] if len(parts) > 8 else '',
                        'billing_note': parts[9] if len(parts) > 9 else '',
                        'pc_catid': parts[10] if len(parts) > 10 else '5',
                        'pricelevel': parts[22] if len(parts) > 22 else 'cash',
                        'enable': parts[38] if len(parts) > 38 else '1',
                        'insurance_name': parts[41] if len(parts) > 41 else '',
                        'policy_number': parts[42] if len(parts) > 42 else '',
                    }
                    
                    batch.append(encounter_data)
                    
                    if len(batch) >= batch_size:
                        if not dry_run:
                            with transaction.atomic():
                                for ed in batch:
                                    stats['encounters_processed'] += 1
                                    encounter, message = self.import_encounter(ed, legacy_pid_map)
                                    if encounter:
                                        if 'Duplicate' in message:
                                            stats['encounters_duplicate'] += 1
                                        elif 'Imported' in message:
                                            stats['encounters_imported'] += 1
                                        else:
                                            stats['encounters_skipped'] += 1
                                    else:
                                        stats['encounters_errors'] += 1
                        else:
                            for ed in batch:
                                stats['encounters_processed'] += 1
                                legacy_pid = ed.get('pid', '')
                                if legacy_pid in legacy_pid_map and legacy_pid_map[legacy_pid] != 'DRY_RUN':
                                    # Check if encounter would be duplicate
                                    patient = legacy_pid_map[legacy_pid]
                                    encounter_date = self.parse_datetime(ed.get('date', ''))
                                    if encounter_date and isinstance(patient, Patient):
                                        existing = Encounter.objects.filter(
                                            patient=patient,
                                            started_at=encounter_date,
                                            is_deleted=False
                                        ).exists()
                                        if existing:
                                            stats['encounters_duplicate'] += 1
                                        else:
                                            stats['encounters_imported'] += 1
                                    else:
                                        stats['encounters_imported'] += 1
                                else:
                                    stats['encounters_skipped'] += 1
                        
                        batch = []
                        
                        # Progress update
                        if stats['encounters_processed'] % 1000 == 0:
                            self.stdout.write(f'Processed {stats["encounters_processed"]} encounters...')
                
                # Process remaining batch
                if batch:
                    if not dry_run:
                        with transaction.atomic():
                            for ed in batch:
                                stats['encounters_processed'] += 1
                                encounter, message = self.import_encounter(ed, legacy_pid_map)
                                if encounter:
                                    if 'Duplicate' in message:
                                        stats['encounters_duplicate'] += 1
                                    elif 'Imported' in message:
                                        stats['encounters_imported'] += 1
                                    else:
                                        stats['encounters_skipped'] += 1
                                else:
                                    stats['encounters_errors'] += 1
                    else:
                        for ed in batch:
                            stats['encounters_processed'] += 1
                            legacy_pid = ed.get('pid', '')
                            if legacy_pid in legacy_pid_map and legacy_pid_map[legacy_pid] != 'DRY_RUN':
                                # Check if encounter would be duplicate
                                patient = legacy_pid_map[legacy_pid]
                                encounter_date = self.parse_datetime(ed.get('date', ''))
                                if encounter_date and isinstance(patient, Patient):
                                    existing = Encounter.objects.filter(
                                        patient=patient,
                                        started_at=encounter_date,
                                        is_deleted=False
                                    ).exists()
                                    if existing:
                                        stats['encounters_duplicate'] += 1
                                    else:
                                        stats['encounters_imported'] += 1
                                else:
                                    stats['encounters_imported'] += 1
                            else:
                                stats['encounters_skipped'] += 1
        
        # Print summary
        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}'))
        self.stdout.write(f'Patients:')
        self.stdout.write(f'  - Processed: {stats["patients_processed"]}')
        self.stdout.write(f'  - Imported: {stats["patients_imported"]}')
        self.stdout.write(f'  - Duplicates (skipped): {stats["patients_duplicate"]}')
        self.stdout.write(f'  - Skipped: {stats["patients_skipped"]}')
        self.stdout.write(f'  - Errors: {stats["patients_errors"]}')
        
        if not skip_encounters:
            self.stdout.write(f'\nEncounters:')
            self.stdout.write(f'  - Processed: {stats["encounters_processed"]}')
            self.stdout.write(f'  - Imported: {stats["encounters_imported"]}')
            self.stdout.write(f'  - Duplicates (skipped): {stats["encounters_duplicate"]}')
            self.stdout.write(f'  - Skipped: {stats["encounters_skipped"]}')
            self.stdout.write(f'  - Errors: {stats["encounters_errors"]}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️ DRY RUN - No changes were made'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Import completed successfully!'))

"""
Django Management Command to Import Legacy Patients and Insurance Data
Imports patients from patient_data.sql and links them to insurance companies
"""
import re
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from hospital.models import Patient
from hospital.models_insurance_companies import InsuranceCompany, PatientInsurance


class Command(BaseCommand):
    help = 'Import legacy patients and their insurance data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-dir',
            type=str,
            default=r'C:\Users\user\Videos\DS',
            help='Directory containing SQL files'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually importing data'
        )
        parser.add_argument(
            '--patients-only',
            action='store_true',
            help='Import only patients, skip insurance linking'
        )
        parser.add_argument(
            '--insurance-only',
            action='store_true',
            help='Import only insurance links, skip patients'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of records to import (for testing)'
        )
    
    def handle(self, *args, **options):
        try:
            # Force output to be written immediately
            import sys
            sys.stdout.flush()
            sys.stderr.flush()
            
            sql_dir = options['sql_dir']
            dry_run = options['dry_run']
            patients_only = options['patients_only']
            insurance_only = options['insurance_only']
            limit = options['limit']
            
            # Write initial output
            self.stdout.write('')
            self.stdout.write('=' * 60)
            self.stdout.write('Legacy Patient Import Command')
            self.stdout.write('=' * 60)
            self.stdout.write(f'SQL Directory: {sql_dir}')
            self.stdout.write(f'Patients Only: {patients_only}')
            self.stdout.write(f'Insurance Only: {insurance_only}')
            self.stdout.write(f'Dry Run: {dry_run}')
            self.stdout.write(f'Limit: {limit}')
            self.stdout.write('=' * 60)
            
            if not os.path.exists(sql_dir):
                raise CommandError(f'SQL directory does not exist: {sql_dir}')
            
            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
            
            self.stdout.write(self.style.SUCCESS('Starting legacy data import...'))
            
            # Import patients first
            if not insurance_only:
                patient_file = os.path.join(sql_dir, 'patient_data.sql')
                self.stdout.write(f'Looking for patient file: {patient_file}')
                if os.path.exists(patient_file):
                    self.stdout.write(f'Found patient file: {patient_file}')
                    patient_map = self.import_patients(patient_file, dry_run, limit)
                else:
                    self.stdout.write(self.style.WARNING(f'File not found: {patient_file}'))
                    patient_map = {}
            else:
                # Build map from existing patients
                patient_map = self.build_patient_map_from_db()
            
            # Import insurance mappings
            if not patients_only:
                insurance_file = os.path.join(sql_dir, 'insurance_data.sql')
                if os.path.exists(insurance_file):
                    self.import_insurance_data(insurance_file, patient_map, dry_run, limit)
                else:
                    self.stdout.write(self.style.WARNING(f'File not found: {insurance_file}'))
            
            self.stdout.write(self.style.SUCCESS('[OK] Legacy data import completed!'))
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'Error in handle: {str(e)}'))
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise
    
    def import_patients(self, file_path, dry_run=False, limit=None):
        """Import patients from patient_data.sql"""
        self.stdout.write('Importing patients...')
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            self.stdout.write(f'  File read successfully. Size: {len(content)} characters')
            
            # Extract INSERT statements
            insert_pattern = r'INSERT INTO patient_data VALUES\((.*?)\);'
            matches = re.findall(insert_pattern, content, re.DOTALL)
            
            self.stdout.write(f'  Found {len(matches)} INSERT statements')
            
            if limit:
                matches = matches[:limit]
                self.stdout.write(f'  Limited to first {limit} records')
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f'Error reading file: {str(e)}'))
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        patient_map = {}
        
        for match in matches:
            try:
                values = self.parse_sql_values(match)
                
                # Map fields from patient_data table
                if len(values) < 45:
                    skipped_count += 1
                    continue
                
                legacy_pid = values[44] if len(values) > 44 and values[44] else values[0]
                fname = values[4] if values[4] else ''
                lname = values[5] if values[5] else ''
                mname = values[6] if values[6] else ''
                dob = self.parse_date(values[7]) if len(values) > 7 and values[7] else None
                sex = values[24] if len(values) > 24 and values[24] else 'M'
                address = values[8] if len(values) > 8 and values[8] else ''
                phone = values[19] if len(values) > 19 and values[19] else ''
                email = values[29] if len(values) > 29 and values[29] else ''
                national_id = values[14] if len(values) > 14 and values[14] else ''
                
                # Skip invalid records
                if not legacy_pid or not fname or not lname:
                    skipped_count += 1
                    continue
                
                # Map gender
                gender_map = {'Male': 'M', 'Female': 'F', 'M': 'M', 'F': 'F', 'male': 'M', 'female': 'F'}
                gender = gender_map.get(sex, 'M')
                
                # Create MRN from legacy PID
                mrn = f"LEGACY{str(legacy_pid).zfill(6)}"
                
                if not dry_run:
                    with transaction.atomic():
                        # Check if patient exists by MRN or national_id
                        existing = None
                        if national_id:
                            existing = Patient.objects.filter(national_id=national_id).first()
                        
                        if not existing:
                            existing = Patient.objects.filter(mrn=mrn).first()
                        
                        if existing:
                            # Update existing patient
                            existing.first_name = fname
                            existing.last_name = lname
                            existing.middle_name = mname
                            if dob:
                                existing.date_of_birth = dob
                            existing.gender = gender
                            existing.address = address
                            existing.phone_number = phone[:17] if phone else ''
                            existing.email = email
                            existing.save()
                            patient_map[legacy_pid] = existing
                            updated_count += 1
                        else:
                            # Create new patient
                            patient = Patient.objects.create(
                                mrn=mrn,
                                national_id=national_id if national_id else None,
                                first_name=fname,
                                last_name=lname,
                                middle_name=mname,
                                date_of_birth=dob or datetime(2000, 1, 1).date(),
                                gender=gender,
                                address=address,
                                phone_number=phone[:17] if phone else '',
                                email=email,
                            )
                            patient_map[legacy_pid] = patient
                            created_count += 1
                            
                            if created_count % 100 == 0:
                                self.stdout.write(f'  Progress: {created_count} patients created...')
                else:
                    self.stdout.write(
                        f'  [DRY RUN] Would import: PID {legacy_pid} - {fname} {lname}'
                    )
                    created_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing patient: {str(e)}'))
                self.stdout.write(self.style.ERROR(f'Record: {match[:100]}...'))
                skipped_count += 1
                continue
        
        self.stdout.write(self.style.SUCCESS(
            f'Patients: {created_count} created, {updated_count} updated, {skipped_count} skipped'
        ))
        
        return patient_map
    
    def build_patient_map_from_db(self):
        """Build patient map from existing database records"""
        patient_map = {}
        
        for patient in Patient.objects.all():
            # Extract legacy PID from MRN if it follows LEGACY format
            if patient.mrn.startswith('LEGACY'):
                try:
                    legacy_pid = patient.mrn.replace('LEGACY', '').lstrip('0')
                    patient_map[legacy_pid] = patient
                except:
                    pass
        
        return patient_map
    
    def import_insurance_data(self, file_path, patient_map, dry_run=False, limit=None):
        """Import insurance data and create PatientInsurance records"""
        self.stdout.write('Importing patient insurance enrollments...')
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Build insurance company map
        insurance_map = self.build_insurance_map()
        
        # Extract INSERT statements
        insert_pattern = r'INSERT INTO insurance_data VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        if limit:
            matches = matches[:limit]
            self.stdout.write(f'  Limited to first {limit} records')
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for match in matches:
            try:
                values = self.parse_sql_values(match)
                
                if len(values) < 27:
                    skipped_count += 1
                    continue
                
                # Extract relevant fields
                insurance_type = values[1] if values[1] else 'primary'
                provider_id = values[2] if values[2] else ''
                plan_name = values[3] if values[3] else ''
                policy_number = values[4] if values[4] else ''
                group_number = values[5] if values[5] else ''
                subscriber_fname = values[8] if len(values) > 8 and values[8] else ''
                subscriber_lname = values[6] if len(values) > 6 and values[6] else ''
                subscriber_relationship = values[9] if len(values) > 9 and values[9] else 'self'
                subscriber_dob_str = values[11] if len(values) > 11 and values[11] else None
                copay = values[24] if len(values) > 24 and values[24] else '0.00'
                date_str = values[25] if len(values) > 25 and values[25] else ''
                patient_pid = values[26] if len(values) > 26 and values[26] else ''
                
                # Skip invalid records
                if not patient_pid or not provider_id:
                    skipped_count += 1
                    continue
                
                # Skip empty/null insurance companies
                if provider_id.strip() in ['', '0', 'NULL', ' ', '84', '96', '99']:
                    # 84, 96, 99 appear to be placeholder values in the data
                    skipped_count += 1
                    continue
                
                # Skip NULL policy numbers
                if policy_number == 'NULL':
                    policy_number = ''
                
                # Get insurance company
                insurance_company = insurance_map.get(provider_id.strip())
                if not insurance_company:
                    # Try without leading zeros
                    try:
                        insurance_company = insurance_map.get(str(int(provider_id)))
                    except:
                        pass
                
                if not insurance_company:
                    error_count += 1
                    continue
                
                # Get patient
                patient = patient_map.get(str(patient_pid))
                if not patient:
                    skipped_count += 1
                    continue
                
                # Parse dates
                effective_date = self.parse_date(date_str) or timezone.now().date()
                subscriber_dob = self.parse_date(subscriber_dob_str)
                
                if not dry_run:
                    with transaction.atomic():
                        # Create or update patient insurance
                        patient_insurance, created = PatientInsurance.objects.update_or_create(
                            patient=patient,
                            insurance_company=insurance_company,
                            member_id=policy_number or f"MEM-{patient_pid}",
                            defaults={
                                'policy_number': policy_number or f"POL-{patient_pid}",
                                'group_number': group_number,
                                'is_primary_subscriber': subscriber_relationship.lower() == 'self',
                                'relationship_to_subscriber': self.map_relationship(subscriber_relationship),
                                'subscriber_name': f"{subscriber_fname} {subscriber_lname}".strip(),
                                'subscriber_dob': subscriber_dob,
                                'effective_date': effective_date,
                                'status': 'active',
                                'is_primary': insurance_type == 'primary',
                                'notes': f"Plan: {plan_name}" if plan_name else '',
                            }
                        )
                        
                        if created:
                            created_count += 1
                            if created_count % 100 == 0:
                                self.stdout.write(f'  Progress: {created_count} insurance links created...')
                        else:
                            updated_count += 1
                else:
                    self.stdout.write(
                        f'  [DRY RUN] {patient.full_name} -> {insurance_company.name} ({insurance_type}) Policy: {policy_number}'
                    )
                    created_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing insurance record: {str(e)}'))
                error_count += 1
                continue
        
        self.stdout.write(self.style.SUCCESS(
            f'Patient Insurance: {created_count} created, {updated_count} updated, '
            f'{skipped_count} skipped, {error_count} errors'
        ))
    
    def build_insurance_map(self):
        """Build mapping of legacy insurance company IDs to Django InsuranceCompany objects"""
        insurance_map = {}
        
        for company in InsuranceCompany.objects.all():
            # Extract numeric ID from codes like INS7, INS24, INS40, etc.
            if company.code.startswith('INS'):
                try:
                    legacy_id = company.code[3:]  # Remove 'INS' prefix
                    insurance_map[legacy_id] = company
                except:
                    pass
            else:
                # Direct codes like APEX, NHIS, GLI, etc.
                insurance_map[company.code] = company
        
        return insurance_map
    
    def parse_sql_values(self, values_str):
        """Parse SQL VALUES string into a list"""
        import csv
        from io import StringIO
        
        # Clean up the string
        values_str = values_str.strip()
        
        # Use csv reader to handle quoted strings properly
        reader = csv.reader(StringIO(values_str), delimiter=',', quotechar='"')
        try:
            values = list(reader)[0]
        except:
            # Fallback to simple split
            values = [v.strip().strip('"').strip("'") for v in values_str.split(',')]
        
        return values
    
    def parse_date(self, date_str):
        """Parse date string to date object"""
        if not date_str or date_str in ['0000-00-00', '00-00-00', '', 'NULL']:
            return None
        
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').date()
            except:
                return None
    
    def map_relationship(self, relationship):
        """Map legacy relationship to Django choices"""
        relationship_map = {
            'self': 'self',
            'spouse': 'spouse',
            'child': 'child',
            'parent': 'parent',
            'dependent': 'dependent',
        }
        return relationship_map.get(relationship.lower(), 'self')




















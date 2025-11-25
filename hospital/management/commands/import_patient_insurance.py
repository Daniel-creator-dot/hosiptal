"""
Django Management Command to Import Patient Insurance Data
Links patients to their insurance companies from legacy data
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
    help = 'Import patient insurance data and create PatientInsurance records'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-file',
            type=str,
            default=r'C:\Users\user\Videos\DS\insurance_data.sql',
            help='Path to insurance_data.sql file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually importing data'
        )
    
    def handle(self, *args, **options):
        sql_file = options['sql_file']
        dry_run = options['dry_run']
        
        if not os.path.exists(sql_file):
            raise CommandError(f'SQL file does not exist: {sql_file}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
        
        self.stdout.write(self.style.SUCCESS('Starting patient insurance import...'))
        
        # Build mapping of legacy IDs to Django objects
        self.stdout.write('Building insurance company mapping...')
        insurance_map = self.build_insurance_map()
        self.stdout.write(f'  Found {len(insurance_map)} insurance companies')
        
        self.stdout.write('Building patient mapping...')
        patient_map = self.build_patient_map()
        self.stdout.write(f'  Found {len(patient_map)} patients')
        
        # Import insurance data
        self.import_insurance_data(sql_file, insurance_map, patient_map, dry_run)
        
        self.stdout.write(self.style.SUCCESS('✓ Patient insurance import completed!'))
    
    def build_insurance_map(self):
        """Build mapping of legacy insurance company IDs to Django InsuranceCompany objects"""
        insurance_map = {}
        
        # Map by extracting the numeric ID from our generated codes
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
    
    def build_patient_map(self):
        """Build mapping of legacy patient IDs to Django Patient objects"""
        patient_map = {}
        
        # Assuming MRN format contains legacy patient ID
        # or we have a mapping table (this needs to be adjusted based on actual data)
        for patient in Patient.objects.all():
            # Try to extract legacy PID from MRN or other field
            # This is a placeholder - adjust based on your actual patient import logic
            if hasattr(patient, 'legacy_pid'):
                patient_map[str(patient.legacy_pid)] = patient
            # If patients were imported with their legacy IDs as part of MRN
            # you'll need to adjust this logic
        
        return patient_map
    
    def import_insurance_data(self, file_path, insurance_map, patient_map, dry_run=False):
        """Import insurance data from SQL file"""
        self.stdout.write('Importing patient insurance enrollments...')
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract INSERT statements
        insert_pattern = r'INSERT INTO insurance_data VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for match in matches:
            try:
                # Parse the values
                values = self.parse_sql_values(match)
                
                if len(values) < 33:
                    skipped_count += 1
                    continue
                
                # Extract relevant fields
                insurance_type = values[1] if values[1] else 'primary'
                provider_id = values[2] if values[2] else ''
                plan_name = values[3] if values[3] else ''
                policy_number = values[4] if values[4] else ''
                group_number = values[5] if values[5] else ''
                subscriber_fname = values[8] if values[8] else ''
                subscriber_lname = values[6] if values[6] else ''
                subscriber_relationship = values[9] if values[9] else 'self'
                subscriber_dob = values[11] if values[11] else None
                copay = values[24] if values[24] else '0.00'
                date_str = values[25] if values[25] else ''
                patient_pid = values[26] if values[26] else ''
                
                # Skip invalid records
                if not patient_pid or not provider_id:
                    skipped_count += 1
                    continue
                
                # Skip empty/null insurance companies
                if provider_id.strip() in ['', '0', 'NULL', ' ']:
                    skipped_count += 1
                    continue
                
                # Get insurance company
                insurance_company = insurance_map.get(provider_id.strip())
                if not insurance_company:
                    # Try without leading zeros
                    insurance_company = insurance_map.get(str(int(provider_id)))
                
                if not insurance_company:
                    self.stdout.write(self.style.WARNING(
                        f'  Insurance company not found: {provider_id} for patient {patient_pid}'
                    ))
                    error_count += 1
                    continue
                
                # Get patient - THIS NEEDS TO BE ADJUSTED
                # Since we don't have the actual patient import yet, we'll skip this for now
                # or implement a lookup strategy
                
                # For now, log what would be created
                if dry_run or not patient_map:
                    self.stdout.write(
                        f'  [WOULD CREATE] Patient PID:{patient_pid} -> {insurance_company.name} '
                        f'({insurance_type}) Policy: {policy_number}'
                    )
                    created_count += 1
                    continue
                
                patient = patient_map.get(str(patient_pid))
                if not patient:
                    skipped_count += 1
                    continue
                
                # Parse dates
                effective_date = self.parse_date(date_str) or timezone.now().date()
                
                if not dry_run:
                    with transaction.atomic():
                        # Create or update patient insurance
                        patient_insurance, created = PatientInsurance.objects.update_or_create(
                            patient=patient,
                            insurance_company=insurance_company,
                            policy_number=policy_number or f"LEGACY-{patient_pid}",
                            defaults={
                                'member_id': policy_number or f"MEM-{patient_pid}",
                                'group_number': group_number,
                                'is_primary_subscriber': subscriber_relationship.lower() == 'self',
                                'relationship_to_subscriber': self.map_relationship(subscriber_relationship),
                                'subscriber_name': f"{subscriber_fname} {subscriber_lname}".strip(),
                                'effective_date': effective_date,
                                'status': 'active',
                                'is_primary': insurance_type == 'primary',
                                'notes': f"Plan: {plan_name}, Copay: {copay}",
                            }
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(f'  ✓ Enrolled: {patient.full_name} -> {insurance_company.name}')
                        else:
                            updated_count += 1
                            self.stdout.write(f'  ⟳ Updated: {patient.full_name} -> {insurance_company.name}')
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing record: {str(e)}'))
                error_count += 1
                continue
        
        self.stdout.write(self.style.SUCCESS(
            f'Patient Insurance: {created_count} created, {updated_count} updated, '
            f'{skipped_count} skipped, {error_count} errors'
        ))
    
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




















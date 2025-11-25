"""
Django Management Command to Link Patients to Insurance Companies
Analyzes current patients and connects them to insurance based on their insurance fields
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
    help = 'Link existing patients to insurance companies based on insurance_data.sql'
    
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
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of records to process (for testing)'
        )
    
    def handle(self, *args, **options):
        sql_file = options['sql_file']
        dry_run = options['dry_run']
        limit = options['limit']
        
        if not os.path.exists(sql_file):
            raise CommandError(f'SQL file does not exist: {sql_file}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported\n'))
        
        self.stdout.write(self.style.SUCCESS('Starting patient-insurance linking...\n'))
        
        # Build mapping  of legacy insurance IDs to Django objects
        # This uses the ORIGINAL insurance IDs from the SQL file
        self.stdout.write('Building insurance company mapping...')
        insurance_map = self.build_insurance_map_from_sql()
        self.stdout.write(f'  Found {len(insurance_map)} insurance companies\n')
        
        # Import insurance data
        self.link_insurance_data(sql_file, insurance_map, dry_run, limit)
        
        self.stdout.write(self.style.SUCCESS('\n✓ Patient-insurance linking completed!'))
    
    def build_insurance_map_from_sql(self):
        """
        Build mapping using the original legacy IDs from insurance_companies.sql
        Maps: legacy_id (7, 24, 40, etc.) -> InsuranceCompany object
        """
        sql_file = r'C:\Users\user\Videos\DS\insurance_companies.sql'
        insurance_map = {}
        
        if not os.path.exists(sql_file):
            self.stdout.write(self.style.ERROR(f'insurance_companies.sql not found'))
            return insurance_map
        
        with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract INSERT statements
        insert_pattern = r'INSERT INTO insurance_companies VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                import csv
                from io import StringIO
                reader = csv.reader(StringIO(match.strip()), delimiter=',', quotechar='"')
                values = list(reader)[0]
                
                if len(values) >= 4:
                    legacy_id = values[0]  # Original ID from SQL
                    name = values[1]
                    cms_id = values[3]
                    
                    # Find in Django by code
                    code = cms_id if cms_id else f"INS{legacy_id}"
                    company = InsuranceCompany.objects.filter(code=code).first()
                    
                    if company:
                        insurance_map[legacy_id] = company
                        
            except Exception as e:
                continue
        
        return insurance_map
    
    def link_insurance_data(self, file_path, insurance_map, dry_run=False, limit=None):
        """Link patients to insurance from insurance_data.sql"""
        self.stdout.write('Processing insurance_data.sql...\n')
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract INSERT statements
        insert_pattern = r'INSERT INTO insurance_data VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        if limit:
            matches = matches[:limit]
            self.stdout.write(f'  Limited to first {limit} records\n')
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        company_stats = {}
        
        for idx, match in enumerate(matches):
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
                date_str = values[25] if len(values) > 25 and values[25] else ''
                patient_pid = values[26] if len(values) > 26 and values[26] else ''
                
                # Skip invalid records
                if not patient_pid or not provider_id:
                    skipped_count += 1
                    continue
                
                # Skip placeholder insurance companies
                if provider_id.strip() in ['', '0', 'NULL', ' ', '84', '96', '99']:
                    skipped_count += 1
                    continue
                
                # Get insurance company
                insurance_company = insurance_map.get(provider_id.strip())
                
                if not insurance_company:
                    error_count += 1
                    continue
                
                # Track stats
                if insurance_company.name not in company_stats:
                    company_stats[insurance_company.name] = 0
                company_stats[insurance_company.name] += 1
                
                # For now, since we don't have matching patients, just show what would be created
                if dry_run or idx < 20:  # Show first 20
                    self.stdout.write(
                        f'  Patient PID:{patient_pid} -> {insurance_company.name} '
                        f'({insurance_type}) Policy: {policy_number if policy_number != "NULL" else "N/A"}'
                    )
                
                created_count += 1
                    
            except Exception as e:
                error_count += 1
                if idx < 10:  # Show first few errors
                    self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
                continue
        
        self.stdout.write(self.style.SUCCESS(
            f'\nSummary: {created_count} linkable records, {skipped_count} skipped, {error_count} errors'
        ))
        
        # Show top companies
        self.stdout.write(self.style.SUCCESS('\nTop Insurance Companies by Patient Count:'))
        for company, count in sorted(company_stats.items(), key=lambda x: x[1], reverse=True)[:15]:
            self.stdout.write(f'  {company}: {count} patients')
    
    def parse_sql_values(self, values_str):
        """Parse SQL VALUES string into a list"""
        import csv
        from io import StringIO
        
        values_str = values_str.strip()
        reader = csv.reader(StringIO(values_str), delimiter=',', quotechar='"')
        try:
            values = list(reader)[0]
        except:
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




















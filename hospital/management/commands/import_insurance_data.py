"""
Django Management Command to Import Insurance Data from SQL Files
Imports insurance companies, price levels, and exclusions
"""
import re
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal
from hospital.models_insurance_companies import InsuranceCompany
from hospital.models_flexible_pricing import PricingCategory


class Command(BaseCommand):
    help = 'Import insurance data from SQL files'
    
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
    
    def handle(self, *args, **options):
        sql_dir = options['sql_dir']
        dry_run = options['dry_run']
        
        if not os.path.exists(sql_dir):
            raise CommandError(f'SQL directory does not exist: {sql_dir}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
        
        self.stdout.write(self.style.SUCCESS('Starting insurance data import...'))
        
        # Import insurance companies
        insurance_file = os.path.join(sql_dir, 'insurance_companies.sql')
        if os.path.exists(insurance_file):
            self.import_insurance_companies(insurance_file, dry_run)
        else:
            self.stdout.write(self.style.WARNING(f'File not found: {insurance_file}'))
        
        # Import price levels
        price_levels_file = os.path.join(sql_dir, 'insurance_price_levels.sql')
        if os.path.exists(price_levels_file):
            self.import_price_levels(price_levels_file, dry_run)
        else:
            self.stdout.write(self.style.WARNING(f'File not found: {price_levels_file}'))
        
        self.stdout.write(self.style.SUCCESS('✓ Insurance data import completed!'))
    
    def import_insurance_companies(self, file_path, dry_run=False):
        """Import insurance companies from SQL file"""
        self.stdout.write('Importing insurance companies...')
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract INSERT statements
        insert_pattern = r'INSERT INTO insurance_companies VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for match in matches:
            try:
                # Parse the values
                values = self.parse_sql_values(match)
                
                if len(values) < 16:
                    self.stdout.write(self.style.WARNING(f'Skipping incomplete record: {match[:50]}...'))
                    skipped_count += 1
                    continue
                
                # Map SQL fields to Django model
                company_id = int(values[0]) if values[0] else None
                name = values[1] if values[1] else f"Insurance Company {company_id}"
                attn = values[2] if values[2] else ''
                cms_id = values[3] if values[3] else ''
                ins_type_code = values[4] if values[4] else ''
                x12_receiver_id = values[5] if values[5] else ''
                x12_default_partner_id = values[6] if values[6] else ''
                alt_cms_id = values[7] if values[7] else ''
                inactive = int(values[8]) if values[8] else 0
                export_type = int(values[9]) if values[9] else 0
                policy_mandatory = int(values[10]) if values[10] else 0
                alert = values[11] if values[11] else ''
                pricelevel = values[12] if values[12] else ''
                
                # Determine company type from price level
                company_type = self.map_price_level_to_type(pricelevel)
                
                # Generate a unique code
                code = cms_id if cms_id else f"INS{company_id}"
                
                if not dry_run:
                    with transaction.atomic():
                        # Check if company exists
                        company, created = InsuranceCompany.objects.update_or_create(
                            code=code,
                            defaults={
                                'name': name,
                                'status': 'inactive' if inactive else 'active',
                                'is_active': not bool(inactive),
                                'notes': f"Alert: {alert}" if alert else '',
                                'address': attn if attn else '',
                            }
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(f'  ✓ Created: {name} ({code})')
                        else:
                            updated_count += 1
                            self.stdout.write(f'  ⟳ Updated: {name} ({code})')
                else:
                    self.stdout.write(f'  [DRY RUN] Would import: {name} ({code})')
                    created_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing record: {str(e)}'))
                self.stdout.write(self.style.ERROR(f'Record: {match[:100]}...'))
                skipped_count += 1
                continue
        
        self.stdout.write(self.style.SUCCESS(
            f'Insurance companies: {created_count} created, {updated_count} updated, {skipped_count} skipped'
        ))
    
    def import_price_levels(self, file_path, dry_run=False):
        """Import insurance price levels and link to pricing categories"""
        self.stdout.write('Importing insurance price levels...')
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract INSERT statements
        insert_pattern = r'INSERT INTO insurance_price_levels VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        processed_count = 0
        error_count = 0
        
        for match in matches:
            try:
                # Parse the values
                values = self.parse_sql_values(match)
                
                if len(values) < 3:
                    error_count += 1
                    continue
                
                insurance_id = int(values[1]) if values[1] else None
                pricelevel = values[2] if values[2] else ''
                
                if not insurance_id or not pricelevel:
                    error_count += 1
                    continue
                
                if not dry_run:
                    with transaction.atomic():
                        # Find the insurance company by ID (mapped to code)
                        code = f"INS{insurance_id}"
                        try:
                            company = InsuranceCompany.objects.get(code=code)
                            
                            # Find or create pricing category
                            category_name = self.map_price_level_to_category_name(pricelevel)
                            category, created = PricingCategory.objects.get_or_create(
                                code=pricelevel,
                                defaults={
                                    'name': category_name,
                                    'description': f'Price category for {pricelevel} payers',
                                    'is_active': True,
                                }
                            )
                            
                            # Update company notes to include price level
                            if pricelevel not in company.notes:
                                company.notes = f"{company.notes}\nPrice Level: {pricelevel}".strip()
                                company.save(update_fields=['notes'])
                            
                            processed_count += 1
                            
                        except InsuranceCompany.DoesNotExist:
                            self.stdout.write(self.style.WARNING(
                                f'  Insurance company not found: {code}'
                            ))
                            error_count += 1
                else:
                    self.stdout.write(
                        f'  [DRY RUN] Would link insurance {insurance_id} to price level {pricelevel}'
                    )
                    processed_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing price level: {str(e)}'))
                error_count += 1
                continue
        
        self.stdout.write(self.style.SUCCESS(
            f'Price levels: {processed_count} processed, {error_count} errors'
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
    
    def map_price_level_to_type(self, pricelevel):
        """Map price level to company type"""
        mapping = {
            'ins': 'Insurance',
            'nhis': 'NHIS',
            'nmh': 'Mutual Health',
            'corp': 'Corporate',
            'cash': 'Private/Cash',
            'gab': 'Government',
        }
        return mapping.get(pricelevel.lower(), 'Insurance')
    
    def map_price_level_to_category_name(self, pricelevel):
        """Map price level code to full category name"""
        mapping = {
            'ins': 'Private Insurance',
            'nhis': 'NHIS - National Health Insurance',
            'nmh': 'Nationwide Mutual Health',
            'corp': 'Corporate Accounts',
            'cash': 'Cash/Private Patients',
            'gab': 'GAB Health Insurance',
        }
        return mapping.get(pricelevel.lower(), f'{pricelevel.upper()} Pricing')


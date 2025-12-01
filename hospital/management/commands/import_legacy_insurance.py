"""
Django management command to import insurance companies from legacy SQL files.
Parses SQL INSERT statements directly without needing MySQL.
"""
import re
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from hospital.models_insurance_companies import InsuranceCompany


class Command(BaseCommand):
    help = 'Import insurance companies from legacy SQL files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='import/legacy/insurance_companies.sql',
            help='Path to insurance_companies.sql file',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of records to import (for testing)',
        )

    def parse_sql_insert(self, line):
        """Parse a SQL INSERT statement and extract values using CSV-like parsing."""
        # Match: INSERT INTO insurance_companies VALUES("7","APEX MUTUAL HEALTH",...);
        match = re.match(r'INSERT INTO\s+\w+\s+VALUES\s*\((.*)\);?$', line, re.IGNORECASE)
        if not match:
            return None
        
        values_str = match.group(1)
        values = []
        current = ''
        in_quotes = False
        quote_char = None
        
        i = 0
        while i < len(values_str):
            char = values_str[i]
            
            if not in_quotes:
                if char in ('"', "'"):
                    in_quotes = True
                    quote_char = char
                elif char == ',':
                    values.append(current.strip())
                    current = ''
                else:
                    current += char
            else:
                if char == quote_char:
                    # Check for escaped quote
                    if i + 1 < len(values_str) and values_str[i + 1] == quote_char:
                        current += quote_char
                        i += 1
                    else:
                        in_quotes = False
                        quote_char = None
                else:
                    current += char
            i += 1
        
        # Add last value
        if current or not values_str.endswith(','):
            values.append(current.strip())
        
        # Clean up values
        cleaned = []
        for v in values:
            # Remove surrounding quotes if present
            if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
                v = v[1:-1]
            cleaned.append(v)
        
        return cleaned

    def generate_code(self, cms_id, name, legacy_id, existing_codes=None):
        """Generate a unique code for the insurance company."""
        if existing_codes is None:
            existing_codes = set(InsuranceCompany.objects.values_list('code', flat=True))
        
        # Use cms_id if available
        if cms_id and cms_id.strip():
            code = cms_id.strip().upper()
            # Ensure it's unique
            if code not in existing_codes:
                return code
        
        # Generate from name (first 3-5 letters, uppercase)
        if name:
            # Remove common words and get initials
            words = name.upper().split()
            if len(words) >= 2:
                code = ''.join([w[0] for w in words[:5]])[:10]
            else:
                code = name[:10].upper().replace(' ', '')
            
            # Remove special characters
            code = re.sub(r'[^A-Z0-9]', '', code)
            
            # Ensure uniqueness
            base_code = code
            counter = 1
            while code in existing_codes:
                code = f"{base_code}{counter}"
                counter += 1
            
            return code
        
        # Fallback to legacy ID
        return f"INS{legacy_id}"
    
    def normalize_status(self, inactive, pricelevel):
        """Map legacy inactive flag and pricelevel to Django status."""
        inactive = inactive.strip() if inactive else '0'
        
        # If inactive, return inactive status
        if inactive == '1':
            return 'inactive'
        
        # Otherwise, return active
        return 'active'

    def handle(self, *args, **options):
        file_path = options['file']
        dry_run = options['dry_run']
        
        # Handle both relative and absolute paths
        if not os.path.isabs(file_path):
            # Try project root first
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            full_path = os.path.join(project_root, file_path)
            if not os.path.exists(full_path):
                # Try current directory
                full_path = file_path
        else:
            full_path = file_path
        
        if not os.path.exists(full_path):
            self.stdout.write(self.style.ERROR(f'File not found: {full_path}'))
            self.stdout.write(self.style.ERROR(f'Tried: {os.path.abspath(full_path)}'))
            return
        
        file_path = full_path
        
        self.stdout.write(self.style.SUCCESS(f'Reading insurance companies from: {file_path}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be imported'))
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        # Get existing codes for uniqueness checking
        existing_codes = set(InsuranceCompany.objects.values_list('code', flat=True)) if not dry_run else set()
        
        limit = options.get('limit')
        processed_count = 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if limit and processed_count >= limit:
                    self.stdout.write(self.style.WARNING(f'Reached limit of {limit} records'))
                    break
                    
                line = line.strip()
                if not line or not line.upper().startswith('INSERT INTO'):
                    continue
                
                try:
                    values = self.parse_sql_insert(line)
                    if not values or len(values) < 13:
                        continue
                    
                    # Extract fields based on insurance_companies table structure:
                    # id, name, attn, cms_id, ins_type_code, x12_receiver_id, x12_default_partner_id,
                    # alt_cms_id, inactive, export_type, policy_mandatory, alert, pricelevel,
                    # claim_policy, copay_service, copay_drug
                    legacy_id = values[0].strip('"\'') if len(values) > 0 else None
                    name = values[1].strip('"\'').strip() if len(values) > 1 else ''
                    attn = values[2].strip('"\'').strip() if len(values) > 2 else ''
                    cms_id = values[3].strip('"\'').strip() if len(values) > 3 else ''
                    inactive = values[8].strip('"\'').strip() if len(values) > 8 else '0'
                    alert = values[11].strip('"\'').strip() if len(values) > 11 else ''
                    pricelevel = values[12].strip('"\'').strip() if len(values) > 12 else ''
                    
                    if not name or name.lower() == 'error':
                        skipped_count += 1
                        continue
                    
                    # Generate code
                    code = self.generate_code(cms_id, name, legacy_id, existing_codes)
                    
                    # Determine status and active flag
                    status = self.normalize_status(inactive, pricelevel)
                    is_active = inactive != '1'
                    
                    # Use attn as billing_contact_name if available
                    billing_contact_name = attn if attn else ''
                    
                    # Use alert as notes if available
                    notes = alert if alert else ''
                    
                    if dry_run:
                        self.stdout.write(
                            f'Would import: {name} (code: {code}, status: {status}, active: {is_active})'
                        )
                        created_count += 1
                    else:
                        with transaction.atomic():
                            company, created = InsuranceCompany.objects.get_or_create(
                                code=code,
                                defaults={
                                    'name': name,
                                    'status': status,
                                    'is_active': is_active,
                                    'billing_contact_name': billing_contact_name,
                                    'notes': notes,
                                }
                            )
                            
                            if not created:
                                # Update existing company
                                company.name = name
                                company.status = status
                                company.is_active = is_active
                                if billing_contact_name:
                                    company.billing_contact_name = billing_contact_name
                                if notes:
                                    company.notes = notes
                                company.save(update_fields=['name', 'status', 'is_active', 
                                                           'billing_contact_name', 'notes'])
                                updated_count += 1
                            else:
                                created_count += 1
                                existing_codes.add(code)  # Track new codes
                            
                             processed_count += 1
                             if processed_count % 10 == 0:
                                 self.stdout.write(f'Processed {processed_count} records...')
                
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'Error on line {line_num}: {e}')
                    )
                    if error_count > 20:
                        self.stdout.write(self.style.ERROR('Too many errors, stopping.'))
                        break
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Import Summary:'))
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'  Would create: {created_count}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  Created: {created_count}'))
            self.stdout.write(self.style.SUCCESS(f'  Updated: {updated_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Skipped: {skipped_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Errors: {error_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 50))


"""
Django Management Command to Comprehensively Fix Corporate Payers
Matches Payer records to corporate companies from db_3 and fixes them
"""
from django.core.management.base import BaseCommand
from django.db import transaction
import re
import os
from hospital.models import Payer


class Command(BaseCommand):
    help = 'Comprehensively fix corporate payers by matching to db_3 source data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='import/db_3_extracted/insurance_companies.sql',
            help='Path to insurance_companies.sql file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually making changes'
        )
    
    def handle(self, *args, **options):
        sql_file = options['file']
        dry_run = options['dry_run']
        
        # Resolve file path
        if not os.path.isabs(sql_file):
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            sql_file = os.path.join(project_root, sql_file)
        
        if not os.path.exists(sql_file):
            raise CommandError(f'SQL file does not exist: {sql_file}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write('='*80)
        self.stdout.write('COMPREHENSIVE CORPORATE PAYER FIX')
        self.stdout.write('='*80)
        
        # Parse corporate companies from source
        corporate_companies = self.parse_corporate_companies(sql_file)
        
        self.stdout.write(f'\nFound {len(corporate_companies)} corporate companies in source data\n')
        
        fixed_count = 0
        not_found_count = 0
        
        with transaction.atomic():
            for company_data in corporate_companies:
                company_name = company_data['name']
                
                if not company_name or company_name.lower() == 'error':
                    continue
                
                # Try to find matching Payer
                # Strategy 1: Exact match
                payers = Payer.objects.filter(
                    name__iexact=company_name,
                    payer_type__in=['insurance', 'private'],
                    is_deleted=False
                )
                
                # Strategy 2: Partial match (first 15 chars)
                if not payers.exists():
                    short_name = company_name[:15].strip()
                    payers = Payer.objects.filter(
                        name__icontains=short_name,
                        payer_type__in=['insurance', 'private'],
                        is_deleted=False
                    )
                
                # Strategy 3: Normalized match (remove common words)
                if not payers.exists():
                    normalized_name = self.normalize_name(company_name)
                    for payer in Payer.objects.filter(payer_type__in=['insurance', 'private'], is_deleted=False):
                        if self.normalize_name(payer.name) == normalized_name:
                            payers = Payer.objects.filter(pk=payer.pk)
                            break
                
                if payers.exists():
                    for payer in payers:
                        if dry_run:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  Would fix: {payer.name} ({payer.payer_type}) → corporate (matches: {company_name})'
                                )
                            )
                        else:
                            payer.payer_type = 'corporate'
                            payer.save(update_fields=['payer_type'])
                            fixed_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'  ✓ Fixed: {payer.name} → corporate')
                            )
                else:
                    not_found_count += 1
                    if not dry_run:
                        # Create corporate payer if it doesn't exist
                        try:
                            payer, created = Payer.objects.get_or_create(
                                name=company_name,
                                defaults={
                                    'payer_type': 'corporate',
                                    'is_active': True,
                                }
                            )
                            if created:
                                fixed_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f'  ✓ Created: {payer.name} (corporate)')
                                )
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'  ✗ Error creating payer for {company_name}: {str(e)}')
                            )
        
        # Summary
        self.stdout.write('\n' + '='*80)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ CORPORATE PAYERS FIXED'))
        
        self.stdout.write(f'  Payers fixed/created: {fixed_count}')
        self.stdout.write(f'  Companies not matched: {not_found_count}')
        self.stdout.write('='*80)
        
        # Final verification
        if not dry_run:
            corporate_payers = Payer.objects.filter(payer_type='corporate', is_deleted=False).count()
            insurance_payers = Payer.objects.filter(payer_type__in=['insurance', 'private'], is_deleted=False).count()
            
            self.stdout.write(f'\nFinal Status:')
            self.stdout.write(f'  Corporate payers: {corporate_payers}')
            self.stdout.write(f'  Insurance payers: {insurance_payers}')
    
    def parse_corporate_companies(self, file_path):
        """Parse insurance_companies.sql and extract companies with pricelevel='corp'"""
        companies = []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        insert_pattern = r'INSERT INTO insurance_companies VALUES\((.*?)\);'
        matches = re.findall(insert_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                values = self.parse_sql_values(match)
                if len(values) < 16:
                    continue
                
                def clean_value(v):
                    if not v:
                        return ''
                    return v.strip().strip('"\'')
                
                name = clean_value(values[1])
                pricelevel = clean_value(values[12])
                
                if pricelevel and pricelevel.lower() == 'corp':
                    if name and name.lower() != 'error':
                        companies.append({'name': name})
            except:
                continue
        
        return companies
    
    def parse_sql_values(self, values_string):
        """Parse SQL VALUES string"""
        values = []
        current = ''
        in_quotes = False
        quote_char = None
        i = 0
        
        while i < len(values_string):
            char = values_string[i]
            if char in ['"', "'"] and (i == 0 or values_string[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current += char
            elif char == ',' and not in_quotes:
                values.append(current.strip())
                current = ''
            else:
                current += char
            i += 1
        
        if current.strip():
            values.append(current.strip())
        
        return values
    
    def normalize_name(self, name):
        """Normalize name for matching (remove common words, lowercase)"""
        if not name:
            return ''
        
        name_lower = name.lower()
        # Remove common words
        words_to_remove = ['ltd', 'limited', 'company', 'corp', 'corporate', 'inc', 'incorporated']
        words = name_lower.split()
        normalized = ' '.join([w for w in words if w not in words_to_remove])
        return normalized.strip()

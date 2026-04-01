"""
Django Management Command to Fix Corporate Accounts from db_3
Uses the source data (pricelevel='corp') to correctly identify and reclassify corporate accounts
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import re
import os
from hospital.models_insurance_companies import InsuranceCompany
from hospital.models import Payer
from hospital.models_enterprise_billing import CorporateAccount


class Command(BaseCommand):
    help = 'Fix corporate accounts using db_3 source data (pricelevel=corp)'
    
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
        self.stdout.write('FIXING CORPORATE ACCOUNTS FROM DB_3 SOURCE DATA')
        self.stdout.write('='*80)
        
        # Parse SQL file to get corporate companies
        corporate_companies_data = self.parse_corporate_companies(sql_file)
        
        self.stdout.write(f'\nFound {len(corporate_companies_data)} corporate companies in source data')
        
        fixed_payers = 0
        fixed_companies = 0
        created_corporate_accounts = 0
        
        with transaction.atomic():
            for company_data in corporate_companies_data:
                company_name = company_data['name']
                company_code = company_data.get('code', '')
                
                # Skip invalid entries
                if not company_name or company_name.lower() == 'error':
                    continue
                
                # Step 1: Fix Payer records (exact match and partial match)
                # Try exact match first
                payers = Payer.objects.filter(
                    name__iexact=company_name,
                    payer_type__in=['insurance', 'private'],
                    is_deleted=False
                )
                
                # If no exact match, try partial match
                if not payers.exists():
                    payers = Payer.objects.filter(
                        name__icontains=company_name[:20],  # First 20 chars
                        payer_type__in=['insurance', 'private'],
                        is_deleted=False
                    )
                
                for payer in payers:
                    if dry_run:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Would fix Payer: {payer.name} ({payer.payer_type}) → corporate'
                            )
                        )
                    else:
                        payer.payer_type = 'corporate'
                        payer.save(update_fields=['payer_type'])
                        fixed_payers += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Fixed Payer: {payer.name} → corporate')
                        )
                
                # Step 2: Fix InsuranceCompany records
                companies = InsuranceCompany.objects.filter(
                    name__iexact=company_name,
                    is_active=True,
                    is_deleted=False
                )
                
                for company in companies:
                    if dry_run:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Would mark inactive: {company.name} (code: {company.code}) - Corporate account'
                            )
                        )
                    else:
                        # Mark as inactive
                        company.is_active = False
                        company.status = 'inactive'
                        company.notes = (company.notes or '') + f'\n[Auto-fixed {timezone.now().date()}] Reclassified as corporate account from db_3 source data (pricelevel=corp).'
                        company.save(update_fields=['is_active', 'status', 'notes'])
                        fixed_companies += 1
                        
                        # Create CorporateAccount (skip if required fields missing)
                        try:
                            # CorporateAccount requires: billing_contact_name, billing_email, billing_phone, billing_address, contract_start_date
                            # Skip creation if we don't have email (required field)
                            if not company.email:
                                self.stdout.write(
                                    self.style.WARNING(f'  ⚠ Skipped CorporateAccount for {company_name} - missing required email')
                                )
                            else:
                                corporate_account, created = CorporateAccount.objects.get_or_create(
                                    company_name=company_name,
                                    defaults={
                                        'company_code': company_code or company.code or f'CORP-{company.id}',
                                        'billing_contact_name': 'To be updated',
                                        'billing_email': company.email or f'contact@{company_name.lower().replace(" ", "")}.com',
                                        'billing_phone': company.phone_number or '0000000000',
                                        'billing_address': company.address or 'Address to be updated',
                                        'contract_start_date': timezone.now().date(),
                                        'is_active': True,
                                        'next_billing_date': timezone.now().date().replace(day=1),
                                        'payment_terms_days': 30,
                                    }
                                )
                            
                            if created:
                                created_corporate_accounts += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f'  ✓ Created CorporateAccount: {company_name}')
                                )
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f'  ✗ Error creating CorporateAccount for {company_name}: {str(e)}')
                            )
                        
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Marked inactive: {company.name} (corporate)')
                        )
        
        # Summary
        self.stdout.write('\n' + '='*80)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ CORPORATE ACCOUNTS FIXED'))
        
        self.stdout.write(f'  Payers fixed: {fixed_payers}')
        self.stdout.write(f'  Insurance companies marked inactive: {fixed_companies}')
        self.stdout.write(f'  Corporate accounts created: {created_corporate_accounts}')
        self.stdout.write('='*80)
        
        # Final verification
        if not dry_run:
            self.stdout.write('\nFinal Status:')
            corporate_payers = Payer.objects.filter(payer_type='corporate', is_deleted=False).count()
            insurance_payers = Payer.objects.filter(payer_type__in=['insurance', 'private'], is_deleted=False).count()
            active_insurance_companies = InsuranceCompany.objects.filter(is_active=True, is_deleted=False).count()
            corporate_accounts = CorporateAccount.objects.filter(is_active=True, is_deleted=False).count()
            
            self.stdout.write(f'  Corporate payers: {corporate_payers}')
            self.stdout.write(f'  Insurance payers: {insurance_payers}')
            self.stdout.write(f'  Active insurance companies: {active_insurance_companies}')
            self.stdout.write(f'  Corporate accounts: {corporate_accounts}')
    
    def parse_corporate_companies(self, file_path):
        """Parse insurance_companies.sql and extract companies with pricelevel='corp'"""
        companies = []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Extract INSERT statements
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
                
                company_id = clean_value(values[0])
                name = clean_value(values[1])
                cms_id = clean_value(values[3])
                pricelevel = clean_value(values[12])
                
                # Only include companies with pricelevel='corp'
                if pricelevel and pricelevel.lower() == 'corp':
                    if name and name.lower() != 'error':
                        companies.append({
                            'id': company_id,
                            'name': name,
                            'code': cms_id if cms_id else self.generate_code_from_name(name),
                        })
            except Exception as e:
                continue
        
        return companies
    
    def parse_sql_values(self, values_string):
        """Parse SQL VALUES string handling quotes and NULL"""
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
    
    def generate_code_from_name(self, name):
        """Generate a short code from company name"""
        words = name.upper().split()
        code = ''
        
        for word in words:
            if word not in ['LTD', 'LIMITED', 'COMPANY', 'CORP', 'CORPORATE']:
                if word:
                    code += word[0]
                if len(code) >= 4:
                    break
        
        if len(code) < 3:
            code = name[:4].upper().replace(' ', '')
        
        return code[:20]

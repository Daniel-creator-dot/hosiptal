"""
Django Management Command to Reclassify Corporate Accounts
Finds companies that are corporate but misclassified as insurance and fixes them
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from hospital.models_insurance_companies import InsuranceCompany
from hospital.models import Payer
from hospital.models_enterprise_billing import CorporateAccount


class Command(BaseCommand):
    help = 'Reclassify corporate accounts that were incorrectly added as insurance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually making changes'
        )
        parser.add_argument(
            '--fix-payers',
            action='store_true',
            default=True,
            help='Fix Payer records with wrong payer_type'
        )
        parser.add_argument(
            '--fix-insurance-companies',
            action='store_true',
            default=True,
            help='Mark InsuranceCompany records as inactive if they are corporate'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fix_payers = options['fix_payers']
        fix_insurance_companies = options['fix_insurance_companies']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write('='*80)
        self.stdout.write('RECLASSIFYING CORPORATE ACCOUNTS')
        self.stdout.write('='*80)
        
        # Corporate indicators
        corporate_keywords = [
            'bank', 'ltd', 'limited', 'company', 'corp', 'corporate',
            'university', 'college', 'church', 'fc', 'football club',
            'motors', 'electricals', 'systems', 'technologies', 'logistics',
            'investment', 'fund', 'incorporated', 'group', 'holdings'
        ]
        
        # Exclude insurance keywords
        insurance_keywords = [
            'insurance', 'health', 'mutual', 'care', 'nhis', 'medical insurance',
            'healthcare', 'health insurance', 'medical care'
        ]
        
        fixed_payers = 0
        fixed_companies = 0
        created_corporate_accounts = 0
        
        with transaction.atomic():
            # Step 1: Fix Payer records
            if fix_payers:
                self.stdout.write('\n[1/2] Checking Payer records...')
                payers = Payer.objects.filter(
                    payer_type__in=['insurance', 'private'],
                    is_deleted=False
                )
                
                for payer in payers:
                    name_lower = payer.name.lower()
                    
                    # Check if it's actually corporate
                    is_corporate = any(keyword in name_lower for keyword in corporate_keywords)
                    is_insurance = any(keyword in name_lower for keyword in insurance_keywords)
                    
                    # Corporate but not insurance
                    if is_corporate and not is_insurance:
                        if dry_run:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  Would fix: {payer.name} (currently: {payer.payer_type}) → corporate'
                                )
                            )
                        else:
                            payer.payer_type = 'corporate'
                            payer.save(update_fields=['payer_type'])
                            fixed_payers += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'  ✓ Fixed: {payer.name} → corporate')
                            )
            
            # Step 2: Fix InsuranceCompany records
            if fix_insurance_companies:
                self.stdout.write('\n[2/2] Checking InsuranceCompany records...')
                companies = InsuranceCompany.objects.filter(
                    is_active=True,
                    is_deleted=False
                )
                
                for company in companies:
                    name_lower = company.name.lower()
                    
                    # Check if it's actually corporate
                    is_corporate = any(keyword in name_lower for keyword in corporate_keywords)
                    is_insurance = any(keyword in name_lower for keyword in insurance_keywords)
                    
                    # Corporate but not insurance
                    if is_corporate and not is_insurance:
                        if dry_run:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  Would mark inactive: {company.name} (code: {company.code}) - This is corporate, not insurance'
                                )
                            )
                        else:
                            # Mark as inactive (don't delete - preserve data)
                            company.is_active = False
                            company.status = 'inactive'
                            company.notes = (company.notes or '') + f'\n[Auto-fixed] Reclassified as corporate account, not insurance company.'
                            company.save(update_fields=['is_active', 'status', 'notes'])
                            fixed_companies += 1
                            
                            # Create or get CorporateAccount
                            corporate_account, created = CorporateAccount.objects.get_or_create(
                                company_name=company.name,
                                defaults={
                                    'company_code': company.code,
                                    'contact_person': '',
                                    'phone_number': company.phone_number or '',
                                    'email': company.email or '',
                                    'address': company.address or '',
                                    'is_active': True,
                                    'billing_frequency': 'monthly',
                                    'next_billing_date': timezone.now().date().replace(day=1),
                                }
                            )
                            
                            if created:
                                created_corporate_accounts += 1
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f'  ✓ Created CorporateAccount: {company.name}'
                                    )
                                )
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  ✓ Marked inactive: {company.name} (was insurance, now corporate)'
                                )
                            )
        
        # Summary
        self.stdout.write('\n' + '='*80)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ RECLASSIFICATION COMPLETE'))
        
        self.stdout.write(f'  Payers fixed: {fixed_payers}')
        self.stdout.write(f'  Insurance companies marked inactive: {fixed_companies}')
        self.stdout.write(f'  Corporate accounts created: {created_corporate_accounts}')
        self.stdout.write('='*80)
        
        # Verify
        if not dry_run:
            self.stdout.write('\nVerification:')
            corporate_payers = Payer.objects.filter(payer_type='corporate', is_deleted=False).count()
            insurance_payers = Payer.objects.filter(payer_type__in=['insurance', 'private'], is_deleted=False).count()
            self.stdout.write(f'  Corporate payers: {corporate_payers}')
            self.stdout.write(f'  Insurance payers: {insurance_payers}')

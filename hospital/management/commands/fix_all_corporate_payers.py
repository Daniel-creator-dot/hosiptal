"""
Django Management Command to Fix All Corporate Payers
Updates Payer records that should be corporate based on name patterns
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from hospital.models import Payer


class Command(BaseCommand):
    help = 'Fix all Payer records that should be corporate based on name patterns'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually making changes'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write('='*80)
        self.stdout.write('FIXING ALL CORPORATE PAYERS')
        self.stdout.write('='*80)
        
        # Corporate indicators
        corporate_keywords = [
            'bank', 'ltd', 'limited', 'company', 'corp', 'corporate',
            'university', 'college', 'church', 'fc', 'football club',
            'motors', 'electricals', 'systems', 'technologies', 'logistics',
            'investment', 'fund', 'incorporated', 'group', 'holdings',
            'pensioneers', 'electricity', 'distribution', 'sewerage',
            'confectionery', 'family pack', 'family account'
        ]
        
        # Exclude insurance keywords
        insurance_keywords = [
            'insurance', 'health', 'mutual', 'care', 'nhis', 'medical insurance',
            'healthcare', 'health insurance', 'medical care', 'gab', 'nmh'
        ]
        
        fixed_count = 0
        
        with transaction.atomic():
            # Get all payers that might be corporate
            payers = Payer.objects.filter(
                payer_type__in=['insurance', 'private'],
                is_deleted=False
            )
            
            self.stdout.write(f'\nChecking {payers.count()} payers...\n')
            
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
                                f'  Would fix: {payer.name} ({payer.payer_type}) → corporate'
                            )
                        )
                    else:
                        payer.payer_type = 'corporate'
                        payer.save(update_fields=['payer_type'])
                        fixed_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Fixed: {payer.name} → corporate')
                        )
        
        # Summary
        self.stdout.write('\n' + '='*80)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ CORPORATE PAYERS FIXED'))
        
        self.stdout.write(f'  Payers fixed: {fixed_count}')
        self.stdout.write('='*80)
        
        # Final verification
        if not dry_run:
            corporate_payers = Payer.objects.filter(payer_type='corporate', is_deleted=False).count()
            insurance_payers = Payer.objects.filter(payer_type__in=['insurance', 'private'], is_deleted=False).count()
            
            self.stdout.write(f'\nFinal Status:')
            self.stdout.write(f'  Corporate payers: {corporate_payers}')
            self.stdout.write(f'  Insurance payers: {insurance_payers}')

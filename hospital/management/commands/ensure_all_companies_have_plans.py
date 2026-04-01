"""
Django Management Command to Ensure All Insurance Companies Have Plans
Creates default plans for any companies that don't have any plans
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from datetime import date
from hospital.models_insurance_companies import InsuranceCompany, InsurancePlan


class Command(BaseCommand):
    help = 'Ensure all active insurance companies have at least one plan'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually creating plans'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No plans will be created'))
        
        # Get all active companies
        companies = InsuranceCompany.objects.filter(
            is_active=True,
            is_deleted=False
        )
        
        self.stdout.write(f'Checking {companies.count()} active insurance companies...')
        
        created_count = 0
        skipped_count = 0
        
        with transaction.atomic():
            for company in companies:
                # Check if company has any active plans
                existing_plans = company.plans.filter(is_deleted=False).count()
                
                if existing_plans > 0:
                    skipped_count += 1
                    continue
                
                # Determine plan type based on company name/code
                plan_type, plan_name = self.determine_plan_type(company)
                
                # Generate plan code
                plan_code = f"{company.code}-PLAN-001"
                
                if dry_run:
                    self.stdout.write(
                        f'  Would create plan for: {company.name} ({plan_name})'
                    )
                else:
                    try:
                        plan = InsurancePlan.objects.create(
                            insurance_company=company,
                            plan_code=plan_code,
                            plan_name=plan_name,
                            plan_type=plan_type,
                            description=f"Default plan for {company.name}",
                            consultation_coverage=Decimal('100.00'),
                            lab_coverage=Decimal('100.00'),
                            imaging_coverage=Decimal('100.00'),
                            pharmacy_coverage=Decimal('100.00'),
                            surgery_coverage=Decimal('100.00'),
                            admission_coverage=Decimal('100.00'),
                            is_active=company.is_active,
                            effective_date=date.today(),
                        )
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Created plan for: {company.name}')
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'  ✗ Error creating plan for {company.name}: {str(e)}')
                        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDRY RUN: Would create {companies.count() - skipped_count} plans'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Complete!'
                    f'\n   Plans created: {created_count}'
                    f'\n   Companies already had plans: {skipped_count}'
                )
            )
    
    def determine_plan_type(self, company):
        """Determine plan type and name based on company"""
        name_lower = company.name.lower()
        code_lower = company.code.lower()
        
        # Check for corporate indicators
        if any(word in name_lower for word in ['corp', 'corporate', 'ltd', 'limited', 'bank', 'company']):
            # But exclude insurance companies
            if not any(word in name_lower for word in ['insurance', 'health', 'mutual', 'care']):
                return 'corporate', f"{company.name} Corporate Plan"
        
        # Check for NHIS
        if 'nhis' in name_lower or 'nhis' in code_lower:
            return 'basic', f"{company.name} NHIS Plan"
        
        # Check for family plans
        if 'family' in name_lower:
            return 'family', f"{company.name} Family Plan"
        
        # Default to standard insurance plan
        return 'standard', f"{company.name} Standard Plan"

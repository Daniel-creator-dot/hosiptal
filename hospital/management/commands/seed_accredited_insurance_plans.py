"""
Django Management Command to Seed Accredited Insurance Plans
Adds the official accredited plans for each insurance company per hospital accreditation.
Insurance companies must already exist in the system.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
from datetime import date
from hospital.models_insurance_companies import InsuranceCompany, InsurancePlan


# Accredited plans per insurance company (company name patterns -> list of plan names)
# Cosmo Essential (Ivory) is NOT ACCEPTABLE - excluded
ACCREDITED_PLANS = {
    'Premier Health Insurance': ['Platinum Plus'],
    'Apex Health Insurance': ['Platinum', 'Gold', 'TPA'],
    'GLICO': ['Enhanced Plus', 'Ultimate', 'Platinum Plus', 'Platinum', 'TPA'],
    'Glico Health': ['Enhanced Plus', 'Ultimate', 'Platinum Plus', 'Platinum', 'TPA'],
    'Cosmopolitan Health Insurance': [
        'Cosmo Classic (Sapphire)',
        'Cosmo Premium',
        'Cosmo Premium Plus',
    ],
    'GAB Health Insurance': ['All Plans'],
    'GAB Health Insurance Company Ltd': ['All Plans'],
    'ACE Medical Insurance': ['Maxcare', 'Maxcare Plus', 'Enhanced Royal Care', 'Royal Care'],
    'Equity Health Insurance': ['All Plans'],
    'Acacia Health Insurance': ['Super Care Plus', 'Super Care', 'TPA'],
    'Phoenix Health Insurance': ['Platinum Health', 'Comprehensive Health'],
    'Metropolitan Health Insurance': [
        'Champagne',
        'Burgundy',
        'Red Light',
        'Turquoise',
        'Red Classic',
    ],
    'Nationwide Medical Insurance': [
        'Premier Plus',
        'Premier Care',
        'Privilege',
        'Executive',
    ],
    'Medfocus': ['TPA'],
    'CAL BANK LTD - MEDFOCUS': ['TPA'],
}


def find_insurance_company(name_pattern):
    """Find insurance company by name (case-insensitive partial match)."""
    # Try exact match first
    company = InsuranceCompany.objects.filter(
        is_deleted=False,
        name__iexact=name_pattern
    ).first()
    if company:
        return company
    # Try contains (pattern in company name)
    company = InsuranceCompany.objects.filter(
        is_deleted=False,
        name__icontains=name_pattern
    ).first()
    if company:
        return company
    # Try company name contained in pattern (e.g. "GLICO" matches "Glico Health")
    first_word = name_pattern.split()[0] if name_pattern else ''
    if first_word:
        company = InsuranceCompany.objects.filter(
            is_deleted=False,
            name__icontains=first_word
        ).first()
    return company


def make_plan_code(company_code, plan_name):
    """Generate unique plan code from company code and plan name."""
    safe = ''.join(c if c.isalnum() else '-' for c in plan_name)
    safe = safe.replace('--', '-').strip('-').upper()[:40]
    prefix = (company_code or 'PLAN').upper().replace(' ', '-')
    return f"{prefix}-{safe}" if safe else f"{prefix}-001"


class Command(BaseCommand):
    help = 'Seed accredited insurance plans for each insurance company (plans from accreditation list)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes',
        )
        parser.add_argument(
            '--company',
            type=str,
            help='Limit to a specific company name (partial match)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        company_filter = options.get('company')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No plans will be created'))

        # Build company -> plans mapping, resolving company names
        resolved = {}
        for name_pattern, plans in ACCREDITED_PLANS.items():
            company = find_insurance_company(name_pattern)
            if not company:
                self.stdout.write(
                    self.style.WARNING(f'  Company not found: {name_pattern}')
                )
                continue
            key = (company.id, company.name)
            if key not in resolved:
                resolved[key] = {'company': company, 'plans': set()}
            resolved[key]['plans'].update(plans)

        # Deduplicate: merge GLICO/Glico etc into one company
        merged = {}
        for (_, name), data in resolved.items():
            company = data['company']
            cid = company.id
            if cid not in merged:
                merged[cid] = data
            else:
                merged[cid]['plans'].update(data['plans'])

        if company_filter:
            merged = {
                k: v for k, v in merged.items()
                if company_filter.lower() in v['company'].name.lower()
            }
            if not merged:
                self.stdout.write(
                    self.style.ERROR(f'No companies match filter: {company_filter}')
                )
                return

        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for cid, data in merged.items():
                company = data['company']
                plans = sorted(data['plans'])
                self.stdout.write(f'\n{company.name} ({company.code}):')

                for plan_name in plans:
                    plan_code = make_plan_code(company.code, plan_name)
                    exists = InsurancePlan.objects.filter(
                        Q(plan_code=plan_code) |
                        Q(insurance_company=company, plan_name__iexact=plan_name)
                    ).exists()

                    if exists:
                        self.stdout.write(f'  - Skip (exists): {plan_name}')
                        skipped_count += 1
                        continue

                    if dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(f'  + Would create: {plan_name} [{plan_code}]')
                        )
                        created_count += 1
                        continue

                    try:
                        InsurancePlan.objects.create(
                            insurance_company=company,
                            plan_code=plan_code,
                            plan_name=plan_name,
                            plan_type='standard',
                            description=f'Accredited plan: {plan_name}',
                            consultation_coverage=Decimal('100.00'),
                            lab_coverage=Decimal('100.00'),
                            imaging_coverage=Decimal('100.00'),
                            pharmacy_coverage=Decimal('80.00'),
                            surgery_coverage=Decimal('90.00'),
                            admission_coverage=Decimal('100.00'),
                            is_active=True,
                            effective_date=date.today(),
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f'  + Created: {plan_name}')
                        )
                        created_count += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'  x Error creating {plan_name}: {e}')
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDone. Plans created: {created_count}, skipped (existing): {skipped_count}'
            )
        )

"""
Import prices from db_3.zip SQL dump
Populates cash, insurance, and corporate prices for all services
"""
import os
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models_insurance_companies import InsuranceCompany


class Command(BaseCommand):
    help = 'Import prices from db_3.zip SQL dump (prices.sql)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='import/db_3_extracted/prices.sql',
            help='Path to prices.sql file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        dry_run = options['dry_run']
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Reading prices from: {file_path}'))
        
        # Ensure pricing categories exist
        self.setup_pricing_categories()
        
        # Map insurance company codes from prices to InsuranceCompany
        self.setup_insurance_company_mapping()
        
        # Parse and import prices
        stats = {
            'total_lines': 0,
            'processed': 0,
            'services_created': 0,
            'prices_created': 0,
            'prices_updated': 0,
            'errors': 0
        }
        
        # Group prices by service to process more efficiently
        price_data = {}
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                stats['total_lines'] += 1
                
                if line_num % 5000 == 0:
                    self.stdout.write(f'Reading line {line_num}...')
                
                # Parse INSERT statement
                match = re.match(r'INSERT INTO prices VALUES\("([^"]+)","([^"]+)","([^"]+)","([^"]+)",', line)
                if not match:
                    continue
                
                pr_id = match.group(1)
                pr_selector = match.group(2)  # Service name/description
                pr_level = match.group(3)  # Price level: cash, corp, ins, or insurance company code
                pr_price = match.group(4)
                
                try:
                    price = Decimal(pr_price)
                    if price < 0:
                        continue
                except (ValueError, TypeError):
                    stats['errors'] += 1
                    continue
                
                # Store price data
                key = (pr_id, pr_selector)
                if key not in price_data:
                    price_data[key] = []
                price_data[key].append((pr_level, price))
        
        self.stdout.write(f'\nFound {len(price_data)} unique services')
        self.stdout.write('Processing prices...\n')
        
        # Process each service
        processed_services = 0
        for (pr_id, pr_selector), prices in price_data.items():
            processed_services += 1
            
            if processed_services % 100 == 0:
                self.stdout.write(f'Processing service {processed_services}/{len(price_data)}...')
            
            # Get or create service code
            service_code = self.get_or_create_service_code(pr_id, pr_selector, stats)
            
            if not service_code:
                stats['errors'] += 1
                continue
            
            # Process all prices for this service
            if not dry_run:
                with transaction.atomic():
                    for pr_level, price in prices:
                        # Map price level to pricing category
                        pricing_category = self.get_pricing_category(pr_level)
                        
                        if not pricing_category:
                            # Skip unknown price levels
                            continue
                        
                        service_price, created = ServicePrice.objects.update_or_create(
                            service_code=service_code,
                            pricing_category=pricing_category,
                            effective_from=timezone.now().date(),
                            defaults={
                                'price': price,
                                'is_active': True,
                                'effective_to': None,
                            }
                        )
                        
                        if created:
                            stats['prices_created'] += 1
                        else:
                            stats['prices_updated'] += 1
                        
                        stats['processed'] += 1
            else:
                # Dry run - just count
                for pr_level, price in prices:
                    pricing_category = self.get_pricing_category(pr_level)
                    if pricing_category:
                        stats['processed'] += 1
        
        # Print summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f"Total lines processed: {stats['total_lines']}")
        self.stdout.write(f"Valid price entries: {stats['processed']}")
        self.stdout.write(f"Services created: {stats['services_created']}")
        if not dry_run:
            self.stdout.write(f"Prices created: {stats['prices_created']}")
            self.stdout.write(f"Prices updated: {stats['prices_updated']}")
        self.stdout.write(f"Errors: {stats['errors']}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('\nImport completed successfully!'))

    def setup_pricing_categories(self):
        """Ensure required pricing categories exist"""
        categories = [
            {
                'name': 'Cash Patients',
                'code': 'CASH',
                'category_type': 'cash',
                'description': 'Walk-in cash paying patients',
                'priority': 100
            },
            {
                'name': 'Corporate',
                'code': 'CORP',
                'category_type': 'corporate',
                'description': 'Corporate/company accounts',
                'priority': 90
            },
            {
                'name': 'General Insurance',
                'code': 'INS',
                'category_type': 'insurance',
                'description': 'General insurance pricing',
                'priority': 80
            },
        ]
        
        for cat_data in categories:
            PricingCategory.objects.get_or_create(
                code=cat_data['code'],
                defaults={
                    'name': cat_data['name'],
                    'category_type': cat_data['category_type'],
                    'description': cat_data['description'],
                    'priority': cat_data['priority'],
                    'is_active': True,
                }
            )
        
        self.stdout.write('Pricing categories ready')

    def setup_insurance_company_mapping(self):
        """Map insurance company codes from prices to InsuranceCompany"""
        # Map price level codes to insurance company names/codes
        self.insurance_mapping = {
            'Cosmo': 'COSMO',
            'cosmo': 'COSMO',
            'Glico': 'GLI',
            'glico': 'GLI',
            'GLICO': 'GLI',
            'gab': 'GAB',  # May need to check actual company
            'GAB': 'GAB',
            'nmh': 'NMH',
            'NMH': 'NMH',
            'nongh': 'NONGH',  # May need to check actual company
            'NONGH': 'NONGH',
            'nhis': 'NHIS',
            'NHIS': 'NHIS',
        }
        
        # Create NHIS pricing category (special case)
        PricingCategory.objects.get_or_create(
            code='NHIS',
            defaults={
                'name': 'NHIS Pricing',
                'category_type': 'insurance',
                'description': 'National Health Insurance Scheme pricing',
                'priority': 75,
                'is_active': True,
            }
        )
        
        # Create pricing categories for each insurance company
        for price_level, company_code in self.insurance_mapping.items():
            if company_code == 'NHIS':
                continue  # Already handled above
            
            try:
                insurance_company = InsuranceCompany.objects.filter(
                    code__iexact=company_code
                ).first()
                
                if insurance_company:
                    PricingCategory.objects.get_or_create(
                        code=f'INS-{company_code}',
                        defaults={
                            'name': f'{insurance_company.name} Pricing',
                            'category_type': 'insurance',
                            'insurance_company': insurance_company,
                            'description': f'Pricing for {insurance_company.name}',
                            'priority': 70,
                            'is_active': True,
                        }
                    )
                else:
                    # Create category even if insurance company doesn't exist
                    PricingCategory.objects.get_or_create(
                        code=f'INS-{company_code}',
                        defaults={
                            'name': f'{company_code} Insurance Pricing',
                            'category_type': 'insurance',
                            'description': f'Pricing for {company_code} insurance',
                            'priority': 70,
                            'is_active': True,
                        }
                    )
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Could not map {price_level}: {e}'))
        
        self.stdout.write('Insurance company mapping ready')

    def get_pricing_category(self, pr_level):
        """Get pricing category for a price level"""
        pr_level = pr_level.strip()
        pr_level_lower = pr_level.lower()
        
        # Direct mappings
        if pr_level_lower == 'cash':
            return PricingCategory.objects.filter(code='CASH', is_active=True).first()
        
        if pr_level_lower == 'corp':
            return PricingCategory.objects.filter(code='CORP', is_active=True).first()
        
        if pr_level_lower == 'ins':
            return PricingCategory.objects.filter(code='INS', is_active=True).first()
        
        if pr_level_lower == 'nhis':
            return PricingCategory.objects.filter(code='NHIS', is_active=True).first()
        
        # Insurance company specific
        if pr_level in self.insurance_mapping:
            company_code = self.insurance_mapping[pr_level]
            if company_code == 'NHIS':
                return PricingCategory.objects.filter(code='NHIS', is_active=True).first()
            return PricingCategory.objects.filter(
                code=f'INS-{company_code}',
                is_active=True
            ).first()
        
        # Try case-insensitive match
        for key, company_code in self.insurance_mapping.items():
            if pr_level_lower == key.lower():
                if company_code == 'NHIS':
                    return PricingCategory.objects.filter(code='NHIS', is_active=True).first()
                return PricingCategory.objects.filter(
                    code=f'INS-{company_code}',
                    is_active=True
                ).first()
        
        return None

    def get_or_create_service_code(self, pr_id, pr_selector, stats):
        """Get or create ServiceCode from pr_id and pr_selector"""
        # Try to find by code first (using pr_id)
        service_code = ServiceCode.objects.filter(code=pr_id, is_deleted=False).first()
        
        if service_code:
            return service_code
        
        # Try to find by description
        service_code = ServiceCode.objects.filter(
            description__iexact=pr_selector,
            is_deleted=False
        ).first()
        
        if service_code:
            return service_code
        
        # Determine category based on service name
        category = self.determine_category(pr_selector)
        
        # Create new service code
        # Use pr_id as code, but ensure it's unique
        code = pr_id
        counter = 1
        while ServiceCode.objects.filter(code=code, is_deleted=False).exists():
            code = f"{pr_id}_{counter}"
            counter += 1
        
        service_code = ServiceCode.objects.create(
            code=code,
            description=pr_selector[:200],  # Truncate if too long
            category=category,
            is_active=True
        )
        
        stats['services_created'] += 1
        return service_code

    def determine_category(self, service_name):
        """Determine service category from name"""
        name_lower = service_name.lower()
        
        # Lab tests
        if any(keyword in name_lower for keyword in ['test', 'lab', 'cbc', 'fbc', 'urine', 'stool', 'blood', 'culture']):
            return 'Laboratory'
        
        # Imaging
        if any(keyword in name_lower for keyword in ['x-ray', 'xray', 'ultrasound', 'scan', 'ct', 'mri', 'imaging']):
            return 'Imaging'
        
        # Pharmacy/Drugs
        if any(keyword in name_lower for keyword in ['tablet', 'capsule', 'injection', 'syrup', 'ointment', 'cream', 'gel', 'drops']):
            return 'Pharmacy'
        
        # Consultations
        if any(keyword in name_lower for keyword in ['consultation', 'consult', 'visit', 'review']):
            return 'Consultation'
        
        # Procedures
        if any(keyword in name_lower for keyword in ['procedure', 'surgery', 'operation', 'dressing', 'injection']):
            return 'Procedure'
        
        # Bed/Admission
        if any(keyword in name_lower for keyword in ['bed', 'ward', 'admission', 'room']):
            return 'Admission'
        
        # Default
        return 'Services'

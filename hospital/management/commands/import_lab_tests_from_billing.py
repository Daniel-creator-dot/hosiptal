"""
Import lab tests from billing.sql where code starts with SL or numeric codes
Updates existing lab tests with proper names and prices
"""
import os
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from hospital.models import LabTest, ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice


class Command(BaseCommand):
    help = 'Import lab tests from billing.sql file (codes starting with SL or numeric lab codes)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='import/billing.sql',
            help='Path to billing.sql file'
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
        
        self.stdout.write(self.style.SUCCESS(f'Reading lab tests from: {file_path}'))
        
        # Ensure pricing categories exist
        cash_category, _ = PricingCategory.objects.get_or_create(
            code='CASH',
            defaults={
                'name': 'Cash',
                'category_type': 'cash',
                'is_active': True,
                'priority': 1
            }
        )
        corp_category, _ = PricingCategory.objects.get_or_create(
            code='CORP',
            defaults={
                'name': 'Corporate',
                'category_type': 'corporate',
                'is_active': True,
                'priority': 2
            }
        )
        ins_category, _ = PricingCategory.objects.get_or_create(
            code='INS',
            defaults={
                'name': 'Insurance',
                'category_type': 'insurance',
                'is_active': True,
                'priority': 3
            }
        )
        
        # Parse billing.sql to extract lab test codes (SL codes or numeric codes)
        lab_tests = {}  # {code: {'name': name, 'prices': {pricelevel: [prices]}}}
        stats = {
            'total_lines': 0,
            'lab_lines': 0,
            'unique_codes': 0,
            'errors': 0
        }
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                stats['total_lines'] += 1
                
                if line_num % 50000 == 0:
                    self.stdout.write(f'Reading line {line_num}...')
                
                # Only look for lab test codes (SL codes or numeric codes starting with 0-9)
                if 'INSERT INTO billing VALUES' not in line:
                    continue
                
                # Check if this might be a lab test (contains SL or starts with number in code field)
                if 'SL' not in line and not re.search(r'"\d{5,}"', line):
                    continue
                
                # Parse INSERT INTO billing VALUES line
                values_start = line.find('VALUES(')
                if values_start == -1:
                    continue
                
                values_end = line.rfind(');')
                if values_end == -1:
                    continue
                
                values_str = line[values_start + 6:values_end].strip()
                
                # Parse quoted values
                parts = []
                current = ''
                in_quotes = False
                i = 0
                while i < len(values_str):
                    char = values_str[i]
                    if char == '"':
                        if i > 0 and values_str[i-1] == '\\':
                            current += char
                        else:
                            in_quotes = not in_quotes
                            current += char
                    elif char == ',' and not in_quotes:
                        parts.append(current.strip().strip('"'))
                        current = ''
                    else:
                        current += char
                    i += 1
                if current:
                    parts.append(current.strip().strip('"'))
                
                if len(parts) < 21:
                    continue
                
                code_type = parts[2] if len(parts) > 2 else ''  # Should be "Service"
                code = parts[3] if len(parts) > 3 else ''  # Service code
                code_text = parts[10] if len(parts) > 10 else ''  # Description
                fee_str = parts[20] if len(parts) > 20 else ''  # Price
                pricelevel = parts[27] if len(parts) > 27 else ''  # Payer type
                
                # Only process lab test codes (SL codes or numeric codes)
                if not code or not code_text:
                    continue
                
                # Check if it's a lab test code
                is_lab_code = False
                if code.startswith('SL'):
                    is_lab_code = True
                elif code.isdigit() and len(code) >= 5:  # Numeric codes (000180, 000222, etc.)
                    # Check if description suggests lab test
                    if any(keyword in code_text.upper() for keyword in ['BLOOD', 'TEST', 'LAB', 'URINE', 'CS', 'CULTURE', 'RBS', 'FBC', 'CBC', 'HB', 'HBSAG']):
                        is_lab_code = True
                
                if not is_lab_code:
                    continue
                
                try:
                    fee = Decimal(fee_str) if fee_str and fee_str.strip() else Decimal('0')
                    if fee <= 0:
                        continue
                    
                    stats['lab_lines'] += 1
                    
                    # Initialize code entry if not exists
                    if code not in lab_tests:
                        lab_tests[code] = {
                            'name': code_text or code,
                            'prices': {}
                        }
                        stats['unique_codes'] += 1
                    
                    # Store price by price level
                    pricelevel_key = pricelevel.lower() if pricelevel else 'cash'
                    if pricelevel_key not in lab_tests[code]['prices']:
                        lab_tests[code]['prices'][pricelevel_key] = []
                    lab_tests[code]['prices'][pricelevel_key].append(fee)
                    
                except (ValueError, TypeError) as e:
                    stats['errors'] += 1
                    if stats['errors'] <= 10:
                        self.stdout.write(self.style.WARNING(f'Error parsing line {line_num}: {e}'))
                    continue
        
        self.stdout.write(self.style.SUCCESS(f'\nFound {stats["unique_codes"]} unique lab test codes from {stats["lab_lines"]} billing entries'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN - No changes will be made ===\n'))
            for code, data in sorted(lab_tests.items())[:20]:
                prices_str = ', '.join([f'{k}: {max(v):.2f}' for k, v in data['prices'].items()])
                self.stdout.write(f'  {code}: {data["name"]} - {prices_str}')
            if len(lab_tests) > 20:
                self.stdout.write(f'  ... and {len(lab_tests) - 20} more')
            return
        
        # Import lab tests
        created_count = 0
        updated_count = 0
        price_count = 0
        
        with transaction.atomic():
            for code, data in lab_tests.items():
                # Get max price from all price levels (use cash as default)
                max_cash_price = max(data['prices'].get('cash', data['prices'].get('', [Decimal('0')])), default=Decimal('0'))
                if not max_cash_price:
                    max_cash_price = max([max(v) for v in data['prices'].values()], default=Decimal('0'))
                
                # Determine specimen type from name or code
                specimen_type = 'Blood'  # Default
                name_lower = data['name'].lower() if data['name'] else ''
                if 'urine' in name_lower or 'UA' in name_lower:
                    specimen_type = 'Urine'
                elif 'stool' in name_lower or 'fecal' in name_lower:
                    specimen_type = 'Stool'
                elif 'sputum' in name_lower:
                    specimen_type = 'Sputum'
                elif 'swab' in name_lower:
                    specimen_type = 'Swab'
                elif 'serum' in name_lower:
                    specimen_type = 'Serum'
                elif 'plasma' in name_lower:
                    specimen_type = 'Plasma'
                elif 'csf' in name_lower or 'cerebrospinal' in name_lower:
                    specimen_type = 'CSF'
                
                # Create or update LabTest
                lab_test, created = LabTest.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': data['name'] if data['name'] and data['name'].strip() else f'Lab Test {code}',
                        'specimen_type': specimen_type,
                        'price': max_cash_price,
                        'is_active': True,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Update name and price if changed (always update name if better name available)
                    updated = False
                    if data['name'] and data['name'].strip() and (not lab_test.name or lab_test.name == 'Blood' or len(data['name']) > len(lab_test.name)):
                        lab_test.name = data['name']
                        updated = True
                    if lab_test.specimen_type == 'Blood' and specimen_type != 'Blood':
                        lab_test.specimen_type = specimen_type
                        updated = True
                    if lab_test.price != max_cash_price and max_cash_price > 0:
                        lab_test.price = max_cash_price
                        updated = True
                    if updated:
                        lab_test.save()
                        updated_count += 1
                
                # Create or update ServiceCode for billing
                service_code, _ = ServiceCode.objects.get_or_create(
                    code=f'LAB-{code}',
                    defaults={
                        'description': data['name'],
                        'category': 'Laboratory Services',
                        'is_active': True,
                    }
                )
                
                # Import prices for each level
                for pricelevel_key, prices in data['prices'].items():
                    if not prices:
                        continue
                    
                    max_price = max(prices)
                    
                    # Determine pricing category
                    if pricelevel_key in ['cash', '']:
                        category = cash_category
                    elif pricelevel_key in ['corp', 'corporate']:
                        category = corp_category
                    elif pricelevel_key in ['ins', 'insurance', 'nhis']:
                        category = ins_category
                    else:
                        category = cash_category  # Default
                    
                    service_price, _ = ServicePrice.objects.update_or_create(
                        service_code=service_code,
                        pricing_category=category,
                        defaults={
                            'price': max_price,
                            'is_active': True,
                            'effective_from': timezone.now().date(),
                        }
                    )
                    price_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Import Summary:'))
        self.stdout.write(f'  - Created: {created_count} lab tests')
        self.stdout.write(f'  - Updated: {updated_count} lab tests')
        self.stdout.write(f'  - Prices imported: {price_count} price entries')
        self.stdout.write(self.style.SUCCESS(f'\n✅ Import completed successfully!'))

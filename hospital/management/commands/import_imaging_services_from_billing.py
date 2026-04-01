"""
Import imaging services from billing.sql where category is diag_imaging or description suggests imaging
Updates existing imaging services with proper names and prices
"""
import os
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from hospital.models_advanced import ImagingCatalog
from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice


class Command(BaseCommand):
    help = 'Import imaging services from billing.sql file (category=diag_imaging or description suggests imaging)'

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
        
        self.stdout.write(self.style.SUCCESS(f'Reading imaging services from: {file_path}'))
        
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
        
        # Parse billing.sql to extract imaging services
        imaging_services = {}  # {code: {'name': name, 'prices': {pricelevel: [prices]}}}
        stats = {
            'total_lines': 0,
            'imaging_lines': 0,
            'unique_codes': 0,
            'errors': 0
        }
        
        # Keywords that suggest imaging services
        imaging_keywords = [
            'x-ray', 'xray', 'x_ray', 'ecg', 'ekg', 'ultrasound', 'scan', 'ct', 'mri', 
            'radiography', 'radiology', 'mammography', 'angiography', 'fluoroscopy',
            'sonography', 'echocardiography', 'endoscopy', 'colonoscopy'
        ]
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                stats['total_lines'] += 1
                
                if line_num % 50000 == 0:
                    self.stdout.write(f'Reading line {line_num}...')
                
                # Only look for imaging services
                if 'INSERT INTO billing VALUES' not in line:
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
                category = parts[28] if len(parts) > 28 else ''  # Category (diag_imaging)
                
                # Only process imaging services
                # Check if category is diag_imaging or description contains imaging keywords
                is_imaging = False
                if category and 'imaging' in category.lower():
                    is_imaging = True
                elif code_text:
                    code_text_lower = code_text.lower()
                    if any(keyword in code_text_lower for keyword in imaging_keywords):
                        is_imaging = True
                
                # Also check if code starts with SD (imaging codes) or is in imaging code range
                if not is_imaging:
                    if code and (code.startswith('SD') or (code.isdigit() and len(code) >= 6 and code.startswith('000'))):
                        # Additional check: codes starting with 000 might be imaging
                        if code.isdigit() and code.startswith('000'):
                            # Check if description suggests imaging
                            if code_text and any(keyword in code_text.lower() for keyword in imaging_keywords):
                                is_imaging = True
                        elif code.startswith('SD'):
                            is_imaging = True
                
                if not is_imaging:
                    continue
                
                try:
                    fee = Decimal(fee_str) if fee_str and fee_str.strip() else Decimal('0')
                    if fee <= 0:
                        continue
                    
                    stats['imaging_lines'] += 1
                    
                    # Initialize code entry if not exists
                    if code not in imaging_services:
                        imaging_services[code] = {
                            'name': code_text or code,
                            'prices': {}
                        }
                        stats['unique_codes'] += 1
                    
                    # Store price by price level
                    pricelevel_key = pricelevel.lower() if pricelevel else 'cash'
                    if pricelevel_key not in imaging_services[code]['prices']:
                        imaging_services[code]['prices'][pricelevel_key] = []
                    imaging_services[code]['prices'][pricelevel_key].append(fee)
                    
                except (ValueError, TypeError) as e:
                    stats['errors'] += 1
                    if stats['errors'] <= 10:
                        self.stdout.write(self.style.WARNING(f'Error parsing line {line_num}: {e}'))
                    continue
        
        self.stdout.write(self.style.SUCCESS(f'\nFound {stats["unique_codes"]} unique imaging service codes from {stats["imaging_lines"]} billing entries'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN - No changes will be made ===\n'))
            for code, data in sorted(imaging_services.items())[:20]:
                prices_str = ', '.join([f'{k}: {max(v):.2f}' for k, v in data['prices'].items()])
                self.stdout.write(f'  {code}: {data["name"]} - {prices_str}')
            if len(imaging_services) > 20:
                self.stdout.write(f'  ... and {len(imaging_services) - 20} more')
            return
        
        # Import imaging services
        created_count = 0
        updated_count = 0
        price_count = 0
        
        with transaction.atomic():
            for code, data in imaging_services.items():
                # Get max price from all price levels (use cash as default)
                max_cash_price = max(data['prices'].get('cash', data['prices'].get('', [Decimal('0')])), default=Decimal('0'))
                if not max_cash_price:
                    max_cash_price = max([max(v) for v in data['prices'].values()], default=Decimal('0'))
                
                # Determine modality from name
                modality = 'xray'  # Default
                name_lower = data['name'].lower() if data['name'] else ''
                if 'ultrasound' in name_lower or 'scan' in name_lower:
                    modality = 'ultrasound'
                elif 'ecg' in name_lower or 'ekg' in name_lower:
                    modality = 'ecg'
                elif 'ct' in name_lower:
                    modality = 'ct'
                elif 'mri' in name_lower:
                    modality = 'mri'
                elif 'x-ray' in name_lower or 'xray' in name_lower or 'radiography' in name_lower:
                    modality = 'xray'
                elif 'mammography' in name_lower:
                    modality = 'mammography'
                elif 'endoscopy' in name_lower or 'colonoscopy' in name_lower:
                    modality = 'endoscopy'
                
                # Create or update ImagingCatalog
                imaging_catalog, created = ImagingCatalog.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': data['name'] if data['name'] and data['name'].strip() else f'Imaging Service {code}',
                        'modality': modality,
                        'price': max_cash_price,
                        'is_active': True,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Update name and price if changed (always update name if better name available)
                    updated = False
                    if data['name'] and data['name'].strip() and (not imaging_catalog.name or len(data['name']) > len(imaging_catalog.name)):
                        imaging_catalog.name = data['name']
                        updated = True
                    if imaging_catalog.modality == 'xray' and modality != 'xray':
                        imaging_catalog.modality = modality
                        updated = True
                    if imaging_catalog.price != max_cash_price and max_cash_price > 0:
                        imaging_catalog.price = max_cash_price
                        updated = True
                    if updated:
                        imaging_catalog.save()
                        updated_count += 1
                
                # Create or update ServiceCode for billing
                service_code, _ = ServiceCode.objects.get_or_create(
                    code=f'IMG-{code}',
                    defaults={
                        'description': data['name'],
                        'category': 'Imaging Services',
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
        self.stdout.write(f'  - Created: {created_count} imaging services')
        self.stdout.write(f'  - Updated: {updated_count} imaging services')
        self.stdout.write(f'  - Prices imported: {price_count} price entries')
        self.stdout.write(self.style.SUCCESS(f'\n✅ Import completed successfully!'))

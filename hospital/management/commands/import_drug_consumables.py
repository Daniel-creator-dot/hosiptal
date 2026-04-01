"""
Import consumables from drugs.sql where consumable=1
These are items marked as consumables in the drugs table
"""
import os
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from hospital.models import ServiceCode
from hospital.models_flexible_pricing import PricingCategory, ServicePrice


class Command(BaseCommand):
    help = 'Import consumables from drugs.sql file (where consumable=1)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='import/drugs.sql',
            help='Path to drugs.sql file'
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
        
        self.stdout.write(self.style.SUCCESS(f'Reading consumables from: {file_path}'))
        
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
        
        # Parse drugs.sql to extract consumables (consumable=1)
        consumables = {}  # {code: {'name': name, 'base_price': price, 'drug_code': drug_code}}
        stats = {
            'total_lines': 0,
            'consumable_lines': 0,
            'unique_codes': 0,
            'errors': 0
        }
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                stats['total_lines'] += 1
                
                if line_num % 50000 == 0:
                    self.stdout.write(f'Reading line {line_num}...')
                
                if 'INSERT INTO drugs VALUES' not in line:
                    continue
                
                # Parse INSERT INTO drugs VALUES line by splitting on comma
                values_start = line.find('VALUES(')
                if values_start == -1:
                    continue
                
                values_end = line.rfind(');')
                if values_end == -1:
                    continue
                
                values_str = line[values_start + 6:values_end].strip()
                
                # Parse quoted values - split carefully to handle commas inside quotes
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
                
                # Extract needed fields
                # Format: drug_id(0), name(1), ndc_number(2), on_order(3), reorder_point(4), max_level(5), last_notify(6), reactions(7), form(8), bill_group(9), size(10), unit(11), route(12), substitute(13), related_code(14), cyp_factor(15), active(16), allow_combining(17), allow_multiple(18), drug_code(19), consumable(20), ..., base_price(26)
                if len(parts) < 27:
                    continue
                
                drug_id = parts[0] if len(parts) > 0 else ''
                name = parts[1] if len(parts) > 1 else ''
                drug_code = parts[19] if len(parts) > 19 else ''  # drug_code field
                consumable_flag = parts[20] if len(parts) > 20 else '0'  # consumable field
                base_price_str = parts[26] if len(parts) > 26 else ''
                
                # Only process consumables (consumable=1)
                if consumable_flag != '1':
                    continue
                
                # Skip if no name
                if not name or name.strip() == '':
                    continue
                
                # Generate code from drug_code or drug_id
                code = drug_code if drug_code and drug_code.strip() else f'CS-DRG-{drug_id}'
                
                # Parse base_price
                base_price = None
                try:
                    if base_price_str and base_price_str.strip() and base_price_str != '':
                        base_price = Decimal(base_price_str)
                        if base_price <= 0:
                            base_price = None
                except:
                    pass
                
                # Use default price if no base_price
                if not base_price:
                    base_price = Decimal('30.00')  # Default price
                
                if code not in consumables:
                    consumables[code] = {
                        'name': name,
                        'base_price': base_price,
                        'drug_id': drug_id,
                        'drug_code': drug_code
                    }
                    stats['consumable_lines'] += 1
                    stats['unique_codes'] += 1
                else:
                    # Update price if higher (take max price)
                    if base_price > consumables[code]['base_price']:
                        consumables[code]['base_price'] = base_price
        
        self.stdout.write(self.style.SUCCESS(f'\nFound {stats["unique_codes"]} unique consumables from {stats["consumable_lines"]} drug entries'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN - No changes will be made ===\n'))
            for code, data in sorted(consumables.items())[:20]:
                self.stdout.write(f'  {code}: {data["name"]} - Price: GHS {data["base_price"]}')
            if len(consumables) > 20:
                self.stdout.write(f'  ... and {len(consumables) - 20} more')
            return
        
        # Import consumables
        created_count = 0
        updated_count = 0
        price_count = 0
        
        with transaction.atomic():
            for code, data in consumables.items():
                # Create or update ServiceCode
                service_code, created = ServiceCode.objects.get_or_create(
                    code=code,
                    defaults={
                        'description': data['name'],
                        'category': 'Clinical Consumables',
                        'is_active': True,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Update description if changed
                    if service_code.description != data['name']:
                        service_code.description = data['name']
                        service_code.save()
                        updated_count += 1
                
                # Create prices for all categories
                for category in [cash_category, corp_category, ins_category]:
                    price = data['base_price']
                    # Corporate and Insurance get slight discount
                    if category == corp_category:
                        price = price * Decimal('1.10')  # 10% markup
                    elif category == ins_category:
                        price = price * Decimal('1.15')  # 15% markup
                    
                    service_price, _ = ServicePrice.objects.update_or_create(
                        service_code=service_code,
                        pricing_category=category,
                        defaults={
                            'price': price,
                            'is_active': True,
                            'effective_from': timezone.now().date(),
                        }
                    )
                    price_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Import Summary:'))
        self.stdout.write(f'  - Created: {created_count} consumable codes')
        self.stdout.write(f'  - Updated: {updated_count} consumable codes')
        self.stdout.write(f'  - Prices imported: {price_count} price entries')
        self.stdout.write(self.style.SUCCESS(f'\n✅ Import completed successfully!'))

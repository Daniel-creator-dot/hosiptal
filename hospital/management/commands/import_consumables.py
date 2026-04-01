"""
Import clinical consumables from billing.sql
Extracts consumable codes (CS001, CS002, CS003, etc.) and their prices
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
    help = 'Import clinical consumables (syringes, etc.) from billing.sql file'

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
        
        # Parse billing.sql to extract consumable codes
        consumables = {}  # {code: {'description': desc, 'prices': {pricelevel: [prices]}}}
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
                
                # Only look for consumable codes (CS001, CS002, CS003, etc.)
                if 'CS' not in line or 'INSERT INTO billing VALUES' not in line:
                    continue
                
                # Parse INSERT INTO billing VALUES line by splitting on comma
                # Extract the part after VALUES( and before );
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
                
                # Extract needed fields (0-indexed after parsing)
                # Format: id(0), date(1), code_type(2), code(3), pid(4), provider_id(5), 
                #         user(6), groupname(7), authorized(8), encounter(9), code_text(10),
                #         billed(11), activity(12), payer_id(13), bill_process(14), bill_date(15),
                #         process_date(16), process_file(17), modifier(18), units(19), fee(20),
                #         justify(21), target(22), x12_partner_id(23), ndc_info(24), notecodes(25),
                #         external_id(26), pricelevel(27), ...
                if len(parts) < 21:
                    continue
                
                code = parts[3] if len(parts) > 3 else ''
                code_text = parts[10] if len(parts) > 10 else ''
                fee_str = parts[20] if len(parts) > 20 else ''
                pricelevel = parts[27] if len(parts) > 27 else ''
                
                # Only process consumable codes (CS001, CS002, CS003, etc.)
                if not code or not code.startswith('CS') or not fee_str:
                    continue
                
                try:
                    fee = Decimal(fee_str)
                    if fee <= 0:
                        continue
                    
                    stats['consumable_lines'] += 1
                    
                    # Initialize code entry if not exists
                    if code not in consumables:
                        consumables[code] = {
                            'description': code_text or f'CONSUMABLES - {code}',
                            'prices': {}
                        }
                        stats['unique_codes'] += 1
                    
                    # Store price by price level
                    if pricelevel:
                        if pricelevel not in consumables[code]['prices']:
                            consumables[code]['prices'][pricelevel] = []
                        consumables[code]['prices'][pricelevel].append(fee)
                    else:
                        # Default to cash if no pricelevel
                        if 'cash' not in consumables[code]['prices']:
                            consumables[code]['prices']['cash'] = []
                        consumables[code]['prices']['cash'].append(fee)
                    
                except (ValueError, TypeError) as e:
                    stats['errors'] += 1
                    if stats['errors'] <= 10:
                        self.stdout.write(self.style.WARNING(f'Error parsing line {line_num}: {e}'))
                    continue
        
        self.stdout.write(self.style.SUCCESS(f'\nFound {stats["unique_codes"]} unique consumable codes from {stats["consumable_lines"]} billing entries'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN - No changes will be made ===\n'))
            for code, data in sorted(consumables.items()):
                desc = data['description']
                # Get average price for each price level
                prices_summary = []
                for pricelevel, prices in data['prices'].items():
                    avg_price = sum(prices) / len(prices) if prices else Decimal('0.00')
                    max_price = max(prices) if prices else Decimal('0.00')
                    prices_summary.append(f'{pricelevel}: {avg_price:.2f} (max: {max_price:.2f})')
                self.stdout.write(f'{code}: {desc} - {", ".join(prices_summary)}')
            return
        
        # Import consumables
        imported = 0
        updated = 0
        prices_imported = 0
        
        with transaction.atomic():
            for code, data in sorted(consumables.items()):
                desc = data['description']
                
                # Get average price as default (most common price)
                all_prices = []
                for pricelevel, prices in data['prices'].items():
                    all_prices.extend(prices)
                
                default_price = sum(all_prices) / len(all_prices) if all_prices else Decimal('30.00')
                # Round to 2 decimal places
                default_price = Decimal(str(round(default_price, 2)))
                
                # Create or update ServiceCode
                service_code, created = ServiceCode.objects.get_or_create(
                    code=code,
                    defaults={
                        'description': desc,
                        'category': 'Clinical Consumables',
                        'is_active': True,
                    }
                )
                
                if created:
                    imported += 1
                    self.stdout.write(self.style.SUCCESS(f'✓ Created: {code} - {desc} (Default: GHS {default_price})'))
                else:
                    # Update if description changed or category is wrong
                    if service_code.description != desc or service_code.category != 'Clinical Consumables':
                        service_code.description = desc
                        service_code.category = 'Clinical Consumables'
                        service_code.is_active = True
                        service_code.save()
                        updated += 1
                        self.stdout.write(self.style.SUCCESS(f'✓ Updated: {code} - {desc}'))
                
                # Import prices for each price level
                for pricelevel, prices in data['prices'].items():
                    # Determine which pricing category to use
                    if pricelevel in ['cash', 'Cash', 'CASH']:
                        category = cash_category
                    elif pricelevel in ['corp', 'Corporate', 'CORP']:
                        category = corp_category
                    elif pricelevel in ['ins', 'Insurance', 'INS', 'insurance']:
                        category = ins_category
                    else:
                        # Default to cash for unknown price levels
                        category = cash_category
                    
                    # Use average price for this price level
                    avg_price = sum(prices) / len(prices) if prices else default_price
                    avg_price = Decimal(str(round(avg_price, 2)))
                    
                    # Create or update ServicePrice
                    service_price, sp_created = ServicePrice.objects.update_or_create(
                        service_code=service_code,
                        pricing_category=category,
                        defaults={
                            'price': avg_price,
                            'is_active': True,
                            'effective_from': timezone.now().date(),
                        }
                    )
                    
                    if sp_created:
                        prices_imported += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Import Summary:'))
        self.stdout.write(f'  - Created: {imported} consumable codes')
        self.stdout.write(f'  - Updated: {updated} consumable codes')
        self.stdout.write(f'  - Prices imported: {prices_imported} price entries')
        self.stdout.write(self.style.SUCCESS(f'\n✅ Import completed successfully!'))

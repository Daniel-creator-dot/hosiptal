"""
Import drug prices and stocks from legacy SQL files
Imports from:
- prices.sql: Maps drug_id to prices by payer level (cash, corp, ins)
- drug_inventory.sql: Maps drug_id to stock quantities by warehouse/location
- drugs.sql: Base drug information including base_price and last_cost
"""
import os
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from hospital.models import Drug, PharmacyStock
from hospital.models_legacy_mapping import LegacyIDMapping
from hospital.models_flexible_pricing import PricingCategory, ServicePrice
from hospital.models import ServiceCode, Payer


class Command(BaseCommand):
    help = 'Import drug prices and stocks from legacy SQL files (prices.sql, drug_inventory.sql, drugs.sql)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prices-file',
            type=str,
            default='import/prices.sql',
            help='Path to prices.sql file'
        )
        parser.add_argument(
            '--inventory-file',
            type=str,
            default='import/drug_inventory.sql',
            help='Path to drug_inventory.sql file'
        )
        parser.add_argument(
            '--drugs-file',
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
        prices_file = options['prices_file']
        inventory_file = options['inventory_file']
        drugs_file = options['drugs_file']
        dry_run = options['dry_run']
        
        stats = {
            'drugs_processed': 0,
            'prices_imported': 0,
            'stocks_imported': 0,
            'errors': 0
        }
        
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
        
        # Step 1: Import base drug prices from drugs.sql
        if os.path.exists(drugs_file):
            self.stdout.write(self.style.SUCCESS(f'\n📦 Step 1: Importing base drug prices from {drugs_file}'))
            self._import_base_drug_prices(drugs_file, dry_run, stats)
        
        # Step 2: Import detailed prices from prices.sql (by payer level)
        if os.path.exists(prices_file):
            self.stdout.write(self.style.SUCCESS(f'\n💰 Step 2: Importing detailed prices from {prices_file}'))
            self._import_detailed_prices(prices_file, dry_run, stats, cash_category, corp_category, ins_category)
        
        # Step 3: Import stock quantities from drug_inventory.sql
        if os.path.exists(inventory_file):
            self.stdout.write(self.style.SUCCESS(f'\n📊 Step 3: Importing stock quantities from {inventory_file}'))
            self._import_stock_quantities(inventory_file, dry_run, stats)
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n✅ Import Summary:'))
        self.stdout.write(f'  - Drugs processed: {stats["drugs_processed"]}')
        self.stdout.write(f'  - Prices imported: {stats["prices_imported"]}')
        self.stdout.write(f'  - Stock records imported: {stats["stocks_imported"]}')
        if stats['errors'] > 0:
            self.stdout.write(self.style.WARNING(f'  - Errors: {stats["errors"]}'))
        self.stdout.write(self.style.SUCCESS(f'\n✅ Import completed!'))
    
    def _import_base_drug_prices(self, drugs_file, dry_run, stats):
        """Import base prices from drugs.sql (base_price and last_cost fields)"""
        # Parse INSERT INTO drugs VALUES
        # Format: INSERT INTO drugs VALUES("drug_id","name",...,"base_price",...,"last_cost",...)
        # drug_id is first field, base_price is around field 26, last_cost is around field 33
        pattern = r'INSERT INTO drugs VALUES\([^)]*"([^"]+)","([^"]+)",[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,"([^"]*)"'
        
        drug_prices = {}  # {drug_id: {base_price: price, last_cost: cost}}
        
        with open(drugs_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if 'INSERT INTO drugs VALUES' not in line:
                    continue
                
                # Parse all fields - split by comma but handle quoted strings
                # More reliable: extract fields by position
                try:
                    # Find values between first ( and last )
                    match = re.search(r'VALUES\((.*)\);', line)
                    if not match:
                        continue
                    
                    values_str = match.group(1)
                    # Split by comma but preserve quoted strings
                    fields = []
                    current_field = ''
                    in_quotes = False
                    for char in values_str:
                        if char == '"' and (not current_field or current_field[-1] != '\\'):
                            in_quotes = not in_quotes
                            current_field += char
                        elif char == ',' and not in_quotes:
                            fields.append(current_field.strip())
                            current_field = ''
                        else:
                            current_field += char
                    if current_field:
                        fields.append(current_field.strip())
                    
                    if len(fields) < 27:
                        continue
                    
                    drug_id = fields[0].strip('"')
                    drug_name = fields[1].strip('"')
                    base_price_str = fields[26].strip('"') if len(fields) > 26 else ''
                    last_cost_str = fields[33].strip('"') if len(fields) > 33 else ''
                    
                    # Try to extract prices
                    base_price = None
                    last_cost = None
                    
                    try:
                        if base_price_str and base_price_str != '':
                            base_price = Decimal(base_price_str)
                    except:
                        pass
                    
                    try:
                        if last_cost_str and last_cost_str != '':
                            last_cost = Decimal(last_cost_str)
                    except:
                        pass
                    
                    if drug_id and drug_name:
                        drug_prices[drug_id] = {
                            'name': drug_name,
                            'base_price': base_price,
                            'last_cost': last_cost
                        }
                        stats['drugs_processed'] += 1
                        
                except Exception as e:
                    stats['errors'] += 1
                    if stats['errors'] <= 5:
                        self.stdout.write(self.style.WARNING(f'  Error parsing line {line_num}: {e}'))
                    continue
        
        if dry_run:
            self.stdout.write(f'  Would update {len(drug_prices)} drugs with base prices')
            for drug_id, data in list(drug_prices.items())[:10]:
                self.stdout.write(f'    Drug {drug_id}: {data["name"]} - Base: {data["base_price"]}, Cost: {data["last_cost"]}')
            return
        
        # Update drugs
        updated_count = 0
        with transaction.atomic():
            for drug_id, data in drug_prices.items():
                # Find drug by legacy mapping or by fuzzy name match
                drug = None
                
                # Try legacy mapping first
                mapping = LegacyIDMapping.objects.filter(
                    legacy_table='drugs',
                    legacy_id=str(drug_id)
                ).first()
                
                if mapping:
                    try:
                        drug = Drug.objects.get(id=mapping.new_id, is_deleted=False)
                    except Drug.DoesNotExist:
                        pass
                
                # If no mapping, try fuzzy name match
                if not drug:
                    # Try exact name match first
                    drug = Drug.objects.filter(
                        name__iexact=data['name'],
                        is_deleted=False
                    ).first()
                
                if drug:
                    updated = False
                    # Update base_price (unit_price)
                    if data['base_price'] and data['base_price'] > 0:
                        if drug.unit_price != data['base_price']:
                            drug.unit_price = data['base_price']
                            updated = True
                    
                    # Update cost_price (last_cost)
                    if data['last_cost'] and data['last_cost'] > 0:
                        if hasattr(drug, 'cost_price'):
                            if drug.cost_price != data['last_cost']:
                                drug.cost_price = data['last_cost']
                                updated = True
                    
                    if updated:
                        drug.save()
                        updated_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Updated {updated_count} drugs with base prices'))
    
    def _import_detailed_prices(self, prices_file, dry_run, stats, cash_category, corp_category, ins_category):
        """Import detailed prices from prices.sql by payer level"""
        # Parse INSERT INTO prices VALUES("pr_id","pr_selector","pr_level","pr_price",...)
        # pr_id = drug_id, pr_selector = drug name, pr_level = cash/corp/ins, pr_price = price
        pattern = r'INSERT INTO prices VALUES\("([^"]+)","([^"]+)","([^"]+)","([^"]+)",[^)]*\);'
        
        drug_prices_by_level = {}  # {drug_id: {cash: price, corp: price, ins: price, ...}}
        
        with open(prices_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if 'INSERT INTO prices VALUES' not in line:
                    continue
                
                match = re.search(pattern, line)
                if not match:
                    continue
                
                drug_id = match.group(1)
                drug_name = match.group(2)
                price_level = match.group(3).lower()
                price_str = match.group(4)
                
                try:
                    price = Decimal(price_str)
                    if price <= 0:
                        continue
                except:
                    continue
                
                if drug_id not in drug_prices_by_level:
                    drug_prices_by_level[drug_id] = {
                        'name': drug_name,
                        'prices': {}
                    }
                
                drug_prices_by_level[drug_id]['prices'][price_level] = price
                stats['prices_imported'] += 1
        
        if dry_run:
            self.stdout.write(f'  Would import prices for {len(drug_prices_by_level)} drugs')
            for drug_id, data in list(drug_prices_by_level.items())[:10]:
                prices_str = ', '.join([f'{k}: {v}' for k, v in data['prices'].items()])
                self.stdout.write(f'    Drug {drug_id}: {data["name"]} - {prices_str}')
            return
        
        # Import prices
        imported_count = 0
        with transaction.atomic():
            for drug_id, data in drug_prices_by_level.items():
                # Find drug by legacy mapping or name
                drug = None
                
                # Try legacy mapping
                mapping = LegacyIDMapping.objects.filter(
                    legacy_table='drugs',
                    legacy_id=str(drug_id)
                ).first()
                
                if mapping:
                    try:
                        drug = Drug.objects.get(id=mapping.new_id, is_deleted=False)
                    except Drug.DoesNotExist:
                        pass
                
                # Try name match
                if not drug:
                    drug = Drug.objects.filter(
                        name__iexact=data['name'],
                        is_deleted=False
                    ).first()
                
                if drug:
                    # Create or get ServiceCode for this drug
                    service_code, _ = ServiceCode.objects.get_or_create(
                        code=f"DRUG-{drug.code if hasattr(drug, 'code') and drug.code else drug.pk}",
                        defaults={
                            'description': f"{drug.name} {drug.strength}".strip(),
                            'category': 'Pharmacy Services',
                            'is_active': True,
                        }
                    )
                    
                    # Import prices for each level
                    for price_level, price in data['prices'].items():
                        # Determine pricing category
                        if price_level in ['cash', '']:
                            category = cash_category
                        elif price_level in ['corp', 'corporate']:
                            category = corp_category
                        elif price_level in ['ins', 'insurance', 'nhis']:
                            category = ins_category
                        else:
                            # Default to cash for unknown levels
                            category = cash_category
                        
                        # Create or update ServicePrice
                        service_price, created = ServicePrice.objects.update_or_create(
                            service_code=service_code,
                            pricing_category=category,
                            defaults={
                                'price': price,
                                'is_active': True,
                                'effective_from': timezone.now().date(),
                            }
                        )
                        
                        if created:
                            imported_count += 1
                        
                        # Also update drug.unit_price with cash price as default
                        if price_level in ['cash', ''] and drug.unit_price == 0:
                            drug.unit_price = price
                            drug.save()
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Imported {imported_count} price entries'))
    
    def _import_stock_quantities(self, inventory_file, dry_run, stats):
        """Import stock quantities from drug_inventory.sql"""
        # Parse INSERT INTO drug_inventory VALUES("inventory_id","drug_id","lot_number",...,"on_hand","warehouse_id",...)
        # drug_id is field 1, on_hand is around field 9, warehouse_id is around field 10
        pattern = r'INSERT INTO drug_inventory VALUES\([^)]*"([^"]+)","([^"]+)",[^)]*\);'
        
        stock_data = {}  # {drug_id: {warehouse: total_qty}}
        
        with open(inventory_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if 'INSERT INTO drug_inventory VALUES' not in line:
                    continue
                
                try:
                    # Extract fields
                    match = re.search(r'VALUES\((.*)\);', line)
                    if not match:
                        continue
                    
                    values_str = match.group(1)
                    fields = []
                    current_field = ''
                    in_quotes = False
                    for char in values_str:
                        if char == '"' and (not current_field or current_field[-1] != '\\'):
                            in_quotes = not in_quotes
                            current_field += char
                        elif char == ',' and not in_quotes:
                            fields.append(current_field.strip())
                            current_field = ''
                        else:
                            current_field += char
                    if current_field:
                        fields.append(current_field.strip())
                    
                    if len(fields) < 10:
                        continue
                    
                    inventory_id = fields[0].strip('"')
                    drug_id = fields[1].strip('"')
                    on_hand_str = fields[9].strip('"') if len(fields) > 9 else '0'
                    warehouse = fields[10].strip('"') if len(fields) > 10 else 'Dispensary'
                    
                    try:
                        on_hand = int(on_hand_str) if on_hand_str and on_hand_str != '' else 0
                    except:
                        on_hand = 0
                    
                    if drug_id and on_hand > 0:
                        if drug_id not in stock_data:
                            stock_data[drug_id] = {}
                        if warehouse not in stock_data[drug_id]:
                            stock_data[drug_id][warehouse] = 0
                        stock_data[drug_id][warehouse] += on_hand
                        stats['stocks_imported'] += 1
                        
                except Exception as e:
                    stats['errors'] += 1
                    if stats['errors'] <= 5:
                        self.stdout.write(self.style.WARNING(f'  Error parsing line {line_num}: {e}'))
                    continue
        
        if dry_run:
            self.stdout.write(f'  Would update stock for {len(stock_data)} drugs')
            for drug_id, warehouses in list(stock_data.items())[:10]:
                totals = ', '.join([f'{w}: {q}' for w, q in warehouses.items()])
                self.stdout.write(f'    Drug {drug_id}: {totals}')
            return
        
        # Update PharmacyStock
        updated_count = 0
        created_count = 0
        
        with transaction.atomic():
            for drug_id, warehouses in stock_data.items():
                # Find drug
                drug = None
                
                # Try legacy mapping
                mapping = LegacyIDMapping.objects.filter(
                    legacy_table='drugs',
                    legacy_id=str(drug_id)
                ).first()
                
                if mapping:
                    try:
                        drug = Drug.objects.get(id=mapping.new_id, is_deleted=False)
                    except Drug.DoesNotExist:
                        pass
                
                if drug:
                    # Update stock for each warehouse
                    for warehouse, total_qty in warehouses.items():
                        # Find or create PharmacyStock
                        # Default location is 'Dispensary' if warehouse is empty
                        location = warehouse if warehouse and warehouse != '' else 'Dispensary'
                        
                        stock, created = PharmacyStock.objects.get_or_create(
                            drug=drug,
                            location=location,
                            is_deleted=False,
                            defaults={
                                'quantity_on_hand': total_qty,
                                'reorder_level': 10,  # Default reorder level
                            }
                        )
                        
                        if created:
                            created_count += 1
                            stock.quantity_on_hand = total_qty
                            stock.save()
                        elif stock.quantity_on_hand != total_qty:
                            # Update quantity if different
                            stock.quantity_on_hand = total_qty
                            stock.save()
                            updated_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Created {created_count} stock records, updated {updated_count}'))

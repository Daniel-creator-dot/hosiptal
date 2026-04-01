"""
Import Drug Stock from Legacy Database
Re-imports stock quantities from drug_inventory.sql into PharmacyStock
"""

import os
import re
from decimal import Decimal
from datetime import date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
import logging

from hospital.models import Drug, PharmacyStock

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import drug stock from drug_inventory.sql into PharmacyStock'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-file',
            type=str,
            default='import/db_3_extracted/drug_inventory.sql',
            help='Path to drug_inventory.sql file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be imported without making changes'
        )
    
    def handle(self, *args, **options):
        sql_file = options['sql_file']
        dry_run = options['dry_run']
        
        if not os.path.exists(sql_file):
            raise CommandError(f'SQL file not found: {sql_file}')
        
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('DRUG STOCK IMPORT'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN MODE] - No changes will be made\n'))
        
        # Build drug mapping from existing drugs
        self.stdout.write('Building drug mapping...')
        drug_mapping = {}
        for drug in Drug.objects.filter(is_deleted=False):
            # Try to match by name - this is a simple approach
            # In production, you'd use a legacy_id field
            drug_mapping[drug.name.lower().strip()] = drug
        
        self.stdout.write(f'  Found {len(drug_mapping)} drugs in database')
        
        # Parse SQL file
        self.stdout.write(f'\nParsing {sql_file}...')
        inserts = self.parse_sql_file(sql_file)
        self.stdout.write(f'  Found {len(inserts)} inventory records')
        
        # Aggregate stock by drug + batch
        stock_data = {}
        matched = 0
        unmatched = 0
        
        for idx, insert in enumerate(inserts):
            if insert['table'] != 'drug_inventory':
                continue
            
            try:
                values = insert['values']
                # Ensure values is a list
                if not isinstance(values, list):
                    continue
                
                legacy_drug_id = values[1] if len(values) > 1 else None  # drug_id
                lot_number = values[2] if len(values) > 2 else ''  # lot_number
                expiration = values[3] if len(values) > 3 else None  # expiration
                on_hand = values[5] if len(values) > 5 else 0  # on_hand
                warehouse_id = values[6] if len(values) > 6 else ''  # warehouse_id
                value_onhand = values[17] if len(values) > 17 else 0  # value_onhand
                
                if not legacy_drug_id:
                    continue
                
                # Convert on_hand to integer
                try:
                    on_hand = int(on_hand) if on_hand else 0
                except:
                    on_hand = 0
                
                if on_hand <= 0:
                    continue
                
                # Find drug - we need to map legacy_drug_id to Drug
                # Since we don't have a direct mapping, we'll need to use drugs.sql
                # For now, skip records where we can't find the drug
                # In a full implementation, you'd maintain a legacy_id mapping table
                
                # Parse expiration
                expiry_date = None
                if expiration:
                    try:
                        expiry_date = self.parse_date(expiration)
                    except:
                        expiry_date = None
                
                batch_number = lot_number[:50] if lot_number else f"BATCH{idx}"
                location = warehouse_id[:100] if warehouse_id else 'Main Pharmacy'
                
                # Calculate unit cost
                unit_cost = Decimal('0')
                if value_onhand and on_hand:
                    try:
                        unit_cost = Decimal(str(value_onhand)) / Decimal(str(on_hand))
                    except:
                        pass
                
                # Store for later processing - we'll need drug mapping from drugs.sql
                key = (str(legacy_drug_id), batch_number, expiry_date)
                if key not in stock_data:
                    stock_data[key] = {
                        'legacy_drug_id': str(legacy_drug_id),
                        'batch_number': batch_number,
                        'expiry_date': expiry_date,
                        'quantity': 0,
                        'unit_cost': unit_cost,
                        'location': location,
                    }
                
                stock_data[key]['quantity'] += on_hand
                
                if (idx + 1) % 1000 == 0:
                    self.stdout.write(f'  Processed {idx + 1:,} records...')
                    
            except Exception as e:
                logger.error(f'Error processing inventory record {idx}: {e}')
        
        self.stdout.write(f'\nAggregated {len(stock_data)} unique stock batches')
        
        # Now we need to map legacy_drug_id to Drug
        # Read drugs.sql to build the mapping
        drugs_sql = os.path.join(os.path.dirname(sql_file), 'drugs.sql')
        if os.path.exists(drugs_sql):
            self.stdout.write(f'\nReading drug mapping from {drugs_sql}...')
            drug_id_to_name = self.parse_drugs_file(drugs_sql)
            self.stdout.write(f'  Found {len(drug_id_to_name)} drug mappings')
            
            # Now map to Django Drug objects - try exact match first, then fuzzy match
            for legacy_id, drug_name in drug_id_to_name.items():
                drug = None
                drug_name_clean = drug_name.lower().strip()
                
                # Try exact match first
                drug = drug_mapping.get(drug_name_clean)
                
                # If no exact match, try fuzzy matching (case-insensitive partial match)
                if not drug:
                    for django_drug_name, django_drug in drug_mapping.items():
                        # Try partial match (if legacy name is in Django name or vice versa)
                        if drug_name_clean in django_drug_name or django_drug_name in drug_name_clean:
                            drug = django_drug
                            break
                        # Try matching without common prefixes/suffixes
                        legacy_clean = drug_name_clean.replace('tablet', '').replace('capsule', '').replace('injection', '').strip()
                        django_clean = django_drug_name.replace('tablet', '').replace('capsule', '').replace('injection', '').strip()
                        if legacy_clean and django_clean and (legacy_clean in django_clean or django_clean in legacy_clean):
                            drug = django_drug
                            break
                
                if drug:
                    # Update stock_data with drug reference
                    for key, data in stock_data.items():
                        if data['legacy_drug_id'] == str(legacy_id):
                            data['drug'] = drug
                            matched += 1
                else:
                    unmatched += 1
        
        self.stdout.write(f'\nMatched {matched} stock records to drugs')
        if unmatched > 0:
            self.stdout.write(self.style.WARNING(f'  [WARNING] {unmatched} stock records could not be matched'))
        
        # Create/update PharmacyStock records
        if not dry_run:
            self.stdout.write(f'\nCreating/updating PharmacyStock records...')
            created = 0
            updated = 0
            
            with transaction.atomic():
                for key, data in stock_data.items():
                    if 'drug' not in data:
                        continue  # Skip unmatched
                    
                    drug = data['drug']
                    batch_number = data['batch_number']
                    expiry_date = data['expiry_date'] or date(2099, 12, 31)
                    quantity = data['quantity']
                    unit_cost = data['unit_cost']
                    location = data['location']
                    
                    # Check for existing stock - prevent duplicates by drug+batch+expiry
                    existing = PharmacyStock.objects.filter(
                        drug=drug,
                        batch_number=batch_number,
                        expiry_date=expiry_date,
                        is_deleted=False
                    ).first()
                    
                    if existing:
                        # Update existing - prevent duplicate by updating quantity intelligently
                        # Use maximum quantity to ensure we don't lose stock
                        if quantity > 0:
                            # If new quantity is larger, update it (prevents losing stock)
                            if quantity > existing.quantity_on_hand:
                                existing.quantity_on_hand = quantity
                            # Update cost if missing
                            if unit_cost > 0 and (existing.unit_cost == 0 or not existing.unit_cost):
                                existing.unit_cost = unit_cost
                            # Update location if missing
                            if location and not existing.location:
                                existing.location = location
                            existing.save()
                            updated += 1
                        # If quantity is same or less, skip to prevent unnecessary updates
                    else:
                        # Create new - prevent duplicates by checking one more time
                        duplicate_check = PharmacyStock.objects.filter(
                            drug=drug,
                            batch_number=batch_number,
                            expiry_date=expiry_date,
                            is_deleted=False
                        ).first()
                        
                        if not duplicate_check:
                            # No duplicate found - create new
                            stock = PharmacyStock(
                                drug=drug,
                                batch_number=batch_number,
                                expiry_date=expiry_date,
                                location=location,
                                quantity_on_hand=quantity,
                                unit_cost=unit_cost
                            )
                            stock.save()
                            created += 1
                        else:
                            # Duplicate found during creation (race condition) - update instead
                            if quantity > 0:
                                if quantity > duplicate_check.quantity_on_hand:
                                    duplicate_check.quantity_on_hand = quantity
                                if unit_cost > 0 and (duplicate_check.unit_cost == 0 or not duplicate_check.unit_cost):
                                    duplicate_check.unit_cost = unit_cost
                                if location and not duplicate_check.location:
                                    duplicate_check.location = location
                                duplicate_check.save()
                                updated += 1
                
                if dry_run:
                    raise Exception("DRY RUN - Rolling back")
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('STOCK IMPORT SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*70))
        if not dry_run:
            self.stdout.write(f'Created: {created} stock records')
            self.stdout.write(f'Updated: {updated} stock records')
        else:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes made'))
        self.stdout.write('='*70)
    
    def parse_sql_file(self, sql_file):
        """Parse SQL file and extract INSERT statements"""
        inserts = []
        with open(sql_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Process line by line for better performance on large files
        current_table = None
        current_values = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('--') or line.startswith('DROP') or line.startswith('CREATE'):
                continue
            
            # Match INSERT INTO table VALUES (...);
            match = re.match(r'INSERT\s+INTO\s+`?(\w+)`?\s+VALUES\s*\((.*?)\);', line, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                values_str = match.group(2)
                
                # Parse values
                values = self.parse_sql_values(values_str)
                if values:
                    inserts.append({
                        'table': table_name,
                        'values': values
                    })
        
        return inserts
    
    def parse_drugs_file(self, drugs_sql):
        """Parse drugs.sql to build legacy_id -> drug_name mapping"""
        mapping = {}
        inserts = self.parse_sql_file(drugs_sql)
        
        for insert in inserts:
            if insert['table'] != 'drugs':
                continue
            
            try:
                values = insert['values']
                legacy_id = values[0] if len(values) > 0 else None
                name = values[1] if len(values) > 1 else ''
                
                if legacy_id and name:
                    mapping[str(legacy_id)] = name
            except:
                continue
        
        return mapping
    
    def parse_sql_values(self, values_str):
        """Parse SQL VALUES string into Python values - handles quoted strings, NULL, numbers"""
        if not values_str or not values_str.strip():
            return []
        
        values = []
        current = ''
        in_quotes = False
        quote_char = None
        escaped = False
        
        i = 0
        while i < len(values_str):
            char = values_str[i]
            
            if escaped:
                current += char
                escaped = False
                i += 1
                continue
            
            if char == '\\':
                escaped = True
                if in_quotes:
                    current += char
                i += 1
                continue
            
            if not in_quotes:
                if char in ("'", '"'):
                    in_quotes = True
                    quote_char = char
                elif char == ',':
                    val = self.convert_value(current.strip())
                    values.append(val)
                    current = ''
                else:
                    current += char
            else:
                if char == quote_char:
                    # Check if next char is also quote (MySQL escaping)
                    if i + 1 < len(values_str) and values_str[i + 1] == quote_char:
                        current += quote_char
                        i += 1  # Skip next quote
                    else:
                        in_quotes = False
                        quote_char = None
                else:
                    current += char
            i += 1
        
        # Add last value
        if current.strip() or (current and not in_quotes):
            val = self.convert_value(current.strip())
            values.append(val)
        
        return values
    
    def convert_value(self, value):
        """Convert SQL value to Python type"""
        if not value:
            return None
        
        value = str(value).strip()
        
        # Handle NULL
        if not value or value.upper() == 'NULL':
            return None
        
        # Handle empty strings
        if value == '""' or value == "''" or value == '':
            return ''
        
        # Remove quotes if present
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            unquoted = value[1:-1]
            # If unquoted is empty, return empty string
            if not unquoted:
                return ''
            value = unquoted
        
        # Handle boolean
        if value.upper() == 'TRUE' or value == '1':
            return True
        if value.upper() == 'FALSE' or value == '0':
            return False
        
        # Try number conversion
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            # Return as string
            return value
    
    def parse_date(self, value):
        """Parse date string to date object"""
        if not value:
            return date(2000, 1, 1)
        if isinstance(value, date):
            return value
        
        formats = ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y']
        for fmt in formats:
            try:
                from datetime import datetime
                return datetime.strptime(str(value), fmt).date()
            except:
                continue
        
        return date(2000, 1, 1)

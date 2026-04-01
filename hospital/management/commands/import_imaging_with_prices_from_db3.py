"""
Import Imaging Services with Body Parts and Prices from db_3
This ensures all sub-services (like Chest X-Ray, Limb X-Ray) are imported with their prices
"""
import os
import re
import zipfile
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from collections import defaultdict

from hospital.models_advanced import ImagingCatalog


class Command(BaseCommand):
    help = 'Import imaging services with body parts and prices from db_3.zip'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='import/db_3.zip',
            help='Path to db_3.zip file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        zip_path = options['file']
        dry_run = options['dry_run']
        
        if not os.path.exists(zip_path):
            self.stdout.write(self.style.ERROR(f'File not found: {zip_path}'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Reading from: {zip_path}'))
        
        # Extract prices
        prices = self.extract_prices(zip_path)
        self.stdout.write(f'Found {len(prices)} unique service price entries')
        
        # Extract imaging studies
        imaging_studies = self.extract_imaging_studies(zip_path)
        self.stdout.write(f'Found {len(imaging_studies)} imaging studies')
        
        # Import to database
        stats = {
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'with_prices': 0,
        }
        
        if not dry_run:
            with transaction.atomic():
                for code, study_data in imaging_studies.items():
                    try:
                        # Get price (prefer cash, then corp, then first available)
                        price = Decimal('0.00')
                        name = study_data['name']
                        
                        # Try to find price by code or name
                        price_found = False
                        
                        # Try exact code match first
                        if code in prices:
                            price_dict = prices[code]
                            if 'cash' in price_dict:
                                price = price_dict['cash']
                                price_found = True
                            elif 'corp' in price_dict:
                                price = price_dict['corp']
                                price_found = True
                            elif price_dict:
                                price = list(price_dict.values())[0]
                                price_found = True
                        
                        # Try exact name match
                        if not price_found and name in prices:
                            price_dict = prices[name]
                            if 'cash' in price_dict:
                                price = price_dict['cash']
                                price_found = True
                            elif 'corp' in price_dict:
                                price = price_dict['corp']
                                price_found = True
                            elif price_dict:
                                price = list(price_dict.values())[0]
                                price_found = True
                        
                        # Try partial name match (for cases where name might have variations)
                        if not price_found:
                            name_clean = name.lower().strip()
                            for price_key, price_dict in prices.items():
                                price_key_clean = str(price_key).lower().strip()
                                # Check if name contains key or key contains name (for partial matches)
                                if (name_clean in price_key_clean or price_key_clean in name_clean) and len(name_clean) > 5:
                                    if 'cash' in price_dict:
                                        price = price_dict['cash']
                                        price_found = True
                                        break
                                    elif 'corp' in price_dict:
                                        price = price_dict['corp']
                                        price_found = True
                                        break
                        
                        # Try matching by removing common words and matching core terms
                        if not price_found:
                            # Extract key terms from name (remove common words)
                            name_words = [w for w in name_clean.split() if w not in ['x-ray', 'xray', 'scan', 'ultrasound', 'with', 'report', 'no', 'reporting', 'the', 'a', 'an']]
                            name_core = ' '.join(name_words[:3])  # First 3 meaningful words
                            
                            for price_key, price_dict in prices.items():
                                price_key_clean = str(price_key).lower().strip()
                                if name_core and name_core in price_key_clean:
                                    if 'cash' in price_dict:
                                        price = price_dict['cash']
                                        price_found = True
                                        break
                                    elif 'corp' in price_dict:
                                        price = price_dict['corp']
                                        price_found = True
                                        break
                        
                        if price_found:
                            stats['with_prices'] += 1
                        
                        # Determine modality
                        modality = self.determine_modality(name)
                        
                        # Extract body part
                        body_part = self.extract_body_part(name)
                        
                        # Create or update
                        imaging_catalog, created = ImagingCatalog.objects.update_or_create(
                            code=code,
                            defaults={
                                'name': name,
                                'modality': modality,
                                'body_part': body_part,
                                'study_type': name,
                                'price': price,
                                'is_active': True,
                            }
                        )
                        
                        if created:
                            stats['imported'] += 1
                            self.stdout.write(f'  ✓ Imported: {name} ({modality}) - GHS {price}')
                        else:
                            stats['updated'] += 1
                            if price > 0:
                                self.stdout.write(f'  ↻ Updated: {name} - Price: GHS {price}')
                    
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ✗ Error importing {code}: {str(e)}'))
                        stats['skipped'] += 1
        else:
            # Dry run - just count
            for code, study_data in imaging_studies.items():
                name = study_data['name']
                price = Decimal('0.00')
                
                if code in prices:
                    price_dict = prices[code]
                    price = price_dict.get('cash', price_dict.get('corp', 
                        list(price_dict.values())[0] if price_dict else Decimal('0.00')))
                elif name in prices:
                    price_dict = prices[name]
                    price = price_dict.get('cash', price_dict.get('corp',
                        list(price_dict.values())[0] if price_dict else Decimal('0.00')))
                
                modality = self.determine_modality(name)
                body_part = self.extract_body_part(name)
                
                self.stdout.write(f'  Would import: {name} ({modality}, {body_part}) - GHS {price}')
                stats['imported'] += 1
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f"Imported: {stats['imported']}")
        self.stdout.write(f"Updated: {stats['updated']}")
        self.stdout.write(f"With prices: {stats['with_prices']}")
        self.stdout.write(f"Skipped: {stats['skipped']}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('\nImport completed successfully!'))

    def extract_prices(self, zip_path):
        """Extract prices from prices.sql"""
        prices = defaultdict(dict)  # {code/name: {level: price}}
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                if 'prices.sql' not in z.namelist():
                    self.stdout.write(self.style.WARNING('prices.sql not found in zip'))
                    return prices
                
                content = z.read('prices.sql').decode('utf-8', errors='ignore')
                
                # Match: INSERT INTO prices VALUES("pr_id","pr_selector","pr_level","pr_price",...)
                pattern = r'INSERT INTO\s+prices\s+VALUES\s*\(([^)]+)\);'
                matches = re.findall(pattern, content, re.IGNORECASE)
                
                for match in matches:
                    # Parse values - handle quoted strings
                    values = self.parse_sql_values(match)
                    
                    if len(values) >= 4:
                        pr_id = values[0].strip()
                        pr_selector = values[1].strip()
                        pr_level = values[2].strip().lower()
                        try:
                            pr_price = Decimal(values[3].strip())
                            
                            # Store by both code and name
                            if pr_id:
                                prices[pr_id][pr_level] = pr_price
                            if pr_selector:
                                prices[pr_selector][pr_level] = pr_price
                        except (ValueError, IndexError):
                            pass
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading prices: {str(e)}'))
        
        return prices

    def extract_imaging_studies(self, zip_path):
        """Extract imaging studies from diag_imaging_order_code.sql"""
        studies = {}
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                if 'diag_imaging_order_code.sql' not in z.namelist():
                    self.stdout.write(self.style.WARNING('diag_imaging_order_code.sql not found in zip'))
                    return studies
                
                content = z.read('diag_imaging_order_code.sql').decode('utf-8', errors='ignore')
                
                # Match INSERT statements
                pattern = r'INSERT INTO\s+\w+\s+VALUES\s*\(([^)]+)\);'
                matches = re.findall(pattern, content, re.IGNORECASE)
                
                for match in matches:
                    values = self.parse_sql_values(match)
                    
                    # Handle different SQL formats
                    # Format 1: order_code_id, procedure_order_id, procedure_order_seq, procedure_code, procedure_name, ...
                    # Format 2: might have different column order
                    if len(values) >= 4:
                        # Try to find procedure_code and procedure_name
                        # Usually they're in positions 3 and 4, but check all positions
                        code = ''
                        name = ''
                        
                        # Look for code-like patterns (usually alphanumeric codes)
                        for i, val in enumerate(values):
                            val_clean = val.strip()
                            # Code is usually shorter and alphanumeric
                            if not code and val_clean and len(val_clean) <= 20 and (val_clean[0].isdigit() or val_clean[0].isalpha()):
                                # Check if next value looks like a name
                                if i + 1 < len(values):
                                    next_val = values[i + 1].strip()
                                    if next_val and len(next_val) > 10:  # Names are usually longer
                                        code = val_clean
                                        name = next_val
                                        break
                        
                        # Fallback: use positions 2 and 3 (most common)
                        if not code and len(values) >= 4:
                            code = values[2].strip() if len(values) > 2 else ''
                            name = values[3].strip() if len(values) > 3 else ''
                        
                        # Also try positions 3 and 4
                        if not code and len(values) >= 5:
                            code = values[3].strip() if len(values) > 3 else ''
                            name = values[4].strip() if len(values) > 4 else ''
                        
                        if code and name and len(code) > 0 and len(name) > 5:
                            # Use code as key to avoid duplicates, prefer longer/more descriptive names
                            if code not in studies or (len(name) > len(studies[code]['name']) and name.lower() not in ['procedure', '']):
                                studies[code] = {'name': name}
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading imaging studies: {str(e)}'))
        
        return studies

    def parse_sql_values(self, value_string):
        """Parse SQL VALUES string handling quoted strings"""
        values = []
        current = ''
        in_quotes = False
        quote_char = None
        
        i = 0
        while i < len(value_string):
            char = value_string[i]
            
            if char in ('"', "'") and (i == 0 or value_string[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current += char
            elif char == ',' and not in_quotes:
                val = current.strip().strip('"').strip("'")
                values.append(val)
                current = ''
            else:
                current += char
            
            i += 1
        
        if current.strip():
            val = current.strip().strip('"').strip("'")
            values.append(val)
        
        return values

    def determine_modality(self, name):
        """Determine imaging modality from name"""
        name_lower = name.lower()
        
        if 'ct' in name_lower or 'computed tomography' in name_lower:
            return 'ct'
        elif 'mri' in name_lower or 'magnetic resonance' in name_lower:
            return 'mri'
        elif 'ultrasound' in name_lower or 'us' in name_lower or 'sono' in name_lower:
            return 'ultrasound'
        elif 'mammography' in name_lower or 'mammo' in name_lower:
            return 'mammography'
        elif 'fluoroscopy' in name_lower:
            return 'fluoroscopy'
        elif 'dexa' in name_lower or 'bone density' in name_lower:
            return 'dexa'
        elif 'nuclear' in name_lower:
            return 'nuclear'
        elif 'pet' in name_lower:
            return 'pet'
        else:
            return 'xray'  # Default

    def extract_body_part(self, name):
        """Extract body part from imaging study name"""
        name_lower = name.lower()
        
        # Common body parts
        body_parts_map = {
            'chest': 'Chest',
            'abdomen': 'Abdomen',
            'abdominal': 'Abdomen',
            'pelvis': 'Pelvis',
            'pelvic': 'Pelvis',
            'skull': 'Skull',
            'head': 'Head',
            'spine': 'Spine',
            'spinal': 'Spine',
            'cervical': 'Cervical Spine',
            'thoracic': 'Thoracic Spine',
            'lumbar': 'Lumbar Spine',
            'limb': 'Limb',
            'upper limb': 'Upper Limb',
            'lower limb': 'Lower Limb',
            'hand': 'Hand',
            'wrist': 'Wrist',
            'elbow': 'Elbow',
            'shoulder': 'Shoulder',
            'foot': 'Foot',
            'ankle': 'Ankle',
            'knee': 'Knee',
            'hip': 'Hip',
            'neck': 'Neck',
            'extremity': 'Extremity',
        }
        
        for keyword, body_part in body_parts_map.items():
            if keyword in name_lower:
                return body_part
        
        return ''

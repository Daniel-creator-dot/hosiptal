"""
Import procedures from procedures.sql and procedure_order_code.sql into ProcedureCatalog
Also imports prices from prices.sql
"""
import os
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

try:
    from hospital.models_advanced import ProcedureCatalog
    HAS_PROCEDURE_CATALOG = True
except ImportError:
    ProcedureCatalog = None
    HAS_PROCEDURE_CATALOG = False


class Command(BaseCommand):
    help = 'Import procedures from SQL files into ProcedureCatalog with prices'

    def add_arguments(self, parser):
        parser.add_argument(
            '--procedures-file',
            type=str,
            default='import/db_3_extracted/procedures.sql',
            help='Path to procedures.sql file'
        )
        parser.add_argument(
            '--procedure-codes-file',
            type=str,
            default='import/db_3_extracted/procedure_order_code.sql',
            help='Path to procedure_order_code.sql file'
        )
        parser.add_argument(
            '--prices-file',
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
        if not HAS_PROCEDURE_CATALOG:
            self.stdout.write(self.style.ERROR('ProcedureCatalog model is not available. Please run migrations first.'))
            return
        
        procedures_file = options['procedures_file']
        procedure_codes_file = options['procedure_codes_file']
        prices_file = options['prices_file']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('\n=== Importing Procedures into ProcedureCatalog ===\n'))
        
        # Step 1: Load procedures from procedures.sql
        self.stdout.write('Step 1: Loading procedures from procedures.sql...')
        procedures_data = self.load_procedures(procedures_file)
        self.stdout.write(self.style.SUCCESS(f'  Loaded {len(procedures_data)} procedures'))
        
        # Step 2: Load procedure codes from procedure_order_code.sql
        self.stdout.write('\nStep 2: Loading procedure codes from procedure_order_code.sql...')
        procedure_codes = self.load_procedure_codes(procedure_codes_file)
        self.stdout.write(self.style.SUCCESS(f'  Loaded {len(procedure_codes)} procedure codes'))
        
        # Step 3: Load prices from prices.sql
        self.stdout.write('\nStep 3: Loading prices from prices.sql...')
        prices = self.load_prices(prices_file)
        self.stdout.write(self.style.SUCCESS(f'  Loaded {len(prices)} price entries'))
        
        # Step 4: Map procedures to categories
        self.stdout.write('\nStep 4: Mapping procedures to categories...')
        mapped_procedures = self.map_procedures_to_catalog(procedures_data, procedure_codes, prices)
        self.stdout.write(self.style.SUCCESS(f'  Mapped {len(mapped_procedures)} procedures'))
        
        # Step 5: Import into ProcedureCatalog
        if not dry_run:
            self.stdout.write('\nStep 5: Importing into ProcedureCatalog...')
            stats = self.import_to_catalog(mapped_procedures)
        else:
            self.stdout.write('\nStep 5: DRY RUN - Would import:')
            stats = self.count_imports(mapped_procedures)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'\nTotal procedures processed: {len(mapped_procedures)}')
        self.stdout.write(f'  Created: {stats["created"]}')
        self.stdout.write(f'  Updated: {stats["updated"]}')
        self.stdout.write(f'  With prices: {stats["with_price"]}')
        self.stdout.write(f'  Without prices: {stats["without_price"]}')
        self.stdout.write(f'  Errors: {stats["errors"]}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('\nImport completed successfully!'))

    def load_procedures(self, file_path):
        """Load procedures from procedures.sql"""
        procedures = []
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.WARNING(f'  File not found: {file_path}'))
            return procedures
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Parse: INSERT INTO procedures VALUES("id","procedure_id","procedure_group_id","procedure_category_id","status");
                match = re.match(r'INSERT INTO procedures VALUES\("([^"]+)","([^"]+)","([^"]+)","([^"]+)","([^"]+)"', line)
                if not match:
                    continue
                
                proc_id = match.group(1).strip()
                proc_name = match.group(2).strip()
                proc_group = match.group(3).strip()
                proc_category = match.group(4).strip()
                status = match.group(5).strip()
                
                if status == '1':  # Only active procedures
                    procedures.append({
                        'id': proc_id,
                        'name': proc_name,
                        'group': proc_group,
                        'category': proc_category,
                    })
        
        return procedures

    def load_procedure_codes(self, file_path):
        """Load procedure codes from procedure_order_code.sql"""
        codes = {}
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.WARNING(f'  File not found: {file_path}'))
            return codes
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Parse: INSERT INTO procedure_order_code VALUES("order_id","seq","procedure_code","procedure_name",...);
                match = re.match(r'INSERT INTO procedure_order_code VALUES\("([^"]+)","[^"]+","([^"]+)","([^"]+)"', line)
                if not match:
                    continue
                
                proc_code = match.group(2).strip()
                proc_name = match.group(3).strip()
                
                # Store unique codes
                if proc_code and proc_code not in codes:
                    codes[proc_code] = proc_name
        
        return codes

    def load_prices(self, file_path):
        """Load prices from prices.sql"""
        prices = {}
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.WARNING(f'  File not found: {file_path}'))
            return prices
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Parse: INSERT INTO prices VALUES("id","selector","level","price");
                match = re.match(r'INSERT INTO prices VALUES\("([^"]+)","([^"]+)","([^"]+)","([^"]+)"', line)
                if not match:
                    continue
                
                pr_id = match.group(1).strip()
                pr_selector = match.group(2).strip()
                pr_level = match.group(3).strip().lower()
                pr_price = match.group(4).strip()
                
                try:
                    price = Decimal(pr_price)
                    if price < 0:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # Store by ID and name, prefer cash prices
                if pr_id not in prices:
                    prices[pr_id] = {}
                if pr_selector not in prices:
                    prices[pr_selector] = {}
                
                if pr_level == 'cash' or 'cash' not in prices[pr_id]:
                    prices[pr_id][pr_level] = price
                    prices[pr_selector][pr_level] = price
        
        return prices

    def map_procedures_to_catalog(self, procedures, procedure_codes, prices):
        """Map procedures to ProcedureCatalog format"""
        mapped = []
        
        # Category mapping from procedure_category_id
        category_map = {
            'OGP': 'major_surgery',  # Obstetrics/Gynecology Procedures
            'GSP': 'minor_surgery',  # General Surgery Procedures
            '0': 'other',
        }
        
        # Group mapping
        group_map = {
            'hpc': 'major_surgery',  # Hospital Procedure Code
        }
        
        for proc in procedures:
            # Determine category
            category = 'other'
            if proc['category'] in category_map:
                category = category_map[proc['category']]
            elif proc['group'] in group_map:
                category = group_map[proc['group']]
            
            # Generate code (PROC + ID padded to 6 digits)
            code = f"PROC{proc['id'].zfill(6)}"
            
            # Find price
            price = Decimal('0.00')
            price_found = False
            
            # Try to find price by procedure name
            proc_name_clean = proc['name'].upper().strip()
            for price_key, price_dict in prices.items():
                if isinstance(price_key, str):
                    price_key_clean = price_key.upper().strip()
                    if proc_name_clean in price_key_clean or price_key_clean in proc_name_clean:
                        if 'cash' in price_dict:
                            price = price_dict['cash']
                            price_found = True
                            break
                        elif 'corp' in price_dict:
                            price = price_dict['corp']
                            price_found = True
                            break
                        elif price_dict:
                            price = list(price_dict.values())[0]
                            price_found = True
                            break
            
            # Try to find price by procedure ID
            if not price_found and proc['id'] in prices:
                price_dict = prices[proc['id']]
                if 'cash' in price_dict:
                    price = price_dict['cash']
                    price_found = True
                elif 'corp' in price_dict:
                    price = price_dict['corp']
                    price_found = True
                elif price_dict:
                    price = list(price_dict.values())[0]
                    price_found = True
            
            # Determine if requires anesthesia or theatre
            requires_anesthesia = 'anaesthesia' in proc['name'].lower() or 'anaesthetic' in proc['name'].lower()
            requires_theatre = category in ['major_surgery', 'minor_surgery']
            
            # Estimate duration (default 30 minutes, longer for major surgery)
            duration = 60 if category == 'major_surgery' else 30
            
            mapped.append({
                'code': code,
                'name': proc['name'],
                'category': category,
                'description': f"Procedure: {proc['name']}",
                'price': price,
                'estimated_duration_minutes': duration,
                'requires_anesthesia': requires_anesthesia,
                'requires_theatre': requires_theatre,
                'is_active': True,
                'has_price': price_found,
            })
        
        return mapped

    @transaction.atomic
    def import_to_catalog(self, mapped_procedures):
        """Import procedures into ProcedureCatalog"""
        stats = {
            'created': 0,
            'updated': 0,
            'with_price': 0,
            'without_price': 0,
            'errors': 0,
        }
        
        for proc_data in mapped_procedures:
            try:
                procedure, created = ProcedureCatalog.objects.update_or_create(
                    code=proc_data['code'],
                    defaults={
                        'name': proc_data['name'],
                        'category': proc_data['category'],
                        'description': proc_data['description'],
                        'price': proc_data['price'],
                        'estimated_duration_minutes': proc_data['estimated_duration_minutes'],
                        'requires_anesthesia': proc_data['requires_anesthesia'],
                        'requires_theatre': proc_data['requires_theatre'],
                        'is_active': proc_data['is_active'],
                        'is_deleted': False,
                    }
                )
                
                if created:
                    stats['created'] += 1
                    if stats['created'] % 50 == 0:
                        self.stdout.write(f'  Created {stats["created"]} procedures...')
                else:
                    stats['updated'] += 1
                
                if proc_data['has_price']:
                    stats['with_price'] += 1
                else:
                    stats['without_price'] += 1
                    
            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(self.style.ERROR(f'  Error importing {proc_data["code"]}: {e}'))
        
        return stats

    def count_imports(self, mapped_procedures):
        """Count what would be imported (dry run)"""
        stats = {
            'created': 0,
            'updated': 0,
            'with_price': 0,
            'without_price': 0,
            'errors': 0,
        }
        
        existing_codes = set(
            ProcedureCatalog.objects.filter(is_deleted=False).values_list('code', flat=True)
        )
        
        for proc_data in mapped_procedures:
            if proc_data['code'] in existing_codes:
                stats['updated'] += 1
            else:
                stats['created'] += 1
            
            if proc_data['has_price']:
                stats['with_price'] += 1
            else:
                stats['without_price'] += 1
        
        return stats

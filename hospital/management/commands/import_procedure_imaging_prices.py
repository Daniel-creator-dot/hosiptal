"""
Import prices for ProcedureCatalog and ImagingCatalog from prices.sql
Matches prices by code and updates the catalog items
"""
import os
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from hospital.models_advanced import ProcedureCatalog, ImagingCatalog


class Command(BaseCommand):
    help = 'Import prices for ProcedureCatalog and ImagingCatalog from prices.sql'

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
            self.stdout.write(self.style.WARNING('Looking for prices.sql in common locations...'))
            # Try alternative locations
            alt_paths = [
                'import/prices.sql',
                'import/db_3/prices.sql',
                'prices.sql',
            ]
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    file_path = alt_path
                    self.stdout.write(self.style.SUCCESS(f'Found: {file_path}'))
                    break
            else:
                self.stdout.write(self.style.ERROR('Please specify the correct path with --file'))
                return
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Importing Prices from {file_path} ===\n'))
        
        # Extract prices from file
        prices = self.extract_prices(file_path)
        self.stdout.write(f'Found {len(prices)} unique service price entries\n')
        
        # Get all catalog items
        procedures = ProcedureCatalog.objects.filter(is_deleted=False)
        imaging_items = ImagingCatalog.objects.filter(is_deleted=False)
        
        self.stdout.write(f'ProcedureCatalog items: {procedures.count()}')
        self.stdout.write(f'ImagingCatalog items: {imaging_items.count()}\n')
        
        stats = {
            'procedures_updated': 0,
            'procedures_no_price': 0,
            'imaging_updated': 0,
            'imaging_no_price': 0,
        }
        
        if not dry_run:
            with transaction.atomic():
                # Update ProcedureCatalog prices
                self.stdout.write('Updating ProcedureCatalog prices...')
                for procedure in procedures:
                    price = self.find_price(procedure.code, procedure.name, prices)
                    if price and price > 0:
                        procedure.price = price
                        procedure.save(update_fields=['price'])
                        stats['procedures_updated'] += 1
                        if stats['procedures_updated'] % 10 == 0:
                            self.stdout.write(f'  Updated {stats["procedures_updated"]} procedures...')
                    else:
                        stats['procedures_no_price'] += 1
                
                # Update ImagingCatalog prices
                self.stdout.write('\nUpdating ImagingCatalog prices...')
                for imaging in imaging_items:
                    price = self.find_price(imaging.code, imaging.name, prices)
                    if price and price > 0:
                        imaging.price = price
                        imaging.save(update_fields=['price'])
                        stats['imaging_updated'] += 1
                        if stats['imaging_updated'] % 10 == 0:
                            self.stdout.write(f'  Updated {stats["imaging_updated"]} imaging items...')
                    else:
                        stats['imaging_no_price'] += 1
        else:
            # Dry run - just count
            self.stdout.write('DRY RUN - Counting matches...')
            for procedure in procedures:
                price = self.find_price(procedure.code, procedure.name, prices)
                if price and price > 0:
                    stats['procedures_updated'] += 1
                else:
                    stats['procedures_no_price'] += 1
            
            for imaging in imaging_items:
                price = self.find_price(imaging.code, imaging.name, prices)
                if price and price > 0:
                    stats['imaging_updated'] += 1
                else:
                    stats['imaging_no_price'] += 1
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'\nProcedures:')
        self.stdout.write(f'  Updated with prices: {stats["procedures_updated"]}')
        self.stdout.write(f'  No price found: {stats["procedures_no_price"]}')
        self.stdout.write(f'\nImaging:')
        self.stdout.write(f'  Updated with prices: {stats["imaging_updated"]}')
        self.stdout.write(f'  No price found: {stats["imaging_no_price"]}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('\nImport completed successfully!'))

    def extract_prices(self, file_path):
        """
        Extract prices from prices.sql file
        Returns: dict {code: {cash: price, corp: price, ins: price}}
        """
        prices = {}
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line_num, line in enumerate(f, 1):
                if line_num % 10000 == 0:
                    self.stdout.write(f'Reading line {line_num}...')
                
                # Parse INSERT statement: INSERT INTO prices VALUES("id","selector","level","price");
                match = re.match(r'INSERT INTO prices VALUES\("([^"]+)","([^"]+)","([^"]+)","([^"]+)"', line)
                if not match:
                    continue
                
                pr_id = match.group(1).strip()
                pr_selector = match.group(2).strip()  # Service name/description
                pr_level = match.group(3).strip().lower()  # cash, corp, ins, etc.
                pr_price = match.group(4).strip()
                
                try:
                    price = Decimal(pr_price)
                    if price < 0:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # Store by code (pr_id) - prefer cash prices
                if pr_id not in prices:
                    prices[pr_id] = {}
                
                # Store by name (pr_selector) as backup
                if pr_selector not in prices:
                    prices[pr_selector] = {}
                
                # Store price by level (prefer cash)
                if pr_level == 'cash' or 'cash' not in prices[pr_id]:
                    prices[pr_id][pr_level] = price
                    prices[pr_selector][pr_level] = price
        
        return prices

    def find_price(self, code, name, prices):
        """
        Find price for a catalog item
        Tries: exact code match, exact name match, partial name match
        Prefers: cash > corp > ins > any
        """
        # Try exact code match first
        if code in prices:
            price_dict = prices[code]
            if 'cash' in price_dict:
                return price_dict['cash']
            elif 'corp' in price_dict:
                return price_dict['corp']
            elif 'ins' in price_dict:
                return price_dict['ins']
            elif price_dict:
                return list(price_dict.values())[0]
        
        # Try exact name match
        if name in prices:
            price_dict = prices[name]
            if 'cash' in price_dict:
                return price_dict['cash']
            elif 'corp' in price_dict:
                return price_dict['corp']
            elif 'ins' in price_dict:
                return price_dict['ins']
            elif price_dict:
                return list(price_dict.values())[0]
        
        # Try partial name match (case-insensitive)
        name_clean = name.lower().strip()
        for price_key, price_dict in prices.items():
            if isinstance(price_key, str):
                price_key_clean = price_key.lower().strip()
                # Check if name contains price_key or vice versa
                if (name_clean in price_key_clean or price_key_clean in name_clean) and len(price_key_clean) > 3:
                    if 'cash' in price_dict:
                        return price_dict['cash']
                    elif 'corp' in price_dict:
                        return price_dict['corp']
                    elif 'ins' in price_dict:
                        return price_dict['ins']
                    elif price_dict:
                        return list(price_dict.values())[0]
        
        return None

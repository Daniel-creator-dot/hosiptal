"""
Import procedure prices from prices.sql with support for cash, corporate, and insurance pricing
Updates ProcedureCatalog with multi-tier pricing (cash_price, corporate_price, insurance_price)
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
    help = 'Import procedure prices from prices.sql with cash, corporate, and insurance pricing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prices-file',
            type=str,
            default='import/db_3_extracted/prices.sql',
            help='Path to prices.sql file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating'
        )
        parser.add_argument(
            '--min-price',
            type=Decimal,
            default=Decimal('0.50'),
            help='Minimum acceptable price (default: 0.50)'
        )
        parser.add_argument(
            '--max-price',
            type=Decimal,
            default=Decimal('100000.00'),
            help='Maximum acceptable price (default: 100000.00)'
        )

    def handle(self, *args, **options):
        if not HAS_PROCEDURE_CATALOG:
            self.stdout.write(self.style.ERROR('ProcedureCatalog model is not available. Please run migrations first.'))
            return
        
        prices_file = options['prices_file']
        dry_run = options['dry_run']
        min_price = options['min_price']
        max_price = options['max_price']
        
        self.stdout.write(self.style.SUCCESS('\n=== Importing Procedure Prices (Multi-Tier) ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        # Step 1: Load all prices from prices.sql
        self.stdout.write('Step 1: Loading prices from prices.sql...')
        prices_data = self.load_prices(prices_file, min_price, max_price)
        self.stdout.write(self.style.SUCCESS(f'  Loaded {len(prices_data)} price entries'))
        
        # Step 2: Group prices by procedure code/name
        self.stdout.write('\nStep 2: Grouping prices by procedure...')
        grouped_prices = self.group_prices_by_procedure(prices_data)
        self.stdout.write(self.style.SUCCESS(f'  Found prices for {len(grouped_prices)} unique procedures'))
        
        # Step 3: Match prices to ProcedureCatalog items
        self.stdout.write('\nStep 3: Matching prices to ProcedureCatalog items...')
        matches = self.match_prices_to_procedures(grouped_prices)
        self.stdout.write(self.style.SUCCESS(f'  Matched {len(matches)} procedures'))
        
        # Step 4: Update ProcedureCatalog with prices
        if not dry_run:
            self.stdout.write('\nStep 4: Updating ProcedureCatalog with prices...')
            stats = self.update_procedures(matches)
        else:
            self.stdout.write('\nStep 4: DRY RUN - Would update:')
            stats = self.count_updates(matches)
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'\nTotal price entries loaded: {len(prices_data)}')
        self.stdout.write(f'Unique procedures with prices: {len(grouped_prices)}')
        self.stdout.write(f'\nProcedures matched: {len(matches)}')
        self.stdout.write(f'  Updated: {stats["updated"]}')
        self.stdout.write(f'  With cash price: {stats["with_cash"]}')
        self.stdout.write(f'  With corporate price: {stats["with_corp"]}')
        self.stdout.write(f'  With insurance price: {stats["with_ins"]}')
        self.stdout.write(f'  With all three prices: {stats["with_all"]}')
        self.stdout.write(f'  Errors: {stats["errors"]}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('\nImport completed successfully!'))

    def load_prices(self, file_path, min_price, max_price):
        """
        Load all prices from prices.sql file
        Returns: list of dicts with pr_id, pr_selector, pr_level, pr_price
        """
        prices = []
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.WARNING(f'  File not found: {file_path}'))
            return prices
        
        self.stdout.write(f'  Reading {file_path}...')
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            line_count = 0
            for line_num, line in enumerate(f, 1):
                if line_num % 50000 == 0:
                    self.stdout.write(f'  Processed {line_num} lines...')
                
                # Parse: INSERT INTO prices VALUES("id","selector","level","price",...);
                # Handle both formats: with and without timestamp
                match = re.match(
                    r'INSERT INTO prices VALUES\("([^"]+)","([^"]+)","([^"]+)","([^"]+)"',
                    line
                )
                if not match:
                    continue
                
                pr_id = match.group(1).strip()
                pr_selector = match.group(2).strip()  # Service name/description
                pr_level = match.group(3).strip().lower()  # cash, corp, ins, nhis, etc.
                pr_price_str = match.group(4).strip()
                
                try:
                    price = Decimal(pr_price_str)
                    # Filter out invalid prices
                    if price < min_price or price > max_price:
                        continue
                except (ValueError, TypeError, Exception):
                    continue
                
                # Only process cash, corp, ins (normalize other insurance types to 'ins')
                normalized_level = self.normalize_price_level(pr_level)
                if not normalized_level:
                    continue
                
                prices.append({
                    'id': pr_id,
                    'selector': pr_selector,
                    'level': normalized_level,
                    'price': price,
                })
                line_count += 1
        
        return prices

    def normalize_price_level(self, level):
        """
        Normalize price level to cash, corp, or ins
        Returns: 'cash', 'corp', 'ins', or None
        """
        level = level.lower().strip()
        
        # Cash variants
        if level == 'cash':
            return 'cash'
        
        # Corporate variants
        if level in ['corp', 'corporate', 'company']:
            return 'corp'
        
        # Insurance variants
        if level in ['ins', 'insurance', 'nhis', 'nongh', 'gab', 'glico', 'cosmo', 'private']:
            return 'ins'
        
        return None

    def group_prices_by_procedure(self, prices_data):
        """
        Group prices by procedure code and name
        Returns: dict {key: {cash: price, corp: price, ins: price}}
        """
        grouped = {}
        
        for price_entry in prices_data:
            # Create keys for both ID and name matching
            keys = [
                price_entry['id'],  # By ID
                price_entry['selector'],  # By name
            ]
            
            for key in keys:
                if not key or key.strip() == '':
                    continue
                
                key = key.strip()
                if key not in grouped:
                    grouped[key] = {
                        'cash': None,
                        'corp': None,
                        'ins': None,
                    }
                
                # Store the highest price if multiple entries exist for same level
                level = price_entry['level']
                current_price = grouped[key][level]
                if current_price is None or price_entry['price'] > current_price:
                    grouped[key][level] = price_entry['price']
        
        return grouped

    def match_prices_to_procedures(self, grouped_prices):
        """
        Match grouped prices to ProcedureCatalog items
        Returns: list of dicts with procedure and prices
        """
        matches = []
        
        # Get all procedures
        procedures = ProcedureCatalog.objects.filter(is_deleted=False, is_active=True)
        total_procedures = procedures.count()
        self.stdout.write(f'  Checking {total_procedures} procedures...')
        
        # Create normalized lookup for faster matching
        normalized_lookup = {}
        for price_key, prices in grouped_prices.items():
            if isinstance(price_key, str):
                normalized = self.normalize_name(price_key)
                if normalized not in normalized_lookup:
                    normalized_lookup[normalized] = []
                normalized_lookup[normalized].append((price_key, prices))
        
        matched_count = 0
        for proc in procedures:
            cash_price = None
            corp_price = None
            ins_price = None
            matched = False
            best_match = None
            best_score = 0
            
            # Try matching by code first (extract numeric ID from code)
            # Examples: "PROC000001" -> "1", "DS0016" -> "16", "DXRAY0001" -> "1"
            code_numeric = None
            code_variants = [
                proc.code,  # Full code first
                proc.code.replace('PROC', '').strip(),
                proc.code.replace('DS', '').strip(),
                proc.code.replace('DXRAY', '').strip(),
            ]
            
            # Extract numeric part from code
            import re as re_module
            numeric_match = re_module.search(r'(\d+)', proc.code)
            if numeric_match:
                code_numeric = str(int(numeric_match.group(1)))  # Remove leading zeros
                code_variants.append(code_numeric)
            
            for code_variant in code_variants:
                if code_variant and code_variant in grouped_prices:
                    prices = grouped_prices[code_variant]
                    cash_price = prices['cash']
                    corp_price = prices['corp']
                    ins_price = prices['ins']
                    matched = True
                    break
            
            # Try matching by procedure name (multiple strategies)
            if not matched:
                proc_name_normalized = self.normalize_name(proc.name)
                
                # Strategy 1: Exact name match
                if proc.name in grouped_prices:
                    prices = grouped_prices[proc.name]
                    cash_price = prices['cash']
                    corp_price = prices['corp']
                    ins_price = prices['ins']
                    matched = True
                # Strategy 2: Normalized name match
                elif proc_name_normalized in normalized_lookup:
                    # Take the first match (could improve with scoring)
                    price_key, prices = normalized_lookup[proc_name_normalized][0]
                    cash_price = prices['cash']
                    corp_price = prices['corp']
                    ins_price = prices['ins']
                    matched = True
                else:
                    # Strategy 3: Fuzzy matching - find best match
                    for price_key, prices in grouped_prices.items():
                        if isinstance(price_key, str) and len(price_key) > 3:
                            price_key_normalized = self.normalize_name(price_key)
                            
                            # Calculate similarity score
                            score = self.calculate_similarity(proc_name_normalized, price_key_normalized)
                            
                            if score > best_score and score >= 0.6:  # 60% similarity threshold
                                best_score = score
                                best_match = (prices, score)
                    
                    if best_match:
                        prices, score = best_match
                        cash_price = prices['cash']
                        corp_price = prices['corp']
                        ins_price = prices['ins']
                        matched = True
            
            if matched and (cash_price or corp_price or ins_price):
                matches.append({
                    'procedure': proc,
                    'cash_price': cash_price,
                    'corporate_price': corp_price,
                    'insurance_price': ins_price,
                })
                matched_count += 1
                
                if matched_count % 100 == 0:
                    self.stdout.write(f'  Matched {matched_count} procedures...')
        
        return matches
    
    def normalize_name(self, name):
        """
        Normalize a name for comparison (remove common words, lowercase, strip)
        """
        if not name:
            return ''
        
        # Common words to remove
        stop_words = {'the', 'a', 'an', 'and', 'or', 'of', 'for', 'in', 'on', 'at', 'to', 'from', 'with', 'by'}
        
        # Clean and split
        normalized = name.upper().strip()
        
        # Remove common prefixes/suffixes
        normalized = normalized.replace('DENTAL', '').replace('DENT', '').strip()
        normalized = normalized.replace('PROCEDURE', '').strip()
        normalized = normalized.replace('RCT', 'ROOT CANAL TREATMENT')
        
        # Split into words and remove stop words
        words = [w for w in normalized.split() if w not in stop_words and len(w) > 1]
        
        return ' '.join(words)
    
    def calculate_similarity(self, name1, name2):
        """
        Calculate similarity score between two normalized names (0.0 to 1.0)
        """
        if not name1 or not name2:
            return 0.0
        
        # Exact match
        if name1 == name2:
            return 1.0
        
        # Substring match
        if name1 in name2 or name2 in name1:
            return 0.8
        
        # Word-based similarity
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return 0.0
        
        jaccard_similarity = len(intersection) / len(union)
        return jaccard_similarity

    def similar_names(self, name1, name2):
        """
        Check if two names are similar (at least 70% words match)
        """
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        if not words1 or not words2:
            return False
        
        # Remove very short words
        words1 = {w for w in words1 if len(w) > 2}
        words2 = {w for w in words2 if len(w) > 2}
        
        if not words1 or not words2:
            return False
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        similarity = len(intersection) / len(union) if union else 0
        return similarity >= 0.5  # 50% similarity threshold

    @transaction.atomic
    def update_procedures(self, matches):
        """Update ProcedureCatalog with prices"""
        stats = {
            'updated': 0,
            'with_cash': 0,
            'with_corp': 0,
            'with_ins': 0,
            'with_all': 0,
            'errors': 0,
        }
        
        for match in matches:
            try:
                proc = match['procedure']
                
                # Update prices
                update_dict = {}
                if match['cash_price']:
                    update_dict['cash_price'] = match['cash_price']
                    # Also update base price if it's zero or much lower than cash price
                    if not proc.price or proc.price < match['cash_price'] * Decimal('0.5'):
                        update_dict['price'] = match['cash_price']
                    stats['with_cash'] += 1
                
                if match['corporate_price']:
                    update_dict['corporate_price'] = match['corporate_price']
                    stats['with_corp'] += 1
                
                if match['insurance_price']:
                    update_dict['insurance_price'] = match['insurance_price']
                    stats['with_ins'] += 1
                
                if match['cash_price'] and match['corporate_price'] and match['insurance_price']:
                    stats['with_all'] += 1
                
                if update_dict:
                    ProcedureCatalog.objects.filter(id=proc.id).update(**update_dict)
                    stats['updated'] += 1
                    
                    if stats['updated'] % 50 == 0:
                        self.stdout.write(f'  Updated {stats["updated"]} procedures...')
                    
            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(self.style.ERROR(f'  Error updating {match["procedure"].code}: {e}'))
        
        return stats

    def count_updates(self, matches):
        """Count what would be updated (dry run)"""
        stats = {
            'updated': 0,
            'with_cash': 0,
            'with_corp': 0,
            'with_ins': 0,
            'with_all': 0,
            'errors': 0,
        }
        
        for match in matches:
            if match['cash_price']:
                stats['with_cash'] += 1
            if match['corporate_price']:
                stats['with_corp'] += 1
            if match['insurance_price']:
                stats['with_ins'] += 1
            if match['cash_price'] and match['corporate_price'] and match['insurance_price']:
                stats['with_all'] += 1
            stats['updated'] += 1
        
        return stats

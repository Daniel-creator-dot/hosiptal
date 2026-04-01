"""
Management command to check and fix incorrect procedure prices
Identifies procedures with suspicious prices and allows fixing them
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

try:
    from hospital.models_advanced import ProcedureCatalog
    HAS_PROCEDURE_CATALOG = True
except ImportError:
    ProcedureCatalog = None
    HAS_PROCEDURE_CATALOG = False


class Command(BaseCommand):
    help = 'Check and fix incorrect procedure prices in ProcedureCatalog'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Actually fix the prices (otherwise just report)'
        )
        parser.add_argument(
            '--min-price',
            type=float,
            default=5.0,
            help='Minimum reasonable price in GHS (default: 5.0)'
        )
        parser.add_argument(
            '--max-price',
            type=float,
            default=50000.0,
            help='Maximum reasonable price in GHS (default: 50000.0)'
        )
        parser.add_argument(
            '--zero-price',
            action='store_true',
            help='Also flag procedures with zero price'
        )

    def handle(self, *args, **options):
        if not HAS_PROCEDURE_CATALOG:
            self.stdout.write(self.style.ERROR('ProcedureCatalog model is not available.'))
            return
        
        fix_mode = options['fix']
        min_price = Decimal(str(options['min_price']))
        max_price = Decimal(str(options['max_price']))
        flag_zero = options['zero_price']
        
        self.stdout.write(self.style.SUCCESS('\n=== Checking Procedure Prices ===\n'))
        
        procedures = ProcedureCatalog.objects.filter(is_deleted=False).order_by('category', 'name')
        total = procedures.count()
        
        self.stdout.write(f'Total procedures: {total}\n')
        
        issues = {
            'zero_price': [],
            'too_low': [],
            'too_high': [],
            'suspicious': [],
        }
        
        # Category-based price expectations (in GHS)
        # Updated with more realistic minimums for Ghana healthcare
        category_expectations = {
            'minor_surgery': (50, 5000),
            'major_surgery': (300, 50000),  # Lowered minimum from 500 to 300 for some minor procedures
            'dental': (20, 5000),
            'ophthalmic': (100, 10000),
            'endoscopy': (200, 10000),
            'biopsy': (100, 3000),
            'injection': (5, 500),  # Some injections can be cheap
            'wound_care': (20, 1000),
            'catheterization': (50, 2000),
            'other': (10, 10000),
        }
        
        # Procedure name-based price adjustments (for procedures that might be incorrectly categorized)
        procedure_name_adjustments = {
            # Minor procedures that might be categorized as major_surgery
            'biopsy': ('biopsy', 100, 3000),
            'd&c': ('minor_surgery', 200, 2000),
            'diagnostic d': ('minor_surgery', 150, 1500),
            'cryo': ('minor_surgery', 100, 1000),
            'cerclage': ('minor_surgery', 300, 3000),
            'episiotomy': ('minor_surgery', 50, 500),
            'delivery': ('major_surgery', 200, 2000),
            'injection': ('injection', 5, 500),
            'iv': ('injection', 10, 300),
            'im': ('injection', 10, 300),
        }
        
        # Check each procedure
        for procedure in procedures:
            price = procedure.price
            category = procedure.category
            
            # Check for zero price
            if price == 0 or price is None:
                if flag_zero or fix_mode:
                    issues['zero_price'].append(procedure)
                continue
            
            # Check absolute min/max
            if price < min_price:
                issues['too_low'].append(procedure)
            elif price > max_price:
                issues['too_high'].append(procedure)
            
            # Check if procedure name suggests different category
            name_lower = procedure.name.lower()
            adjusted_category = category
            cat_min, cat_max = None, None
            
            for keyword, (suggested_cat, suggested_min, suggested_max) in procedure_name_adjustments.items():
                if keyword in name_lower:
                    adjusted_category = suggested_cat
                    cat_min = Decimal(str(suggested_min))
                    cat_max = Decimal(str(suggested_max))
                    break
            
            # Use category expectations if no adjustment found
            if cat_min is None and category in category_expectations:
                cat_min, cat_max = category_expectations[category]
                cat_min = Decimal(str(cat_min))
                cat_max = Decimal(str(cat_max))
            
            # Check expectations if we have them
            if cat_min is not None:
                if price < cat_min:
                    # Only flag if significantly lower (less than 50% of expected min)
                    if price < (cat_min * Decimal('0.5')):
                        issues['suspicious'].append({
                            'procedure': procedure,
                            'issue': f'Price {price} seems too low for {category} (expected min: {cat_min})',
                            'category': category,
                            'adjusted_category': adjusted_category,
                            'current_price': price,
                            'expected_min': cat_min,
                            'suggested_price': cat_min,
                        })
                elif price > cat_max:
                    issues['suspicious'].append({
                        'procedure': procedure,
                        'issue': f'Price {price} seems too high for {category} (expected max: {cat_max})',
                        'category': category,
                        'current_price': price,
                        'expected_max': cat_max,
                    })
        
        # Report issues
        self.stdout.write(self.style.WARNING('\n=== ISSUES FOUND ===\n'))
        
        if issues['zero_price']:
            self.stdout.write(self.style.ERROR(f"\n❌ Zero Price ({len(issues['zero_price'])} procedures):"))
            for proc in issues['zero_price'][:20]:  # Show first 20
                self.stdout.write(f"  - {proc.code}: {proc.name} - GHS {proc.price}")
            if len(issues['zero_price']) > 20:
                self.stdout.write(f"  ... and {len(issues['zero_price']) - 20} more")
        
        if issues['too_low']:
            self.stdout.write(self.style.WARNING(f"\n⚠️ Too Low (< {min_price}) ({len(issues['too_low'])} procedures):"))
            for proc in issues['too_low'][:20]:
                self.stdout.write(f"  - {proc.code}: {proc.name} - GHS {proc.price}")
            if len(issues['too_low']) > 20:
                self.stdout.write(f"  ... and {len(issues['too_low']) - 20} more")
        
        if issues['too_high']:
            self.stdout.write(self.style.WARNING(f"\n⚠️ Too High (> {max_price}) ({len(issues['too_high'])} procedures):"))
            for proc in issues['too_high'][:20]:
                self.stdout.write(f"  - {proc.code}: {proc.name} - GHS {proc.price}")
            if len(issues['too_high']) > 20:
                self.stdout.write(f"  ... and {len(issues['too_high']) - 20} more")
        
        if issues['suspicious']:
            self.stdout.write(self.style.WARNING(f"\n⚠️ Suspicious Prices ({len(issues['suspicious'])} procedures):"))
            for item in issues['suspicious'][:30]:
                proc = item['procedure']
                self.stdout.write(f"  - {proc.code}: {proc.name} ({item['category']}) - GHS {item['current_price']}")
                self.stdout.write(f"    Issue: {item['issue']}")
            if len(issues['suspicious']) > 30:
                self.stdout.write(f"  ... and {len(issues['suspicious']) - 30} more")
        
        # Summary
        total_issues = (
            len(issues['zero_price']) +
            len(issues['too_low']) +
            len(issues['too_high']) +
            len(issues['suspicious'])
        )
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'\nTotal procedures checked: {total}')
        self.stdout.write(f'Zero price: {len(issues["zero_price"])}')
        self.stdout.write(f'Too low (< {min_price}): {len(issues["too_low"])}')
        self.stdout.write(f'Too high (> {max_price}): {len(issues["too_high"])}')
        self.stdout.write(f'Suspicious prices: {len(issues["suspicious"])}')
        self.stdout.write(f'\nTotal issues: {total_issues}')
        
        # Fix mode
        if fix_mode:
            self.stdout.write(self.style.WARNING('\n=== FIXING PRICES ===\n'))
            
            fixed_count = 0
            skipped_count = 0
            
            with transaction.atomic():
                # Fix zero prices - set to category minimum or default
                for proc in issues['zero_price']:
                    # Check for name-based adjustment
                    name_lower = proc.name.lower()
                    suggested_price = None
                    for keyword, (suggested_cat, suggested_min, suggested_max) in procedure_name_adjustments.items():
                        if keyword in name_lower:
                            suggested_price = Decimal(str(suggested_min))
                            break
                    
                    if suggested_price:
                        new_price = suggested_price
                    elif proc.category in category_expectations:
                        cat_min, _ = category_expectations[proc.category]
                        new_price = Decimal(str(cat_min))
                    else:
                        new_price = min_price
                    
                    proc.price = new_price
                    proc.save(update_fields=['price'])
                    self.stdout.write(self.style.SUCCESS(f'Fixed: {proc.code} - {proc.name}: GHS {proc.price} (was 0)'))
                    fixed_count += 1
                
                # Fix too low prices - set to category minimum or suggested price
                for proc in issues['too_low']:
                    # Check for name-based adjustment first
                    name_lower = proc.name.lower()
                    suggested_price = None
                    for keyword, (suggested_cat, suggested_min, suggested_max) in procedure_name_adjustments.items():
                        if keyword in name_lower:
                            suggested_price = Decimal(str(suggested_min))
                            break
                    
                    if suggested_price and suggested_price > proc.price:
                        old_price = proc.price
                        proc.price = suggested_price
                        proc.save(update_fields=['price'])
                        self.stdout.write(self.style.SUCCESS(f'Fixed: {proc.code} - {proc.name}: GHS {old_price} → GHS {suggested_price}'))
                        fixed_count += 1
                    elif proc.category in category_expectations:
                        cat_min, _ = category_expectations[proc.category]
                        new_price = Decimal(str(cat_min))
                        if new_price > proc.price:
                            old_price = proc.price
                            proc.price = new_price
                            proc.save(update_fields=['price'])
                            self.stdout.write(self.style.SUCCESS(f'Fixed: {proc.code} - {proc.name}: GHS {old_price} → GHS {new_price}'))
                            fixed_count += 1
                        else:
                            skipped_count += 1
                    else:
                        if min_price > proc.price:
                            old_price = proc.price
                            proc.price = min_price
                            proc.save(update_fields=['price'])
                            self.stdout.write(self.style.SUCCESS(f'Fixed: {proc.code} - {proc.name}: GHS {old_price} → GHS {min_price}'))
                            fixed_count += 1
                        else:
                            skipped_count += 1
                
                # Fix suspicious prices (those significantly below expected minimum)
                for item in issues['suspicious']:
                    proc = item['procedure']
                    if 'suggested_price' in item and item['suggested_price'] > proc.price:
                        old_price = proc.price
                        proc.price = item['suggested_price']
                        proc.save(update_fields=['price'])
                        self.stdout.write(self.style.SUCCESS(f'Fixed: {proc.code} - {proc.name}: GHS {old_price} → GHS {item["suggested_price"]}'))
                        fixed_count += 1
                
                # For too high prices, we'll just flag them (don't auto-fix as they might be correct)
                if issues['too_high']:
                    self.stdout.write(self.style.WARNING(f'\n⚠️ Skipped {len(issues["too_high"])} procedures with very high prices (manual review recommended)'))
                    skipped_count += len(issues['too_high'])
            
            self.stdout.write(self.style.SUCCESS(f'\n✅ Fixed {fixed_count} procedures'))
            if skipped_count > 0:
                self.stdout.write(self.style.WARNING(f'⚠️ Skipped {skipped_count} procedures (may need manual review)'))
        else:
            self.stdout.write(self.style.WARNING('\n⚠️ DRY RUN - No changes made'))
            self.stdout.write(self.style.WARNING('Use --fix to actually fix the prices'))
        
        self.stdout.write('')

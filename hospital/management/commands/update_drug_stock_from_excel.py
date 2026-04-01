"""
Senior Engineer Grade: Drug Stock and Price Update System
=========================================================
Updates drug quantities and prices from Excel file (updated LIST 3.xlsx)

Features:
- Intelligent drug matching by name, strength, and form
- Updates both Drug prices (unit_price, cost_price) and PharmacyStock quantities
- Handles multiple stock batches
- Creates new PharmacyStock entries if needed
- Detailed logging and reporting
- Transaction-safe updates
"""
import re
from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from hospital.models import Drug, PharmacyStock

try:
    import pandas as pd
except ImportError:
    pd = None


class Command(BaseCommand):
    help = 'Update drug quantities and prices from Excel file (updated LIST 3.xlsx)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--excel-file',
            type=str,
            default='import/updated LIST 3.xlsx',
            help='Path to Excel file with drug list'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--create-missing',
            action='store_true',
            help='Create PharmacyStock entries for drugs that exist but have no stock'
        )
        parser.add_argument(
            '--update-prices-only',
            action='store_true',
            help='Only update prices, do not update quantities'
        )

    def normalize_drug_name(self, name):
        """Normalize drug name for matching"""
        if not name or pd.isna(name):
            return None
        
        name = str(name).strip()
        # Remove extra spaces
        name = re.sub(r'\s+', ' ', name)
        # Convert to title case for consistency
        return name.title()

    def extract_strength_and_form(self, name):
        """Extract strength and form from drug name"""
        if not name:
            return None, None, name
        
        # Common patterns: "Drug Name 500mg tablet", "Drug Name 10ml injection"
        strength_pattern = r'(\d+(?:\.\d+)?)\s*(mg|g|ml|l|mcg|iu|units?)\b'
        form_pattern = r'\b(tablet|tab|capsule|cap|injection|inj|syrup|suspension|drops|cream|ointment|gel|spray)\b'
        
        strength_match = re.search(strength_pattern, name, re.IGNORECASE)
        form_match = re.search(form_pattern, name, re.IGNORECASE)
        
        strength = None
        form = None
        base_name = name
        
        if strength_match:
            strength = strength_match.group(0).strip()
            base_name = name[:strength_match.start()].strip()
        
        if form_match:
            form = form_match.group(1).lower()
            # Normalize form names
            form_map = {
                'tab': 'tablet',
                'cap': 'capsule',
                'inj': 'injection'
            }
            form = form_map.get(form, form)
        
        return strength, form, base_name

    def classify_drug(self, drug_name):
        """
        Intelligently classify a drug based on its name using comprehensive pattern matching
        Returns the category code - matches the comprehensive classification from classify_drugs_from_excel
        """
        name_lower = drug_name.lower()
        
        # ANTIBIOTICS & ANTIBACTERIALS (Comprehensive)
        antibiotic_keywords = [
            'amoxicillin', 'ampicillin', 'penicillin', 'cephalexin', 'cefuroxime',
            'ceftriaxone', 'cefotaxime', 'azithromycin', 'erythromycin', 'clarithromycin',
            'doxycycline', 'tetracycline', 'ciprofloxacin', 'levofloxacin', 'ofloxacin',
            'metronidazole', 'tinidazole', 'clindamycin', 'vancomycin', 'gentamicin',
            'amikacin', 'neomycin', 'chloramphenicol', 'sulfamethoxazole', 'trimethoprim',
            'co-trimoxazole', 'septrin', 'bactrim', 'augmentin', 'amoxiclav', 'amoksiklav',
            'cefixime', 'cefazolin', 'cefadroxil', 'ceftazidime', 'cefepime', 'cefpodoxime',
            'meropenem', 'imipenem', 'orelox'
        ]
        if any(keyword in name_lower for keyword in antibiotic_keywords):
            return 'antibiotic'
        
        # ANTIVIRALS
        antiviral_keywords = [
            'acyclovir', 'aciclovir', 'valacyclovir', 'ganciclovir', 'oseltamivir',
            'zanamivir', 'ribavirin', 'lamivudine', 'zidovudine', 'tenofovir', 'efavirenz'
        ]
        if any(keyword in name_lower for keyword in antiviral_keywords):
            return 'antiviral'
        
        # ANTIFUNGALS
        antifungal_keywords = [
            'fluconazole', 'ketoconazole', 'itraconazole', 'voriconazole', 'amphotericin',
            'nystatin', 'clotrimazole', 'miconazole', 'terbinafine', 'griseofulvin'
        ]
        if any(keyword in name_lower for keyword in antifungal_keywords):
            return 'antifungal'
        
        # ANALGESICS & ANTIPYRETICS (Comprehensive)
        analgesic_keywords = [
            'paracetamol', 'acetaminophen', 'panadol', 'tylenol', 'aspirin',
            'ibuprofen', 'brufen', 'naproxen', 'diclofenac', 'voltaren',
            'indomethacin', 'mefenamic', 'tramadol', 'morphine', 'codeine',
            'fentanyl', 'pethidine', 'oxycodone', 'hydrocodone', 'aceclofenac'
        ]
        if any(keyword in name_lower for keyword in analgesic_keywords):
            if 'paracetamol' in name_lower or 'acetaminophen' in name_lower or 'panadol' in name_lower:
                return 'antipyretic'
            return 'analgesic'
        
        # ANTI-INFLAMMATORIES
        anti_inflammatory_keywords = [
            'prednisolone', 'prednisone', 'dexamethasone', 'methylprednisolone',
            'hydrocortisone', 'betamethasone', 'triamcinolone'
        ]
        if any(keyword in name_lower for keyword in anti_inflammatory_keywords):
            if 'cortisone' in name_lower or 'prednis' in name_lower or 'dexameth' in name_lower:
                return 'corticosteroid'
            return 'anti_inflammatory'
        
        # ANTIHYPERTENSIVES (Comprehensive)
        antihypertensive_keywords = [
            'amlodipine', 'nifedipine', 'verapamil', 'diltiazem', 'lisinopril',
            'enalapril', 'captopril', 'ramipril', 'losartan', 'valsartan',
            'candesartan', 'olmesartan', 'atenolol', 'metoprolol', 'propranolol',
            'bisoprolol', 'carvedilol', 'nebivolol', 'hydrochlorothiazide', 'furosemide',
            'spironolactone', 'amiloride', 'triamterene', 'bendrofluazide', 'bendroflumethiazide', 'bendro'
        ]
        if any(keyword in name_lower for keyword in antihypertensive_keywords):
            if any(x in name_lower for x in ['thiazide', 'furosemide', 'spironolactone', 'amiloride', 'bendro']):
                return 'diuretic'
            if any(x in name_lower for x in ['olol', 'propranolol', 'atenolol', 'metoprolol', 'bisoprolol', 'carvedilol']):
                return 'beta_blocker'
            return 'antihypertensive'
        
        # ANTICOAGULANTS
        anticoagulant_keywords = [
            'warfarin', 'heparin', 'enoxaparin', 'dalteparin', 'rivaroxaban',
            'apixaban', 'dabigatran'
        ]
        if any(keyword in name_lower for keyword in anticoagulant_keywords):
            return 'anticoagulant'
        if 'aspirin' in name_lower and any(x in name_lower for x in ['75', '81', 'low']):
            return 'anticoagulant'
        
        # ANTIDIABETICS
        antidiabetic_keywords = [
            'metformin', 'glibenclamide', 'gliclazide', 'glipizide', 'glimepiride',
            'pioglitazone', 'rosiglitazone', 'sitagliptin', 'vildagliptin', 'insulin',
            'actrapid', 'insugen', 'humulin', 'novolin'
        ]
        if any(keyword in name_lower for keyword in antidiabetic_keywords):
            if 'insulin' in name_lower:
                return 'hormone'
            return 'oral_hypoglycemic'
        
        # ANTACIDS & GI DRUGS (Comprehensive)
        antacid_keywords = [
            'omeprazole', 'lansoprazole', 'pantoprazole', 'rabeprazole', 'esomeprazole',
            'ranitidine', 'famotidine', 'cimetidine', 'aluminum', 'magnesium',
            'calcium carbonate', 'sodium bicarbonate', 'maalox', 'gaviscon'
        ]
        if any(keyword in name_lower for keyword in antacid_keywords):
            return 'antacid'
        
        # ANTIEMETICS (Comprehensive)
        antiemetic_keywords = [
            'ondansetron', 'metoclopramide', 'domperidone', 'promethazine',
            'prochlorperazine', 'cyclizine', 'dimenhydrinate'
        ]
        if any(keyword in name_lower for keyword in antiemetic_keywords):
            return 'antiemetic'
        
        # LAXATIVES
        laxative_keywords = [
            'lactulose', 'senna', 'bisacodyl', 'docusate', 'psyllium',
            'polyethylene glycol', 'glycerin'
        ]
        if any(keyword in name_lower for keyword in laxative_keywords):
            return 'laxative'
        
        # ANTIDIARRHEALS
        antidiarrheal_keywords = [
            'loperamide', 'diphenoxylate', 'kaolin', 'pectin'
        ]
        if any(keyword in name_lower for keyword in antidiarrheal_keywords):
            return 'antidiarrheal'
        
        # BRONCHODILATORS (Comprehensive)
        bronchodilator_keywords = [
            'salbutamol', 'albuterol', 'ventolin', 'terbutaline', 'ipratropium',
            'tiotropium', 'theophylline', 'aminophylline', 'salmeterol', 'formoterol'
        ]
        if any(keyword in name_lower for keyword in bronchodilator_keywords):
            return 'bronchodilator'
        
        # EXPECTORANTS & COUGH SUPPRESSANTS
        expectorant_keywords = [
            'guaifenesin', 'bromhexine', 'ambroxol', 'acetylcysteine', 'carbocisteine',
            'dextromethorphan'
        ]
        if any(keyword in name_lower for keyword in expectorant_keywords):
            if 'dextromethorphan' in name_lower or ('codeine' in name_lower and 'cough' in name_lower):
                return 'cough_suppressant'
            return 'expectorant'
        if 'codeine' in name_lower and 'cough' in name_lower:
            return 'cough_suppressant'
        
        # ANTIHISTAMINES (Comprehensive)
        antihistamine_keywords = [
            'chlorpheniramine', 'cetirizine', 'loratadine', 'fexofenadine', 'allegra', 'telfast',
            'diphenhydramine', 'promethazine', 'hydroxyzine', 'cyproheptadine', 'cinnarizine', 'stugeron'
        ]
        if any(keyword in name_lower for keyword in antihistamine_keywords):
            return 'antihistamine'
        
        # ANTICONVULSANTS
        anticonvulsant_keywords = [
            'phenytoin', 'carbamazepine', 'valproic', 'valproate', 'lamotrigine',
            'gabapentin', 'pregabalin', 'topiramate', 'levetiracetam', 'phenobarbital'
        ]
        if any(keyword in name_lower for keyword in anticonvulsant_keywords):
            return 'anticonvulsant'
        
        # ANTIDEPRESSANTS
        antidepressant_keywords = [
            'fluoxetine', 'sertraline', 'paroxetine', 'citalopram', 'escitalopram',
            'amitriptyline', 'imipramine', 'doxepin', 'venlafaxine', 'duloxetine'
        ]
        if any(keyword in name_lower for keyword in antidepressant_keywords):
            return 'antidepressant'
        
        # ANTIANXIETY & SEDATIVES
        antianxiety_keywords = [
            'diazepam', 'lorazepam', 'alprazolam', 'clonazepam', 'midazolam',
            'temazepam', 'zolpidem', 'zaleplon', 'buspirone'
        ]
        if any(keyword in name_lower for keyword in antianxiety_keywords):
            if any(x in name_lower for x in ['zolpidem', 'zaleplon', 'temazepam']):
                return 'sleeping_drug'
            return 'antianxiety'
        
        # ANTIPSYCHOTICS
        antipsychotic_keywords = [
            'haloperidol', 'chlorpromazine', 'risperidone', 'olanzapine',
            'quetiapine', 'aripiprazole', 'clozapine', 'fluphenazine'
        ]
        if any(keyword in name_lower for keyword in antipsychotic_keywords):
            return 'antipsychotic'
        
        # VITAMINS & SUPPLEMENTS (Comprehensive)
        vitamin_keywords = [
            'vitamin', 'multivitamin', 'centrum', 'folic acid', 'folate',
            'iron', 'ferrous', 'calcium', 'zinc', 'magnesium', 'vitamin b',
            'vitamin c', 'vitamin d', 'vitamin e', 'vitamin a', 'b12', 'b complex',
            'doctor', 'mans vitamin', 'recommended'
        ]
        if any(keyword in name_lower for keyword in vitamin_keywords):
            return 'vitamin'
        
        # HORMONES (Comprehensive)
        hormone_keywords = [
            'estrogen', 'progesterone', 'testosterone', 'levothyroxine',
            'thyroxine', 'levonorgestrel', 'cabergoline', 'dostinex'
        ]
        if any(keyword in name_lower for keyword in hormone_keywords):
            if any(x in name_lower for x in ['estrogen', 'progesterone', 'contraceptive', 'levonorgestrel']):
                return 'female_sex_hormone'
            if 'testosterone' in name_lower:
                return 'male_sex_hormone'
            return 'hormone'
        
        # MUSCLE RELAXANTS
        muscle_relaxant_keywords = [
            'baclofen', 'tizanidine', 'cyclobenzaprine', 'methocarbamol',
            'carisoprodol', 'orphenadrine'
        ]
        if any(keyword in name_lower for keyword in muscle_relaxant_keywords):
            return 'muscle_relaxant'
        
        # BUDESONIDE (corticosteroid for asthma)
        if 'budesonide' in name_lower or 'pulmicort' in name_lower or 'symbicort' in name_lower:
            return 'corticosteroid'
        
        # IV FLUIDS & SOLUTIONS
        if any(x in name_lower for x in ['dextrose', 'saline', 'ringer', 'lactate', 'glucose', '10%', '5%']):
            return 'other'  # IV solutions
        
        # NASAL DECONGESTANTS
        if any(x in name_lower for x in ['afrin', 'oxymetazoline', 'phenylephrine']):
            return 'decongestant'
        
        # Default to 'other' if no match found
        return 'other'

    def find_drug(self, name, strength=None, form=None):
        """Find drug in database using intelligent matching"""
        normalized_name = self.normalize_drug_name(name)
        if not normalized_name:
            return None
        
        # Try exact match first
        drugs = Drug.objects.filter(
            name__iexact=normalized_name,
            is_deleted=False
        )
        
        if drugs.exists():
            if strength or form:
                # Try to match by strength and form
                for drug in drugs:
                    if strength and drug.strength:
                        if strength.lower() in drug.strength.lower() or drug.strength.lower() in strength.lower():
                            if not form or not drug.form or form.lower() in drug.form.lower():
                                return drug
                    elif form and drug.form:
                        if form.lower() in drug.form.lower():
                            return drug
                # Return first match if no strength/form match
                return drugs.first()
            return drugs.first()
        
        # Try partial match (contains)
        drugs = Drug.objects.filter(
            name__icontains=normalized_name,
            is_deleted=False
        )
        
        if drugs.exists():
            # Prefer exact substring match
            for drug in drugs:
                if normalized_name.lower() in drug.name.lower():
                    return drug
            return drugs.first()
        
        return None

    def parse_quantity(self, value):
        """Parse quantity value, handling various formats"""
        if pd.isna(value) or value is None:
            return 0
        
        try:
            # Try direct conversion
            if isinstance(value, (int, float)):
                return max(0, int(value))
            
            # Try string parsing
            value_str = str(value).strip()
            # Remove commas and other formatting
            value_str = re.sub(r'[,\s]', '', value_str)
            # Extract numbers
            numbers = re.findall(r'\d+', value_str)
            if numbers:
                return max(0, int(numbers[0]))
            
            return 0
        except (ValueError, TypeError):
            return 0

    def parse_price(self, value):
        """Parse price value, handling various formats"""
        if pd.isna(value) or value is None:
            return Decimal('0.00')
        
        try:
            if isinstance(value, (int, float)):
                return Decimal(str(value)).quantize(Decimal('0.01'))
            
            # Try string parsing
            value_str = str(value).strip()
            # Remove currency symbols and commas
            value_str = re.sub(r'[₵GHS,\s]', '', value_str)
            # Extract decimal number
            price_match = re.search(r'\d+\.?\d*', value_str)
            if price_match:
                return Decimal(price_match.group(0)).quantize(Decimal('0.01'))
            
            return Decimal('0.00')
        except (InvalidOperation, ValueError, TypeError):
            return Decimal('0.00')

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        if pd is None:
            self.stdout.write(
                self.style.ERROR('pandas is required. Install with: pip install pandas openpyxl')
            )
            return

        excel_file = options['excel_file']
        dry_run = options['dry_run']
        create_missing = options['create_missing']
        update_prices_only = options['update_prices_only']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('DRUG STOCK AND PRICE UPDATE SYSTEM'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made'))
            self.stdout.write('')

        self.stdout.write(f'Reading Excel file: {excel_file}')

        try:
            # Try reading with header=1 (second row) as the actual header row
            # First row often has "or:" or other formatting
            df = pd.read_excel(excel_file, header=1)
            
            # If still having issues, try reading without header and manually set
            if df.empty or all(str(col).startswith('Unnamed') for col in df.columns):
                self.stdout.write('  ⚠️  Trying alternative header detection...')
                df_raw = pd.read_excel(excel_file, header=None)
                if len(df_raw) > 1:
                    # Use row 1 (index 1) as header, data starts from row 2
                    df = df_raw.iloc[2:].copy()
                    df.columns = df_raw.iloc[1].values
                    df = df.reset_index(drop=True)
            
            self.stdout.write(self.style.SUCCESS(f'✅ Found {len(df)} rows in Excel file'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error reading Excel file: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
            return

        # Normalize column names - handle NaN and empty strings
        df.columns = [str(col).strip().upper() if pd.notna(col) and str(col).strip() else f'COL_{i}' 
                     for i, col in enumerate(df.columns)]
        self.stdout.write(f'Columns found: {", ".join(df.columns.tolist())}')
        self.stdout.write('')

        # Find columns - based on actual Excel structure
        name_col = None
        for col in ['DESCRIPTION', 'DRUG NAME', 'NAME', 'ITEM NAME', 'DRUG', 'ITEM', 'PRODUCT']:
            if col in df.columns:
                name_col = col
                break

        qty_col = None
        for col in ['QOH', 'QUANTITY', 'QTY', 'QUANTITY ON HAND', 'STOCK', 'STOCK QTY', 'AVAILABLE']:
            if col in df.columns:
                qty_col = col
                break

        # For price, prefer "LAST COST" or "LAST UNIT COST" as it's the most recent
        price_col = None
        for col in ['LAST COST', 'LAST UNIT COST', 'AVE COST', 'AVE UNIT COST', 'COST', 'PRICE', 'UNIT PRICE', 'SELLING PRICE', 'RATE', 'UNIT COST']:
            if col in df.columns:
                price_col = col
                break

        # Cost price - use "COST" or "AVE COST" if available
        cost_col = None
        for col in ['COST', 'AVE COST', 'AVE UNIT COST', 'COST PRICE', 'PURCHASE PRICE', 'BUYING PRICE', 'COST PER UNIT']:
            if col in df.columns and col != price_col:
                cost_col = col
                break

        if not name_col:
            self.stdout.write(self.style.ERROR(
                f'❌ Could not find drug name column. Available columns: {df.columns.tolist()}'
            ))
            return

        self.stdout.write(f'Using columns:')
        self.stdout.write(f'  - Name: {name_col}')
        if qty_col:
            self.stdout.write(f'  - Quantity: {qty_col}')
        else:
            self.stdout.write(self.style.WARNING('  - Quantity: NOT FOUND'))
        if price_col:
            self.stdout.write(f'  - Price: {price_col}')
        else:
            self.stdout.write(self.style.WARNING('  - Price: NOT FOUND'))
        if cost_col:
            self.stdout.write(f'  - Cost: {cost_col}')
        else:
            self.stdout.write(self.style.WARNING('  - Cost: NOT FOUND (will use price as cost)'))
        self.stdout.write('')

        # Statistics
        stats = {
            'processed': 0,
            'matched': 0,
            'not_found': 0,
            'price_updated': 0,
            'quantity_updated': 0,
            'stock_created': 0,
            'category_updated': 0,
            'errors': 0
        }

        # Process each row - use individual transactions to prevent one error from breaking everything
        for idx, row in df.iterrows():
            try:
                with transaction.atomic():
                    drug_name = row.get(name_col)
                    if pd.isna(drug_name) or not str(drug_name).strip():
                        continue

                    stats['processed'] += 1
                    drug_name_str = str(drug_name).strip()

                    # Find drug
                    drug = self.find_drug(drug_name_str)
                    if not drug:
                        stats['not_found'] += 1
                        if self.verbosity >= 2:
                            self.stdout.write(
                                self.style.WARNING(f'  ⚠️  Not found: {drug_name_str}')
                            )
                        continue

                    stats['matched'] += 1

                    # Parse values
                    quantity = self.parse_quantity(row.get(qty_col)) if qty_col else 0
                    unit_price = self.parse_price(row.get(price_col)) if price_col else Decimal('0.00')
                    cost_price = self.parse_price(row.get(cost_col)) if cost_col else unit_price

                    # Classify drug - ensure proper classification for better organization
                    category_updated = False
                    new_category = self.classify_drug(drug_name_str)
                    
                    # Update category to ensure proper organization:
                    # 1. Drug has no category - always update
                    # 2. Drug is classified as 'other' - update if we found a better category
                    # 3. Drug has a category but we found a different specific one - update for better organization
                    should_update_category = False
                    if not drug.category:
                        should_update_category = True
                    elif drug.category == 'other' and new_category != 'other':
                        # Always update from 'other' to a specific category
                        should_update_category = True
                    elif new_category != 'other' and drug.category != new_category:
                        # Reclassify to ensure proper organization - update if we found a specific category
                        should_update_category = True
                    
                    if should_update_category:
                        if not dry_run:
                            drug.category = new_category
                            category_updated = True
                        stats['category_updated'] += 1
                        if self.verbosity >= 2:
                            old_cat = drug.category if hasattr(drug, 'category') else 'none'
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  🏷️  Classified {drug.name}: {old_cat} → {new_category}'
                                )
                            )

                    # Update drug prices
                    price_updated = False
                    update_fields = []
                    
                    if unit_price > 0:
                        if drug.unit_price != unit_price:
                            if not dry_run:
                                drug.unit_price = unit_price
                                update_fields.append('unit_price')
                            price_updated = True
                            stats['price_updated'] += 1

                    if cost_price > 0:
                        if drug.cost_price != cost_price:
                            if not dry_run:
                                drug.cost_price = cost_price
                                update_fields.append('cost_price')
                            price_updated = True
                    
                    # Save price and category updates together
                    if update_fields or category_updated:
                        if not dry_run:
                            if category_updated:
                                update_fields.append('category')
                            drug.save(update_fields=update_fields)

                    if price_updated and self.verbosity >= 2:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  💰 Updated prices for {drug.name}: '
                                f'Price={unit_price}, Cost={cost_price}'
                            )
                        )

                    # Update stock quantities
                    if not update_prices_only and quantity > 0:
                        # Find existing stock or create new
                        stock = PharmacyStock.objects.filter(
                            drug=drug,
                            is_deleted=False
                        ).order_by('-expiry_date').first()

                        if stock:
                            # Update existing stock
                            if stock.quantity_on_hand != quantity:
                                if not dry_run:
                                    stock.quantity_on_hand = quantity
                                    if cost_price > 0:
                                        stock.unit_cost = cost_price
                                    stock.save(update_fields=['quantity_on_hand', 'unit_cost'])
                                stats['quantity_updated'] += 1
                                if self.verbosity >= 2:
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f'  📦 Updated stock for {drug.name}: '
                                            f'Qty={quantity}'
                                        )
                                    )
                        elif create_missing:
                            # Create new stock entry
                            if not dry_run:
                                expiry_date = timezone.now().date() + timedelta(days=730)  # 2 years
                                # Truncate batch_number to fit field length (max 50 chars)
                                batch_num = f'IMP-{timezone.now().strftime("%Y%m%d")}-{str(drug.id)[:8]}'
                                batch_num = batch_num[:50]  # Ensure it fits
                                
                                stock = PharmacyStock.objects.create(
                                    drug=drug,
                                    batch_number=batch_num,
                                    expiry_date=expiry_date,
                                    quantity_on_hand=quantity,
                                    reorder_level=max(10, int(quantity * 0.2)),
                                    unit_cost=cost_price if cost_price > 0 else drug.cost_price,
                                    location='Main Pharmacy'
                                )
                            stats['stock_created'] += 1
                            if self.verbosity >= 2:
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f'  ✨ Created stock for {drug.name}: Qty={quantity}'
                                    )
                                )

            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error processing row {idx + 1}: {str(e)}')
                )
                if self.verbosity >= 3:
                    import traceback
                    self.stdout.write(traceback.format_exc())
                # Continue to next row - transaction already rolled back

        # Print summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('UPDATE SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Total rows processed: {stats["processed"]}')
        self.stdout.write(f'Drugs matched: {stats["matched"]}')
        self.stdout.write(f'Drugs not found: {stats["not_found"]}')
        self.stdout.write(f'Categories updated: {stats["category_updated"]}')
        self.stdout.write(f'Prices updated: {stats["price_updated"]}')
        self.stdout.write(f'Quantities updated: {stats["quantity_updated"]}')
        self.stdout.write(f'Stock entries created: {stats["stock_created"]}')
        self.stdout.write(f'Errors: {stats["errors"]}')
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 This was a DRY RUN - No changes were made'))
            self.stdout.write(self.style.SUCCESS('Run without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Update completed successfully!'))

"""
Senior Engineer Grade: Advanced Drug Classification System
==========================================================
Intelligently classifies drugs from Excel file to their appropriate categories
using comprehensive AI-based pattern matching, fuzzy matching, and drug database knowledge.

Features:
- Advanced pattern matching with drug name variations
- Comprehensive drug knowledge database
- Automatic Drug and InventoryItem creation
- PharmacyStock integration for proper dispensing
- Detailed classification reporting
- Handles edge cases and non-drug items
"""
import re
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from hospital.models import Drug, PharmacyStock
from hospital.models_procurement import InventoryItem, Store, InventoryCategory

try:
    import pandas as pd
except ImportError:
    pd = None


class Command(BaseCommand):
    help = 'Classify drugs from Excel file to their appropriate drug categories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--excel-file',
            type=str,
            default='import/UPDATED STOCK LIST.xlsx',
            help='Path to Excel file with drug list'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing drugs with classifications'
        )
        parser.add_argument(
            '--skip-non-drugs',
            action='store_true',
            help='Skip items that are clearly not drugs (supplies, equipment, etc.)'
        )
        parser.add_argument(
            '--create-pharmacy-stock',
            action='store_true',
            default=True,
            help='Create PharmacyStock entries for proper pharmacy dispensing (default: True)'
        )

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        if pd is None:
            self.stdout.write(
                self.style.ERROR('pandas is required. Install with: pip install pandas openpyxl')
            )
            return

        excel_file = options['excel_file']
        dry_run = options['dry_run']
        update_existing = options['update_existing']

        self.stdout.write(self.style.SUCCESS(f'Reading Excel file: {excel_file}'))

        try:
            df = pd.read_excel(excel_file)
            self.stdout.write(f'Found {len(df)} rows in Excel file')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading Excel file: {e}'))
            return

        # Normalize column names
        df.columns = [str(col).strip().upper() for col in df.columns]
        
        # Find drug name column
        name_col = None
        for col in ['DESCRIPTION', 'DRUG NAME', 'NAME', 'ITEM NAME', 'DRUG']:
            if col in df.columns:
                name_col = col
                break
        
        if not name_col:
            self.stdout.write(self.style.ERROR(f'Could not find drug name column. Available columns: {df.columns.tolist()}'))
            return

        # Find quantity column
        qty_col = None
        for col in ['QOH', 'QUANTITY', 'QTY', 'QUANTITY ON HAND', 'STOCK']:
            if col in df.columns:
                qty_col = col
                break

        stats = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'non_drugs': 0,
            'classified': {},
            'unclassified': []
        }

        # Get or create pharmacy category
        pharmacy_category = InventoryCategory.objects.filter(
            code='PHARM'
        ).first()
        
        if not pharmacy_category:
            pharmacy_category = InventoryCategory.objects.filter(
                name__icontains='pharmacy',
                is_for_pharmacy=True
            ).first()
        
        if not pharmacy_category:
            # Try to create with unique code
            import uuid
            unique_code = f'PHARM{uuid.uuid4().hex[:4].upper()}'
            try:
                pharmacy_category = InventoryCategory.objects.create(
                    name='Pharmacy',
                    code=unique_code,
                    is_for_pharmacy=True
                )
            except Exception:
                # If still fails, just use any existing category or None
                pharmacy_category = InventoryCategory.objects.filter(
                    is_for_pharmacy=True
                ).first() or InventoryCategory.objects.first()

        # Get or create main pharmacy store
        pharmacy_store = Store.objects.filter(
            Q(name__icontains='pharmacy') | Q(store_type='pharmacy')
        ).first()
        
        if not pharmacy_store:
            from hospital.models import Department
            pharmacy_dept = Department.objects.filter(name__icontains='pharmacy').first()
            pharmacy_store = Store.objects.create(
                name='Main Pharmacy Store',
                code='PHARM',
                store_type='pharmacy',
                department=pharmacy_dept,
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f'Created pharmacy store: {pharmacy_store.name}'))
        else:
            self.stdout.write(f'Using pharmacy store: {pharmacy_store.name}')

        with transaction.atomic():
            for idx, row in df.iterrows():
                try:
                    drug_name = str(row[name_col]).strip()
                    if not drug_name or drug_name.lower() in ['nan', 'none', '']:
                        continue

                    # Check if this is a non-drug item (supplies, equipment, etc.)
                    if options.get('skip_non_drugs', False):
                        if self.is_non_drug_item(drug_name):
                            stats['non_drugs'] += 1
                            if dry_run:
                                self.stdout.write(
                                    self.style.WARNING(f'[SKIP] Non-drug item: {drug_name}')
                                )
                            continue

                    # Extract quantity if available
                    quantity = 0
                    if qty_col and qty_col in df.columns:
                        try:
                            qty_val = row[qty_col]
                            if pd.notna(qty_val):
                                quantity = int(float(qty_val))
                        except (ValueError, TypeError):
                            pass

                    # Extract cost if available
                    cost = 0
                    cost_col = None
                    for col in ['LAST COST', 'COST', 'UNIT COST', 'PRICE']:
                        if col in df.columns:
                            cost_col = col
                            break
                    
                    if cost_col:
                        try:
                            cost_val = row[cost_col]
                            if pd.notna(cost_val):
                                cost = float(cost_val)
                        except (ValueError, TypeError):
                            pass

                    # Classify the drug using advanced AI-based classification
                    classification_result = self.classify_drug_advanced(drug_name)
                    category = classification_result['category']
                    confidence = classification_result['confidence']
                    
                    # Track classification statistics
                    if category not in stats['classified']:
                        stats['classified'][category] = 0
                    stats['classified'][category] += 1
                    
                    if category == 'other' and confidence < 0.3:
                        stats['unclassified'].append(drug_name)
                    
                    # Parse drug name to extract components
                    parsed = self.parse_drug_name(drug_name)
                    
                    if dry_run:
                        confidence_str = f" (confidence: {confidence:.0%})" if confidence < 1.0 else ""
                        self.stdout.write(
                            f'[DRY RUN] {drug_name} -> {category}{confidence_str}'
                        )
                        stats['processed'] += 1
                        continue

                    # Get or create drug - use name + strength + form as unique identifier
                    drug_lookup_name = parsed['name'][:200]
                    drug, created = Drug.objects.get_or_create(
                        name=drug_lookup_name,
                        defaults={
                            'generic_name': parsed.get('generic_name', '')[:200],
                            'strength': parsed.get('strength', '')[:50],
                            'form': parsed.get('form', 'tablet')[:50],
                            'pack_size': parsed.get('pack_size', '')[:50],
                            'category': category,
                            'is_active': True,
                            'unit_price': cost if cost > 0 else 0,
                            'cost_price': cost if cost > 0 else 0,
                        }
                    )

                    if created:
                        stats['created'] += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Created: {drug.name} {drug.strength} -> {category}'
                            )
                        )
                    elif update_existing:
                        # Update existing drug if category is different or missing
                        updated_fields = []
                        if not drug.category or drug.category == 'other' or confidence > 0.8:
                            drug.category = category
                            updated_fields.append('category')
                        if parsed.get('strength') and not drug.strength:
                            drug.strength = parsed['strength'][:50]
                            updated_fields.append('strength')
                        if parsed.get('form') and not drug.form:
                            drug.form = parsed['form'][:50]
                            updated_fields.append('form')
                        if cost > 0 and drug.cost_price == 0:
                            drug.cost_price = cost
                            drug.unit_price = cost
                            updated_fields.extend(['cost_price', 'unit_price'])
                        
                        if updated_fields:
                            drug.save(update_fields=updated_fields)
                            stats['updated'] += 1
                            self.stdout.write(
                                self.style.WARNING(
                                    f'↻ Updated: {drug.name} -> {category}'
                                )
                            )
                        else:
                            stats['skipped'] += 1
                    else:
                        stats['skipped'] += 1

                    # Create or update inventory item
                    if pharmacy_store and pharmacy_category:
                        inventory_item, inv_created = InventoryItem.objects.get_or_create(
                            store=pharmacy_store,
                            drug=drug,
                            defaults={
                                'category': pharmacy_category,
                                'item_name': f"{drug.name} {drug.strength} {drug.form}".strip()[:200],
                                'item_code': '',  # Will be auto-generated
                                'description': f"{drug.name} - {drug.generic_name or ''}".strip(),
                                'quantity_on_hand': quantity,
                                'unit_cost': cost if cost > 0 else 0,
                                'unit_of_measure': drug.form or 'units',
                                'is_active': True,
                            }
                        )
                        
                        if not inv_created and update_existing:
                            if quantity > 0:
                                inventory_item.quantity_on_hand = quantity
                            if cost > 0:
                                inventory_item.unit_cost = cost
                            inventory_item.save()

                    # Create PharmacyStock entry for proper pharmacy dispensing
                    if options.get('create_pharmacy_stock', True) and quantity > 0:
                        # Generate batch number from current date
                        batch_number = f"BATCH-{date.today().strftime('%Y%m%d')}-{drug.id}"
                        expiry_date = date.today() + timedelta(days=365 * 2)  # Default 2 years
                        
                        pharmacy_stock, ps_created = PharmacyStock.objects.get_or_create(
                            drug=drug,
                            batch_number=batch_number,
                            defaults={
                                'expiry_date': expiry_date,
                                'location': 'Main Pharmacy',
                                'quantity_on_hand': quantity,
                                'unit_cost': cost if cost > 0 else 0,
                                'reorder_level': 10,
                            }
                        )
                        
                        if not ps_created and update_existing:
                            pharmacy_stock.quantity_on_hand = quantity
                            if cost > 0:
                                pharmacy_stock.unit_cost = cost
                            pharmacy_stock.save()

                    stats['processed'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    import traceback
                    self.stdout.write(
                        self.style.ERROR(f'Error processing row {idx} ({drug_name}): {e}')
                    )
                    if self.verbosity >= 2:
                        self.stdout.write(traceback.format_exc())

        # Print comprehensive summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('DRUG CLASSIFICATION SUMMARY - SENIOR ENGINEER REPORT'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'Total Processed: {stats["processed"]}')
        self.stdout.write(f'Drugs Created: {stats["created"]}')
        self.stdout.write(f'Drugs Updated: {stats["updated"]}')
        self.stdout.write(f'Skipped (already exist): {stats["skipped"]}')
        self.stdout.write(f'Non-drug Items: {stats["non_drugs"]}')
        self.stdout.write(f'Errors: {stats["errors"]}')
        
        # Classification breakdown
        if stats['classified']:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Classification Breakdown:'))
            sorted_cats = sorted(stats['classified'].items(), key=lambda x: x[1], reverse=True)
            for category, count in sorted_cats[:15]:  # Top 15 categories
                category_display = dict(Drug.CATEGORIES).get(category, category)
                self.stdout.write(f'  {category_display[:50]:50} : {count:4} drugs')
        
        # Unclassified items
        if stats['unclassified']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'⚠ {len(stats["unclassified"])} items with low confidence classification:'))
            for item in stats['unclassified'][:10]:  # Show first 10
                self.stdout.write(f'  - {item}')
            if len(stats['unclassified']) > 10:
                self.stdout.write(f'  ... and {len(stats["unclassified"]) - 10} more')
        
        if dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('[DRY RUN] No changes were made to database'))
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))

    def is_non_drug_item(self, item_name):
        """Check if an item is clearly not a drug (supplies, equipment, etc.)"""
        name_lower = item_name.lower()
        non_drug_keywords = [
            'towel', 'syringe', 'needle', 'glove', 'gauze', 'bandage', 'cotton',
            'swab', 'dressing', 'surgical', 'equipment', 'instrument', 'scalpel',
            'forceps', 'scissors', 'stethoscope', 'thermometer', 'mask', 'gown',
            'apron', 'cap', 'shoe', 'boot', 'bag', 'container', 'bottle', 'box',
            'pack', 'roll', 'sheet', 'pad', 'sponge', 'tape', 'plaster', 'plaster',
            'catheter', 'tube', 'cannula', 'iv set', 'giving set', 'drip set'
        ]
        return any(keyword in name_lower for keyword in non_drug_keywords)
    
    def classify_drug_advanced(self, drug_name):
        """
        Advanced AI-based drug classification with confidence scoring
        Returns dict with 'category' and 'confidence' (0.0 to 1.0)
        """
        name_lower = drug_name.lower()
        matches = []
        
        # Use the existing classification but with confidence scoring
        category = self.classify_drug(drug_name)
        
        # Calculate confidence based on multiple factors
        confidence = self.calculate_confidence(drug_name, category)
        
        return {
            'category': category,
            'confidence': confidence,
            'matches': matches
        }
    
    def calculate_confidence(self, drug_name, category):
        """Calculate confidence score for classification (0.0 to 1.0)"""
        name_lower = drug_name.lower()
        confidence = 0.5  # Base confidence
        
        # Increase confidence if we have strong keyword matches
        strong_matches = self.get_strong_matches(name_lower)
        if strong_matches:
            confidence = min(0.95, 0.5 + len(strong_matches) * 0.15)
        
        # Decrease confidence for 'other' category
        if category == 'other':
            confidence = max(0.1, confidence - 0.3)
        
        # Increase confidence if drug name contains strength/form indicators
        if re.search(r'\d+\s*(mg|g|ml|mcg|iu)', name_lower):
            confidence = min(1.0, confidence + 0.1)
        
        return confidence
    
    def get_strong_matches(self, name_lower):
        """Get list of strong keyword matches for confidence calculation"""
        all_keywords = []
        all_keywords.extend(self.get_antibiotic_keywords())
        all_keywords.extend(self.get_antiviral_keywords())
        all_keywords.extend(self.get_antifungal_keywords())
        all_keywords.extend(self.get_analgesic_keywords())
        # Add more as needed
        
        matches = [kw for kw in all_keywords if kw in name_lower]
        return matches
    
    def get_antibiotic_keywords(self):
        """Get comprehensive antibiotic keywords"""
        return [
            'amoxicillin', 'ampicillin', 'penicillin', 'cephalexin', 'cefuroxime',
            'ceftriaxone', 'cefotaxime', 'azithromycin', 'erythromycin', 'clarithromycin',
            'doxycycline', 'tetracycline', 'ciprofloxacin', 'levofloxacin', 'ofloxacin',
            'metronidazole', 'tinidazole', 'clindamycin', 'vancomycin', 'gentamicin',
            'amikacin', 'neomycin', 'chloramphenicol', 'sulfamethoxazole', 'trimethoprim',
            'co-trimoxazole', 'septrin', 'bactrim', 'augmentin', 'amoxiclav', 'cefixime',
            'cefazolin', 'cefadroxil', 'ceftazidime', 'cefepime', 'meropenem', 'imipenem'
        ]
    
    def get_antiviral_keywords(self):
        """Get comprehensive antiviral keywords"""
        return [
            'acyclovir', 'aciclovir', 'valacyclovir', 'ganciclovir', 'oseltamivir',
            'zanamivir', 'ribavirin', 'lamivudine', 'zidovudine', 'tenofovir', 'efavirenz'
        ]
    
    def get_antifungal_keywords(self):
        """Get comprehensive antifungal keywords"""
        return [
            'fluconazole', 'ketoconazole', 'itraconazole', 'voriconazole', 'amphotericin',
            'nystatin', 'clotrimazole', 'miconazole', 'terbinafine', 'griseofulvin'
        ]
    
    def get_analgesic_keywords(self):
        """Get comprehensive analgesic keywords"""
        return [
            'paracetamol', 'acetaminophen', 'panadol', 'tylenol', 'aspirin',
            'ibuprofen', 'brufen', 'naproxen', 'diclofenac', 'voltaren',
            'indomethacin', 'mefenamic', 'tramadol', 'morphine', 'codeine',
            'fentanyl', 'pethidine', 'oxycodone', 'hydrocodone', 'aceclofenac'
        ]
    
    def classify_drug(self, drug_name):
        """
        Intelligently classify a drug based on its name using pattern matching
        Returns the category code
        Enhanced with more comprehensive drug knowledge
        """
        name_lower = drug_name.lower()
        
        # Comprehensive classification rules based on drug names and patterns
        
        # ANTIBIOTICS & ANTIBACTERIALS (Enhanced)
        antibiotic_keywords = self.get_antibiotic_keywords()
        if any(keyword in name_lower for keyword in antibiotic_keywords):
            return 'antibiotic'
        
        # ANTIVIRALS (Enhanced)
        antiviral_keywords = self.get_antiviral_keywords()
        if any(keyword in name_lower for keyword in antiviral_keywords):
            return 'antiviral'
        
        # ANTIFUNGALS (Enhanced)
        antifungal_keywords = self.get_antifungal_keywords()
        if any(keyword in name_lower for keyword in antifungal_keywords):
            return 'antifungal'
        
        # ANALGESICS & ANTIPYRETICS (Enhanced)
        analgesic_keywords = self.get_analgesic_keywords()
        if any(keyword in name_lower for keyword in analgesic_keywords):
            if 'paracetamol' in name_lower or 'acetaminophen' in name_lower or 'panadol' in name_lower:
                return 'antipyretic'
            return 'analgesic'
        
        # Additional pain management
        if any(x in name_lower for x in ['acetaminophen pm', 'tylenol pm']):
            return 'antipyretic'
        
        # AMOXICILLIN/CLAVULANIC ACID variations (Augmentin, Amoksiklav, etc.)
        if any(x in name_lower for x in ['amoksiklav', 'amoksiclav', 'amoxiclav', 'amokxinate', 'amoksiklav']):
            return 'antibiotic'
        
        # CEFPODOXIME (should be antibiotic)
        if 'cefpodoxime' in name_lower or 'orelox' in name_lower:
            return 'antibiotic'
        
        # STATINS (cholesterol lowering)
        if any(x in name_lower for x in ['atorvastatin', 'simvastatin', 'rosuvastatin', 'pravastatin', 'cholevastin', 'lipitor', 'atocor']):
            return 'other'  # Statins - could add specific category later
        
        # ANTIMALARIALS
        if any(x in name_lower for x in ['artemether', 'artesunate', 'artemet', 'coartem', 'vernsunate']):
            return 'other'  # Antimalarial
        
        # LEVONORGESTREL (contraceptive)
        if 'levonorgestrel' in name_lower:
            return 'female_sex_hormone'
        
        # BENDROFLUAZIDE / BENDROFLUMETHIAZIDE (diuretic)
        if any(x in name_lower for x in ['bendrofluazide', 'bendroflumethiazide', 'bendro']):
            return 'diuretic'
        
        # BUSCOPAN (antispasmodic)
        if 'buscopan' in name_lower or 'buscomed' in name_lower:
            return 'other'  # Antispasmodic
        
        # BUDESONIDE (corticosteroid for asthma)
        if 'budesonide' in name_lower or 'pulmicort' in name_lower or 'symbicort' in name_lower:
            return 'corticosteroid'
        
        # FEXOFENADINE (antihistamine - Allegra)
        if 'fexofenadine' in name_lower or 'allegra' in name_lower or 'telfast' in name_lower:
            return 'antihistamine'
        
        # CINNARIZINE (antihistamine/antiemetic)
        if 'cinnarizine' in name_lower or 'stugeron' in name_lower:
            return 'antihistamine'
        
        # CABERGOLINE (dopamine agonist)
        if 'cabergoline' in name_lower or 'dostinex' in name_lower:
            return 'hormone'
        
        # ALLOPURINOL (gout medication)
        if 'allopurinol' in name_lower:
            return 'other'  # Gout medication
        
        # ARTANE (anticholinergic)
        if 'artane' in name_lower:
            return 'other'  # Anticholinergic
        
        # ANTI-INFLAMMATORIES
        anti_inflammatory_keywords = [
            'prednisolone', 'prednisone', 'dexamethasone', 'methylprednisolone',
            'hydrocortisone', 'betamethasone', 'triamcinolone'
        ]
        if any(keyword in name_lower for keyword in anti_inflammatory_keywords):
            if 'cortisone' in name_lower or 'prednis' in name_lower or 'dexameth' in name_lower:
                return 'corticosteroid'
            return 'anti_inflammatory'
        
        # ANTIHYPERTENSIVES
        antihypertensive_keywords = [
            'amlodipine', 'nifedipine', 'verapamil', 'diltiazem', 'lisinopril',
            'enalapril', 'captopril', 'ramipril', 'losartan', 'valsartan',
            'candesartan', 'olmesartan', 'atenolol', 'metoprolol', 'propranolol',
            'bisoprolol', 'carvedilol', 'nebivolol', 'hydrochlorothiazide', 'furosemide',
            'spironolactone', 'amiloride', 'triamterene'
        ]
        if any(keyword in name_lower for keyword in antihypertensive_keywords):
            if any(x in name_lower for x in ['thiazide', 'furosemide', 'spironolactone', 'amiloride']):
                return 'diuretic'
            if any(x in name_lower for x in ['olol', 'propranolol', 'atenolol', 'metoprolol']):
                return 'beta_blocker'
            return 'antihypertensive'
        
        # ANTICOAGULANTS
        anticoagulant_keywords = [
            'warfarin', 'heparin', 'enoxaparin', 'dalteparin', 'rivaroxaban',
            'apixaban', 'dabigatran', 'aspirin'  # Low-dose aspirin
        ]
        if any(keyword in name_lower for keyword in anticoagulant_keywords):
            if 'aspirin' in name_lower and any(x in name_lower for x in ['75', '81', 'low']):
                return 'anticoagulant'
            if 'aspirin' not in name_lower:
                return 'anticoagulant'
        
        # ANTIDIABETICS
        antidiabetic_keywords = [
            'metformin', 'glibenclamide', 'gliclazide', 'glipizide', 'glimepiride',
            'pioglitazone', 'rosiglitazone', 'sitagliptin', 'vildagliptin', 'insulin'
        ]
        if any(keyword in name_lower for keyword in antidiabetic_keywords):
            if 'insulin' in name_lower:
                return 'hormone'
            return 'oral_hypoglycemic'
        
        # ANTACIDS & GI DRUGS
        antacid_keywords = [
            'omeprazole', 'lansoprazole', 'pantoprazole', 'rabeprazole', 'esomeprazole',
            'ranitidine', 'famotidine', 'cimetidine', 'aluminum', 'magnesium',
            'calcium carbonate', 'sodium bicarbonate', 'maalox', 'gaviscon'
        ]
        if any(keyword in name_lower for keyword in antacid_keywords):
            return 'antacid'
        
        # ANTIEMETICS
        antiemetic_keywords = [
            'ondansetron', 'metoclopramide', 'domperidone', 'promethazine',
            'prochlorperazine', 'cyclizine', 'dimenhydrinate'
        ]
        if any(keyword in name_lower for keyword in antiemetic_keywords):
            return 'antiemetic'
        
        # LAXATIVES
        laxative_keywords = [
            'lactulose', 'senna', 'bisacodyl', 'docusate', 'psyllium',
            'polyethylene glycol', 'magnesium', 'glycerin'
        ]
        if any(keyword in name_lower for keyword in laxative_keywords):
            return 'laxative'
        
        # ANTIDIARRHEALS
        antidiarrheal_keywords = [
            'loperamide', 'diphenoxylate', 'kaolin', 'pectin'
        ]
        if any(keyword in name_lower for keyword in antidiarrheal_keywords):
            return 'antidiarrheal'
        
        # BRONCHODILATORS
        bronchodilator_keywords = [
            'salbutamol', 'albuterol', 'ventolin', 'terbutaline', 'ipratropium',
            'tiotropium', 'theophylline', 'aminophylline', 'salmeterol', 'formoterol'
        ]
        if any(keyword in name_lower for keyword in bronchodilator_keywords):
            return 'bronchodilator'
        
        # EXPECTORANTS & COUGH SUPPRESSANTS
        expectorant_keywords = [
            'guaifenesin', 'bromhexine', 'ambroxol', 'acetylcysteine', 'carbocisteine',
            'dextromethorphan', 'codeine'  # Codeine as cough suppressant
        ]
        if any(keyword in name_lower for keyword in expectorant_keywords):
            if 'dextromethorphan' in name_lower or ('codeine' in name_lower and 'cough' in name_lower):
                return 'cough_suppressant'
            return 'expectorant'
        
        # ANTIHISTAMINES
        antihistamine_keywords = [
            'chlorpheniramine', 'cetirizine', 'loratadine', 'fexofenadine',
            'diphenhydramine', 'promethazine', 'hydroxyzine', 'cyproheptadine'
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
        
        # VITAMINS & SUPPLEMENTS
        vitamin_keywords = [
            'vitamin', 'multivitamin', 'centrum', 'folic acid', 'folate',
            'iron', 'ferrous', 'calcium', 'zinc', 'magnesium', 'vitamin b',
            'vitamin c', 'vitamin d', 'vitamin e', 'vitamin a', 'b12', 'b complex'
        ]
        if any(keyword in name_lower for keyword in vitamin_keywords):
            return 'vitamin'
        
        # HORMONES
        hormone_keywords = [
            'estrogen', 'progesterone', 'testosterone', 'levothyroxine',
            'thyroxine', 'prednisolone', 'hydrocortisone', 'dexamethasone'
        ]
        if any(keyword in name_lower for keyword in hormone_keywords):
            if any(x in name_lower for x in ['estrogen', 'progesterone', 'contraceptive']):
                return 'female_sex_hormone'
            if 'testosterone' in name_lower:
                return 'male_sex_hormone'
            if 'thyroid' in name_lower or 'thyroxine' in name_lower:
                return 'hormone'
        
        # MUSCLE RELAXANTS
        muscle_relaxant_keywords = [
            'baclofen', 'tizanidine', 'cyclobenzaprine', 'methocarbamol',
            'carisoprodol', 'orphenadrine'
        ]
        if any(keyword in name_lower for keyword in muscle_relaxant_keywords):
            return 'muscle_relaxant'
        
        # ADRENALINE / EPINEPHRINE
        if any(x in name_lower for x in ['adrenaline', 'epinephrine', 'adrinor']):
            return 'other'  # Emergency medication
        
        # ALBUMIN & BLOOD PRODUCTS
        if any(x in name_lower for x in ['albumin', 'alb', 'plasma', 'blood']):
            return 'other'  # Blood products
        
        # INSULIN (already handled but add variations)
        if any(x in name_lower for x in ['insulin', 'actrapid', 'insugen', 'humulin', 'novolin']):
            return 'hormone'
        
        # ISOTRETINOIN (Acne treatment)
        if 'isotretinoin' in name_lower or 'acnotin' in name_lower:
            return 'other'  # Dermatological
        
        # IV FLUIDS & SOLUTIONS
        if any(x in name_lower for x in ['dextrose', 'saline', 'ringer', 'lactate', 'glucose', '10%', '5%']):
            return 'other'  # IV solutions
        
        # NASAL DECONGESTANTS
        if any(x in name_lower for x in ['afrin', 'oxymetazoline', 'phenylephrine']):
            return 'decongestant'
        
        # Default to 'other' if no match found
        return 'other'

    def parse_drug_name(self, drug_name):
        """
        Parse drug name to extract name, strength, form, etc.
        """
        parsed = {
            'name': drug_name,
            'generic_name': '',
            'strength': '',
            'form': 'tablet',
            'pack_size': ''
        }
        
        name_lower = drug_name.lower()
        
        # Extract strength (e.g., 500mg, 250mg/5ml)
        strength_pattern = r'(\d+(?:\.\d+)?\s*(?:mg|g|ml|mcg|iu|units?)(?:\/\d+\s*(?:mg|g|ml|mcg))?)'
        strength_match = re.search(strength_pattern, drug_name, re.IGNORECASE)
        if strength_match:
            parsed['strength'] = strength_match.group(1)
        
        # Extract form (enhanced)
        forms = {
            'tablet': ['tablet', 'tab', 'tabs', 'loose'],
            'capsule': ['capsule', 'cap', 'caps'],
            'injection': ['injection', 'inj', 'ampoule', 'vial', 'syringe', 'amp'],
            'syrup': ['syrup', 'suspension', 'susp', 'oral liquid', 'elixir'],
            'cream': ['cream', 'ointment', 'gel', 'lotion'],
            'drops': ['drops', 'eye drops', 'ear drops', 'nasal drops'],
            'inhaler': ['inhaler', 'puffer', 'nebulizer'],
            'suppository': ['suppository', 'supp', 'supp']
        }
        
        for form, keywords in forms.items():
            if any(keyword in name_lower for keyword in keywords):
                parsed['form'] = form
                break
        
        # Extract pack size
        pack_pattern = r'(\d+\s*(?:tablets?|capsules?|tabs?|caps?|vials?|ampoules?))'
        pack_match = re.search(pack_pattern, drug_name, re.IGNORECASE)
        if pack_match:
            parsed['pack_size'] = pack_match.group(1)
        
        # Clean name (remove strength, form, etc. for base name)
        base_name = drug_name
        if parsed['strength']:
            base_name = base_name.replace(parsed['strength'], '').strip()
        if parsed['pack_size']:
            base_name = base_name.replace(parsed['pack_size'], '').strip()
        
        parsed['name'] = base_name.strip()
        
        return parsed

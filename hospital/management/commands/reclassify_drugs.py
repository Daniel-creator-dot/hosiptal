"""
Reclassify all drugs to ensure proper organization under various classifications
Updates drugs that are unclassified (category='other') or have incorrect classifications
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from hospital.models import Drug
import re


class Command(BaseCommand):
    help = 'Reclassify all drugs to ensure proper organization under various classifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--only-other',
            action='store_true',
            help='Only reclassify drugs currently marked as "other"'
        )

    def classify_drug(self, drug_name):
        """
        Intelligently classify a drug based on its name using comprehensive pattern matching
        Returns the category code
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
        
        # AMOXYCILLIN variations (should be antibiotic)
        if any(x in name_lower for x in ['amoxycillin', 'amoxicillin', 'amox']):
            return 'antibiotic'
        
        # ADRENALINE / EPINEPHRINE (emergency medication)
        if any(x in name_lower for x in ['adrenaline', 'epinephrine', 'adrinor']):
            return 'other'  # Emergency medication - keep as other
        
        # ISOTRETINOIN (Acne treatment)
        if 'isotretinoin' in name_lower or 'acnotin' in name_lower:
            return 'other'  # Dermatological - keep as other
        
        # IV FLUIDS & SOLUTIONS
        if any(x in name_lower for x in ['dextrose', 'saline', 'ringer', 'lactate', 'glucose', '10%', '5%']):
            return 'other'  # IV solutions - correctly classified as other
        
        # NASAL DECONGESTANTS
        if any(x in name_lower for x in ['afrin', 'oxymetazoline', 'phenylephrine']):
            return 'decongestant'
        
        # Default to 'other' if no match found
        return 'other'

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        dry_run = options['dry_run']
        only_other = options['only_other']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('DRUG RECLASSIFICATION SYSTEM'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
        
        # Get drugs to reclassify
        if only_other:
            drugs = Drug.objects.filter(is_active=True, is_deleted=False, category='other')
            self.stdout.write(f'Reclassifying drugs currently marked as "other"...')
        else:
            drugs = Drug.objects.filter(is_active=True, is_deleted=False)
            self.stdout.write(f'Reclassifying all drugs to ensure proper organization...')
        
        self.stdout.write(f'Found {drugs.count()} drugs to process')
        self.stdout.write('')
        
        stats = {
            'processed': 0,
            'reclassified': 0,
            'unchanged': 0,
            'errors': 0
        }
        
        category_changes = {}
        
        # Process each drug
        for drug in drugs:
            try:
                with transaction.atomic():
                    stats['processed'] += 1
                    old_category = drug.category or 'none'
                    new_category = self.classify_drug(drug.name)
                    
                    if new_category != old_category and new_category != 'other':
                        # Reclassify
                        if not dry_run:
                            drug.category = new_category
                            drug.save(update_fields=['category'])
                        
                        stats['reclassified'] += 1
                        key = f'{old_category} → {new_category}'
                        category_changes[key] = category_changes.get(key, 0) + 1
                        
                        if self.verbosity >= 2:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  🏷️  {drug.name[:40]:40s}: {old_category} → {new_category}'
                                )
                            )
                    else:
                        stats['unchanged'] += 1
                        
            except Exception as e:
                stats['errors'] += 1
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error processing {drug.name}: {str(e)}')
                )
        
        # Print summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('RECLASSIFICATION SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'Total drugs processed: {stats["processed"]}')
        self.stdout.write(f'Drugs reclassified: {stats["reclassified"]}')
        self.stdout.write(f'Drugs unchanged: {stats["unchanged"]}')
        self.stdout.write(f'Errors: {stats["errors"]}')
        self.stdout.write('')
        
        if category_changes:
            self.stdout.write('Category changes:')
            for change, count in sorted(category_changes.items(), key=lambda x: x[1], reverse=True)[:20]:
                self.stdout.write(f'  {change}: {count} drugs')
            self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 This was a DRY RUN - No changes were made'))
            self.stdout.write(self.style.SUCCESS('Run without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Reclassification completed successfully!'))

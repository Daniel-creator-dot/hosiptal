"""
Separate procedures and other services from ImagingCatalog
Intelligently identifies items that should be in ProcedureCatalog or LabTest instead
"""
import re
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

try:
    from hospital.models_advanced import ImagingCatalog, ProcedureCatalog
    HAS_MODELS = True
except ImportError:
    HAS_MODELS = False

try:
    from hospital.models import LabTest
    HAS_LAB_TEST = True
except ImportError:
    HAS_LAB_TEST = False


class Command(BaseCommand):
    help = 'Separate procedures and other services from ImagingCatalog'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be moved without actually moving'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force move even if item already exists in target catalog'
        )

    def handle(self, *args, **options):
        if not HAS_MODELS:
            self.stdout.write(self.style.ERROR('Required models are not available.'))
            return
        
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.SUCCESS('\n=== Separating Procedures from Imaging Catalog ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        # Get all imaging catalog items
        imaging_items = ImagingCatalog.objects.filter(is_deleted=False)
        total_items = imaging_items.count()
        self.stdout.write(f'Total ImagingCatalog items: {total_items}\n')
        
        # Analyze and categorize
        to_move_to_procedures = []
        to_move_to_labs = []
        to_delete = []
        to_keep_as_imaging = []
        
        for item in imaging_items:
            classification = self.classify_item(item)
            
            if classification == 'procedure':
                to_move_to_procedures.append(item)
            elif classification == 'lab_test' and HAS_LAB_TEST:
                to_move_to_labs.append(item)
            elif classification == 'invalid':
                to_delete.append(item)
            else:
                to_keep_as_imaging.append(item)
        
        # Display analysis
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('ANALYSIS RESULTS'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'\nItems to move to ProcedureCatalog: {len(to_move_to_procedures)}')
        if HAS_LAB_TEST:
            self.stdout.write(f'Items to move to LabTest: {len(to_move_to_labs)}')
        self.stdout.write(f'Items to delete (invalid): {len(to_delete)}')
        self.stdout.write(f'Items to keep as Imaging: {len(to_keep_as_imaging)}')
        
        # Show samples
        if to_move_to_procedures:
            self.stdout.write(self.style.WARNING('\n--- Sample Procedures to Move ---'))
            for item in to_move_to_procedures[:10]:
                self.stdout.write(f'  {item.code} | {item.name} | Current modality: {item.modality}')
        
        if to_delete:
            self.stdout.write(self.style.ERROR('\n--- Sample Invalid Items to Delete ---'))
            for item in to_delete[:10]:
                self.stdout.write(f'  {item.code} | {item.name} | Current modality: {item.modality}')
        
        # Execute moves
        if not dry_run:
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('EXECUTING MOVES'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
            stats = {
                'moved_to_procedures': 0,
                'moved_to_labs': 0,
                'deleted': 0,
                'errors': 0,
                'skipped_exists': 0,
            }
            
            with transaction.atomic():
                # Move to ProcedureCatalog
                for item in to_move_to_procedures:
                    try:
                        success = self.move_to_procedure_catalog(item, force)
                        if success:
                            stats['moved_to_procedures'] += 1
                        else:
                            stats['skipped_exists'] += 1
                    except Exception as e:
                        stats['errors'] += 1
                        self.stdout.write(self.style.ERROR(f'  Error moving {item.code}: {e}'))
                
                # Move to LabTest (if available)
                if HAS_LAB_TEST:
                    for item in to_move_to_labs:
                        try:
                            success = self.move_to_lab_test(item, force)
                            if success:
                                stats['moved_to_labs'] += 1
                            else:
                                stats['skipped_exists'] += 1
                        except Exception as e:
                            stats['errors'] += 1
                            self.stdout.write(self.style.ERROR(f'  Error moving {item.code}: {e}'))
                
                # Delete invalid items
                for item in to_delete:
                    try:
                        item.is_deleted = True
                        item.save()
                        stats['deleted'] += 1
                    except Exception as e:
                        stats['errors'] += 1
                        self.stdout.write(self.style.ERROR(f'  Error deleting {item.code}: {e}'))
            
            # Summary
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('MOVE SUMMARY'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(f'\nMoved to ProcedureCatalog: {stats["moved_to_procedures"]}')
            if HAS_LAB_TEST:
                self.stdout.write(f'Moved to LabTest: {stats["moved_to_labs"]}')
            self.stdout.write(f'Deleted (invalid): {stats["deleted"]}')
            self.stdout.write(f'Skipped (already exists): {stats["skipped_exists"]}')
            self.stdout.write(f'Errors: {stats["errors"]}')
            
            self.stdout.write(self.style.SUCCESS('\nSeparation completed!'))
        else:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes made'))

    def classify_item(self, item):
        """
        Classify an ImagingCatalog item as: 'procedure', 'lab_test', 'imaging', or 'invalid'
        """
        name_upper = item.name.upper()
        code_upper = item.code.upper()
        
        # Keywords that indicate procedures/surgeries (more comprehensive)
        procedure_keywords = [
            # Surgeries (comprehensive list)
            'APPENDICECTOMY', 'CAESAREAN', 'C-SECTION', 'SALPINGECTOMY', 'ECTOPIC',
            'SURGERY', 'SURGICAL', 'OPERATION', 'OPERATIVE', 'RESECTION',
            'HYSTERECTOMY', 'LAPAROTOMY', 'LAPAROSCOPY', 'LAPARATOMY',
            'CHOLECYSTECTOMY', 'CYSTECTOMY', 'THYROIDECTOMY', 'MYOMECTOMY',
            'HEMORRHOIDECTOMY', 'LUMPECTOMY', 'EXCISION', 'BIOPSY',
            'EXTRACTION', 'REMOVAL', 'SPHINCTEROTOMY', 'VARICOSE',
            'POLYPECTOMY', 'OPERCULECTOMY', 'PROLAPSE', 'CORPORRHAPL',
            
            # Dental procedures (check code prefix too)
            'DENTAL', 'DENT', 'RCT', 'ROOT CANAL', 'APICECTOMY', 'CROWN', 'BRIDGE',
            'IMPLANT', 'SCALING', 'POLISHING', 'FILLING', 'MOLAR', 'PREMOLAR',
            
            # Medical procedures
            'ENDOSCOPY', 'COLONOSCOPY', 'GASTROSCOPY', 'BRONCHOSCOPY',
            'CATHETERIZATION', 'CATHETER', 'STENT', 'ANGIOGRAM',
            'INJECTION', 'INFUSION', 'DRIP', 'INJECT', 'INJECTABLE',
            'DRESSING', 'SUTURE', 'SUTURING', 'STITCH',
            'DRAINAGE', 'ASPIRATION', 'DRAIN', 'SD001',  # Surgical drain code
            'CIRCUMCISION', 'VASECTOMY', 'TUBAL', 'BTL',
            
            # Ophthalmic procedures
            'CATARACT', 'LENS', 'RETINA', 'GLAUCOMA', 'SPECTACLE',
            
            # Diagnostic procedures
            'ECG', 'EKG', 'EEG', 'ELECTROENCEPHALOGRAM',
            'HOLTER', 'STRESS TEST', 'TREADMILL',
            
            # Consultations (not imaging)
            'CONSULT', 'CONSULTATION',
            
            # Other procedures
            'PROCEDURE', 'MANIPULATION', 'REDUCTION', 'REDUCE',
            'KNEE INJECTION', 'INTRA ARTICULAR', 'INTRA-ARTICULAR',
        ]
        
        # Check code prefixes that indicate procedures
        procedure_code_prefixes = ['DS', 'DNT', 'C00', 'CAECTOP', 'LAPECTOP', 
                                   'SAP', 'PRO', 'INTRA', 'INART', 'KNIJ', 'SGS', 'OPC']
        
        # Check if code starts with procedure prefix
        for prefix in procedure_code_prefixes:
            if code_upper.startswith(prefix):
                return 'procedure'
        
        # Keywords that indicate lab tests
        lab_keywords = [
            'HORMONE', 'ACTH', 'TSH', 'T3', 'T4', 'PROTEIN', 'ANTIGEN',
            'ANTIBODY', 'SERUM', 'PLASMA', 'BLOOD', 'CULTURE',
            'ELECTROLYTES', 'UREA', 'CREATININE', 'LIVER FUNCTION',
            'LFT', 'LIPID', 'CHOLESTEROL', 'GLUCOSE', 'SUGAR',
            'HB', 'HEMOGLOBIN', 'HAEMOGLOBIN', 'CBC', 'FBC',
            'TEST', 'ASSAY', 'SCREENING', 'PROFILE',
            'CRP', 'C-REACTIVE', 'ESR', 'PCR', 'HS-CRP',
            'RHEUMATOID', 'FACTOR', 'VON WILLEBRAND', 'LANCET',
            'PROLACTIN', 'THYROID FUNCTION', 'ELECTROLPHEROSIS',
            'ANTI-BODY', 'HISTOPATHOLOGY',
        ]
        
        # Check if it's a lab test (prioritize this check)
        for keyword in lab_keywords:
            if keyword in name_upper or keyword in code_upper:
                return 'lab_test'
        
        # Check if it's a procedure (but exclude if clearly imaging)
        for keyword in procedure_keywords:
            if keyword in name_upper or keyword in code_upper:
                # Exclude only if it's clearly an imaging study with imaging keywords
                imaging_words_in_name = ['XRAY', 'X-RAY', 'RADIOGRAPH', 'CT SCAN', 'MRI', 
                                         'ULTRASOUND', 'SCAN', 'MAMMOGRAM', 'DEXA']
                if not any(img_word in name_upper for img_word in imaging_words_in_name):
                    return 'procedure'
                # Special case: if it has both procedure and imaging keywords, 
                # check if it's an imaging procedure (keep as imaging) or surgical procedure
                # e.g., "DENTAL XRAY" should be imaging, but "CAESAREAN SECTION" is procedure
                if 'XRAY' in name_upper or 'X-RAY' in name_upper:
                    # Dental XRAY is imaging, but check if it's clearly a procedure
                    if 'DENTAL XRAY' not in name_upper:
                        # This might be a procedure with XRAY in name, but prioritize procedure keywords
                        if any(kw in name_upper for kw in ['SURGERY', 'SURGICAL', 'OPERATION', 'MAJOR', 'MINOR']):
                            return 'procedure'
        
        # Check if modality is invalid (e.g., 'ct' for non-CT items)
        valid_imaging_modalities = ['xray', 'ct', 'mri', 'ultrasound', 'mammography', 'fluoroscopy', 'nuclear', 'pet', 'dexa']
        if item.modality not in valid_imaging_modalities:
            # If it has invalid modality and doesn't look like imaging, it's probably misclassified
            if not self.looks_like_imaging(item.name):
                return 'procedure'  # Assume procedure if invalid modality
        
        # Check if it's clearly not an imaging study
        if not self.looks_like_imaging(item.name):
            # If it's not clearly a procedure or lab, and doesn't look like imaging, mark as procedure
            if any(kw in name_upper for kw in ['FEE', 'CONSULT', 'INJECTION', 'SURGERY']):
                return 'procedure'
            # If it's just a number or invalid name, mark as invalid
            if not name_upper.strip() or name_upper.strip().isdigit():
                return 'invalid'
        
        return 'imaging'
    
    def looks_like_imaging(self, name):
        """Check if a name looks like an imaging study"""
        name_upper = name.upper()
        imaging_keywords = [
            'XRAY', 'X-RAY', 'RADIOGRAPH', 'RADIOGRAPHY',
            'CT', 'CAT SCAN', 'COMPUTED TOMOGRAPHY',
            'MRI', 'MAGNETIC RESONANCE',
            'ULTRASOUND', 'SONOGRAPHY', 'ECHO',
            'MAMMOGRAPHY', 'MAMMOGRAM',
            'FLUOROSCOPY', 'FLUOROSCOPIC',
            'SCAN', 'SCANNING',
            'DEXA', 'BONE DENSITY',
            'NUCLEAR', 'PET',
        ]
        
        return any(keyword in name_upper for keyword in imaging_keywords)
    
    @transaction.atomic
    def move_to_procedure_catalog(self, imaging_item, force=False):
        """Move an ImagingCatalog item to ProcedureCatalog"""
        # Check if already exists
        existing = ProcedureCatalog.objects.filter(code=imaging_item.code, is_deleted=False).first()
        if existing:
            if force:
                # Update existing
                existing.name = imaging_item.name
                existing.price = imaging_item.price
                existing.description = imaging_item.description
                existing.is_active = imaging_item.is_active
                existing.save()
                self.stdout.write(f'  Updated existing procedure: {imaging_item.code}')
                return True
            else:
                self.stdout.write(f'  Skipped (exists): {imaging_item.code}')
                return False
        
        # Determine category based on name
        category = self.determine_procedure_category(imaging_item.name)
        
        # Create new procedure
        procedure = ProcedureCatalog.objects.create(
            code=imaging_item.code,
            name=imaging_item.name,
            category=category,
            description=imaging_item.description or f"Moved from ImagingCatalog: {imaging_item.name}",
            price=imaging_item.price,
            cash_price=imaging_item.price,  # Use base price as cash price
            is_active=imaging_item.is_active,
            is_deleted=False,
        )
        
        # Mark imaging item as deleted
        imaging_item.is_deleted = True
        imaging_item.save()
        
        self.stdout.write(f'  ✓ Moved to ProcedureCatalog: {imaging_item.code} ({category})')
        return True
    
    def determine_procedure_category(self, name):
        """Determine the procedure category from name"""
        name_upper = name.upper()
        
        if any(word in name_upper for word in ['DENTAL', 'DENT', 'TOOTH', 'RCT', 'EXTRACTION']):
            return 'dental'
        elif any(word in name_upper for word in ['CAESAREAN', 'C-SECTION', 'DELIVERY', 'EPISIOTOMY']):
            return 'major_surgery'
        elif any(word in name_upper for word in ['SURGERY', 'SURGICAL', 'OPERATION', 'APPENDICECTOMY', 'HYSTERECTOMY']):
            return 'major_surgery'
        elif any(word in name_upper for word in ['ENDOSCOPY', 'COLONOSCOPY', 'GASTROSCOPY']):
            return 'endoscopy'
        elif any(word in name_upper for word in ['BIOPSY', 'ASPIRATION']):
            return 'biopsy'
        elif any(word in name_upper for word in ['INJECTION', 'INFUSION']):
            return 'injection'
        elif any(word in name_upper for word in ['DRESSING', 'SUTURE', 'WOUND']):
            return 'wound_care'
        elif any(word in name_upper for word in ['CATHETER', 'CATHETERIZATION']):
            return 'catheterization'
        elif any(word in name_upper for word in ['CATARACT', 'LENS', 'OPHTHALMIC']):
            return 'ophthalmic'
        elif any(word in name_upper for word in ['EEG', 'ECG', 'ECHO', 'HOLTER']):
            return 'other'  # Diagnostic procedures
        else:
            return 'minor_surgery'  # Default for surgical procedures
    
    def move_to_lab_test(self, imaging_item, force=False):
        """Move an ImagingCatalog item to LabTest (if model exists)"""
        if not HAS_LAB_TEST:
            return False
        
        # Check if already exists
        existing = LabTest.objects.filter(code=imaging_item.code, is_deleted=False).first()
        if existing:
            if force:
                existing.name = imaging_item.name
                existing.price = imaging_item.price
                existing.save()
                self.stdout.write(f'  Updated existing lab test: {imaging_item.code}')
                return True
            else:
                self.stdout.write(f'  Skipped (exists): {imaging_item.code}')
                return False
        
        # Create new lab test
        lab_test = LabTest.objects.create(
            code=imaging_item.code,
            name=imaging_item.name,
            price=imaging_item.price,
            is_active=imaging_item.is_active,
            is_deleted=False,
        )
        
        # Mark imaging item as deleted
        imaging_item.is_deleted = True
        imaging_item.save()
        
        self.stdout.write(f'  ✓ Moved to LabTest: {imaging_item.code}')
        return True

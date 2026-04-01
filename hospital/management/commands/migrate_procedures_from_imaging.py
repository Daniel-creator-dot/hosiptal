"""
Management command to migrate procedures from ImagingCatalog to ProcedureCatalog
Identifies procedures mixed in with imaging services and moves them to the correct catalog
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal

from hospital.models_advanced import ImagingCatalog, ProcedureCatalog, ImagingStudy


class Command(BaseCommand):
    help = 'Migrate procedures from ImagingCatalog to ProcedureCatalog'

    # Keywords that indicate a procedure (not imaging)
    PROCEDURE_KEYWORDS = [
        'surgery', 'surgical', 'operation', 'biopsy', 'injection', 'dressing',
        'suturing', 'suture', 'incision', 'drainage', 'catheter', 'endoscopy',
        'colonoscopy', 'gastroscopy', 'bronchoscopy', 'cystoscopy', 'arthroscopy',
        'laparoscopy', 'hysteroscopy', 'procedure', 'minor surgery', 'major surgery',
        'dental', 'extraction', 'filling', 'root canal', 'cleaning', 'scaling',
        'wound care', 'wound dressing', 'debridement', 'removal', 'insertion',
        'placement', 'repair', 'reconstruction', 'revision'
    ]

    # Valid imaging modalities (from ImagingStudy.MODALITY_CHOICES)
    VALID_IMAGING_MODALITIES = [
        'xray', 'ct', 'mri', 'ultrasound', 'mammography', 'fluoroscopy',
        'nuclear', 'pet', 'dexa'
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it',
        )
        parser.add_argument(
            '--force-all',
            action='store_true',
            help='Force migrate all items (use with caution)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force_all = options['force_all']

        self.stdout.write(self.style.SUCCESS('\n=== Procedure Migration from ImagingCatalog ===\n'))

        # Get all ImagingCatalog items
        all_items = ImagingCatalog.objects.filter(is_deleted=False)
        total_count = all_items.count()
        self.stdout.write(f'Total ImagingCatalog items: {total_count}')

        # Identify procedures
        procedures_to_migrate = []
        imaging_items = []

        for item in all_items:
            # Check 1: Invalid modality (not in valid imaging modalities)
            if item.modality not in self.VALID_IMAGING_MODALITIES:
                procedures_to_migrate.append((item, 'invalid_modality'))
                continue

            # Check 2: Name contains procedure keywords
            name_lower = item.name.lower()
            code_lower = item.code.lower() if item.code else ''
            description_lower = (item.description or '').lower()
            
            is_procedure = False
            reason = None
            
            for keyword in self.PROCEDURE_KEYWORDS:
                if (keyword in name_lower or 
                    keyword in code_lower or 
                    keyword in description_lower):
                    is_procedure = True
                    reason = f'contains_keyword_{keyword}'
                    break

            if is_procedure:
                procedures_to_migrate.append((item, reason))
            else:
                imaging_items.append(item)

        self.stdout.write(f'\nFound {len(procedures_to_migrate)} procedures to migrate')
        self.stdout.write(f'Found {len(imaging_items)} valid imaging items\n')

        if not procedures_to_migrate:
            self.stdout.write(self.style.SUCCESS('No procedures found in ImagingCatalog. All items are valid imaging services.'))
            return

        # Show what will be migrated
        self.stdout.write(self.style.WARNING('\nProcedures to migrate:'))
        for item, reason in procedures_to_migrate[:20]:  # Show first 20
            self.stdout.write(f'  - {item.code}: {item.name} (Reason: {reason})')
        if len(procedures_to_migrate) > 20:
            self.stdout.write(f'  ... and {len(procedures_to_migrate) - 20} more')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN - No changes made ==='))
            return

        # Confirm migration
        if not force_all:
            confirm = input('\nProceed with migration? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Migration cancelled.'))
                return

        # Perform migration
        migrated_count = 0
        skipped_count = 0
        errors = []

        with transaction.atomic():
            for item, reason in procedures_to_migrate:
                try:
                    # Determine procedure category
                    category = self._determine_category(item)
                    
                    # Check if procedure already exists in ProcedureCatalog
                    existing = ProcedureCatalog.objects.filter(
                        code=item.code,
                        is_deleted=False
                    ).first()

                    if existing:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Skipping {item.code} - already exists in ProcedureCatalog'
                            )
                        )
                        skipped_count += 1
                        # Mark imaging catalog item as deleted
                        item.is_deleted = True
                        item.is_active = False
                        item.save(update_fields=['is_deleted', 'is_active'])
                        continue

                    # Create ProcedureCatalog entry
                    procedure = ProcedureCatalog.objects.create(
                        code=item.code,
                        name=item.name,
                        category=category,
                        description=item.description or f'Migrated from ImagingCatalog. Original modality: {item.modality}',
                        price=item.price or Decimal('0.00'),
                        estimated_duration_minutes=30,  # Default
                        requires_anesthesia=category in ['major_surgery', 'minor_surgery'],
                        requires_theatre=category in ['major_surgery', 'minor_surgery'],
                        is_active=item.is_active,
                    )

                    # Mark imaging catalog item as deleted
                    item.is_deleted = True
                    item.is_active = False
                    item.save(update_fields=['is_deleted', 'is_active'])

                    migrated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'[OK] Migrated: {item.code} -> {category}'
                        )
                    )

                except Exception as e:
                    error_msg = f'Error migrating {item.code}: {str(e)}'
                    errors.append(error_msg)
                    self.stdout.write(self.style.ERROR(f'[ERROR] {error_msg}'))

        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n=== Migration Complete ==='))
        self.stdout.write(f'Migrated: {migrated_count}')
        self.stdout.write(f'Skipped: {skipped_count}')
        if errors:
            self.stdout.write(self.style.ERROR(f'Errors: {len(errors)}'))
            for error in errors:
                self.stdout.write(f'  - {error}')

    def _determine_category(self, item):
        """Determine procedure category based on name/keywords"""
        name_lower = item.name.lower()
        code_lower = (item.code or '').lower()
        text = f'{name_lower} {code_lower}'

        # Major surgery
        if any(kw in text for kw in ['major surgery', 'major operation', 'laparotomy', 'thoracotomy']):
            return 'major_surgery'

        # Minor surgery
        if any(kw in text for kw in ['minor surgery', 'minor operation', 'surgical']):
            return 'minor_surgery'

        # Dental
        if any(kw in text for kw in ['dental', 'tooth', 'teeth', 'extraction', 'filling', 'root canal', 'cleaning', 'scaling']):
            return 'dental'

        # Ophthalmic
        if any(kw in text for kw in ['ophthalmic', 'eye', 'cataract', 'retina']):
            return 'ophthalmic'

        # Endoscopy
        if any(kw in text for kw in ['endoscopy', 'colonoscopy', 'gastroscopy', 'bronchoscopy', 'cystoscopy', 'arthroscopy', 'laparoscopy', 'hysteroscopy']):
            return 'endoscopy'

        # Biopsy
        if 'biopsy' in text:
            return 'biopsy'

        # Injection
        if 'injection' in text:
            return 'injection'

        # Wound care
        if any(kw in text for kw in ['wound care', 'wound dressing', 'debridement']):
            return 'wound_care'

        # Catheterization
        if 'catheter' in text:
            return 'catheterization'

        # Dressing
        if 'dressing' in text:
            return 'dressing'

        # Suturing
        if any(kw in text for kw in ['suturing', 'suture']):
            return 'suturing'

        # Incision & Drainage
        if any(kw in text for kw in ['incision', 'drainage']):
            return 'incision_drainage'

        # Default
        return 'other'

"""
Seed pre-employment screening templates for specific companies (Toyota Ghana, Anointed, ECG, etc.).
Run: python manage.py seed_screening_companies
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q


# Company-specific pre-employment templates (for_company set)
COMPANY_TEMPLATES = [
    {
        'for_company': 'Toyota Ghana',
        'name': 'Pre-employment (Toyota Ghana)',
        'code': 'PREEMP-TOYOTA-GH',
        'description': 'Standard pre-employment medical: FBC, Urinalysis, Chest X-ray. For Toyota Ghana.',
        'lab_terms': ['FBC', 'Full Blood Count', 'CBC', 'Urinalysis', 'Urine', 'UA'],
        'imaging_terms': ['Chest X-ray', 'CXR', 'Chest radiograph'],
        'physical_exam_sections': ['General', 'Cardiovascular', 'Respiratory', 'Vision', 'Hearing'],
        'sort_order': 100,
    },
    {
        'for_company': 'Anointed',
        'name': 'Pre-employment (Anointed)',
        'code': 'PREEMP-ANOINTED',
        'description': 'Standard pre-employment medical: FBC, Urinalysis, Chest X-ray. For Anointed.',
        'lab_terms': ['FBC', 'Full Blood Count', 'CBC', 'Urinalysis', 'Urine', 'UA'],
        'imaging_terms': ['Chest X-ray', 'CXR', 'Chest radiograph'],
        'physical_exam_sections': ['General', 'Cardiovascular', 'Respiratory', 'Vision', 'Hearing'],
        'sort_order': 101,
    },
    {
        'for_company': 'ECG',
        'name': 'Pre-employment (ECG)',
        'code': 'PREEMP-ECG',
        'description': 'Pre-employment for Electricity Company of Ghana: FBC, Urinalysis, Chest X-ray, ECG (test) if required.',
        'lab_terms': ['FBC', 'Full Blood Count', 'CBC', 'Urinalysis', 'Urine', 'UA'],
        'imaging_terms': ['Chest X-ray', 'CXR', 'Chest radiograph'],
        'physical_exam_sections': ['General', 'Cardiovascular', 'Respiratory', 'Vision', 'Hearing'],
        'sort_order': 102,
    },
    {
        'for_company': 'Ghana Ports and Harbours',
        'name': 'Pre-employment (Ghana Ports)',
        'code': 'PREEMP-GHA-PORTS',
        'description': 'Pre-employment for Ghana Ports and Harbours: FBC, Urinalysis, Chest X-ray.',
        'lab_terms': ['FBC', 'Full Blood Count', 'CBC', 'Urinalysis', 'Urine', 'UA'],
        'imaging_terms': ['Chest X-ray', 'CXR', 'Chest radiograph'],
        'physical_exam_sections': ['General', 'Cardiovascular', 'Respiratory', 'Vision', 'Hearing'],
        'sort_order': 103,
    },
    {
        'for_company': 'Tullow Ghana',
        'name': 'Pre-employment (Tullow Ghana)',
        'code': 'PREEMP-TULLOW',
        'description': 'Pre-employment for Tullow Ghana: FBC, Urinalysis, Chest X-ray, Hepatitis, HIV as required.',
        'lab_terms': ['FBC', 'Full Blood Count', 'CBC', 'Urinalysis', 'Urine', 'HBsAg', 'Hepatitis B', 'HIV'],
        'imaging_terms': ['Chest X-ray', 'CXR', 'Chest radiograph'],
        'physical_exam_sections': ['General', 'Cardiovascular', 'Respiratory', 'Vision', 'Hearing'],
        'sort_order': 104,
    },
    {
        'for_company': 'Mining Sector',
        'name': 'Pre-employment (Mining)',
        'code': 'PREEMP-MINING',
        'description': 'Pre-employment for mining sector: FBC, Urinalysis, Chest X-ray, audiometry considerations.',
        'lab_terms': ['FBC', 'Full Blood Count', 'CBC', 'Urinalysis', 'Urine', 'UA'],
        'imaging_terms': ['Chest X-ray', 'CXR', 'Chest radiograph'],
        'physical_exam_sections': ['General', 'Cardiovascular', 'Respiratory', 'Vision', 'Hearing'],
        'sort_order': 105,
    },
]


class Command(BaseCommand):
    help = 'Seed pre-employment templates for Toyota Ghana, Anointed, ECG, and other companies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without writing to DB',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Do not update templates that already exist (by code)',
        )

    def handle(self, *args, **options):
        from hospital.models import LabTest
        from hospital.models_advanced import ImagingCatalog
        from hospital.models_screening import ScreeningCheckTemplate

        dry_run = options['dry_run']
        skip_existing = options['skip_existing']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be saved.'))
            for d in COMPANY_TEMPLATES:
                self.stdout.write('  Would create/update: %s for company "%s"' % (d['name'], d['for_company']))
            return

        created = 0
        updated = 0
        with transaction.atomic():
            for d in list(COMPANY_TEMPLATES):
                code = d.pop('code')
                for_company = d.pop('for_company')
                lab_terms = d.pop('lab_terms', [])
                imaging_terms = d.pop('imaging_terms', [])
                physical_exam_sections = d.get('physical_exam_sections', [])
                d['category'] = 'pre_employment'
                d['for_company'] = for_company
                d['physical_exam_sections'] = physical_exam_sections
                d['is_active'] = True

                existing = ScreeningCheckTemplate.objects.filter(code=code, is_deleted=False).first()
                if existing and skip_existing:
                    continue
                if existing:
                    for k, v in d.items():
                        setattr(existing, k, v)
                    existing.save()
                    template = existing
                    updated += 1
                    self.stdout.write(self.style.WARNING('  Updated: %s (%s)' % (template.name, for_company)))
                else:
                    template = ScreeningCheckTemplate.objects.create(code=code, **d)
                    created += 1
                    self.stdout.write(self.style.SUCCESS('  Created: %s (%s)' % (template.name, for_company)))

                # Resolve and attach lab tests
                lab_qs = LabTest.objects.filter(is_active=True, is_deleted=False)
                lab_add = []
                for term in lab_terms:
                    t = lab_qs.filter(
                        Q(code__iexact=term) | Q(name__icontains=term)
                    ).first()
                    if t and t not in lab_add:
                        lab_add.append(t)
                if lab_add:
                    template.lab_tests.add(*lab_add)
                # Resolve and attach imaging
                img_qs = ImagingCatalog.objects.filter(is_active=True, is_deleted=False)
                img_add = []
                for term in imaging_terms:
                    im = img_qs.filter(
                        Q(code__iexact=term) | Q(name__icontains=term)
                    ).first()
                    if im and im not in img_add:
                        img_add.append(im)
                if img_add:
                    template.imaging_items.add(*img_add)

        self.stdout.write(self.style.SUCCESS('\nDone. Created: %s, Updated: %s' % (created, updated)))
        self.stdout.write('Filter by company on the screening dashboard to see these templates.')

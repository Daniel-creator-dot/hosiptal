"""
Seed default institutional screening templates (pre-employment / pre-admission).
Includes: Basic Pre-employment, Hepatitis screen, HIV screen, Chest X-ray, Full Executive, School Entry.
Templates are general (for_company blank); add company-specific ones via Admin.
Run: python manage.py seed_screening_templates
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q


class Command(BaseCommand):
    help = 'Seed default screening templates (chest x-ray, hepatitis, HIV, FBC, etc.) for institutions'

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

        # Define default institutional templates (for_company = '')
        # Lab/imaging keys are search terms (code or name); resolution is best-effort.
        defaults = [
            {
                'name': 'Basic Pre-employment',
                'code': 'PREEMP-BASIC',
                'category': 'pre_employment',
                'description': 'FBC, Urinalysis, Chest X-ray. Standard for most companies.',
                'lab_terms': ['FBC', 'Full Blood Count', 'CBC', 'Urinalysis', 'Urine', 'UA'],
                'imaging_terms': ['Chest X-ray', 'CXR', 'Chest X-ray', 'Chest radiograph'],
                'physical_exam_sections': ['General', 'Cardiovascular', 'Respiratory', 'Vision', 'Hearing'],
                'sort_order': 10,
            },
            {
                'name': 'Hepatitis Screen',
                'code': 'PREEMP-HEP',
                'category': 'pre_employment',
                'description': 'Hepatitis B and C screening (HBsAg, Anti-HCV). For food handlers, healthcare.',
                'lab_terms': ['HBsAg', 'Hepatitis B', 'Anti-HCV', 'Hepatitis C', 'HCV'],
                'imaging_terms': [],
                'physical_exam_sections': ['General', 'Abdomen'],
                'sort_order': 20,
            },
            {
                'name': 'HIV Screen',
                'code': 'PREEMP-HIV',
                'category': 'pre_employment',
                'description': 'HIV screening. Required by some employers or sectors.',
                'lab_terms': ['HIV', 'HIV Antibody', 'HIV Ag/Ab'],
                'imaging_terms': [],
                'physical_exam_sections': ['General'],
                'sort_order': 30,
            },
            {
                'name': 'Chest X-ray Only',
                'code': 'PREEMP-CXR',
                'category': 'pre_employment',
                'description': 'Chest X-ray only (e.g. TB clearance, respiratory fitness).',
                'lab_terms': [],
                'imaging_terms': ['Chest X-ray', 'CXR', 'Chest radiograph'],
                'physical_exam_sections': ['Respiratory'],
                'sort_order': 40,
            },
            {
                'name': 'Full Executive Check',
                'code': 'PREEMP-EXEC',
                'category': 'pre_employment',
                'description': 'Comprehensive: FBC, U&E, LFT, Lipid, Blood glucose, Urinalysis, Chest X-ray. For senior roles.',
                'lab_terms': [
                    'FBC', 'Full Blood Count', 'CBC',
                    'U&E', 'Urea', 'Electrolyte', 'Creatinine', 'RFT', 'Renal',
                    'LFT', 'Liver', 'ALT', 'AST', 'Bilirubin',
                    'Lipid', 'Cholesterol', 'Triglyceride',
                    'Glucose', 'Blood sugar', 'FBS',
                    'Urinalysis', 'Urine',
                ],
                'imaging_terms': ['Chest X-ray', 'CXR'],
                'physical_exam_sections': ['General', 'Cardiovascular', 'Respiratory', 'Abdomen', 'Vision', 'Hearing'],
                'sort_order': 50,
            },
            {
                'name': 'School Entry (Basic)',
                'code': 'PREADM-BASIC',
                'category': 'pre_admission',
                'description': 'Basic school entry: FBC, Urinalysis. Optional stool if required by school.',
                'lab_terms': ['FBC', 'Full Blood Count', 'CBC', 'Urinalysis', 'Urine'],
                'imaging_terms': [],
                'physical_exam_sections': ['General', 'Vision', 'Hearing'],
                'sort_order': 10,
            },
            {
                'name': 'School Entry (with Chest X-ray)',
                'code': 'PREADM-CXR',
                'category': 'pre_admission',
                'description': 'School entry with chest X-ray (e.g. boarding schools, TB clearance).',
                'lab_terms': ['FBC', 'Full Blood Count', 'Urinalysis'],
                'imaging_terms': ['Chest X-ray', 'CXR'],
                'physical_exam_sections': ['General', 'Respiratory', 'Vision', 'Hearing'],
                'sort_order': 20,
            },
        ]

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be saved.'))
            for d in defaults:
                self.stdout.write('  Would create/update: %s (%s)' % (d['name'], d['code']))
            return

        created = 0
        updated = 0
        with transaction.atomic():
            for d in defaults:
                code = d.pop('code')
                lab_terms = d.pop('lab_terms', [])
                imaging_terms = d.pop('imaging_terms', [])
                physical_exam_sections = d.get('physical_exam_sections', [])
                d['for_company'] = ''  # general institutional use
                d['physical_exam_sections'] = physical_exam_sections

                existing = ScreeningCheckTemplate.objects.filter(code=code, is_deleted=False).first()
                if existing and skip_existing:
                    continue
                if existing:
                    for k, v in d.items():
                        setattr(existing, k, v)
                    existing.save()
                    template = existing
                    updated += 1
                    self.stdout.write(self.style.WARNING('  Updated: %s' % template.name))
                else:
                    template = ScreeningCheckTemplate.objects.create(code=code, **d)
                    created += 1
                    self.stdout.write(self.style.SUCCESS('  Created: %s' % template.name))

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
        self.stdout.write('Add company-specific templates via Admin: Screening check templates -> Add, then set "For company".')

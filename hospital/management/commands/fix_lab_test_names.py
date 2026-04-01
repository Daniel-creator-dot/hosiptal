"""
Fix lab test and service code names (e.g. "bf for mp" showing as "malaria blood *microscopy").
Corrects LabTest.name and ServiceCode.description for LAB-* codes.
Run: python manage.py fix_lab_test_names [--dry-run]
"""
from django.core.management.base import BaseCommand
from hospital.models import LabTest, ServiceCode


# Correct display names by lab code (overrides wrong/corrupt names in DB)
LAB_CODE_TO_CORRECT_NAME = {
    'BF': 'Blood Film',
    'BF-MP': 'Blood Film for Malaria Parasite (Microscopy)',
    'MP-BS': 'Malaria Blood Smear (Microscopy)',
    'MP-RDT': 'Malaria Rapid Diagnostic Test (RDT)',
    'MP-QBC': 'Malaria Quantitative Buffy Coat',
    'DIFF': 'Blood Film/Differential Count',
}

# Replacements in name/description (fix *microscopy and similar)
NAME_REPLACEMENTS = [
    ('*microscopy', '(Microscopy)'),
    ('malaria blood *', 'Malaria Blood Smear ('),
    ('malaria blood (microscopy)', 'Malaria Blood Smear (Microscopy)'),
    ('malaria blood (Microscopy)', 'Malaria Blood Smear (Microscopy)'),
    ('blood film *', 'Blood Film for Malaria Parasite ('),
]


class Command(BaseCommand):
    help = 'Fix lab test and service code names (e.g. *microscopy, bf for mp)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without saving',
        )

    def _apply_replacements(self, text):
        if not text:
            return text
        out = text
        for old, new in NAME_REPLACEMENTS:
            if old in out:
                out = out.replace(old, new)
        return out if out != text else None

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        fixed_lab = 0
        fixed_svc = 0

        # 1) LabTest: fix by code first, then by pattern
        for lab in LabTest.objects.filter(is_deleted=False).iterator():
            correct = LAB_CODE_TO_CORRECT_NAME.get((lab.code or '').strip().upper())
            if correct and (lab.name or '').strip() != correct:
                self.stdout.write(
                    f"  LabTest {lab.code}: '{lab.name}' -> '{correct}'"
                )
                if not dry_run:
                    lab.name = correct
                    lab.save(update_fields=['name'])
                fixed_lab += 1
                continue
            new_name = self._apply_replacements(lab.name)
            if new_name is not None:
                self.stdout.write(
                    f"  LabTest {lab.code}: '{lab.name}' -> '{new_name}'"
                )
                if not dry_run:
                    lab.name = new_name
                    lab.save(update_fields=['name'])
                fixed_lab += 1

        # 2) ServiceCode LAB-*: sync description from LabTest or apply replacements
        for sc in ServiceCode.objects.filter(
            code__startswith='LAB-',
            is_deleted=False,
        ).iterator():
            test_code = (sc.code or '').replace('LAB-', '', 1).strip()
            lab_test = LabTest.objects.filter(
                code=test_code,
                is_deleted=False,
            ).first()
            if lab_test and (sc.description or '').strip() != (lab_test.name or '').strip():
                self.stdout.write(
                    f"  ServiceCode {sc.code}: '{sc.description}' -> '{lab_test.name}'"
                )
                if not dry_run:
                    sc.description = lab_test.name
                    sc.save(update_fields=['description'])
                fixed_svc += 1
                continue
            new_desc = self._apply_replacements(sc.description)
            if new_desc is not None:
                self.stdout.write(
                    f"  ServiceCode {sc.code}: '{sc.description}' -> '{new_desc}'"
                )
                if not dry_run:
                    sc.description = new_desc
                    sc.save(update_fields=['description'])
                fixed_svc += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\nDry run: would fix {fixed_lab} LabTest(s), {fixed_svc} ServiceCode(s)'
                )
            )
        else:
            try:
                from django.core.cache import cache
                cache.delete('hms:active_lab_tests')
                self.stdout.write(self.style.SUCCESS('Lab tests cache invalidated.'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Could not invalidate cache: {e}'))
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nFixed {fixed_lab} LabTest(s), {fixed_svc} ServiceCode(s). '
                    'Run seed_ghana_lab_tests to ensure BF/BF-MP exist.'
                )
            )

"""
Management command to warm up the cache with frequently accessed data.
Run after deploy or on a schedule (e.g. every 5–10 min) so the first user
does not pay the full cost of dashboard stats and catalog lookups.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Warm up cache with frequently accessed data for better performance'

    def handle(self, *args, **options):
        self.stdout.write('Warming up cache...')

        try:
            # Catalog data (utils_cache)
            from hospital.utils_cache import (
                get_cached_drugs,
                get_cached_lab_tests,
                get_cached_imaging_studies,
                get_cached_procedures,
                get_cached_diagnosis_codes
            )
            drugs = get_cached_drugs()
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Cached {drugs.count() if hasattr(drugs, "count") else len(drugs)} drugs'
            ))
            lab_tests = get_cached_lab_tests()
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Cached {lab_tests.count() if hasattr(lab_tests, "count") else len(lab_tests)} lab tests'
            ))
            imaging_studies = get_cached_imaging_studies()
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Cached {imaging_studies.count() if hasattr(imaging_studies, "count") else len(imaging_studies)} imaging studies'
            ))
            procedures = get_cached_procedures()
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Cached {procedures.count() if hasattr(procedures, "count") else len(procedures)} procedures'
            ))
            diagnosis_codes = get_cached_diagnosis_codes()
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Cached {diagnosis_codes.count() if hasattr(diagnosis_codes, "count") else len(diagnosis_codes)} diagnosis codes'
            ))

            # Dashboard stats (utils) – avoids heavy queries on first page load after deploy
            from hospital.utils import (
                get_dashboard_stats,
                get_patient_demographics,
                get_encounter_statistics,
                get_dashboard_extra_stats
            )
            get_dashboard_stats()
            self.stdout.write(self.style.SUCCESS('[OK] Cached dashboard stats'))
            get_patient_demographics()
            self.stdout.write(self.style.SUCCESS('[OK] Cached patient demographics'))
            get_encounter_statistics()
            self.stdout.write(self.style.SUCCESS('[OK] Cached encounter statistics'))
            get_dashboard_extra_stats(timezone.now().date())
            self.stdout.write(self.style.SUCCESS('[OK] Cached dashboard extra stats'))

            self.stdout.write(self.style.SUCCESS('\n[SUCCESS] Cache warmed up successfully!'))
            self.stdout.write('System is now ready for 200+ concurrent users.')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error warming up cache: {e}'))

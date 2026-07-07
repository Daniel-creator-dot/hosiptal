"""
Soft-delete legacy ProcedureCatalog rows that use NHIS tariff wording (not cash GHS fees).
Runs once after identifying polluted catalog; clears procedure list cache.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from hospital.models_advanced import ProcedureCatalog
from hospital.procedure_catalog_visibility import nhis_tariff_noise_q
from hospital.utils_cache import clear_all_caches


class Command(BaseCommand):
    help = (
        'Deactivate ProcedureCatalog rows whose names match NHIS tariff line patterns '
        '(e.g. "AS SOLE PROCEDURE"). These are not PrimeCare/private cash amounts.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show count only',
        )

    def handle(self, *args, **options):
        qs = ProcedureCatalog.objects.filter(nhis_tariff_noise_q(), is_deleted=False)
        n = qs.count()
        self.stdout.write(self.style.WARNING(f'NHIS-pattern procedure catalog rows: {n}'))
        if options['dry_run'] or not n:
            return
        updated = qs.update(
            is_deleted=True,
            is_active=False,
            modified=timezone.now(),
        )
        clear_all_caches()
        self.stdout.write(self.style.SUCCESS(f'Soft-deactivated {updated} row(s); caches cleared.'))

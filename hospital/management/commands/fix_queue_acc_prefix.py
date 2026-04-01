"""
One-time fix: replace ACC (and other blocked) queue_prefix values in QueueConfiguration.

New tickets use normalized prefixes via queue_service; this updates stored config so
admin and reports match. Existing QueueEntry.queue_number values are unchanged.
"""
from django.core.management.base import BaseCommand
from django.conf import settings

from hospital.models_queue import QueueConfiguration


BLOCKED = {'ACC', 'XXX', 'ASS'}


class Command(BaseCommand):
    help = 'Update QueueConfiguration.queue_prefix away from ACC (and similar) for patient-friendly SMS tickets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print changes without saving',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        fallback = (getattr(settings, 'QUEUE_TICKET_PREFIX_FALLBACK', None) or 'VIS').strip().upper()[:5]
        updated = 0

        for cfg in QueueConfiguration.objects.select_related('department').all():
            raw = (cfg.queue_prefix or '').strip().upper()
            if raw not in BLOCKED:
                continue
            dept = cfg.department
            code = (getattr(dept, 'code', None) or '').strip().upper()
            code = ''.join(c for c in code if c.isalnum())[:5]
            new_prefix = code if code and code not in BLOCKED else fallback
            self.stdout.write(f'  {dept.name}: {cfg.queue_prefix!r} → {new_prefix!r}')
            if not dry:
                cfg.queue_prefix = new_prefix
                cfg.save(update_fields=['queue_prefix', 'modified'])
            updated += 1

        if dry:
            self.stdout.write(self.style.WARNING(f'Dry run: would update {updated} configuration(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Updated {updated} queue configuration(s). Fallback used: {fallback}'))

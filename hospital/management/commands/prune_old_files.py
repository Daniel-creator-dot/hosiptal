"""
Delete backup and import files older than the retention period (default 14 days).
"""
from django.core.management.base import BaseCommand

from hospital.backup_retention import get_retention_days, prune_all_retention_targets


class Command(BaseCommand):
    help = 'Delete backup and import files older than the retention period'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Retention in days (default: HospitalSettings.backup_retention_days or 14)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List files that would be deleted without removing them',
        )

    def handle(self, *args, **options):
        keep_days = options['days']
        if keep_days is None:
            keep_days = get_retention_days(default=14)

        dry_run = options['dry_run']
        mode = 'DRY RUN' if dry_run else 'DELETE'
        self.stdout.write(f'\n=== Prune old files ({mode}) — keep {keep_days} days ===\n')

        if keep_days <= 0:
            self.stdout.write(self.style.WARNING('Retention is 0 — skipping cleanup.'))
            return

        summary = prune_all_retention_targets(keep_days=keep_days, dry_run=dry_run)
        mb = summary['bytes_freed'] / (1024 * 1024)

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Would delete' if dry_run else 'Deleted'} "
                f"{summary['files_deleted']} file(s), "
                f"{summary['folders_deleted']} folder(s), "
                f"~{mb:.1f} MB freed."
            )
        )

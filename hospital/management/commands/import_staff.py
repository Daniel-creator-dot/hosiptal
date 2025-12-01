"""
Management command to import staff from spreadsheet data.
"""

from django.core.management.base import BaseCommand

from hospital.seed_data.staff_seed import STAFF_DATA, seed_staff_dataset


class Command(BaseCommand):
    help = 'Import staff from spreadsheet data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing staff members',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting staff import...'))

        result = seed_staff_dataset(
            update=options['update'],
            stdout_writer=self.stdout.write,
        )

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Import Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {result.created}'))
        self.stdout.write(self.style.SUCCESS(f'  Updated: {result.updated}'))
        self.stdout.write(self.style.SUCCESS(f'  Skipped: {result.skipped}'))
        self.stdout.write(self.style.SUCCESS(f'  Total: {result.total}'))
        self.stdout.write(self.style.SUCCESS('=' * 50))

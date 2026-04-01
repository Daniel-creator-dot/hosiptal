"""
Convenience wrapper: apply missed stock deductions for calendar yesterday.

Equivalent to:
  python manage.py backfill_pharmacy_stock_from_dispensings

Run after: python manage.py migrate
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Deduct stock for all dispensed sales from yesterday (see backfill_pharmacy_stock_from_dispensings)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deducted without changing stock',
        )

    def handle(self, *args, **options):
        call_command(
            'backfill_pharmacy_stock_from_dispensings',
            dry_run=options['dry_run'],
        )

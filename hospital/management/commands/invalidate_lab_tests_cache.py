"""
Invalidate the lab tests cache so the consultation page shows the latest tests.
Run this after adding new lab tests (e.g. after seed_ghana_lab_tests).
If using local memory cache, you must RESTART the Django server instead.
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Invalidate lab tests cache so doctors see the latest tests on the consultation page'

    def handle(self, *args, **options):
        key = 'hms:active_lab_tests'
        try:
            cache.delete(key)
            self.stdout.write(self.style.SUCCESS(f'Lab tests cache invalidated ({key}).'))
            self.stdout.write(
                'Refresh the consultation page (or restart the server if the test still does not appear).'
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to invalidate cache: {e}'))

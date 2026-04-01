"""
Show drug classification summary
"""
from django.core.management.base import BaseCommand
from collections import Counter
from hospital.models import Drug


class Command(BaseCommand):
    help = 'Show drug classification summary'

    def handle(self, *args, **options):
        drugs = Drug.objects.filter(is_active=True, is_deleted=False)
        cats = Counter(drug.category for drug in drugs)
        
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('DRUG CLASSIFICATION SUMMARY'))
        self.stdout.write('=' * 70)
        self.stdout.write('')
        
        # Get category display names
        category_map = dict(Drug.CATEGORIES)
        
        for cat, count in sorted(cats.items(), key=lambda x: x[1], reverse=True):
            display_name = category_map.get(cat, cat)
            self.stdout.write(f'{display_name[:50]:50s}: {count:4d} drugs')
        
        self.stdout.write('')
        self.stdout.write('=' * 70)
        self.stdout.write(f'Total: {sum(cats.values())} drugs')
        
        # Show unclassified
        unclassified = cats.get('other', 0)
        if unclassified > 0:
            self.stdout.write(self.style.WARNING(f'Unclassified (other): {unclassified} drugs'))

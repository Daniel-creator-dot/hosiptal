"""
Apply stock reductions for known shortfalls from the backfill.
Run this ONCE after backfill_pharmacy_stock_from_dispensings reported insufficient stock,
and after migrating to allow negative stock (1097).
"""
from django.core.management.base import BaseCommand

# Shortfalls reported from backfill - (drug_name_substring, quantity_to_reduce)
SHORTFALLS = [
    ('Misoprostol ( Cytotec ) Tablet', 2),
    ('Cough Syrup ( Luex Child Dry )', 1),
    ('Prednisolone Tablet', 40),  # 20 + 20 from two sales
]


class Command(BaseCommand):
    help = "Apply stock shortfalls from backfill (run once after migration 1097)"

    def handle(self, *args, **options):
        from hospital.models import Drug
        from hospital.pharmacy_stock_utils import reduce_pharmacy_stock

        for name_part, qty in SHORTFALLS:
            drug = Drug.objects.filter(name__icontains=name_part.strip(), is_deleted=False).first()
            if not drug:
                self.stdout.write(self.style.WARNING(f"Drug not found: {name_part}"))
                continue
            shortfall = reduce_pharmacy_stock(drug, qty)
            self.stdout.write(f"  {drug.name} x{qty} -> shortfall remaining: {shortfall}")
        self.stdout.write(self.style.SUCCESS("Shortfall fix complete."))

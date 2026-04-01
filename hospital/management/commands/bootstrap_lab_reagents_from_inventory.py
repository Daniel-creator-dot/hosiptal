from decimal import Decimal
import re

from django.core.management.base import BaseCommand

from hospital.models import LabTest
from hospital.models_lab_management import LabReagent
from hospital.models_procurement import InventoryItem


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _test_matches_reagent(test_name, reagent_name):
    t = _norm(test_name)
    r = _norm(reagent_name)
    if not t or not r:
        return False
    if t in r or r in t:
        return True
    tokens = [tok for tok in t.split() if len(tok) > 2]
    return any(tok in r for tok in tokens)


class Command(BaseCommand):
    help = "Bootstrap LabReagent rows from existing inventory items (LAB-* codes)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--link-tests",
            action="store_true",
            help="Also auto-link likely LabTest records to imported reagents.",
        )

    def handle(self, *args, **options):
        link_tests = options["link_tests"]
        items = InventoryItem.objects.filter(
            is_deleted=False,
            item_code__istartswith="LAB-",
        ).select_related("preferred_supplier")

        created = 0
        updated = 0
        linked = 0

        tests = list(LabTest.objects.filter(is_deleted=False, is_active=True)) if link_tests else []

        for item in items:
            reagent = LabReagent.objects.filter(
                inventory_item_id=item.id,
                is_deleted=False,
            ).first()

            if reagent:
                reagent.name = item.item_name[:200]
                reagent.item_code = (item.item_code or reagent.item_code)[:50]
                reagent.quantity_on_hand = Decimal(str(item.quantity_on_hand or 0))
                reagent.unit_cost = item.unit_cost
                reagent.unit = item.unit_of_measure or reagent.unit or "units"
                reagent.supplier = (
                    item.preferred_supplier.name if getattr(item, "preferred_supplier", None) else reagent.supplier
                )
                reagent.save()
                updated += 1
            else:
                reagent = LabReagent.objects.create(
                    item_code=(item.item_code or f"LAB-AUTO-{item.id}")[:50],
                    name=item.item_name[:200],
                    category="reagent",
                    inventory_item_id=item.id,
                    quantity_on_hand=Decimal(str(item.quantity_on_hand or 0)),
                    unit=item.unit_of_measure or "units",
                    unit_cost=item.unit_cost,
                    supplier=item.preferred_supplier.name if getattr(item, "preferred_supplier", None) else "",
                    notes=f"Bootstrapped from inventory item {item.id}",
                )
                created += 1

            if link_tests and tests:
                for test in tests:
                    if _test_matches_reagent(test.name, reagent.name):
                        reagent.tests.add(test)
                        linked += 1

        self.stdout.write(self.style.SUCCESS(
            f"Bootstrap complete. Created: {created}, Updated: {updated}, Auto-links: {linked}"
        ))

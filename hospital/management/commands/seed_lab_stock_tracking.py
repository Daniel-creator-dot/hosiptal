from decimal import Decimal

from django.core.management.base import BaseCommand

from hospital.lab_stock_catalog import (
    IMMEASURABLE_REAGENTS,
    MEASURABLE_KITS,
    STOCK_TRACKING_IMMEASURABLE,
    STOCK_TRACKING_MEASURABLE,
    name_matches_aliases,
    should_skip_kit_for_test,
)
from hospital.models import LabTest
from hospital.models_lab_management import LabReagent


class Command(BaseCommand):
    help = (
        "Create measurable kit and chemistry reagent stock rows from the lab letter, "
        "tag matching LabTest catalog rows, and link them for auto-deduct."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show matches without writing.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        tests = list(LabTest.objects.filter(is_deleted=False))
        created_reagents = 0
        updated_reagents = 0
        tagged_tests = 0
        links = 0
        reagents_by_code = {}

        for row in MEASURABLE_KITS:
            reagent, was_created = self._upsert_kit(row, dry=dry)
            reagents_by_code[row["code"]] = reagent
            if was_created:
                created_reagents += 1
            else:
                updated_reagents += 1

        for row in IMMEASURABLE_REAGENTS:
            reagent, was_created = self._upsert_chem(row, dry=dry)
            reagents_by_code[row["code"]] = reagent
            if was_created:
                created_reagents += 1
            else:
                updated_reagents += 1

        for test in tests:
            kit_hits = []
            for row in MEASURABLE_KITS:
                if should_skip_kit_for_test(row, test.name, test.code):
                    continue
                if name_matches_aliases(test.name, test.code, row["aliases"]):
                    kit_hits.append(row)
            chem_hits = []
            for row in IMMEASURABLE_REAGENTS:
                if should_skip_kit_for_test(row, test.name, test.code):
                    continue
                aliases = list(row.get("aliases") or [])
                if row.get("link_only_to_panel"):
                    match_aliases = aliases
                else:
                    match_aliases = aliases + list(row.get("panel_aliases") or [])
                if name_matches_aliases(test.name, test.code, match_aliases):
                    chem_hits.append(row)

            if not kit_hits and not chem_hits:
                continue

            tracking = STOCK_TRACKING_MEASURABLE if kit_hits else STOCK_TRACKING_IMMEASURABLE
            primary = kit_hits[0] if kit_hits else chem_hits[0]
            if not dry:
                test.stock_tracking = tracking
                test.kit_name = primary["name"]
                if tracking == STOCK_TRACKING_MEASURABLE:
                    test.qty_per_box = primary.get("qty_per_box")
                    extra_codes = primary.get("also_link_codes") or []
                    if extra_codes:
                        test.kit_name = "T3, T4, TSH kits"
                else:
                    test.tests_per_kit = primary.get("tests_per_kit")
                    test.reagent_volume_note = primary.get("volume_note") or ""
                test.save(
                    update_fields=[
                        "stock_tracking",
                        "kit_name",
                        "qty_per_box",
                        "tests_per_kit",
                        "reagent_volume_note",
                        "modified",
                    ]
                )
            tagged_tests += 1

            codes_to_link = []
            for row in kit_hits:
                codes_to_link.append(row["code"])
                codes_to_link.extend(row.get("also_link_codes") or [])
            for row in chem_hits:
                codes_to_link.append(row["code"])
            for code in dict.fromkeys(codes_to_link):
                reagent = reagents_by_code.get(code)
                if reagent is None:
                    continue
                if dry:
                    links += 1
                    continue
                if not reagent.tests.filter(pk=test.pk).exists():
                    reagent.tests.add(test)
                    links += 1

        linked_skus = 0
        if not dry:
            from hospital.services.lab_reagent_usage_service import ensure_procurement_item_for_reagent

            for reagent in reagents_by_code.values():
                if reagent and getattr(reagent, "pk", None):
                    ensure_procurement_item_for_reagent(reagent)
                    linked_skus += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Reagents created={created_reagents} updated={updated_reagents}; "
                f"tests tagged={tagged_tests}; new links={links}; store SKUs={linked_skus}"
                + (" (dry-run)" if dry else "")
            )
        )

    def _upsert_kit(self, row, dry=False):
        existing = LabReagent.objects.filter(item_code=row["code"], is_deleted=False).first()
        if dry:
            return existing or LabReagent(item_code=row["code"], name=row["name"]), not bool(existing)
        if existing:
            existing.name = row["name"]
            existing.stock_tracking = STOCK_TRACKING_MEASURABLE
            existing.qty_per_box = row["qty_per_box"]
            existing.qty_consumed_per_test = Decimal("1")
            if existing.unit in ("bottle", ""):
                existing.unit = "pcs"
            existing.save(
                update_fields=[
                    "name",
                    "stock_tracking",
                    "qty_per_box",
                    "qty_consumed_per_test",
                    "unit",
                    "modified",
                ]
            )
            return existing, False
        reagent = LabReagent.objects.create(
            item_code=row["code"],
            name=row["name"],
            category="consumable",
            stock_tracking=STOCK_TRACKING_MEASURABLE,
            qty_per_box=row["qty_per_box"],
            qty_consumed_per_test=Decimal("1"),
            quantity_on_hand=Decimal("0"),
            unit="pcs",
            reorder_level=Decimal(str(row["qty_per_box"])),
            notes="Seeded from measurable labs letter (kit / cassette).",
        )
        return reagent, True

    def _upsert_chem(self, row, dry=False):
        qty_per_test = Decimal(str(row.get("qty_consumed_per_test", 1)))
        unit = row.get("unit") or "tests"
        existing = LabReagent.objects.filter(item_code=row["code"], is_deleted=False).first()
        if dry:
            return existing or LabReagent(item_code=row["code"], name=row["name"]), not bool(existing)
        if existing:
            existing.name = row["name"]
            existing.stock_tracking = STOCK_TRACKING_IMMEASURABLE
            existing.tests_per_kit = row.get("tests_per_kit")
            existing.reagent_volume_note = row.get("volume_note") or ""
            existing.qty_consumed_per_test = qty_per_test
            if existing.unit in ("bottle", "") and unit:
                existing.unit = unit
            existing.save(
                update_fields=[
                    "name",
                    "stock_tracking",
                    "tests_per_kit",
                    "reagent_volume_note",
                    "qty_consumed_per_test",
                    "unit",
                    "modified",
                ]
            )
            return existing, False
        reagent = LabReagent.objects.create(
            item_code=row["code"],
            name=row["name"],
            category="reagent",
            stock_tracking=STOCK_TRACKING_IMMEASURABLE,
            tests_per_kit=row.get("tests_per_kit"),
            reagent_volume_note=row.get("volume_note") or "",
            qty_consumed_per_test=qty_per_test,
            quantity_on_hand=Decimal("0"),
            unit=unit,
            reorder_level=Decimal(str(row["tests_per_kit"] or 0)),
            notes="Seeded from immeasurable labs letter (chemistry).",
        )
        return reagent, True

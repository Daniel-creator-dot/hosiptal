"""
Fix invoice lines with obviously inflated quantities (e.g. ECG 1191 from merge bug).
Sets quantity to 1 and recalculates line_total and invoice totals.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from hospital.models import Invoice, InvoiceLine


# Lines with quantity above this are treated as inflated (procedure/imaging are typically 1)
DEFAULT_QUANTITY_THRESHOLD = 200


class Command(BaseCommand):
    help = (
        "Find invoice lines with quantity above threshold (e.g. 200), set to 1, "
        "recalc line_total and invoice totals. Fixes same issue as ECG001 qty 1191."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be changed",
        )
        parser.add_argument(
            "--threshold",
            type=int,
            default=DEFAULT_QUANTITY_THRESHOLD,
            help=f"Lines with quantity > this are fixed (default {DEFAULT_QUANTITY_THRESHOLD})",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Log each line and invoice updated",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        threshold = options["threshold"]
        verbose = options.get("verbose", False)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made\n"))

        qs = (
            InvoiceLine.objects.filter(is_deleted=False, quantity__gt=threshold)
            .select_related("invoice", "service_code")
            .order_by("invoice_id", "id")
        )
        total_lines = qs.count()
        if total_lines == 0:
            self.stdout.write(self.style.SUCCESS(f"No lines with quantity > {threshold} found."))
            return

        invoices_to_recalc = set()
        fixed_count = 0

        for line in qs:
            code = (getattr(line.service_code, "code", None) or "") if line.service_code else ""
            desc = (getattr(line.service_code, "description", None) or line.description or "")[:40]
            if dry_run:
                if verbose:
                    self.stdout.write(
                        f"  Would fix: {line.invoice.invoice_number} "
                        f"{code} qty {line.quantity} -> 1 (line_total {line.line_total} -> {line.unit_price})"
                    )
                fixed_count += 1
                invoices_to_recalc.add(line.invoice_id)
                continue

            with transaction.atomic():
                line.quantity = Decimal("1")
                # Recalc line_total (same as InvoiceLine.save())
                subtotal = line.quantity * (line.unit_price or Decimal("0"))
                tax = line.tax_amount or Decimal("0")
                discount = line.discount_amount or Decimal("0")
                if discount > subtotal + tax:
                    discount = subtotal + tax
                    line.discount_amount = discount
                line.line_total = subtotal - discount + tax
                line.save(update_fields=["quantity", "line_total", "discount_amount", "modified"])
                fixed_count += 1
                invoices_to_recalc.add(line.invoice_id)
                if verbose:
                    self.stdout.write(
                        f"  Fixed: {line.invoice.invoice_number} {code} qty -> 1, line_total -> {line.line_total}"
                    )

        # Recalculate totals for affected invoices
        if not dry_run and invoices_to_recalc:
            for inv in Invoice.objects.filter(pk__in=invoices_to_recalc, is_deleted=False):
                try:
                    inv.calculate_totals()
                    inv.save(update_fields=["total_amount", "balance", "modified"])
                    if verbose:
                        self.stdout.write(f"  Recalculated: {inv.invoice_number} total={inv.total_amount} balance={inv.balance}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Failed to recalc {inv.invoice_number}: {e}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(f"  Lines fixed (qty set to 1): {fixed_count}")
        self.stdout.write(f"  Invoices recalculated: {len(invoices_to_recalc)}")
        if dry_run and fixed_count > 0:
            self.stdout.write(self.style.WARNING("\nRun without --dry-run to apply changes."))

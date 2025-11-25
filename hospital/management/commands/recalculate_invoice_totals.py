from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal

from hospital.models import Invoice


class Command(BaseCommand):
    help = "Recalculate total_amount and balance for all invoices (use after importing or fixing data)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show changes without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        updated = 0
        total_difference = Decimal("0.00")

        qs = Invoice.objects.filter(is_deleted=False).order_by("issued_at")
        total = qs.count()

        self.stdout.write(f"Recalculating {total} invoices (dry_run={dry_run})...")

        for invoice in qs.iterator():
            old_total = invoice.total_amount or Decimal("0.00")
            old_balance = invoice.balance or Decimal("0.00")

            invoice.calculate_totals()

            if invoice.total_amount != old_total or invoice.balance != old_balance:
                updated += 1
                total_difference += invoice.total_amount - old_total

                self.stdout.write(
                    f"- {invoice.invoice_number}: total {old_total} -> {invoice.total_amount}, "
                    f"balance {old_balance} -> {invoice.balance}"
                )

                if not dry_run:
                    with transaction.atomic():
                        invoice.save(update_fields=["total_amount", "balance", "status"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Recalculation complete. Updated {updated} invoice(s). "
                f"Net total change: {total_difference:.2f} GHS"
            )
        )











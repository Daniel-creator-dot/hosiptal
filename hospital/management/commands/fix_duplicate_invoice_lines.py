"""
Fix duplicate invoice lines (e.g. same ECG001 many times on one invoice).
Merges lines with the same invoice + service_code into one line (sums quantity).
Run to correct outrageous figures from old combine/merge invoice or repeated Add Services.
"""
import uuid

from django.core.management.base import BaseCommand

from hospital.models import Invoice
from hospital.utils_invoice_line import merge_duplicate_lines_on_invoice


class Command(BaseCommand):
    help = (
        "Merge duplicate invoice lines (same invoice + service_code) into one line per service. "
        "Fixes outrageous totals from duplicate ECG/dressing/etc. lines."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be merged, do not change data",
        )
        parser.add_argument(
            "--invoice",
            type=str,
            default=None,
            help="Limit to one invoice (invoice_number or id)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Log each invoice processed",
        )
        parser.add_argument(
            "--insurance-only",
            action="store_true",
            help="Only process invoices with insurance payer (NHIS, private, insurance)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        invoice_arg = options.get("invoice")
        verbose = options.get("verbose", False)
        insurance_only = options.get("insurance_only", False)

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made\n"))

        qs = Invoice.objects.filter(is_deleted=False).select_related("payer")
        if insurance_only:
            qs = qs.filter(payer__payer_type__in=("insurance", "private", "nhis"))
            self.stdout.write(self.style.NOTICE("Filtering to insurance invoices only.\n"))
        if invoice_arg:
            try:
                uid = uuid.UUID(str(invoice_arg).strip())
                qs = qs.filter(pk=uid)
            except (ValueError, TypeError, AttributeError):
                if invoice_arg.isdigit():
                    qs = qs.filter(pk=int(invoice_arg))
                else:
                    qs = qs.filter(invoice_number=invoice_arg)
            if not qs.exists():
                self.stdout.write(self.style.ERROR(f"Invoice not found: {invoice_arg}"))
                return

        total_merged = 0
        invoices_fixed = 0
        for invoice in qs.order_by("id"):
            if dry_run:
                from hospital.models import InvoiceLine
                from django.db.models import Count
                dupes = (
                    InvoiceLine.objects.filter(
                        invoice=invoice, is_deleted=False, waived_at__isnull=True
                    )
                    .values("service_code_id")
                    .annotate(cnt=Count("id"))
                    .filter(cnt__gt=1)
                )
                for d in dupes:
                    total_merged += d["cnt"] - 1
                    if verbose:
                        self.stdout.write(
                            f"  Would merge {d['cnt']} lines (service_code_id={d['service_code_id']}) on {invoice.invoice_number}"
                        )
                if dupes:
                    invoices_fixed += 1
            else:
                n = merge_duplicate_lines_on_invoice(invoice)
                if n > 0:
                    total_merged += n
                    invoices_fixed += 1
                    if verbose:
                        self.stdout.write(f"  {invoice.invoice_number}: merged {n} duplicate line(s)")
                    try:
                        invoice.calculate_totals()
                        invoice.save(update_fields=["total_amount", "balance", "modified"])
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Failed to update totals: {e}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(f"  Invoices with duplicates fixed: {invoices_fixed}")
        self.stdout.write(f"  Duplicate lines merged (removed): {total_merged}")
        if dry_run and total_merged > 0:
            self.stdout.write(self.style.WARNING("\nRun without --dry-run to apply changes."))

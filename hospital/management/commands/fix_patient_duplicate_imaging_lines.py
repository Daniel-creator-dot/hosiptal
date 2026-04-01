"""
Fix duplicate scan lines for a patient (e.g. Opare Enerstina).
- Merges duplicate invoice lines (same invoice + service_code) via merge_duplicate_lines_on_invoice
  (which now caps IMG-* quantity at 1).
- Caps any remaining IMG-* line with quantity > 1 to 1.
Run: python manage.py fix_patient_duplicate_imaging_lines "Opare" "Enerstina"
     python manage.py fix_patient_duplicate_imaging_lines --mrn MRN123
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from hospital.models import Patient, Invoice, InvoiceLine
from hospital.utils_invoice_line import merge_duplicate_lines_on_invoice


class Command(BaseCommand):
    help = (
        "Fix duplicate imaging/scan lines for a patient by name or MRN: "
        "merge duplicate lines, cap IMG-* quantity at 1, recalc totals."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "first_name",
            nargs="?",
            default=None,
            help="Patient first name (e.g. Opare)",
        )
        parser.add_argument(
            "last_name",
            nargs="?",
            default=None,
            help="Patient last name (e.g. Enerstina)",
        )
        parser.add_argument(
            "--mrn",
            type=str,
            default=None,
            help="Patient MRN instead of name",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be changed",
        )
        parser.add_argument(
            "--all-invoices",
            action="store_true",
            help="Process all patient invoices; default is unpaid only",
        )

    def handle(self, *args, **options):
        first_name = (options.get("first_name") or "").strip()
        last_name = (options.get("last_name") or "").strip()
        mrn = (options.get("mrn") or "").strip()
        dry_run = options["dry_run"]
        all_invoices = options["all_invoices"]

        if not mrn and not (first_name and last_name):
            self.stdout.write(
                self.style.ERROR("Provide first name + last name, or --mrn MRN")
            )
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes\n"))

        # Find patient
        if mrn:
            patients = Patient.objects.filter(mrn=mrn, is_deleted=False)
        else:
            patients = Patient.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                is_deleted=False,
            )
        if not patients.exists():
            self.stdout.write(
                self.style.ERROR(f"Patient not found: {first_name} {last_name}" if not mrn else f"MRN {mrn}")
            )
            return
        patient = patients.first()
        self.stdout.write(
            self.style.NOTICE(f"Patient: {patient.full_name} (MRN: {patient.mrn}, id={patient.id})\n")
        )

        # Invoices to process
        inv_qs = Invoice.objects.filter(patient=patient, is_deleted=False)
        if not all_invoices:
            inv_qs = inv_qs.filter(
                status__in=("draft", "issued", "partially_paid", "overdue")
            ).filter(Q(balance__gt=0) | Q(total_amount__gt=0))
        invoices = list(inv_qs.order_by("id"))
        if not invoices:
            self.stdout.write(self.style.SUCCESS("No invoices to process."))
            return

        merged_count = 0
        capped_count = 0
        invoices_updated = set()

        for invoice in invoices:
            if not dry_run:
                n = merge_duplicate_lines_on_invoice(invoice)
                if n > 0:
                    merged_count += n
                    invoices_updated.add(invoice.id)
                    self.stdout.write(
                        f"  {invoice.invoice_number}: merged {n} duplicate line(s)"
                    )

            # Cap any IMG-* line with quantity > 1
            img_lines = (
                InvoiceLine.objects.filter(
                    invoice=invoice,
                    is_deleted=False,
                    service_code__code__startswith="IMG-",
                    quantity__gt=1,
                )
                .select_related("service_code")
            )
            for line in img_lines:
                if dry_run:
                    self.stdout.write(
                        f"  Would cap {invoice.invoice_number} {line.service_code.code} "
                        f"qty {line.quantity} -> 1"
                    )
                    capped_count += 1
                    invoices_updated.add(invoice.id)
                    continue
                with transaction.atomic():
                    line.quantity = Decimal("1")
                    line.line_total = (
                        line.quantity * (line.unit_price or Decimal("0"))
                        - (line.discount_amount or Decimal("0"))
                        + (line.tax_amount or Decimal("0"))
                    )
                    line.save(update_fields=["quantity", "line_total", "modified"])
                    capped_count += 1
                    invoices_updated.add(invoice.id)
                    self.stdout.write(
                        f"  Capped {invoice.invoice_number} {line.service_code.code} qty -> 1"
                    )

        # Recalc totals
        if not dry_run and invoices_updated:
            for inv in Invoice.objects.filter(pk__in=invoices_updated, is_deleted=False):
                try:
                    inv.calculate_totals()
                    inv.save(update_fields=["total_amount", "balance", "modified"])
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Failed to recalc {inv.invoice_number}: {e}")
                    )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(f"  Duplicate lines merged: {merged_count}")
        self.stdout.write(f"  IMG-* lines capped to qty 1: {capped_count}")
        self.stdout.write(f"  Invoices updated: {len(invoices_updated)}")
        if dry_run and (merged_count or capped_count):
            self.stdout.write(
                self.style.WARNING("\nRun without --dry-run to apply changes.")
            )

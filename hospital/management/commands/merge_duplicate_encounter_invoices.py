"""
Merge duplicate invoices per encounter so each encounter has at most one non-deleted invoice.
Use before running migration 1102_invoice_one_per_encounter_constraint.

For each encounter with multiple non-deleted invoices: keeps the oldest (by created),
moves all lines and related references to it, soft-deletes the others.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count


def merge_invoice_into(source, target):
    """Move all lines and references from source to target. Returns True if merged."""
    if source.id == target.id:
        return False

    from hospital.models import InvoiceLine
    from hospital.models_accounting import (
        AccountsReceivable,
        PaymentAllocation,
        PaymentReceipt,
        Transaction,
    )
    from hospital.models_workflow import Bill, PaymentRequest

    # 1. Move InvoiceLines
    InvoiceLine.objects.filter(invoice=source, is_deleted=False).update(invoice=target)

    # 2. Update related FKs
    for model, fk_attr in [
        (Transaction, "invoice"),
        (PaymentReceipt, "invoice"),
        (Bill, "invoice"),
        (PaymentRequest, "invoice"),
    ]:
        try:
            qs = model.objects.filter(**{fk_attr: source})
            if hasattr(model, "is_deleted"):
                qs = qs.exclude(is_deleted=True)
            qs.update(**{fk_attr: target})
        except Exception:
            pass

    try:
        qs = PaymentAllocation.objects.filter(invoice=source)
        if hasattr(PaymentAllocation, "is_deleted"):
            qs = qs.exclude(is_deleted=True)
        qs.update(invoice=target)
    except Exception:
        pass

    try:
        qs = AccountsReceivable.objects.filter(invoice=source)
        if hasattr(AccountsReceivable, "is_deleted"):
            qs = qs.exclude(is_deleted=True)
        qs.update(invoice=target)
    except Exception:
        pass

    try:
        from hospital.models_insurance import InsuranceClaimItem

        InsuranceClaimItem.objects.filter(invoice=source).update(invoice=target)
    except Exception:
        pass

    try:
        from hospital.models_accounting_advanced import AdvancedAccountsReceivable

        src_ar = AdvancedAccountsReceivable.objects.filter(invoice=source).first()
        tgt_ar = AdvancedAccountsReceivable.objects.filter(invoice=target).first()
        if src_ar and not tgt_ar:
            src_ar.invoice = target
            src_ar.save(update_fields=["invoice"])
    except Exception:
        pass

    try:
        from hospital.models_accounting_advanced import DoctorCommission

        DoctorCommission.objects.filter(invoice=source).update(invoice=target)
    except Exception:
        pass

    try:
        from hospital.models_patient_deposits import DepositApplication

        qs = DepositApplication.objects.filter(invoice=source)
        if hasattr(DepositApplication, "is_deleted"):
            qs = qs.exclude(is_deleted=True)
        qs.update(invoice=target)
    except Exception:
        pass

    return True


class Command(BaseCommand):
    help = (
        "Merge duplicate encounter invoices so each encounter has at most one non-deleted invoice. "
        "Run before migration 1102 (one-invoice-per-encounter constraint)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be merged without making changes",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Log each encounter and invoice merged",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options.get("verbose", False)

        from hospital.models import Invoice

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made\n"))

        # All non-deleted invoices with an encounter (use all_objects to include zero-amount)
        qs = getattr(Invoice, "all_objects", Invoice.objects).filter(
            encounter__isnull=False,
            is_deleted=False,
        )

        dupes = (
            qs.values("encounter_id")
            .annotate(cnt=Count("id"))
            .filter(cnt__gt=1)
        )
        encounter_ids = [d["encounter_id"] for d in dupes]

        if not encounter_ids:
            self.stdout.write(
                self.style.SUCCESS("No duplicate encounter invoices found. Safe to run migration 1102.")
            )
            return

        self.stdout.write(
            f"Found {len(encounter_ids)} encounter(s) with more than one non-deleted invoice.\n"
        )

        total_merged = 0
        errors = []

        for encounter_id in encounter_ids:
            invoices = (
                getattr(Invoice, "all_objects", Invoice.objects)
                .filter(encounter_id=encounter_id, is_deleted=False)
                .order_by("created")
            )
            keeper = invoices.first()
            to_merge = list(invoices[1:])
            if not keeper or not to_merge:
                continue

            if verbose:
                self.stdout.write(
                    f"  Encounter {encounter_id}: keep {keeper.invoice_number}, "
                    f"merge {[i.invoice_number for i in to_merge]}"
                )

            if dry_run:
                total_merged += len(to_merge)
                continue

            try:
                with transaction.atomic():
                    for dup in to_merge:
                        merge_invoice_into(dup, keeper)
                        dup.is_deleted = True
                        dup.save(update_fields=["is_deleted", "modified"])
                        total_merged += 1
                    # Merge duplicate lines (e.g. multiple ECG001) that came from merged invoices
                    from hospital.utils_invoice_line import merge_duplicate_lines_on_invoice
                    merge_duplicate_lines_on_invoice(keeper)
                    keeper.calculate_totals()
                    keeper.save(update_fields=["total_amount", "balance", "modified"])
            except Exception as e:
                errors.append((str(encounter_id), str(e)))
                self.stdout.write(
                    self.style.ERROR(f"  Encounter {encounter_id}: {e}")
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(f"  Encounters with duplicates: {len(encounter_ids)}")
        self.stdout.write(f"  Invoices merged (soft-deleted): {total_merged}")
        if errors:
            self.stdout.write(self.style.ERROR(f"  Errors: {len(errors)}"))
        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nRun without --dry-run to apply changes, then: python manage.py migrate hospital 1102")
            )
        elif not errors:
            self.stdout.write(
                self.style.SUCCESS("\nRun: python manage.py migrate hospital 1102")
            )

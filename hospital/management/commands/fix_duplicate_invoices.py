"""
Management command to find and fix duplicate Invoice records in the cashier.
Duplicates = same patient + same encounter (or same patient when encounter is null) created same day.
Merges duplicate invoices: keeps oldest, moves lines and references to it, soft-deletes the rest.
"""
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone


class Command(BaseCommand):
    help = (
        'Find and fix duplicate Invoice records '
        '(same patient+encounter, created same day). Merges into one, soft-deletes rest.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Only consider invoices from last N days (default: 90)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information',
        )
        parser.add_argument(
            '--conservative',
            action='store_true',
            help='Only merge groups of exactly 2 invoices; skip larger groups',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days = options['days']
        verbose = options.get('verbose', False)
        conservative = options.get('conservative', False)

        from hospital.models import Invoice, InvoiceLine

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('FIX DUPLICATE INVOICES'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        if dry_run:
            self.stdout.write(self.style.WARNING('\n*** DRY RUN MODE ***\n'))

        cutoff = timezone.now() - timezone.timedelta(days=days)
        invoices = (
            Invoice.objects.filter(is_deleted=False, created__gte=cutoff)
            .select_related('patient', 'payer', 'encounter')
            .order_by('created')
        )

        # Group by (patient_id, encounter_id, issued_at date)
        # Only merge when same patient + same encounter (non-null) + same day
        # Skip encounter=None - those may be walk-ins/summaries that should stay separate
        groups = defaultdict(list)
        for inv in invoices:
            if inv.encounter_id is None:
                continue  # Don't merge invoices without encounter - could be legit separate
            issued_date = inv.issued_at.date() if inv.issued_at else inv.created.date()
            key = (inv.patient_id, inv.encounter_id, issued_date)
            groups[key].append(inv)

        duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
        if conservative:
            duplicate_groups = {k: v for k, v in duplicate_groups.items() if len(v) == 2}
        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS('\nNo duplicate invoice groups found.'))
            return

        self.stdout.write(f'\nFound {len(duplicate_groups)} duplicate groups\n')

        total_merged = 0
        for key, invs in duplicate_groups.items():
            patient_id, enc_key, issued_date = key
            # Keep oldest (first by created)
            keeper = invs[0]
            duplicates = invs[1:]

            if verbose:
                self.stdout.write(
                    f'\nPatient {keeper.patient_id}, Encounter {enc_key}: '
                    f'keeper={keeper.invoice_number}, dupes={[d.invoice_number for d in duplicates]}'
                )

            if dry_run:
                total_merged += len(duplicates)
                self.stdout.write(
                    f'  Would merge {len(duplicates)} invoice(s) into {keeper.invoice_number}'
                )
                continue

            try:
                with transaction.atomic():
                    for dup in duplicates:
                        merged = self._merge_invoice_into(dup, keeper)
                        if merged:
                            total_merged += 1
                            dup.is_deleted = True
                            dup.save(update_fields=['is_deleted', 'modified'])
                            if verbose:
                                self.stdout.write(f'  Merged {dup.invoice_number} -> {keeper.invoice_number}')
                    # Merge duplicate lines (e.g. same service_code from merged invoices) so totals are correct
                    from hospital.utils_invoice_line import merge_duplicate_lines_on_invoice
                    merge_duplicate_lines_on_invoice(keeper)
                    keeper.calculate_totals()
                    keeper.save(update_fields=['total_amount', 'balance', 'status'])
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'Duplicate groups: {len(duplicate_groups)}')
        self.stdout.write(f'Invoices merged (soft-deleted): {total_merged}')
        if dry_run:
            self.stdout.write(self.style.WARNING('\nRun without --dry-run to apply changes'))

    def _merge_invoice_into(self, source, target):
        """Move all lines and references from source to target. Returns True if merged."""
        from hospital.models import InvoiceLine
        from hospital.models_accounting import Transaction, PaymentReceipt, PaymentAllocation, AccountsReceivable
        from hospital.models_workflow import Bill, PaymentRequest
        from hospital.models_insurance import InsuranceClaimItem

        if source.id == target.id:
            return False

        # 1. Move InvoiceLines
        InvoiceLine.objects.filter(invoice=source, is_deleted=False).update(invoice=target)

        # 2. Update related FKs
        for model, fk_attr in [
            (Transaction, 'invoice'),
            (PaymentReceipt, 'invoice'),
            (Bill, 'invoice'),
            (PaymentRequest, 'invoice'),
        ]:
            try:
                qs = model.objects.filter(**{fk_attr: source})
                if hasattr(model, 'is_deleted'):
                    qs = qs.exclude(is_deleted=True)
                qs.update(**{fk_attr: target})
            except Exception:
                pass

        try:
            qs = PaymentAllocation.objects.filter(invoice=source)
            if hasattr(PaymentAllocation, 'is_deleted'):
                qs = qs.exclude(is_deleted=True)
            qs.update(invoice=target)
        except Exception:
            pass

        try:
            qs = AccountsReceivable.objects.filter(invoice=source)
            if hasattr(AccountsReceivable, 'is_deleted'):
                qs = qs.exclude(is_deleted=True)
            qs.update(invoice=target)
        except Exception:
            pass

        try:
            InsuranceClaimItem.objects.filter(invoice=source).update(invoice=target)
        except Exception:
            pass

        # Advanced AR: OneToOne - only move if target doesn't have one
        try:
            from hospital.models_accounting_advanced import AdvancedAccountsReceivable
            src_ar = AdvancedAccountsReceivable.objects.filter(invoice=source).first()
            tgt_ar = AdvancedAccountsReceivable.objects.filter(invoice=target).first()
            if src_ar and not tgt_ar:
                src_ar.invoice = target
                src_ar.save(update_fields=['invoice'])
        except Exception:
            pass

        # DoctorCommission: FK not OneToOne, safe to update
        try:
            from hospital.models_accounting_advanced import DoctorCommission
            DoctorCommission.objects.filter(invoice=source).update(invoice=target)
        except Exception:
            pass

        # Patient deposits
        try:
            from hospital.models_patient_deposits import DepositApplication
            qs = DepositApplication.objects.filter(invoice=source)
            if hasattr(DepositApplication, 'is_deleted'):
                qs = qs.exclude(is_deleted=True)
            qs.update(invoice=target)
        except Exception:
            pass

        return True

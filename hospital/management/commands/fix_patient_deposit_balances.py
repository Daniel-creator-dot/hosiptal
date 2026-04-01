"""
Fix patient deposit balances - recalculate available_balance from deposit_amount - used_amount.
Use when deposits show wrong available balance (e.g. 4000 total but only 100 applied).
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum
from decimal import Decimal
from hospital.models_patient_deposits import PatientDeposit, DepositApplication


class Command(BaseCommand):
    help = 'Recalculate patient deposit available_balance from deposit_amount minus applied amount'

    def add_arguments(self, parser):
        parser.add_argument(
            '--patient',
            type=str,
            help='MRN or patient name to fix (e.g. "Patricia" or "Debrah")',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )

    def handle(self, *args, **options):
        patient_filter = (options.get('patient') or '').strip()
        dry_run = options.get('dry_run', False)

        from django.db.models import Q
        qs = PatientDeposit.objects.filter(is_deleted=False).select_related('patient')
        if patient_filter:
            qs = qs.filter(
                Q(patient__first_name__icontains=patient_filter)
                | Q(patient__last_name__icontains=patient_filter)
                | Q(patient__mrn__icontains=patient_filter)
            )

        fixed = 0
        for dep in qs.order_by('patient', 'deposit_date'):
            applied_sum = DepositApplication.objects.filter(
                deposit=dep,
                is_deleted=False
            ).aggregate(s=Sum('applied_amount'))['s'] or Decimal('0.00')
            expected_available = dep.deposit_amount - applied_sum
            if expected_available != dep.available_balance:
                self.stdout.write(
                    f"Deposit {dep.deposit_number} ({dep.patient.full_name}): "
                    f"available={dep.available_balance} -> {expected_available} "
                    f"(deposit_amount={dep.deposit_amount}, applied={applied_sum})"
                )
                if not dry_run:
                    dep.available_balance = expected_available
                    dep.used_amount = applied_sum
                    if dep.available_balance <= 0 and dep.used_amount > 0:
                        dep.status = 'fully_used'
                    elif dep.available_balance > 0:
                        dep.status = 'active'
                    dep.save(update_fields=['available_balance', 'used_amount', 'status'])
                    fixed += 1

        if dry_run and fixed == 0:
            self.stdout.write("No discrepancies found (or no matches).")
        elif fixed > 0:
            self.stdout.write(self.style.SUCCESS(f"Fixed {fixed} deposit(s)."))
        elif not dry_run:
            self.stdout.write("No deposits needed fixing.")

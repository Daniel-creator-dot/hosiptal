"""
Restore patient deposit stuck on cancelled/soft-deleted invoices, then optionally
apply restored credit to open cash invoices.

Usage:
  python manage.py heal_stuck_deposit_applications
  python manage.py heal_stuck_deposit_applications --dry-run
  python manage.py heal_stuck_deposit_applications --no-apply
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = (
        'Free deposit applications stuck on cancelled/deleted invoices and '
        'optionally apply restored credit to open bills.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report affected patients/amounts without writing changes.',
        )
        parser.add_argument(
            '--no-apply',
            action='store_true',
            help='Only restore stuck deposit; do not apply to open invoices.',
        )
        parser.add_argument(
            '--patient-id',
            type=str,
            default='',
            help='Limit to one patient UUID.',
        )

    def handle(self, *args, **options):
        from hospital.models import Patient
        from hospital.models_patient_deposits import DepositApplication
        from hospital.services.deposit_payment_service import heal_patient_deposits_for_billing

        dry_run = options['dry_run']
        apply_restored = not options['no_apply']
        patient_id = (options.get('patient_id') or '').strip()

        apps = DepositApplication.objects.filter(
            is_deleted=False,
            deposit__is_deleted=False,
        ).filter(
            Q(invoice__status='cancelled') | Q(invoice__is_deleted=True)
        ).select_related('deposit', 'deposit__patient', 'invoice')

        if patient_id:
            apps = apps.filter(deposit__patient_id=patient_id)

        by_patient = {}
        for app in apps.iterator(chunk_size=200):
            dep = app.deposit
            if not dep or not dep.patient_id:
                continue
            pid = dep.patient_id
            row = by_patient.setdefault(
                pid,
                {'patient': dep.patient, 'stuck': Decimal('0.00'), 'invoices': set()},
            )
            row['stuck'] += app.applied_amount or Decimal('0.00')
            if app.invoice_id:
                row['invoices'].add(str(app.invoice_id))

        if not by_patient:
            self.stdout.write(self.style.SUCCESS('No stuck deposit applications found.'))
            return

        self.stdout.write(
            f'Found {len(by_patient)} patient(s) with deposit stuck on cancelled/deleted invoices.'
        )
        total_restored = Decimal('0.00')
        total_applied = Decimal('0.00')

        for pid, info in by_patient.items():
            patient = info['patient']
            if patient is None:
                try:
                    patient = Patient.objects.get(pk=pid)
                except Patient.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f'Skip missing patient {pid}'))
                    continue
            mrn = getattr(patient, 'mrn', '') or str(pid)
            self.stdout.write(
                f'  {mrn}: stuck GHS {info["stuck"]:.2f} on {len(info["invoices"])} invoice(s)'
            )
            if dry_run:
                total_restored += info['stuck']
                continue
            result = heal_patient_deposits_for_billing(patient, apply_restored=apply_restored)
            total_restored += result.get('restored') or Decimal('0.00')
            total_applied += result.get('applied') or Decimal('0.00')
            self.stdout.write(
                f'    restored GHS {result.get("restored", 0):.2f}, '
                f'applied GHS {result.get("applied", 0):.2f}, '
                f'available GHS {result.get("available", 0):.2f}'
            )

        prefix = 'DRY-RUN totals' if dry_run else 'Done'
        self.stdout.write(
            self.style.SUCCESS(
                f'{prefix}: restored GHS {total_restored:.2f}, applied GHS {total_applied:.2f}'
            )
        )

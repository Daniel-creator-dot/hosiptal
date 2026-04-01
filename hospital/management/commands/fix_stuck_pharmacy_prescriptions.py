"""
Fix prescriptions that were sent to cashier but got stuck (missing from both pharmacy and cashier).

This can happen when:
- Send-to-cashier errored partway
- Old merge logic orphaned prescriptions (waived their lines but linked merged line to another rx)

Run: python manage.py fix_stuck_pharmacy_prescriptions "agnes aboagyewa"
     python manage.py fix_stuck_pharmacy_prescriptions  # finds all stuck prescriptions
"""
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = "Fix pharmacy prescriptions stuck between pharmacy and cashier (e.g. after send error)"

    def add_arguments(self, parser):
        parser.add_argument(
            'patient_name',
            nargs='?',
            default='',
            help='Patient name to search (e.g. "agnes aboagyewa"). Omit to find all stuck.',
        )
        parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without making changes')

    def handle(self, *args, **options):
        from hospital.models import Patient, Prescription, InvoiceLine
        from hospital.models_payment_verification import PharmacyDispensing
        from hospital.services.auto_billing_service import AutoBillingService

        patient_name = (options.get('patient_name') or '').strip()
        dry_run = options.get('dry_run', False)

        if patient_name:
            patients = Patient.objects.filter(is_deleted=False).filter(
                Q(first_name__icontains=patient_name) |
                Q(last_name__icontains=patient_name) |
                Q(mrn__icontains=patient_name)
            )
            if ' ' in patient_name:
                parts = patient_name.split(None, 1)
                patients = patients | Patient.objects.filter(
                    is_deleted=False,
                    first_name__icontains=parts[0],
                    last_name__icontains=parts[-1]
                )
        else:
            patients = Patient.objects.filter(is_deleted=False)

        fixed = 0
        for patient in patients.distinct():
            self.stdout.write(f"\nPatient: {patient.full_name} (MRN: {patient.mrn})")
            # Prescriptions with dispensing pending_payment, not paid
            dispensings = PharmacyDispensing.objects.filter(
                patient=patient,
                is_deleted=False,
                dispensing_status='pending_payment',
                payment_receipt_id__isnull=True,
            ).exclude(
                quantity_ordered__lte=0
            ).select_related('prescription', 'prescription__drug', 'prescription__order')

            for disp in dispensings:
                rx = disp.prescription
                if not rx or rx.is_deleted:
                    continue
                # Check: has only waived lines or no active line for this prescription
                active_lines = InvoiceLine.objects.filter(
                    prescription=rx,
                    is_deleted=False,
                    waived_at__isnull=True
                )
                if active_lines.exists():
                    continue  # Has active bill, not stuck
                waived = InvoiceLine.objects.filter(
                    prescription=rx,
                    is_deleted=False,
                    waived_at__isnull=False
                ).exists()
                if not waived:
                    continue  # No line at all - might not have been sent yet
                # Stuck: has waived line(s) but no active line
                drug = disp.drug_to_dispense or rx.drug
                qty = disp.quantity_ordered or rx.quantity or 0
                self.stdout.write(
                    f"  Stuck: {drug.name} x{qty} (rx={rx.id})"
                )
                if dry_run:
                    self.stdout.write(self.style.WARNING("    [dry-run] Would re-create bill"))
                    fixed += 1
                    continue
                result = AutoBillingService.create_pharmacy_bill(
                    rx,
                    substitute_drug=disp.substitute_drug if hasattr(disp, 'substitute_drug') else None,
                    quantity_override=int(qty)
                )
                if result.get('success'):
                    self.stdout.write(self.style.SUCCESS(f"    Fixed: GHS {result.get('amount')}"))
                    fixed += 1
                else:
                    self.stdout.write(self.style.ERROR(f"    Failed: {result.get('message', result.get('error'))}"))

        self.stdout.write(self.style.SUCCESS(f"\nDone. Fixed {fixed} prescription(s)."))

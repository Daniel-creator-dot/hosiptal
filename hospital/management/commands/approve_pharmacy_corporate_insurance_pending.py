"""
Approve all pending pharmacy dispensing records for corporate and insurance patients.

These patients are billed to the company/insurer (no cash at till). This command
marks all such pending_payment PharmacyDispensing as ready_to_dispense so they
no longer show in pharmacy payment verification and can be dispensed. Also reduces
pharmacy stock so drug quantities go down (under patient bill).

Run: python manage.py approve_pharmacy_corporate_insurance_pending [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from hospital.models_payment_verification import PharmacyDispensing
from hospital.models import Payer


INSURANCE_CORPORATE_PAYER_TYPES = ('insurance', 'private', 'nhis', 'corporate')


def patient_has_corporate_or_insurance(patient):
    """True if patient has a corporate or insurance payer (primary_insurance or encounter invoice)."""
    if not patient:
        return False
    payer = getattr(patient, 'primary_insurance', None)
    if payer and getattr(payer, 'payer_type', None) in INSURANCE_CORPORATE_PAYER_TYPES:
        return True
    # Fallback: check encounter's invoice payer
    try:
        from hospital.models import Encounter
        enc = Encounter.objects.filter(patient=patient, is_deleted=False).order_by('-created').first()
        if enc and getattr(enc, 'current_invoice', None):
            inv = enc.current_invoice
            if inv and inv.payer_id and getattr(inv.payer, 'payer_type', None) in INSURANCE_CORPORATE_PAYER_TYPES:
                return True
    except Exception:
        pass
    return False


class Command(BaseCommand):
    help = 'Approve all pending pharmacy items for corporate and insurance (mark ready to dispense)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report what would be updated',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN – no changes will be saved'))

        qs = PharmacyDispensing.objects.filter(
            is_deleted=False,
            dispensing_status='pending_payment',
        ).select_related('patient', 'prescription', 'prescription__order', 'prescription__order__encounter')

        approved = 0
        for disp in qs:
            patient = disp.patient
            if not patient_has_corporate_or_insurance(patient):
                continue
            if dry_run:
                drug_name = getattr(disp.prescription.drug, 'name', '?') if disp.prescription_id else '?'
                qty = getattr(disp, 'quantity_ordered', None) or (getattr(disp.prescription, 'quantity', 0) if disp.prescription_id else 0)
                self.stdout.write(
                    f'  Would approve & reduce stock: RX {disp.prescription_id} – {drug_name} x{qty} – {patient.full_name}'
                )
                approved += 1
                continue
            disp.dispensing_status = 'ready_to_dispense'
            disp.payment_verified_at = timezone.now()
            update_fields = ['dispensing_status', 'payment_verified_at', 'modified']
            drug_to_dispense = disp.drug_to_dispense or (disp.prescription.drug if disp.prescription_id else None)
            qty = int(disp.quantity_ordered or (getattr(disp.prescription, 'quantity', 0) if disp.prescription_id else 0))
            if drug_to_dispense and qty > 0 and not getattr(disp, 'stock_reduced_at', None):
                from hospital.models_payment_verification import PharmacyStockDeductionLog
                from hospital.pharmacy_stock_utils import reduce_pharmacy_stock_once

                shortfall = reduce_pharmacy_stock_once(
                    drug_to_dispense,
                    qty,
                    PharmacyStockDeductionLog.SOURCE_PHARMACY_DISPENSING,
                    disp.id,
                )
                disp.stock_reduced_at = timezone.now()
                update_fields.append('stock_reduced_at')
                if shortfall > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  Stock shortfall {shortfall} for {drug_to_dispense.name} – RX {disp.prescription_id}'
                        )
                    )
            disp.save(update_fields=update_fields)
            approved += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'  Approved (stock reduced): RX {disp.prescription_id} – {getattr(disp.prescription.drug, "name", "?")} x{qty} – {patient.full_name}'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f'\nDone. Approved {approved} pending pharmacy item(s) for corporate/insurance.')
        )

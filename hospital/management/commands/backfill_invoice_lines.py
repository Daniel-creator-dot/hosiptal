from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from hospital.models import Invoice, InvoiceLine, ServiceCode


class Command(BaseCommand):
    help = (
        "Backfill InvoiceLine records for invoices that only have payment receipts. "
        "This uses receipt service_details to reconstruct reasonable line descriptions."
    )

    SERVICE_CODE_MAP = {
        'pharmacy_walkin': ('PHARM-WALKIN', 'Walk-in Pharmacy Sale', 'Pharmacy Services'),
        'pharmacy_prescription': ('PHARM-RX', 'Pharmacy Prescription', 'Pharmacy Services'),
        'pharmacy': ('PHARM-GENERAL', 'Pharmacy Sale', 'Pharmacy Services'),
        'medication': ('MED-GENERAL', 'Medication Sale', 'Pharmacy Services'),
        'lab': ('LAB-GENERAL', 'Laboratory Test', 'Laboratory Services'),
        'imaging': ('IMG-GENERAL', 'Imaging/Radiology', 'Imaging Services'),
        'imaging_study': ('IMG-STUDY', 'Imaging Study', 'Imaging Services'),
        'consultation': ('CONSULT', 'Consultation Fee', 'Clinical Services'),
        'admission': ('ADMISSION', 'Admission / Bed Charge', 'Inpatient Services'),
        'procedure': ('PROCEDURE', 'Medical Procedure', 'Clinical Services'),
        'combined': ('COMBINED', 'Combined Services', 'Clinical Services'),
        'other': ('OTHER', 'Hospital Service', 'Clinical Services'),
    }

    def handle(self, *args, **options):
        invoices = (
            Invoice.objects.filter(is_deleted=False)
            .prefetch_related('receipts')
            .order_by('issued_at')
        )

        updated = 0
        for invoice in invoices.iterator():
            if invoice.lines.filter(is_deleted=False).exists():
                continue

            receipts = invoice.receipts.filter(is_deleted=False)
            if not receipts.exists():
                continue

            created_lines = self._build_lines_from_receipts(invoice, receipts)
            if not created_lines:
                continue

            invoice.calculate_totals()
            if invoice.status == 'paid':
                invoice.balance = Decimal('0.00')
            invoice.save(update_fields=['total_amount', 'balance', 'status'])
            updated += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated invoice {invoice.invoice_number} with {created_lines} line(s)."
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Done. Updated {updated} invoice(s)."))

    def _build_lines_from_receipts(self, invoice, receipts):
        line_count = 0
        for receipt in receipts:
            details = receipt.service_details or {}
            svc_code, description, category = self.SERVICE_CODE_MAP.get(
                receipt.service_type,
                self.SERVICE_CODE_MAP['other'],
            )
            service_code, _ = ServiceCode.objects.get_or_create(
                code=svc_code,
                defaults={
                    'description': description,
                    'category': category,
                    'is_active': True,
                },
            )

            if receipt.service_type == 'pharmacy_walkin' and details.get('items'):
                for item in details['items']:
                    item_desc = (
                        f"{item.get('drug')} {item.get('strength', '')}".strip()
                        or description
                    )
                    InvoiceLine.objects.create(
                        invoice=invoice,
                        service_code=service_code,
                        description=f"{item_desc} (Sale {details.get('sale_number', '')})",
                        quantity=Decimal(str(item.get('quantity', 1))),
                        unit_price=Decimal(str(item.get('unit_price', receipt.amount_paid))),
                        line_total=Decimal(str(item.get('line_total', receipt.amount_paid))),
                    )
                    line_count += 1
                continue

            # Generic line fall-back
            line_description = self._derive_description(receipt, details, default=description)
            quantity = Decimal(str(details.get('quantity', 1)))
            unit_price = Decimal(str(details.get('unit_price', receipt.amount_paid)))
            line_total = Decimal(str(details.get('line_total', receipt.amount_paid)))

            InvoiceLine.objects.create(
                invoice=invoice,
                service_code=service_code,
                description=line_description,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
            line_count += 1

        return line_count

    @staticmethod
    def _derive_description(receipt, details, default):
        return (
            details.get('drug_name')
            or details.get('test_name')
            or details.get('procedure_name')
            or details.get('study_type')
            or details.get('sale_number')
            or receipt.notes
            or f"{default} - {receipt.receipt_number}"
        )


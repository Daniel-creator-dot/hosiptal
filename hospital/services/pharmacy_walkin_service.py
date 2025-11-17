"""
Helper utilities for Walk-in Pharmacy sales.
Handles automatic patient linkage and payment receipt generation
so cashier workflows stay consistent with prescriptions/lab/imaging.
"""
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

from ..models import Patient
from ..models_pharmacy_walkin import WalkInPharmacySale
from .unified_receipt_service import UnifiedReceiptService


class WalkInPharmacyService:
    """Utility helpers for walk-in pharmacy workflows."""

    @staticmethod
    def ensure_sale_patient(sale: WalkInPharmacySale) -> Patient:
        """
        Guarantee that a walk-in sale is linked to a Patient record.
        Creates a lightweight patient profile when customer chose "walk-in".
        """
        if sale.patient:
            return sale.patient

        customer_name = (sale.customer_name or "Walk-in Customer").strip()
        if " " in customer_name:
            first_name, last_name = customer_name.split(" ", 1)
        else:
            first_name, last_name = customer_name, f"WALKIN-{sale.sale_number}"

        patient = Patient.objects.create(
            first_name=first_name or "Walk-in",
            last_name=last_name or sale.sale_number,
            phone_number=sale.customer_phone or "",
            address=sale.customer_address or "Walk-in pharmacy customer",
            gender='O',
        )

        sale.patient = patient
        sale.customer_type = 'registered'
        sale.save(update_fields=['patient', 'customer_type', 'modified'])
        return patient

    @staticmethod
    def serialize_items(sale: WalkInPharmacySale):
        """Return a clean list of sale items for service_details JSON."""
        items = []
        for item in sale.items.filter(is_deleted=False).select_related('drug'):
            items.append({
                'drug': item.drug.name,
                'strength': item.drug.strength,
                'form': item.drug.form,
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'line_total': str(item.line_total),
            })
        return items

    @staticmethod
    def ensure_sale_invoice(sale: WalkInPharmacySale, patient: Patient):
        """Create or update an Invoice with line items for this walk-in sale."""
        from hospital.models import Invoice, InvoiceLine, ServiceCode, Payer

        payer = patient.primary_insurance
        if not payer or getattr(payer, 'is_deleted', False):
            payer = (
                Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
                or Payer.objects.filter(is_active=True, is_deleted=False).first()
            )
            if not payer:
                payer = Payer.objects.create(name='Cash', payer_type='cash', is_active=True)

        invoice = Invoice.objects.filter(
            patient=patient,
            is_deleted=False,
            lines__description__icontains=sale.sale_number
        ).order_by('-issued_at').first()

        if not invoice:
            invoice = Invoice.objects.create(
                patient=patient,
                payer=payer,
                status='issued',
                encounter=None,
                issued_at=sale.sale_date,
                due_at=sale.sale_date + timedelta(days=7),
            )

        for item in sale.items.filter(is_deleted=False).select_related('drug'):
            service_code, _ = ServiceCode.objects.get_or_create(
                code=f"WALKIN-{item.drug.pk}",
                defaults={
                    'description': f"{item.drug.name} {item.drug.strength}",
                    'category': 'Pharmacy Services',
                    'is_active': True,
                },
            )

            description = f"{item.drug.name} {item.drug.strength} (Sale {sale.sale_number})"
            InvoiceLine.objects.update_or_create(
                invoice=invoice,
                service_code=service_code,
                description=description,
                defaults={
                    'quantity': Decimal(str(item.quantity)),
                    'unit_price': item.unit_price,
                    'line_total': item.line_total,
                },
            )

        invoice.status = 'issued'
        invoice.calculate_totals()
        invoice.save(update_fields=['total_amount', 'balance', 'status'])
        return invoice

    @staticmethod
    def create_payment_receipt(sale: WalkInPharmacySale, amount: Decimal, payment_method: str,
                               received_by_user, notes: str = ""):
        """
        Generate a unified receipt for a walk-in sale and sync accounting.
        """
        patient = WalkInPharmacyService.ensure_sale_patient(sale)

        invoice = WalkInPharmacyService.ensure_sale_invoice(sale, patient)

        service_details = {
            'sale_id': str(sale.id),
            'sale_number': sale.sale_number,
            'customer_name': sale.customer_name,
            'customer_phone': sale.customer_phone,
            'total_amount': str(sale.total_amount),
            'items': WalkInPharmacyService.serialize_items(sale),
            'created': sale.sale_date.isoformat(),
        }

        receipt_notes = notes or f"Walk-in sale {sale.sale_number}"

        result = UnifiedReceiptService.create_receipt_with_qr(
            patient=patient,
            amount=amount,
            payment_method=payment_method,
            received_by_user=received_by_user,
            invoice=invoice,
            service_type='pharmacy_walkin',
            service_details=service_details,
            notes=receipt_notes,
        )

        if result.get('success'):
            # Update sale payment figures & timestamps
            sale.amount_paid = (sale.amount_paid or Decimal('0.00')) + amount
            sale.save()
        return result


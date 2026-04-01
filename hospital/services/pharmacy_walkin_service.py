"""
Helper utilities for Walk-in Pharmacy sales.
Handles automatic patient linkage and payment receipt generation
so cashier workflows stay consistent with prescriptions/lab/imaging.
"""
from decimal import Decimal
from datetime import timedelta

from django.db import transaction
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
        CRITICAL: Checks for duplicates before creating to prevent duplicate patients.
        """
        if sale.patient:
            return sale.patient

        customer_name = (sale.customer_name or "Walk-in Customer").strip()
        if " " in customer_name:
            first_name, last_name = customer_name.split(" ", 1)
        else:
            first_name, last_name = customer_name, f"WALKIN-{sale.sale_number}"

        # CRITICAL: Check for duplicate patient before creating
        # Normalize phone number for comparison
        def normalize_phone(phone):
            if not phone:
                return ''
            phone = str(phone).strip()
            phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if phone.startswith('0') and len(phone) == 10:
                phone = '233' + phone[1:]
            elif phone.startswith('+'):
                phone = phone[1:]
            return phone

        normalized_phone = normalize_phone(sale.customer_phone or "")
        
        # Check for existing patient by name + phone
        existing_patient = None
        if first_name and last_name and normalized_phone:
            from django.db.models import Q
            candidates = Patient.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                is_deleted=False
            )
            for candidate in candidates:
                if normalize_phone(candidate.phone_number) == normalized_phone:
                    existing_patient = candidate
                    break
        
        # If no duplicate found, create new patient
        if not existing_patient:
            from django.db import transaction
            with transaction.atomic():
                # Double-check inside transaction to prevent race conditions
                if first_name and last_name and normalized_phone:
                    candidates = Patient.objects.select_for_update().filter(
                        first_name__iexact=first_name,
                        last_name__iexact=last_name,
                        is_deleted=False
                    )
                    for candidate in candidates:
                        if normalize_phone(candidate.phone_number) == normalized_phone:
                            existing_patient = candidate
                            break
                
                if not existing_patient:
                    patient = Patient.objects.create(
                        first_name=first_name or "Walk-in",
                        last_name=last_name or sale.sale_number,
                        phone_number=sale.customer_phone or "",
                        address=sale.customer_address or "Walk-in pharmacy customer",
                        gender='O',
                    )
                else:
                    patient = existing_patient
        else:
            patient = existing_patient

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
    def _cancel_duplicate_prescribe_invoices_for_sale(sale: WalkInPharmacySale, patient: Patient, keep_invoice):
        """
        If multiple open invoices contain lines for this prescribe sale_number (double-submit /
        race / VisibleManager missing a draft), cancel extras that are prescribe-only clones
        so Total Bill does not show the same basket twice.
        """
        from hospital.models import Invoice

        sn = (sale.sale_number or '').strip()
        if not sn or not keep_invoice or not getattr(keep_invoice, 'pk', None):
            return

        candidates = list(
            Invoice.all_objects.filter(patient=patient, is_deleted=False)
            .exclude(status__in=['cancelled', 'paid'])
            .filter(lines__description__icontains=sn)
            .distinct()
            .order_by('issued_at', 'pk')
        )
        if len(candidates) <= 1:
            return

        # Prefer the invoice we just synced lines onto (not necessarily oldest).
        ordered = [keep_invoice] + [i for i in candidates if i.pk != keep_invoice.pk]

        for inv in ordered[1:]:
            if inv.pk == keep_invoice.pk:
                continue
            inv.refresh_from_db()
            if inv.status in ('cancelled', 'paid'):
                continue
            paid = (inv.total_amount or Decimal('0.00')) - (inv.balance or Decimal('0.00'))
            if paid > Decimal('0.00'):
                continue
            billable = inv.lines.filter(is_deleted=False, waived_at__isnull=True)
            if not billable.exists():
                inv.status = 'cancelled'
                inv.save(update_fields=['status', 'modified'])
                continue
            if all(sn in (line.description or '') for line in billable):
                inv.status = 'cancelled'
                inv.save(update_fields=['status', 'modified'])

    @staticmethod
    def ensure_sale_invoice(sale: WalkInPharmacySale, patient: Patient):
        """Create or update an Invoice with line items for this walk-in sale."""
        from hospital.models import Invoice, InvoiceLine, ServiceCode, Payer

        # Use sale's payer if set (Cash/Corporate/Insurance), else patient's primary_insurance, else cash
        payer = sale.payer
        if not payer or getattr(payer, 'is_deleted', False):
            payer = patient.primary_insurance
        if not payer or getattr(payer, 'is_deleted', False):
            payer = (
                Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
                or Payer.objects.filter(is_active=True, is_deleted=False).first()
            )
            if not payer:
                payer = Payer.objects.create(name='Cash', payer_type='cash', is_active=True)

        with transaction.atomic():
            # Use all_objects: default Invoice manager hides total_amount=0 drafts, which caused
            # a second invoice to be created for the same sale (duplicate Total Bill rows).
            # Never reuse cancelled or paid invoices — "Remove from bill" must stay cancelled.
            invoice = (
                Invoice.all_objects.filter(patient=patient, is_deleted=False)
                .exclude(status__in=['cancelled', 'paid'])
                .filter(lines__description__icontains=sale.sale_number)
                .order_by('-issued_at')
                .select_for_update(of=('self',), skip_locked=False)
                .first()
            )

            if not invoice:
                invoice = Invoice.all_objects.create(
                    patient=patient,
                    payer=payer,
                    status='issued',
                    encounter=None,
                    issued_at=sale.sale_date,
                    due_at=sale.sale_date + timedelta(days=7),
                )

            for item in sale.items.filter(is_deleted=False).select_related('drug'):
                # Generate a code that fits within the 20-character limit
                # "WALKIN-" is 7 chars, so we use first 13 chars of UUID (without hyphens)
                drug_uuid_str = str(item.drug.pk).replace('-', '')[:13]
                service_code, _ = ServiceCode.objects.get_or_create(
                    code=f"WALKIN-{drug_uuid_str}",
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

            # Do not downgrade partially_paid or reopen cancelled (cancelled cannot reach here).
            if invoice.status == 'draft':
                invoice.status = 'issued'
            invoice.calculate_totals()
            invoice.save(update_fields=['total_amount', 'balance', 'status'])
            WalkInPharmacyService._cancel_duplicate_prescribe_invoices_for_sale(
                sale, patient, invoice
            )

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

        receipt_notes = notes or f"Prescribe sale {sale.sale_number}"

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


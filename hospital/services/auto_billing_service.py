"""
💰 AUTOMATIC BILLING SERVICE
Auto-generates bills when services are ordered
Ensures payment before service delivery
"""
from datetime import timedelta
from decimal import Decimal
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class AutoBillingService:
    """
    Automatically create bills when services are ordered
    Ensures payment control from the start
    """

    @staticmethod
    def create_lab_bill(lab_result):
        """
        Auto-create bill when lab test is ordered

        Args:
            lab_result: LabResult object

        Returns:
            dict with bill and invoice details
        """
        from hospital.models import InvoiceLine
        from hospital.models_payment_verification import LabResultRelease

        try:
            with transaction.atomic():
                patient = lab_result.order.encounter.patient
                encounter = lab_result.order.encounter
                test = lab_result.test

                payer = AutoBillingService._ensure_payer(patient)
                invoice, _ = AutoBillingService._get_or_create_invoice(patient, encounter, payer)

                service_code = AutoBillingService._get_or_create_service_code(
                    code=f"LAB-{test.code}",
                    description=test.name,
                    category='Laboratory Services',
                    default_price=test.price or Decimal('0.00')
                )

                unit_price = AutoBillingService._resolve_price(patient, payer, service_code, test.price)

                invoice_line, created = InvoiceLine.objects.get_or_create(
                    invoice=invoice,
                    service_code=service_code,
                    defaults={
                        'description': test.name,
                        'quantity': Decimal('1.00'),
                        'unit_price': unit_price,
                        'line_total': unit_price
                    }
                )

                if not created:
                    invoice_line.quantity += Decimal('1.00')
                    invoice_line.unit_price = unit_price
                    invoice_line.save()

                AutoBillingService._finalize_invoice(invoice)

                release_record, _ = LabResultRelease.objects.get_or_create(
                    lab_result=lab_result,
                    patient=patient,
                    defaults={'release_status': 'pending_payment'}
                )

                logger.info(
                    "✅ Auto-bill created for %s - %s - GHS %s",
                    test.name,
                    patient.full_name,
                    unit_price,
                )

                return {
                    'success': True,
                    'invoice': invoice,
                    'invoice_line': invoice_line,
                    'amount': unit_price,
                    'release_record': release_record,
                    'message': f'Bill created: GHS {unit_price} for {test.name}',
                }

        except Exception as exc:
            logger.error("❌ Error creating lab bill: %s", exc, exc_info=True)
            return {
                'success': False,
                'error': str(exc),
                'message': f'Auto-billing failed: {exc}',
            }

    @staticmethod
    def create_pharmacy_bill(prescription):
        """
        Auto-create bill when medication is prescribed

        Args:
            prescription: Prescription object

        Returns:
            dict with bill and invoice details
        """
        from hospital.models import InvoiceLine
        from hospital.models_payment_verification import PharmacyDispensing

        try:
            with transaction.atomic():
                patient = prescription.order.encounter.patient
                encounter = prescription.order.encounter
                drug = prescription.drug

                payer = AutoBillingService._ensure_payer(patient)
                invoice, _ = AutoBillingService._get_or_create_invoice(patient, encounter, payer)

                service_code = AutoBillingService._get_or_create_service_code(
                    code=f"DRUG-{drug.code if hasattr(drug, 'code') else drug.pk}",
                    description=f"{drug.name} {drug.strength}".strip(),
                    category='Pharmacy Services',
                    default_price=getattr(drug, 'unit_price', Decimal('0.00')),
                )

                unit_price = AutoBillingService._resolve_price(
                    patient,
                    payer,
                    service_code,
                    getattr(drug, 'unit_price', Decimal('0.00')),
                )
                line_total = unit_price * Decimal(str(prescription.quantity))

                invoice_line, created = InvoiceLine.objects.get_or_create(
                    invoice=invoice,
                    service_code=service_code,
                    defaults={
                        'description': f"{drug.name} x{prescription.quantity}",
                        'quantity': Decimal(str(prescription.quantity)),
                        'unit_price': unit_price,
                        'line_total': line_total,
                    },
                )

                if not created:
                    invoice_line.quantity += Decimal(str(prescription.quantity))
                    invoice_line.unit_price = unit_price
                    invoice_line.save()

                AutoBillingService._finalize_invoice(invoice)

                dispensing_record, _ = PharmacyDispensing.objects.get_or_create(
                    prescription=prescription,
                    patient=patient,
                    defaults={
                        'dispensing_status': 'pending_payment',
                        'quantity_ordered': prescription.quantity,
                    },
                )

                logger.info(
                    "✅ Auto-bill created for %s x%s - %s - GHS %s",
                    drug.name,
                    prescription.quantity,
                    patient.full_name,
                    line_total,
                )

                return {
                    'success': True,
                    'invoice': invoice,
                    'invoice_line': invoice_line,
                    'amount': line_total,
                    'dispensing_record': dispensing_record,
                    'message': f'Bill created: GHS {line_total} for {drug.name}',
                }

        except Exception as exc:
            logger.error("❌ Error creating pharmacy bill: %s", exc, exc_info=True)
            return {
                'success': False,
                'error': str(exc),
                'message': f'Auto-billing failed: {exc}',
            }

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    @staticmethod
    def _ensure_payer(patient):
        from hospital.models import Payer

        payer = patient.primary_insurance
        if payer and not payer.is_deleted:
            return payer

        payer = (
            Payer.objects.filter(payer_type='cash', is_active=True, is_deleted=False).first()
            or Payer.objects.filter(is_active=True, is_deleted=False).first()
        )
        if payer:
            return payer

        return Payer.objects.create(name='Cash', payer_type='cash', is_active=True)

    @staticmethod
    def _get_or_create_invoice(patient, encounter, payer):
        from hospital.models import Invoice

        invoice = (
            Invoice.objects.filter(
                patient=patient,
                encounter=encounter,
                is_deleted=False,
            )
            .order_by('-created')
            .first()
        )
        if invoice:
            return invoice, False

        invoice = Invoice.objects.create(
            patient=patient,
            encounter=encounter,
            payer=payer,
            status='draft',
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=30),
        )
        return invoice, True

    @staticmethod
    def _get_or_create_service_code(code, description, category, default_price):
        from hospital.models import ServiceCode

        service_code, _ = ServiceCode.objects.get_or_create(
            code=str(code)[:20],
            defaults={
                'description': description[:200],
                'category': category[:50],
                'is_active': True,
            },
        )
        # Attach default price to price book if needed later
        return service_code

    @staticmethod
    def _resolve_price(patient, payer, service_code, fallback_price):
        from hospital.services.pricing_engine_service import pricing_engine

        try:
            price = pricing_engine.get_service_price(service_code=service_code, patient=patient, payer=payer)
            if price and price > 0:
                return price
        except Exception as exc:
            logger.warning("Pricing engine fallback for %s: %s", service_code.code, exc)
        return fallback_price or Decimal('0.00')

    @staticmethod
    def _finalize_invoice(invoice):
        invoice.status = 'issued'
        invoice.update_totals()
    
    @staticmethod
    def check_payment_status(service_type, service_id):
        """
        Check if service has been paid for
        
        Args:
            service_type: 'lab' or 'pharmacy'
            service_id: ID of LabResult or Prescription
        
        Returns:
            dict with payment status
        """
        try:
            if service_type == 'lab':
                from hospital.models import LabResult
                from hospital.models_payment_verification import LabResultRelease
                
                lab_result = LabResult.objects.get(id=service_id, is_deleted=False)
                
                try:
                    release_record = lab_result.release_record
                    is_paid = release_record.payment_receipt is not None
                    
                    return {
                        'paid': is_paid,
                        'status': release_record.release_status,
                        'receipt': release_record.payment_receipt if is_paid else None,
                        'message': 'Payment verified' if is_paid else 'Payment pending'
                    }
                except:
                    return {
                        'paid': False,
                        'status': 'pending_payment',
                        'receipt': None,
                        'message': 'Payment pending - bill not paid'
                    }
                    
            elif service_type == 'pharmacy':
                from hospital.models import Prescription
                from hospital.models_payment_verification import PharmacyDispensing
                
                prescription = Prescription.objects.get(id=service_id, is_deleted=False)
                
                try:
                    dispensing_record = prescription.dispensing_record
                    is_paid = dispensing_record.payment_receipt is not None
                    
                    return {
                        'paid': is_paid,
                        'status': dispensing_record.dispensing_status,
                        'receipt': dispensing_record.payment_receipt if is_paid else None,
                        'message': 'Payment verified' if is_paid else 'Payment pending'
                    }
                except:
                    return {
                        'paid': False,
                        'status': 'pending_payment',
                        'receipt': None,
                        'message': 'Payment pending - bill not paid'
                    }
                    
        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
            return {
                'paid': False,
                'status': 'error',
                'receipt': None,
                'message': f'Error: {str(e)}'
            }


# Export
__all__ = ['AutoBillingService']


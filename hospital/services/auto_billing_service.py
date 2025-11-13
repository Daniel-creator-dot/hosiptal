"""
💰 AUTOMATIC BILLING SERVICE
Auto-generates bills when services are ordered
Ensures payment before service delivery
"""
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import logging

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
        from hospital.models_workflow import Bill
        from hospital.models import Invoice, InvoiceLine, ServiceCode
        
        try:
            with transaction.atomic():
                patient = lab_result.order.encounter.patient
                encounter = lab_result.order.encounter
                test = lab_result.test
                
                # Get or create invoice for this encounter
                invoice, created = Invoice.objects.get_or_create(
                    patient=patient,
                    encounter=encounter,
                    status='draft',
                    defaults={
                        'invoice_date': timezone.now(),
                        'payer': patient.primary_insurance,
                        'subtotal': Decimal('0.00'),
                        'total_amount': Decimal('0.00'),
                        'balance': Decimal('0.00')
                    }
                )
                
                # Add invoice line for lab test
                service_code = f"LAB-{test.code}"
                
                invoice_line, line_created = InvoiceLine.objects.get_or_create(
                    invoice=invoice,
                    service_code=service_code,
                    defaults={
                        'description': test.name,
                        'quantity': 1,
                        'unit_price': test.price,
                        'line_total': test.price
                    }
                )
                
                if line_created:
                    # Update invoice totals
                    invoice.total_amount += test.price
                    invoice.balance += test.price
                    invoice.status = 'issued'  # Ready for payment
                    invoice.save()
                
                # Create payment verification requirement
                from hospital.models_payment_verification import LabResultRelease
                
                release_record, _ = LabResultRelease.objects.get_or_create(
                    lab_result=lab_result,
                    patient=patient,
                    defaults={
                        'release_status': 'pending_payment'
                    }
                )
                
                logger.info(f"✅ Auto-bill created for {test.name} - {patient.full_name} - GHS {test.price}")
                
                return {
                    'success': True,
                    'invoice': invoice,
                    'invoice_line': invoice_line,
                    'amount': test.price,
                    'release_record': release_record,
                    'message': f'Bill created: GHS {test.price} for {test.name}'
                }
                
        except Exception as e:
            logger.error(f"❌ Error creating lab bill: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Auto-billing failed: {str(e)}'
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
        from hospital.models_workflow import Bill
        from hospital.models import Invoice, InvoiceLine
        
        try:
            with transaction.atomic():
                patient = prescription.order.encounter.patient
                encounter = prescription.order.encounter
                drug = prescription.drug
                
                # Calculate total cost
                unit_price = getattr(drug, 'unit_price', Decimal('0.00'))
                total_cost = unit_price * prescription.quantity
                
                # Get or create invoice for this encounter
                invoice, created = Invoice.objects.get_or_create(
                    patient=patient,
                    encounter=encounter,
                    status='draft',
                    defaults={
                        'invoice_date': timezone.now(),
                        'payer': patient.primary_insurance,
                        'subtotal': Decimal('0.00'),
                        'total_amount': Decimal('0.00'),
                        'balance': Decimal('0.00')
                    }
                )
                
                # Add invoice line for medication
                service_code = f"DRUG-{drug.name[:20]}"
                
                invoice_line, line_created = InvoiceLine.objects.get_or_create(
                    invoice=invoice,
                    service_code=service_code,
                    description=f"{drug.name} {drug.strength} - {prescription.quantity} units",
                    defaults={
                        'quantity': prescription.quantity,
                        'unit_price': unit_price,
                        'line_total': total_cost
                    }
                )
                
                if line_created:
                    # Update invoice totals
                    invoice.total_amount += total_cost
                    invoice.balance += total_cost
                    invoice.status = 'issued'  # Ready for payment
                    invoice.save()
                
                # Create payment verification requirement
                from hospital.models_payment_verification import PharmacyDispensing
                
                dispensing_record, _ = PharmacyDispensing.objects.get_or_create(
                    prescription=prescription,
                    patient=patient,
                    defaults={
                        'dispensing_status': 'pending_payment',
                        'quantity_ordered': prescription.quantity
                    }
                )
                
                logger.info(f"✅ Auto-bill created for {drug.name} x{prescription.quantity} - {patient.full_name} - GHS {total_cost}")
                
                return {
                    'success': True,
                    'invoice': invoice,
                    'invoice_line': invoice_line,
                    'amount': total_cost,
                    'dispensing_record': dispensing_record,
                    'message': f'Bill created: GHS {total_cost} for {drug.name}'
                }
                
        except Exception as e:
            logger.error(f"❌ Error creating pharmacy bill: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Auto-billing failed: {str(e)}'
            }
    
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


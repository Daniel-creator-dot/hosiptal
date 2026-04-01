"""
Enhanced Payment Processing Service
Provides validated payment processing with comprehensive error checking
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger(__name__)


class EnhancedPaymentService:
    """
    Enhanced payment processing service with comprehensive validation
    Ensures accuracy for Cash, Corporate, and Insurance payments
    """
    
    def __init__(self):
        self.logger = logger
    
    @transaction.atomic
    def process_payment(
        self,
        invoice,
        amount,
        payment_method='cash',
        processed_by=None,
        reference_number='',
        validate=True,
        create_receipt=True
    ):
        """
        Process payment with comprehensive validation
        
        Args:
            invoice: Invoice object
            amount: Payment amount (Decimal, float, or string)
            payment_method: Payment method ('cash', 'card', 'mobile_money', 'bank_transfer', 'cheque', 'insurance', 'corporate')
            processed_by: User processing the payment
            reference_number: Payment reference number
            validate: If True, validate payment before processing
            create_receipt: If True, create payment receipt
        
        Returns:
            dict: {
                'success': bool,
                'transaction': Transaction object or None,
                'receipt': PaymentReceipt object or None,
                'errors': list,
                'warnings': list,
                'message': str
            }
        """
        from hospital.models_accounting import Transaction, PaymentReceipt
        from hospital.services.billing_validation_service import billing_validator
        
        result = {
            'success': False,
            'transaction': None,
            'receipt': None,
            'errors': [],
            'warnings': [],
            'message': ''
        }
        
        try:
            # Convert amount to Decimal
            amount = Decimal(str(amount))
            
            # Validate payment
            if validate:
                validation = billing_validator.validate_payment(invoice, amount, payment_method)
                if not validation['valid']:
                    result['errors'] = validation['errors']
                    result['message'] = 'Payment validation failed'
                    return result
                result['warnings'] = validation['warnings']
            
            # Validate invoice integrity before payment
            invoice_validation = billing_validator.validate_invoice_integrity(invoice)
            if not invoice_validation['valid']:
                # Log errors but don't block payment if they're non-critical
                critical_errors = [e for e in invoice_validation['errors'] 
                                 if 'balance mismatch' not in e.lower() and 'status' not in e.lower()]
                if critical_errors:
                    result['errors'] = critical_errors
                    result['message'] = 'Invoice validation failed'
                    return result
            
            # Process payment using invoice's mark_as_paid method (which now has validation)
            transaction_obj = invoice.mark_as_paid(
                amount=amount,
                payment_method=payment_method,
                processed_by=processed_by,
                reference_number=reference_number,
                validate=False  # Already validated above
            )
            
            result['transaction'] = transaction_obj
            result['success'] = True
            result['message'] = f'Payment of GHS {amount:.2f} processed successfully'
            
            # Get receipt if created
            if create_receipt:
                try:
                    receipt = PaymentReceipt.objects.filter(transaction=transaction_obj).first()
                    result['receipt'] = receipt
                except Exception as e:
                    self.logger.warning(f"Could not retrieve receipt: {str(e)}")
            
            # Payer-specific post-processing
            if invoice.payer:
                if invoice.payer.payer_type == 'corporate':
                    self._update_corporate_account(invoice, amount)
                elif invoice.payer.payer_type in ['nhis', 'private']:
                    self._log_insurance_payment(invoice, amount)
            
            return result
        
        except ValidationError as e:
            result['errors'] = [str(e)]
            result['message'] = 'Payment validation error'
            return result
        except Exception as e:
            self.logger.error(f"Error processing payment: {str(e)}", exc_info=True)
            result['errors'] = [f"Payment processing error: {str(e)}"]
            result['message'] = 'Payment processing failed'
            return result
    
    def _update_corporate_account(self, invoice, amount):
        """
        Update corporate account balance after payment
        """
        try:
            from hospital.models_enterprise_billing import CorporateEmployee
            
            enrollment = CorporateEmployee.objects.filter(
                patient=invoice.patient,
                is_active=True,
                is_deleted=False
            ).select_related('corporate_account').first()
            
            if enrollment:
                corporate_account = enrollment.corporate_account
                # Payment reduces corporate account balance
                corporate_account.current_balance = max(
                    corporate_account.current_balance - amount,
                    Decimal('0.00')
                )
                corporate_account.save(update_fields=['current_balance'])
                
                self.logger.info(
                    f"Updated corporate account {corporate_account.company_name} balance: "
                    f"GHS {corporate_account.current_balance}"
                )
        except Exception as e:
            self.logger.warning(f"Could not update corporate account: {str(e)}")
    
    def _log_insurance_payment(self, invoice, amount):
        """
        Log insurance payment for tracking
        """
        try:
            self.logger.info(
                f"Insurance payment processed: Invoice {invoice.invoice_number}, "
                f"Payer: {invoice.payer.name}, Amount: GHS {amount}"
            )
        except Exception as e:
            self.logger.warning(f"Could not log insurance payment: {str(e)}")
    
    def process_partial_payment(
        self,
        invoice,
        amount,
        payment_method='cash',
        processed_by=None,
        reference_number=''
    ):
        """
        Process partial payment with validation
        
        Returns:
            dict: Payment processing result
        """
        if amount >= invoice.balance:
            # If amount equals or exceeds balance, process as full payment
            return self.process_payment(
                invoice=invoice,
                amount=invoice.balance,
                payment_method=payment_method,
                processed_by=processed_by,
                reference_number=reference_number
            )
        else:
            # Process partial payment
            return self.process_payment(
                invoice=invoice,
                amount=amount,
                payment_method=payment_method,
                processed_by=processed_by,
                reference_number=reference_number
            )
    
    def process_full_payment(
        self,
        invoice,
        payment_method='cash',
        processed_by=None,
        reference_number=''
    ):
        """
        Process full payment (pay entire balance)
        
        Returns:
            dict: Payment processing result
        """
        return self.process_payment(
            invoice=invoice,
            amount=invoice.balance,
            payment_method=payment_method,
            processed_by=processed_by,
            reference_number=reference_number
        )


# Global instance
enhanced_payment_service = EnhancedPaymentService()






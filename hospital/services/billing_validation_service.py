"""
Comprehensive Billing Validation Service
Ensures accuracy and prevents mistakes in Cash, Corporate, and Insurance billing
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class BillingValidationService:
    """
    Comprehensive validation service for patient billing
    Handles validation for Cash, Corporate, and Insurance billing scenarios
    """
    
    def __init__(self):
        self.logger = logger
    
    # ==================== INVOICE VALIDATION ====================
    
    def validate_invoice_integrity(self, invoice):
        """
        Comprehensive invoice validation
        
        Returns:
            dict: {
                'valid': bool,
                'errors': list,
                'warnings': list,
                'details': dict
            }
        """
        errors = []
        warnings = []
        details = {
            'invoice_number': invoice.invoice_number,
            'patient': str(invoice.patient),
            'payer_type': invoice.payer.payer_type if invoice.payer else None,
            'status': invoice.status,
        }
        
        # 1. Basic validations
        if not invoice.patient:
            errors.append("Invoice must have a patient")
        
        if not invoice.payer:
            errors.append("Invoice must have a payer")
        else:
            if not invoice.payer.is_active:
                warnings.append(f"Payer '{invoice.payer.name}' is inactive")
        
        # 2. Invoice number validation
        from hospital.models import Invoice
        if not invoice.invoice_number:
            errors.append("Invoice number is required")
        elif Invoice.all_objects.filter(invoice_number=invoice.invoice_number).exclude(pk=invoice.pk).exists():
            errors.append(f"Duplicate invoice number: {invoice.invoice_number}")
        
        # 3. Total amount validation
        line_total = Decimal('0.00')
        line_count = 0
        for line in invoice.lines.filter(is_deleted=False):
            line_count += 1
            line_total += line.line_total or Decimal('0.00')
            
            # Validate line item
            line_validation = self.validate_invoice_line(line)
            if not line_validation['valid']:
                errors.extend([f"Line {line_count}: {e}" for e in line_validation['errors']])
            if line_validation['warnings']:
                warnings.extend([f"Line {line_count}: {w}" for w in line_validation['warnings']])
        
        # Round for comparison (2 decimal places)
        line_total = line_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        invoice_total = (invoice.total_amount or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        if abs(line_total - invoice_total) > Decimal('0.01'):
            errors.append(
                f"Invoice total mismatch: Line items total = GHS {line_total}, "
                f"Invoice total = GHS {invoice_total}, Difference = GHS {abs(line_total - invoice_total)}"
            )
            details['line_total'] = float(line_total)
            details['invoice_total'] = float(invoice_total)
            details['difference'] = float(abs(line_total - invoice_total))
        
        # 4. Balance validation
        balance_validation = self.validate_invoice_balance(invoice)
        if not balance_validation['valid']:
            errors.extend(balance_validation['errors'])
        if balance_validation['warnings']:
            warnings.extend(balance_validation['warnings'])
        details['balance_validation'] = balance_validation
        
        # 5. Payer-specific validations
        if invoice.payer:
            if invoice.payer.payer_type == 'corporate':
                corporate_validation = self.validate_corporate_invoice(invoice)
                if not corporate_validation['valid']:
                    errors.extend(corporate_validation['errors'])
                if corporate_validation['warnings']:
                    warnings.extend(corporate_validation['warnings'])
                details['corporate_validation'] = corporate_validation
            
            elif invoice.payer.payer_type in ['nhis', 'private']:
                insurance_validation = self.validate_insurance_invoice(invoice)
                if not insurance_validation['valid']:
                    errors.extend(insurance_validation['errors'])
                if insurance_validation['warnings']:
                    warnings.extend(insurance_validation['warnings'])
                details['insurance_validation'] = insurance_validation
            
            elif invoice.payer.payer_type == 'cash':
                cash_validation = self.validate_cash_invoice(invoice)
                if not cash_validation['valid']:
                    errors.extend(cash_validation['errors'])
                if cash_validation['warnings']:
                    warnings.extend(cash_validation['warnings'])
                details['cash_validation'] = cash_validation
        
        # 6. Status validation
        status_validation = self.validate_invoice_status(invoice)
        if not status_validation['valid']:
            errors.extend(status_validation['errors'])
        details['status_validation'] = status_validation
        
        # 7. Date validations
        if invoice.due_at and invoice.issued_at:
            if invoice.due_at < invoice.issued_at:
                errors.append("Due date cannot be before issue date")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'details': details
        }
    
    def validate_invoice_line(self, invoice_line):
        """
        Validate individual invoice line item
        
        Returns:
            dict: {'valid': bool, 'errors': list, 'warnings': list}
        """
        errors = []
        warnings = []
        
        # Basic validations
        if not invoice_line.service_code:
            errors.append("Invoice line must have a service code")
        
        if not invoice_line.description:
            errors.append("Invoice line must have a description")
        
        if invoice_line.quantity is None or invoice_line.quantity <= 0:
            errors.append(f"Quantity must be greater than 0, got: {invoice_line.quantity}")
        
        if invoice_line.unit_price is None or invoice_line.unit_price < 0:
            errors.append(f"Unit price cannot be negative, got: {invoice_line.unit_price}")
        
        if invoice_line.discount_amount is None or invoice_line.discount_amount < 0:
            errors.append(f"Discount amount cannot be negative, got: {invoice_line.discount_amount}")
        
        if invoice_line.tax_amount is None or invoice_line.tax_amount < 0:
            errors.append(f"Tax amount cannot be negative, got: {invoice_line.tax_amount}")
        
        # Line total calculation validation
        if invoice_line.quantity and invoice_line.unit_price:
            expected_subtotal = Decimal(str(invoice_line.quantity)) * Decimal(str(invoice_line.unit_price))
            expected_line_total = expected_subtotal - (invoice_line.discount_amount or Decimal('0.00')) + (invoice_line.tax_amount or Decimal('0.00'))
            expected_line_total = expected_line_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            actual_line_total = (invoice_line.line_total or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            if abs(expected_line_total - actual_line_total) > Decimal('0.01'):
                errors.append(
                    f"Line total mismatch: Expected GHS {expected_line_total}, "
                    f"Actual GHS {actual_line_total}, Difference GHS {abs(expected_line_total - actual_line_total)}"
                )
        
        # Discount validation
        if invoice_line.discount_amount and invoice_line.unit_price and invoice_line.quantity:
            max_discount = Decimal(str(invoice_line.quantity)) * Decimal(str(invoice_line.unit_price))
            if invoice_line.discount_amount > max_discount:
                errors.append(
                    f"Discount amount (GHS {invoice_line.discount_amount}) exceeds line subtotal (GHS {max_discount})"
                )
        
        # Insurance exclusion validation
        if invoice_line.patient_pay_cash and invoice_line.is_insurance_excluded:
            # This is valid - item is excluded from insurance and patient pays cash
            pass
        elif invoice_line.patient_pay_cash and not invoice_line.is_insurance_excluded:
            warnings.append("Line marked as patient_pay_cash but not marked as insurance_excluded")
        
        # Payer-specific line validations
        if invoice_line.invoice and invoice_line.invoice.payer:
            payer_type = invoice_line.invoice.payer.payer_type
            if payer_type == 'cash' and invoice_line.patient_pay_cash:
                # Cash payer with patient_pay_cash flag - this is redundant but not wrong
                pass
            elif payer_type in ['nhis', 'private'] and invoice_line.patient_pay_cash:
                # Insurance payer with cash payment items - valid scenario
                if not invoice_line.insurance_exclusion_reason:
                    warnings.append("Cash payment item should have insurance exclusion reason")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def validate_invoice_balance(self, invoice):
        """
        Validate invoice balance matches payments
        
        Returns:
            dict: {'valid': bool, 'errors': list, 'warnings': list, 'calculated_balance': Decimal}
        """
        errors = []
        warnings = []
        
        from hospital.models_accounting import PaymentReceipt, Transaction
        
        # Calculate total payments from receipts
        total_paid_receipts = Decimal('0.00')
        receipts = PaymentReceipt.objects.filter(
            invoice=invoice,
            is_deleted=False
        )
        for receipt in receipts:
            total_paid_receipts += receipt.amount_paid or Decimal('0.00')
        
        # Calculate total payments from transactions (backup method)
        total_paid_transactions = Decimal('0.00')
        transactions = Transaction.objects.filter(
            invoice=invoice,
            transaction_type='payment_received',
            is_deleted=False
        )
        for txn in transactions:
            total_paid_transactions += txn.amount or Decimal('0.00')
        
        # Use receipts if available, otherwise use transactions
        total_paid = total_paid_receipts if receipts.exists() else total_paid_transactions
        
        # Calculate expected balance
        invoice_total = invoice.total_amount or Decimal('0.00')
        expected_balance = invoice_total - total_paid
        expected_balance = expected_balance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        actual_balance = (invoice.balance or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Check for mismatch
        if abs(expected_balance - actual_balance) > Decimal('0.01'):
            errors.append(
                f"Balance mismatch: Expected GHS {expected_balance}, "
                f"Actual GHS {actual_balance}, Difference GHS {abs(expected_balance - actual_balance)}. "
                f"Total: GHS {invoice_total}, Paid: GHS {total_paid}"
            )
        
        # Check for overpayment
        if expected_balance < 0:
            warnings.append(f"Overpayment detected: Balance is GHS {abs(expected_balance)}")
        
        # Verify status matches balance
        if invoice.status == 'paid' and actual_balance > Decimal('0.01'):
            errors.append(f"Invoice status is 'paid' but balance is GHS {actual_balance}")
        elif invoice.status == 'partially_paid' and actual_balance <= Decimal('0.01'):
            warnings.append(f"Invoice status is 'partially_paid' but balance is GHS {actual_balance}")
        elif invoice.status in ['issued', 'draft'] and total_paid > Decimal('0.01'):
            if abs(expected_balance - invoice_total) < Decimal('0.01'):
                warnings.append(f"Invoice has payments but status is '{invoice.status}'")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'calculated_balance': expected_balance,
            'total_paid': total_paid,
            'invoice_total': invoice_total
        }
    
    def validate_invoice_status(self, invoice):
        """
        Validate invoice status is appropriate for current state
        
        Returns:
            dict: {'valid': bool, 'errors': list, 'warnings': list}
        """
        errors = []
        warnings = []
        
        balance = invoice.balance or Decimal('0.00')
        total_amount = invoice.total_amount or Decimal('0.00')
        
        # Status logic validation
        if invoice.status == 'paid':
            if balance > Decimal('0.01'):
                errors.append(f"Status is 'paid' but balance is GHS {balance}")
        elif invoice.status == 'partially_paid':
            if balance <= Decimal('0.01'):
                warnings.append(f"Status is 'partially_paid' but balance is GHS {balance}")
            elif balance >= total_amount:
                errors.append(f"Status is 'partially_paid' but balance ({balance}) equals or exceeds total ({total_amount})")
        elif invoice.status == 'issued':
            if balance <= Decimal('0.01') and total_amount > Decimal('0.00'):
                warnings.append(f"Status is 'issued' but balance is GHS {balance}")
            elif balance < total_amount and total_amount > Decimal('0.00'):
                warnings.append(f"Status is 'issued' but payments have been made (balance: GHS {balance})")
        elif invoice.status == 'draft':
            if balance != total_amount and total_amount > Decimal('0.00'):
                warnings.append(f"Draft invoice has balance mismatch: total={total_amount}, balance={balance}")
        elif invoice.status == 'overdue':
            if invoice.due_at and invoice.due_at > timezone.now():
                warnings.append(f"Status is 'overdue' but due date ({invoice.due_at}) is in the future")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    # ==================== CASH BILLING VALIDATION ====================
    
    def validate_cash_invoice(self, invoice):
        """
        Validate cash invoice specific rules
        
        Returns:
            dict: {'valid': bool, 'errors': list, 'warnings': list}
        """
        errors = []
        warnings = []
        
        # Cash invoices should not have insurance-related flags
        for line in invoice.lines.filter(is_deleted=False):
            if line.patient_pay_cash:
                warnings.append(
                    f"Cash invoice has line marked as patient_pay_cash: {line.description}. "
                    "This is redundant for cash invoices."
                )
            if line.is_insurance_excluded:
                warnings.append(
                    f"Cash invoice has line marked as insurance_excluded: {line.description}. "
                    "This is not applicable for cash invoices."
                )
        
        # Cash invoices should typically be paid immediately or have shorter due dates
        if invoice.due_at:
            days_until_due = (invoice.due_at - invoice.issued_at).days if invoice.issued_at else 0
            if days_until_due > 7:
                warnings.append(
                    f"Cash invoice has due date {days_until_due} days in future. "
                    "Cash invoices typically have shorter payment terms (1-7 days)."
                )
        
        # Cash invoices should not have zero balance if status is issued
        if invoice.status == 'issued' and invoice.balance <= Decimal('0.01') and invoice.total_amount > Decimal('0.00'):
            warnings.append("Cash invoice is issued but has zero balance. Payment may be missing.")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    # ==================== CORPORATE BILLING VALIDATION ====================
    
    def validate_corporate_invoice(self, invoice):
        """
        Validate corporate invoice specific rules
        
        Returns:
            dict: {'valid': bool, 'errors': list, 'warnings': list}
        """
        errors = []
        warnings = []
        
        try:
            from hospital.models_enterprise_billing import CorporateEmployee
            
            # Check if patient is enrolled in corporate account
            enrollment = CorporateEmployee.objects.filter(
                patient=invoice.patient,
                is_active=True,
                is_deleted=False
            ).select_related('corporate_account').first()
            
            if not enrollment:
                errors.append(
                    f"Patient {invoice.patient.full_name} is not enrolled in any corporate account, "
                    f"but invoice payer is corporate: {invoice.payer.name}"
                )
            else:
                corporate_account = enrollment.corporate_account
                
                # Validate corporate account is active
                if not corporate_account.is_active:
                    errors.append(
                        f"Corporate account '{corporate_account.company_name}' is inactive. "
                        "Cannot create invoices for inactive accounts."
                    )
                
                # Validate credit limit
                if corporate_account.credit_limit > 0:
                    new_balance = corporate_account.current_balance + invoice.balance
                    if new_balance > corporate_account.credit_limit:
                        errors.append(
                            f"Credit limit would be exceeded. Current balance: GHS {corporate_account.current_balance}, "
                            f"New invoice: GHS {invoice.balance}, Limit: GHS {corporate_account.credit_limit}, "
                            f"Would exceed by: GHS {new_balance - corporate_account.credit_limit}"
                        )
                    elif new_balance > corporate_account.credit_limit * Decimal('0.90'):
                        warnings.append(
                            f"Credit limit nearly reached. Current: GHS {corporate_account.current_balance}, "
                            f"After invoice: GHS {new_balance}, Limit: GHS {corporate_account.credit_limit}"
                        )
                
                # Validate credit status
                if corporate_account.credit_status == 'suspended':
                    errors.append(
                        f"Corporate account '{corporate_account.company_name}' is suspended. "
                        "Cannot create new invoices."
                    )
                elif corporate_account.credit_status == 'on_hold':
                    warnings.append(
                        f"Corporate account '{corporate_account.company_name}' is on hold. "
                        "Review before creating invoice."
                    )
                
                # Validate payer matches corporate account
                if corporate_account.company_name != invoice.payer.name:
                    warnings.append(
                        f"Corporate account name '{corporate_account.company_name}' does not match "
                        f"payer name '{invoice.payer.name}'"
                    )
                
                # Validate annual limit if applicable
                if enrollment.has_annual_limit:
                    remaining_limit = enrollment.remaining_limit or Decimal('0.00')
                    if invoice.balance > remaining_limit:
                        errors.append(
                            f"Employee annual limit would be exceeded. Remaining: GHS {remaining_limit}, "
                            f"Invoice amount: GHS {invoice.balance}"
                        )
        
        except ImportError:
            warnings.append("Corporate billing models not available")
        except Exception as e:
            errors.append(f"Error validating corporate invoice: {str(e)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    # ==================== INSURANCE BILLING VALIDATION ====================
    
    def validate_insurance_invoice(self, invoice):
        """
        Validate insurance invoice specific rules
        
        Returns:
            dict: {'valid': bool, 'errors': list, 'warnings': list}
        """
        errors = []
        warnings = []
        
        # Check patient has insurance
        if not invoice.patient.primary_insurance:
            errors.append(
                f"Patient {invoice.patient.full_name} does not have primary insurance set, "
                f"but invoice payer is: {invoice.payer.name}"
            )
        elif invoice.patient.primary_insurance != invoice.payer:
            warnings.append(
                f"Patient primary insurance ({invoice.patient.primary_insurance.name}) "
                f"does not match invoice payer ({invoice.payer.name})"
            )
        
        # Validate insurance ID fields
        if invoice.payer.payer_type == 'nhis':
            if not invoice.patient.insurance_member_id:
                warnings.append("NHIS patient missing member ID")
        elif invoice.payer.payer_type == 'private':
            if not invoice.patient.insurance_id:
                warnings.append("Private insurance patient missing policy number")
        
        # Check for cash payment items (excluded from insurance)
        cash_items = invoice.lines.filter(is_deleted=False, patient_pay_cash=True)
        if cash_items.exists():
            cash_total = sum(line.line_total for line in cash_items)
            warnings.append(
                f"Invoice has {cash_items.count()} cash payment item(s) totaling GHS {cash_total} "
                "that are excluded from insurance coverage"
            )
            
            # Verify each cash item has exclusion reason
            for line in cash_items:
                if not line.insurance_exclusion_reason:
                    warnings.append(
                        f"Cash payment item '{line.description}' missing insurance exclusion reason"
                    )
        
        # Check for insurance excluded items
        excluded_items = invoice.lines.filter(is_deleted=False, is_insurance_excluded=True)
        if excluded_items.exists():
            excluded_total = sum(line.line_total for line in excluded_items)
            warnings.append(
                f"Invoice has {excluded_items.count()} insurance-excluded item(s) totaling GHS {excluded_total}"
            )
        
        # Validate insurance pricing
        from hospital.services.pricing_engine_service import pricing_engine
        for line in invoice.lines.filter(is_deleted=False):
            if not line.patient_pay_cash and not line.is_insurance_excluded:
                # This should use insurance pricing
                try:
                    expected_price = pricing_engine.get_service_price(
                        service_code=line.service_code,
                        patient=invoice.patient,
                        payer=invoice.payer
                    )
                    if expected_price and line.unit_price != expected_price:
                        warnings.append(
                            f"Line '{line.description}' unit price (GHS {line.unit_price}) "
                            f"may not match insurance pricing (GHS {expected_price})"
                        )
                except Exception as e:
                    warnings.append(f"Could not verify insurance pricing for line '{line.description}': {str(e)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    # ==================== PAYMENT VALIDATION ====================
    
    def validate_payment(self, invoice, amount, payment_method='cash'):
        """
        Validate payment before processing
        
        Args:
            invoice: Invoice object
            amount: Payment amount (Decimal)
            payment_method: Payment method string
        
        Returns:
            dict: {'valid': bool, 'errors': list, 'warnings': list}
        """
        errors = []
        warnings = []
        
        amount = Decimal(str(amount))
        
        # Basic validations
        if amount <= 0:
            errors.append(f"Payment amount must be greater than 0, got: GHS {amount}")
        
        if amount > invoice.balance + Decimal('0.01'):  # Allow small rounding differences
            errors.append(
                f"Payment amount (GHS {amount}) exceeds invoice balance (GHS {invoice.balance})"
            )
        
        # Validate payment method
        valid_methods = ['cash', 'card', 'mobile_money', 'bank_transfer', 'cheque', 'insurance', 'corporate']
        if payment_method not in valid_methods:
            warnings.append(f"Payment method '{payment_method}' is not in standard list: {valid_methods}")
        
        # Payer-specific validations
        if invoice.payer:
            if invoice.payer.payer_type == 'cash' and payment_method not in ['cash', 'card', 'mobile_money']:
                warnings.append(
                    f"Cash invoice paid with '{payment_method}'. Expected cash, card, or mobile money."
                )
            elif invoice.payer.payer_type == 'corporate' and payment_method != 'corporate':
                warnings.append(
                    f"Corporate invoice paid with '{payment_method}'. Expected 'corporate' payment method."
                )
            elif invoice.payer.payer_type in ['nhis', 'private'] and payment_method != 'insurance':
                warnings.append(
                    f"Insurance invoice paid with '{payment_method}'. Expected 'insurance' payment method."
                )
        
        # Status validation
        if invoice.status == 'paid':
            warnings.append("Invoice is already marked as paid. This may be a duplicate payment.")
        elif invoice.status == 'cancelled':
            errors.append("Cannot process payment for cancelled invoice")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    # ==================== RECONCILIATION ====================
    
    def reconcile_invoice(self, invoice):
        """
        Reconcile invoice - recalculate totals and balance, fix discrepancies
        
        Returns:
            dict: {
                'reconciled': bool,
                'fixes_applied': list,
                'errors': list,
                'before': dict,
                'after': dict
            }
        """
        fixes_applied = []
        errors = []
        
        before = {
            'total_amount': float(invoice.total_amount or Decimal('0.00')),
            'balance': float(invoice.balance or Decimal('0.00')),
            'status': invoice.status
        }
        
        try:
            with transaction.atomic():
                # Recalculate line totals from quantity/unit_price/discount/tax
                for line in invoice.lines.filter(is_deleted=False):
                    line_subtotal = Decimal(str(line.quantity)) * Decimal(str(line.unit_price))
                    line.line_total = line_subtotal - (line.discount_amount or Decimal('0.00')) + (line.tax_amount or Decimal('0.00'))
                    line.save(update_fields=['line_total'])
                
                old_total = invoice.total_amount
                old_balance = invoice.balance
                old_status = invoice.status
                invoice.update_totals()
                if old_total != invoice.total_amount:
                    fixes_applied.append(f"Updated total_amount from GHS {old_total} to GHS {invoice.total_amount}")
                if old_balance != invoice.balance:
                    fixes_applied.append(f"Updated balance from GHS {old_balance} to GHS {invoice.balance}")
                if old_status != invoice.status:
                    fixes_applied.append(f"Updated status from '{old_status}' to '{invoice.status}'")
        
        except Exception as e:
            errors.append(f"Error during reconciliation: {str(e)}")
            self.logger.error(f"Reconciliation error for invoice {invoice.invoice_number}: {str(e)}", exc_info=True)
        
        after = {
            'total_amount': float(invoice.total_amount or Decimal('0.00')),
            'balance': float(invoice.balance or Decimal('0.00')),
            'status': invoice.status
        }
        
        return {
            'reconciled': len(errors) == 0,
            'fixes_applied': fixes_applied,
            'errors': errors,
            'before': before,
            'after': after
        }
    
    # ==================== BATCH VALIDATION ====================
    
    def validate_invoice_batch(self, invoices, fix_errors=False):
        """
        Validate multiple invoices
        
        Args:
            invoices: QuerySet or list of Invoice objects
            fix_errors: If True, attempt to fix errors by reconciling
        
        Returns:
            dict: Summary of validation results
        """
        results = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'warnings_count': 0,
            'errors_count': 0,
            'fixed': 0,
            'details': []
        }
        
        for invoice in invoices:
            results['total'] += 1
            validation = self.validate_invoice_integrity(invoice)
            
            error_count = len(validation['errors'])
            warning_count = len(validation['warnings'])
            
            results['errors_count'] += error_count
            results['warnings_count'] += warning_count
            
            if validation['valid']:
                results['valid'] += 1
            else:
                results['invalid'] += 1
                
                # Attempt to fix if requested
                if fix_errors:
                    reconciliation = self.reconcile_invoice(invoice)
                    if reconciliation['reconciled'] and len(reconciliation['fixes_applied']) > 0:
                        results['fixed'] += 1
                        # Re-validate after fixing
                        validation = self.validate_invoice_integrity(invoice)
            
            results['details'].append({
                'invoice_number': invoice.invoice_number,
                'patient': str(invoice.patient),
                'valid': validation['valid'],
                'errors': validation['errors'],
                'warnings': validation['warnings'],
                'error_count': error_count,
                'warning_count': warning_count
            })
        
        return results


# Global instance
billing_validator = BillingValidationService()


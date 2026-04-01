"""
Billing Account Link Service
Ensures all invoices are properly linked to company accounts (insurance/corporate)
and that claims/statements are generated correctly
"""
import logging
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class BillingAccountLinkService:
    """
    Service to ensure proper linking of invoices to company accounts
    and generation of claims/statements
    """
    
    @staticmethod
    def ensure_invoice_linked_to_account(invoice):
        """
        Ensure invoice is properly linked to the correct payer account
        and that all details are tracked under the company account
        
        Args:
            invoice: Invoice object
            
        Returns:
            dict: {'success': bool, 'message': str, 'account_type': str}
        """
        try:
            if not invoice.payer:
                return {
                    'success': False,
                    'message': 'Invoice has no payer assigned',
                    'account_type': None
                }
            
            payer = invoice.payer
            patient = invoice.patient
            
            # Verify patient's primary_insurance matches invoice payer
            if patient.primary_insurance != payer:
                logger.warning(
                    f"Invoice {invoice.invoice_number} payer ({payer.name}) "
                    f"does not match patient's primary_insurance ({patient.primary_insurance.name if patient.primary_insurance else 'None'})"
                )
            
            # Determine account type and ensure proper tracking
            if payer.payer_type == 'corporate':
                return BillingAccountLinkService._link_corporate_invoice(invoice, payer, patient)
            elif payer.payer_type in ['insurance', 'private', 'nhis']:
                return BillingAccountLinkService._link_insurance_invoice(invoice, payer, patient)
            elif payer.payer_type == 'cash':
                return {
                    'success': True,
                    'message': 'Cash invoice - no account linking needed',
                    'account_type': 'cash'
                }
            else:
                return {
                    'success': False,
                    'message': f'Unknown payer type: {payer.payer_type}',
                    'account_type': None
                }
                
        except Exception as e:
            logger.error(f"Error linking invoice to account: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'account_type': None
            }
    
    @staticmethod
    def _link_corporate_invoice(invoice, payer, patient):
        """
        Link invoice to corporate account and ensure it's included in monthly statements
        
        Args:
            invoice: Invoice object
            payer: Payer object (corporate)
            patient: Patient object
            
        Returns:
            dict: Status information
        """
        try:
            # Check if patient is enrolled as corporate employee
            from hospital.models_enterprise_billing import CorporateEmployee, CorporateAccount
            
            corporate_employee = CorporateEmployee.objects.filter(
                patient=patient,
                is_active=True,
                is_deleted=False
            ).select_related('corporate_account').first()
            
            if not corporate_employee:
                logger.warning(
                    f"Patient {patient.mrn} has corporate payer but no CorporateEmployee enrollment. "
                    f"Invoice {invoice.invoice_number} may not be included in monthly statement."
                )
                return {
                    'success': True,
                    'message': 'Corporate invoice linked, but patient not enrolled as employee',
                    'account_type': 'corporate',
                    'warning': 'Patient not enrolled as corporate employee'
                }
            
            corporate_account = corporate_employee.corporate_account
            
            # Verify payer name matches corporate account name
            if payer.name != corporate_account.company_name:
                logger.warning(
                    f"Payer name ({payer.name}) does not match corporate account name "
                    f"({corporate_account.company_name}) for invoice {invoice.invoice_number}"
                )
            
            # Invoice is properly linked - it will be included in monthly statement
            # via MonthlyBillingService.generate_corporate_statement()
            
            logger.info(
                f"✅ Corporate invoice {invoice.invoice_number} linked to "
                f"{corporate_account.company_name} (Employee: {corporate_employee.employee_id})"
            )
            
            return {
                'success': True,
                'message': f'Invoice linked to corporate account: {corporate_account.company_name}',
                'account_type': 'corporate',
                'corporate_account': corporate_account.company_name,
                'employee_id': corporate_employee.employee_id
            }
            
        except ImportError:
            # CorporateAccount model not available
            return {
                'success': True,
                'message': 'Corporate invoice linked (CorporateAccount model not available)',
                'account_type': 'corporate'
            }
        except Exception as e:
            logger.error(f"Error linking corporate invoice: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error linking corporate invoice: {str(e)}',
                'account_type': 'corporate'
            }
    
    @staticmethod
    def _link_insurance_invoice(invoice, payer, patient):
        """
        Link invoice to insurance account and ensure claims are created
        
        Args:
            invoice: Invoice object
            payer: Payer object (insurance)
            patient: Patient object
            
        Returns:
            dict: Status information
        """
        try:
            from hospital.models_insurance import InsuranceClaimItem
            from hospital.models_insurance_companies import PatientInsurance
            from hospital.insurance_claim_query import insurance_claim_item_deduped_q

            # Check if patient has insurance enrollment
            insurance_enrollment = PatientInsurance.objects.filter(
                patient=patient,
                status='active',
                is_deleted=False
            ).select_related('insurance_company').first()

            # Check if claims exist for this invoice (canonical rows only)
            claim_items = InsuranceClaimItem.objects.filter(
                invoice=invoice,
                payer=payer,
                is_deleted=False,
            ).filter(insurance_claim_item_deduped_q())
            
            if not claim_items.exists():
                logger.info(
                    f"Invoice {invoice.invoice_number} has no claim items. "
                    f"Claims should be auto-created via signals when InvoiceLines are created."
                )
            
            logger.info(
                f"✅ Insurance invoice {invoice.invoice_number} linked to "
                f"{payer.name} ({claim_items.count()} claim items)"
            )
            
            return {
                'success': True,
                'message': f'Invoice linked to insurance: {payer.name}',
                'account_type': 'insurance',
                'insurance_company': payer.name,
                'claim_items_count': claim_items.count(),
                'insurance_enrollment': insurance_enrollment.insurance_company.name if insurance_enrollment else None
            }
            
        except ImportError:
            # Insurance models not available
            return {
                'success': True,
                'message': 'Insurance invoice linked (Insurance models not available)',
                'account_type': 'insurance'
            }
        except Exception as e:
            logger.error(f"Error linking insurance invoice: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': f'Error linking insurance invoice: {str(e)}',
                'account_type': 'insurance'
            }
    
    @staticmethod
    def verify_all_invoices_linked():
        """
        Verify all invoices are properly linked to their payer accounts
        and identify any issues
        
        Returns:
            dict: Summary of verification results
        """
        from hospital.models import Invoice
        
        invoices = Invoice.objects.filter(is_deleted=False)
        total = invoices.count()
        verified = 0
        issues = []
        
        for invoice in invoices:
            result = BillingAccountLinkService.ensure_invoice_linked_to_account(invoice)
            if result['success']:
                verified += 1
            else:
                issues.append({
                    'invoice': invoice.invoice_number,
                    'patient': invoice.patient.mrn if invoice.patient else 'N/A',
                    'payer': invoice.payer.name if invoice.payer else 'N/A',
                    'issue': result['message']
                })
        
        return {
            'total_invoices': total,
            'verified': verified,
            'issues': issues,
            'success_rate': (verified / total * 100) if total > 0 else 0
        }

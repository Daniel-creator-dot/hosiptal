"""
Visit Payer Type Synchronization Service
Ensures payer type is properly set and synced throughout the visit lifecycle
Acts as Senior Engineering & Pricing Officer
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class VisitPayerSyncService:
    """
    Senior Engineering & Pricing Officer Service
    Ensures proper payer type handling, pricing, and claims creation
    """
    
    def __init__(self):
        self.logger = logger
    
    def verify_and_set_payer_type(self, encounter, payer_type=None, payer=None):
        """
        Verify and set payer type for encounter
        Ensures patient, encounter, and invoice all have correct payer
        
        Args:
            encounter: Encounter object
            payer_type: 'cash', 'insurance', 'corporate' (optional, will auto-detect)
            payer: Payer object (optional, will get from patient)
        
        Returns:
            dict: {
                'success': bool,
                'payer': Payer object,
                'payer_type': str,
                'message': str,
                'pricing_category': PricingCategory object
            }
        """
        try:
            from hospital.models import Payer
            from hospital.models_flexible_pricing import PricingCategory
            from hospital.models_enterprise_billing import CorporateEmployee
            from hospital.models_insurance_companies import PatientInsurance, InsuranceCompany
            
            patient = encounter.patient
            # Fresh FK from DB — encounter may carry a cached Patient instance from create()
            # without the primary_insurance_id set after registration just saved the patient.
            patient.refresh_from_db(fields=['primary_insurance_id'])

            # Step 1: Determine payer type
            if payer_type:
                # Use provided payer type
                determined_payer_type = payer_type
            elif payer:
                # Get payer type from payer object
                determined_payer_type = payer.payer_type
            elif patient.primary_insurance:
                # Get from patient's primary insurance
                payer = patient.primary_insurance
                determined_payer_type = payer.payer_type
            else:
                # Default to cash
                determined_payer_type = 'cash'
            
            # Step 2: Get or create appropriate payer
            if payer:
                # Use provided payer
                final_payer = payer
            elif determined_payer_type == 'cash':
                # Get or create Cash payer
                final_payer, _ = Payer.objects.get_or_create(
                    name='Cash',
                    defaults={
                        'payer_type': 'cash',
                        'is_active': True,
                    }
                )
            elif determined_payer_type == 'corporate':
                # Get corporate payer from patient's enrollment
                corporate_enrollment = CorporateEmployee.objects.filter(
                    patient=patient,
                    is_active=True,
                    is_deleted=False
                ).select_related('corporate_account').first()
                
                if corporate_enrollment:
                    from hospital.patient_payer import ensure_corporate_payer

                    company_name = corporate_enrollment.corporate_account.company_name
                    final_payer = ensure_corporate_payer(company_name)
                else:
                    # Fallback to cash if no corporate enrollment
                    self.logger.warning(f"Patient {patient.mrn} marked as corporate but no enrollment found, using cash")
                    final_payer, _ = Payer.objects.get_or_create(
                        name='Cash',
                        defaults={
                            'payer_type': 'cash',
                            'is_active': True,
                        }
                    )
                    determined_payer_type = 'cash'
            elif determined_payer_type in ['insurance', 'private', 'nhis']:
                # Get insurance payer from patient's insurance
                patient_insurance = PatientInsurance.objects.filter(
                    patient=patient,
                    is_primary=True,
                    status='active',
                    is_deleted=False
                ).select_related('insurance_company').first()
                
                if patient_insurance and patient_insurance.insurance_company:
                    from hospital.patient_payer import resolve_payer_for_insurance_company

                    final_payer = resolve_payer_for_insurance_company(
                        patient_insurance.insurance_company
                    )
                elif patient.primary_insurance:
                    final_payer = patient.primary_insurance
                else:
                    # Fallback to cash
                    self.logger.warning(f"Patient {patient.mrn} marked as insurance but no insurance found, using cash")
                    final_payer, _ = Payer.objects.get_or_create(
                        name='Cash',
                        defaults={
                            'payer_type': 'cash',
                            'is_active': True,
                        }
                    )
                    determined_payer_type = 'cash'
            else:
                # Unknown type, default to cash
                final_payer, _ = Payer.objects.get_or_create(
                    name='Cash',
                    defaults={
                        'payer_type': 'cash',
                        'is_active': True,
                    }
                )
                determined_payer_type = 'cash'

            # Never replace a persisted non-cash primary payer with Cash (stale sync / missing enrollment timing)
            patient.refresh_from_db(fields=['primary_insurance_id'])
            if patient.primary_insurance_id:
                pi = patient.primary_insurance
                if (
                    pi
                    and not getattr(pi, 'is_deleted', False)
                    and getattr(pi, 'payer_type', None) != 'cash'
                    and final_payer.payer_type == 'cash'
                ):
                    self.logger.warning(
                        'Keeping patient %s primary payer %s (%s); sync would have set Cash',
                        patient.mrn,
                        pi.name,
                        pi.payer_type,
                    )
                    final_payer = pi
                    determined_payer_type = pi.payer_type
            
            # Step 3: Update patient's primary insurance if needed
            if patient.primary_insurance != final_payer:
                patient.primary_insurance = final_payer
                patient.save(update_fields=['primary_insurance'])
                self.logger.info(f"Updated patient {patient.mrn} primary_insurance to {final_payer.name}")
            
            # Step 4: Get pricing category
            pricing_category = self._get_pricing_category(final_payer, determined_payer_type, patient)
            
            # Step 5: Sync encounter invoice payer
            self._sync_encounter_invoice_payer(encounter, final_payer)
            
            return {
                'success': True,
                'payer': final_payer,
                'payer_type': determined_payer_type,
                'pricing_category': pricing_category,
                'message': f'Payer type set to {determined_payer_type} ({final_payer.name})'
            }
            
        except Exception as e:
            self.logger.error(f"Error verifying payer type: {str(e)}", exc_info=True)
            return {
                'success': False,
                'payer': None,
                'payer_type': 'cash',
                'pricing_category': None,
                'message': f'Error: {str(e)}'
            }
    
    def _get_pricing_category(self, payer, payer_type, patient):
        """Get appropriate pricing category for payer"""
        try:
            from hospital.models_flexible_pricing import PricingCategory
            from hospital.models_insurance_companies import InsuranceCompany
            from hospital.models_enterprise_billing import CorporateEmployee
            
            if payer_type == 'cash':
                return PricingCategory.objects.filter(
                    code='CASH',
                    is_active=True,
                    is_deleted=False
                ).first()
            
            elif payer_type == 'corporate':
                return PricingCategory.objects.filter(
                    code='CORP',
                    is_active=True,
                    is_deleted=False
                ).first()
            
            elif payer_type in ['insurance', 'private', 'nhis']:
                # Try to find insurance company specific category
                insurance_company = InsuranceCompany.objects.filter(
                    name__iexact=payer.name,
                    is_active=True,
                    is_deleted=False
                ).first()
                
                if insurance_company:
                    category = PricingCategory.objects.filter(
                        insurance_company=insurance_company,
                        category_type='insurance',
                        is_active=True,
                        is_deleted=False
                    ).first()
                    if category:
                        return category
                
                # Fallback to general insurance or NHIS
                if payer_type == 'nhis':
                    return PricingCategory.objects.filter(
                        code='NHIS',
                        is_active=True,
                        is_deleted=False
                    ).first()
                else:
                    return PricingCategory.objects.filter(
                        code='INS',
                        is_active=True,
                        is_deleted=False
                    ).first()
            
            # Default to cash
            return PricingCategory.objects.filter(
                code='CASH',
                is_active=True,
                is_deleted=False
            ).first()
            
        except Exception as e:
            self.logger.error(f"Error getting pricing category: {str(e)}")
            return None
    
    def _sync_encounter_invoice_payer(self, encounter, payer):
        """Ensure encounter's invoice has correct payer and consultation line price."""
        try:
            from hospital.utils_billing import (
                get_consultation_line_for_encounter,
                get_consultation_price_for_encounter_and_payer,
                get_mat_anc_consultation_price,
                get_or_create_encounter_invoice,
            )

            # all_objects + IntegrityError pattern; avoids missing zero-total invoices and duplicate key errors
            invoice = get_or_create_encounter_invoice(encounter)
            if not invoice:
                return None

            if invoice.payer_id != payer.id:
                invoice.payer = payer
                invoice.save(update_fields=['payer'])
                self.logger.info(f"Updated invoice {invoice.id} payer to {payer.name}")

                # Consultation lines: CON001/CON002/MAT-ANC — match reception billing
                consultation_line = get_consultation_line_for_encounter(encounter)
                if consultation_line and consultation_line.service_code_id:
                    code = (getattr(consultation_line.service_code, 'code', None) or '').strip().upper()
                    if code == 'MAT-ANC':
                        new_price = get_mat_anc_consultation_price(encounter.patient, payer)
                    elif code in ('CON001', 'CON002', 'CONS-GEN', 'S00023'):
                        consultation_type = 'specialist' if code == 'CON002' else 'general'
                        new_price = get_consultation_price_for_encounter_and_payer(
                            encounter, payer, consultation_type=consultation_type
                        )
                    else:
                        new_price = None
                    if new_price is not None:
                        consultation_line.unit_price = new_price
                        consultation_line.line_total = new_price
                        consultation_line.save(update_fields=['unit_price', 'line_total', 'modified'])
                        invoice.update_totals()
                        self.logger.info(
                            f"Updated consultation line {consultation_line.id} to GHS {new_price} for payer {payer.name}"
                        )

            return invoice

        except Exception as e:
            self.logger.error(f"Error syncing invoice payer: {str(e)}")
            return None
    
    def ensure_claims_created(self, encounter):
        """
        Ensure insurance claims are created for insurance patients
        This is called after services are added to invoice
        """
        try:
            from hospital.models import Invoice, InvoiceLine
            from hospital.models_insurance import InsuranceClaimItem
            
            patient = encounter.patient
            
            # Only create claims for insurance patients
            if not patient.primary_insurance or patient.primary_insurance.payer_type == 'cash':
                return {'success': True, 'message': 'Not an insurance patient, no claims needed'}
            
            # all_objects: zero-total draft invoices are excluded from default manager
            invoice = Invoice.all_objects.filter(
                encounter=encounter,
                is_deleted=False
            ).first()
            
            if not invoice:
                return {'success': False, 'message': 'No invoice found for encounter'}
            
            # Check each invoice line
            created_count = 0
            for line in invoice.lines.filter(is_deleted=False):
                # Skip if already has claim
                if InsuranceClaimItem.objects.filter(
                    invoice_line=line,
                    is_deleted=False
                ).exists():
                    continue
                
                # Skip if excluded from insurance
                if line.is_insurance_excluded:
                    continue
                
                # Create claim item
                insurance_id = (
                    patient.insurance_member_id or 
                    patient.insurance_id or 
                    patient.insurance_policy_number or
                    'NOT_PROVIDED'
                )
                
                InsuranceClaimItem.objects.create(
                    patient=patient,
                    payer=invoice.payer,
                    patient_insurance_id=insurance_id,
                    invoice=invoice,
                    invoice_line=line,
                    encounter=encounter,
                    service_code=line.service_code,
                    service_description=line.description,
                    service_date=invoice.issued_at.date() if invoice.issued_at else timezone.now().date(),
                    billed_amount=line.line_total,
                    claim_status='pending',
                    notes=f"Auto-generated from encounter {encounter.id}"
                )
                created_count += 1
            
            if created_count > 0:
                self.logger.info(f"Created {created_count} claim items for encounter {encounter.id}")
                return {'success': True, 'message': f'Created {created_count} claim items', 'count': created_count}
            else:
                return {'success': True, 'message': 'No new claims needed', 'count': 0}
                
        except Exception as e:
            self.logger.error(f"Error ensuring claims created: {str(e)}", exc_info=True)
            return {'success': False, 'message': f'Error: {str(e)}'}


# Singleton instance
visit_payer_sync_service = VisitPayerSyncService()

"""
Pricing Engine Service
Determines correct price based on payer type, contracts, and pricing tiers
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)


class PricingEngineService:
    """
    Intelligent pricing engine for multi-tier healthcare billing
    Handles Cash, Corporate, Insurance, and custom contract pricing
    """
    
    def __init__(self):
        self.logger = logger
    
    def get_service_price(self, service_code, patient, payer=None):
        """
        Get correct price for service based on patient's payer type
        
        Priority Order:
        1. Payer-specific custom price (if corporate/insurance has special contract)
        2. Corporate pricing (if patient is corporate employee)
        3. Insurance pricing (if patient has insurance)
        4. Cash pricing (default)
        
        Args:
            service_code: ServiceCode object
            patient: Patient object
            payer: Payer object (optional, will auto-detect from patient)
        
        Returns:
            Decimal: Price to charge
        """
        try:
            from hospital.models_enterprise_billing import ServicePricing, CorporateEmployee
            
            # Auto-detect payer if not provided
            if not payer:
                payer = patient.primary_insurance
            
            # Check if patient is corporate employee
            corporate_enrollment = self._get_corporate_enrollment(patient)
            
            # Get pricing record
            today = timezone.now().date()
            
            # Priority 1: Payer-specific custom price
            if payer:
                custom_pricing = ServicePricing.objects.filter(
                    service_code=service_code,
                    payer=payer,
                    is_active=True,
                    effective_from__lte=today
                ).filter(
                    Q(effective_to__isnull=True) | Q(effective_to__gte=today)
                ).first()
                
                if custom_pricing and custom_pricing.custom_price:
                    self.logger.info(
                        f"Using custom price for {service_code.description}: "
                        f"GHS {custom_pricing.custom_price} (Payer: {payer.name})"
                    )
                    return custom_pricing.custom_price
            
            # Get standard pricing tiers
            standard_pricing = ServicePricing.objects.filter(
                service_code=service_code,
                payer__isnull=True,  # Standard pricing, not payer-specific
                is_active=True,
                effective_from__lte=today
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=today)
            ).first()
            
            if not standard_pricing:
                # Fallback to a default price
                self.logger.warning(
                    f"No pricing record found for {service_code.description}, "
                    f"using default fallback price GHS 0.00"
                )
                return Decimal('0.00')
            
            # Priority 2: Corporate pricing (if enrolled)
            if corporate_enrollment and corporate_enrollment.is_active:
                price = standard_pricing.corporate_price
                
                # Apply corporate-specific discount
                corporate_account = corporate_enrollment.corporate_account
                if corporate_account.global_discount_percentage > 0:
                    discount = price * (corporate_account.global_discount_percentage / 100)
                    price = price - discount
                    self.logger.info(
                        f"Applied {corporate_account.global_discount_percentage}% "
                        f"corporate discount for {corporate_account.company_name}"
                    )
                
                self.logger.info(
                    f"Using corporate price for {service_code.description}: GHS {price} "
                    f"(Company: {corporate_account.company_name})"
                )
                return price
            
            # Priority 3: Insurance pricing (if patient has insurance)
            if payer and payer.payer_type == 'insurance':
                price = standard_pricing.insurance_price
                self.logger.info(
                    f"Using insurance price for {service_code.description}: GHS {price}"
                )
                return price
            
            # Priority 4: Cash pricing (default)
            price = standard_pricing.cash_price
            self.logger.info(
                f"Using cash price for {service_code.description}: GHS {price}"
            )
            return price
            
        except Exception as e:
            self.logger.error(f"Error getting service price: {str(e)}", exc_info=True)
            # Return zero as fallback
            return Decimal('0.00')
    
    def apply_corporate_discount(self, amount, corporate_account):
        """
        Apply corporate-specific discount to amount
        
        Args:
            amount: Decimal amount
            corporate_account: CorporateAccount object
        
        Returns:
            Decimal: Discounted amount
        """
        if corporate_account.global_discount_percentage > 0:
            discount = amount * (corporate_account.global_discount_percentage / 100)
            final_amount = amount - discount
            self.logger.info(
                f"Applied {corporate_account.global_discount_percentage}% discount "
                f"for {corporate_account.company_name}: "
                f"GHS {amount} → GHS {final_amount}"
            )
            return final_amount
        return amount
    
    def check_coverage_limits(self, patient, amount):
        """
        Check if patient is within coverage limits
        
        Args:
            patient: Patient object
            amount: Decimal amount to charge
        
        Returns:
            dict: {
                'within_limit': bool,
                'remaining_limit': Decimal or None,
                'exceeded_by': Decimal or None,
                'message': str
            }
        """
        try:
            from hospital.models_enterprise_billing import CorporateEmployee
            
            # Check if patient is corporate employee
            enrollment = CorporateEmployee.objects.filter(
                patient=patient,
                is_active=True
            ).first()
            
            if not enrollment:
                # Not a corporate employee, no limits apply
                return {
                    'within_limit': True,
                    'remaining_limit': None,
                    'exceeded_by': None,
                    'message': 'No coverage limits apply'
                }
            
            if not enrollment.has_annual_limit:
                # Corporate employee but no annual limit set
                return {
                    'within_limit': True,
                    'remaining_limit': None,
                    'exceeded_by': None,
                    'message': f'Corporate coverage (No limit) - {enrollment.corporate_account.company_name}'
                }
            
            # Check if limit would be exceeded
            remaining = enrollment.remaining_limit or Decimal('0.00')
            
            if amount <= remaining:
                return {
                    'within_limit': True,
                    'remaining_limit': remaining,
                    'exceeded_by': None,
                    'message': f'Within limit. GHS {remaining:.2f} remaining'
                }
            else:
                exceeded_by = amount - remaining
                return {
                    'within_limit': False,
                    'remaining_limit': remaining,
                    'exceeded_by': exceeded_by,
                    'message': f'⚠️ Exceeds limit by GHS {exceeded_by:.2f}. Only GHS {remaining:.2f} remaining'
                }
                
        except Exception as e:
            self.logger.error(f"Error checking coverage limits: {str(e)}", exc_info=True)
            return {
                'within_limit': True,  # Default to allowing service
                'remaining_limit': None,
                'exceeded_by': None,
                'message': 'Error checking limits'
            }
    
    def update_utilization(self, patient, amount):
        """
        Update patient's utilization amount after service
        
        Args:
            patient: Patient object
            amount: Decimal amount charged
        """
        try:
            from hospital.models_enterprise_billing import CorporateEmployee
            
            enrollment = CorporateEmployee.objects.filter(
                patient=patient,
                is_active=True
            ).first()
            
            if enrollment and enrollment.has_annual_limit:
                enrollment.utilized_amount += amount
                enrollment.save(update_fields=['utilized_amount'])
                
                self.logger.info(
                    f"Updated utilization for {patient.full_name}: "
                    f"GHS {enrollment.utilized_amount:.2f} / GHS {enrollment.annual_limit:.2f}"
                )
                
        except Exception as e:
            self.logger.error(f"Error updating utilization: {str(e)}", exc_info=True)
    
    def _get_corporate_enrollment(self, patient):
        """Get active corporate enrollment for patient"""
        try:
            from hospital.models_enterprise_billing import CorporateEmployee
            
            return CorporateEmployee.objects.filter(
                patient=patient,
                is_active=True
            ).select_related('corporate_account').first()
            
        except Exception as e:
            self.logger.error(f"Error getting corporate enrollment: {str(e)}", exc_info=True)
            return None
    
    def get_pricing_summary(self, service_code):
        """
        Get summary of all pricing tiers for a service
        
        Args:
            service_code: ServiceCode object
        
        Returns:
            dict: Pricing information
        """
        try:
            from hospital.models_enterprise_billing import ServicePricing
            
            today = timezone.now().date()
            
            pricing = ServicePricing.objects.filter(
                service_code=service_code,
                payer__isnull=True,
                is_active=True,
                effective_from__lte=today
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=today)
            ).first()
            
            if pricing:
                return {
                    'cash_price': pricing.cash_price,
                    'corporate_price': pricing.corporate_price,
                    'insurance_price': pricing.insurance_price,
                    'effective_from': pricing.effective_from,
                    'effective_to': pricing.effective_to,
                }
            else:
                return {
                    'cash_price': service_code.default_price or Decimal('0.00'),
                    'corporate_price': None,
                    'insurance_price': None,
                    'effective_from': None,
                    'effective_to': None,
                    'note': 'No pricing tiers configured, using default price'
                }
                
        except Exception as e:
            self.logger.error(f"Error getting pricing summary: {str(e)}", exc_info=True)
            return {}


# Global instance
pricing_engine = PricingEngineService()


"""
Pricing Engine Service
Determines correct price based on payer type, contracts, and pricing tiers
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q

logger = logging.getLogger(__name__)

# 30% markup for lab and imaging/scan when payer is insurance or corporate
LAB_IMAGING_INSURANCE_CORPORATE_MARKUP = Decimal('0.30')


class PricingEngineService:
    """
    Intelligent pricing engine for multi-tier healthcare billing
    Handles Cash, Corporate, Insurance, and custom contract pricing
    """
    
    def __init__(self):
        self.logger = logger

    @staticmethod
    def _apply_lab_imaging_markup(price, service_code, payer):
        """Apply 30% markup for lab and imaging/scan when payer is insurance or corporate."""
        if not price or price <= 0:
            return price
        if not payer or getattr(payer, 'payer_type', None) not in ('insurance', 'private', 'nhis', 'corporate'):
            return price
        if not service_code:
            return price
        code = (getattr(service_code, 'code', None) or '').strip().upper()
        category = (getattr(service_code, 'category', None) or '').lower()
        is_lab = code.startswith('LAB-') or 'laboratory' in category or 'lab' in category
        is_imaging = code.startswith('IMG-') or 'imaging' in category or 'radiology' in category or 'scan' in category
        if not (is_lab or is_imaging):
            return price
        return (price * (1 + LAB_IMAGING_INSURANCE_CORPORATE_MARKUP)).quantize(Decimal('0.01'))
    
    def get_service_price(self, service_code, patient, payer=None):
        """
        Get correct price for service based on patient's payer type
        
        Priority Order:
        1. Insurance-specific pricing (if patient has insurance with specific company)
        2. Corporate pricing (if patient is corporate employee)
        3. General insurance pricing (if patient has insurance)
        4. Cash pricing (default)
        
        Uses the flexible pricing system (ServicePrice + PricingCategory)
        
        Args:
            service_code: ServiceCode object
            patient: Patient object
            payer: Payer object (optional, will auto-detect from patient)
        
        Returns:
            Decimal: Price to charge
        """
        try:
            from hospital.models_flexible_pricing import ServicePrice, PricingCategory
            from hospital.models_insurance_companies import InsuranceCompany
            from hospital.models_enterprise_billing import CorporateEmployee
            
            # Auto-detect payer if not provided
            if not payer:
                payer = patient.primary_insurance
            
            # Get pricing record
            today = timezone.now().date()
            
            # Treat private and NHIS as insurance for pricing (see Payer.INSURANCE_PAYER_TYPES)
            is_insurance_payer = payer and payer.payer_type in ('insurance', 'private', 'nhis')
            
            # Priority 1: Insurance-specific pricing (if patient has specific insurance company)
            if is_insurance_payer:
                # Find InsuranceCompany from Payer name
                insurance_company = InsuranceCompany.objects.filter(
                    name__iexact=payer.name,
                    is_active=True,
                    is_deleted=False
                ).first()
                
                if insurance_company:
                    # Find PricingCategory linked to this insurance company
                    pricing_category = PricingCategory.objects.filter(
                        insurance_company=insurance_company,
                        category_type='insurance',
                        is_active=True,
                        is_deleted=False
                    ).first()
                    
                    if pricing_category:
                        # Get ServicePrice for this specific insurance
                        service_price = ServicePrice.get_price(service_code, pricing_category, today)
                        if service_price:
                            final = self._apply_lab_imaging_markup(service_price, service_code, payer)
                            self.logger.info(
                                f"Using {insurance_company.name} price for {service_code.description}: "
                                f"GHS {final}"
                            )
                            return final
            
            # Priority 2: Corporate pricing (if patient is corporate employee)
            corporate_enrollment = self._get_corporate_enrollment(patient)
            if corporate_enrollment and corporate_enrollment.is_active:
                # Find corporate pricing category
                corporate_category = PricingCategory.objects.filter(
                    category_type='corporate',
                    is_active=True,
                    is_deleted=False
                ).order_by('priority').first()
                
                if corporate_category:
                    service_price = ServicePrice.get_price(service_code, corporate_category, today)
                    if service_price:
                        final = self._apply_lab_imaging_markup(service_price, service_code, payer)
                        self.logger.info(
                            f"Using corporate price for {service_code.description}: GHS {final} "
                            f"(Company: {corporate_enrollment.corporate_account.company_name})"
                        )
                        return final
            
            # Priority 3: General insurance pricing (if patient has insurance but no specific company match)
            if is_insurance_payer:
                # Try general insurance category
                insurance_category = PricingCategory.objects.filter(
                    category_type='insurance',
                    is_active=True,
                    is_deleted=False
                ).exclude(name__icontains='cash').exclude(name__icontains='other company').order_by('priority').first()
                
                if insurance_category:
                    service_price = ServicePrice.get_price(service_code, insurance_category, today)
                    if service_price:
                        final = self._apply_lab_imaging_markup(service_price, service_code, payer)
                        self.logger.info(
                            f"Using general insurance price for {service_code.description}: GHS {final}"
                        )
                        return final
            
            # Priority 4: Cash pricing (default)
            cash_category = PricingCategory.objects.filter(
                category_type='cash',
                is_active=True,
                is_deleted=False
            ).order_by('priority').first()
            
            if cash_category:
                service_price = ServicePrice.get_price(service_code, cash_category, today)
                if service_price:
                    final = self._apply_lab_imaging_markup(service_price, service_code, payer)
                    self.logger.info(
                        f"Using cash price for {service_code.description}: GHS {final}"
                    )
                    return final
            
            # Priority 5: Fallback to ServicePricing (enterprise billing) so all insurance/cash/corporate prices sync
            from hospital.models import ServiceCode
            from hospital.models_enterprise_billing import ServicePricing
            
            # Build list of service codes to try (consultation CON001/CON002 and S00023 are interchangeable)
            service_codes_to_try = []
            if service_code:
                service_codes_to_try.append(service_code)
                if service_code.code in ('CON001', 'CON002'):
                    alt = ServiceCode.objects.filter(code='S00023', is_deleted=False).first()
                    if alt and alt not in service_codes_to_try:
                        service_codes_to_try.append(alt)
                elif service_code.code == 'S00023':
                    alt = ServiceCode.objects.filter(code='CON001', is_deleted=False).first()
                    if alt and alt not in service_codes_to_try:
                        service_codes_to_try.append(alt)
            
            for sc in service_codes_to_try:
                pricing_qs = ServicePricing.objects.filter(
                    service_code=sc,
                    is_active=True,
                    effective_from__lte=today,
                    is_deleted=False
                ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
                pricing = None
                if payer:
                    pricing = pricing_qs.filter(payer=payer).first()
                if not pricing:
                    pricing = pricing_qs.filter(payer__isnull=True).first()
                if not pricing:
                    pricing = pricing_qs.first()
                if pricing:
                    if is_insurance_payer and getattr(pricing, 'insurance_price', None) and Decimal(str(pricing.insurance_price)) > 0:
                        p = Decimal(str(pricing.insurance_price))
                        final = self._apply_lab_imaging_markup(p, sc, payer)
                        self.logger.info(f"Using ServicePricing insurance price for {sc.description}: GHS {final}")
                        return final
                    if payer and payer.payer_type == 'corporate' and getattr(pricing, 'corporate_price', None) and Decimal(str(pricing.corporate_price)) > 0:
                        p = Decimal(str(pricing.corporate_price))
                        final = self._apply_lab_imaging_markup(p, sc, payer)
                        self.logger.info(f"Using ServicePricing corporate price for {sc.description}: GHS {final}")
                        return final
                    if (not payer or payer.payer_type == 'cash') and getattr(pricing, 'cash_price', None) and Decimal(str(pricing.cash_price)) > 0:
                        p = Decimal(str(pricing.cash_price))
                        final = self._apply_lab_imaging_markup(p, sc, payer)
                        self.logger.info(f"Using ServicePricing cash price for {sc.description}: GHS {final}")
                        return final
                    if is_insurance_payer and getattr(pricing, 'insurance_price', None) and Decimal(str(pricing.insurance_price)) > 0:
                        return self._apply_lab_imaging_markup(Decimal(str(pricing.insurance_price)), sc, payer)
                    if getattr(pricing, 'corporate_price', None) and Decimal(str(pricing.corporate_price)) > 0:
                        return self._apply_lab_imaging_markup(Decimal(str(pricing.corporate_price)), sc, payer)
                    if getattr(pricing, 'cash_price', None) and Decimal(str(pricing.cash_price)) > 0:
                        return self._apply_lab_imaging_markup(Decimal(str(pricing.cash_price)), sc, payer)
            
            # Final fallback
            self.logger.warning(
                f"No pricing record found for {service_code.description if service_code else 'service'}, "
                f"using default fallback price GHS 0.00"
            )
            return self._apply_lab_imaging_markup(Decimal('0.00'), service_code, payer)
            
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
                    'cash_price': Decimal('0.00'),
                    'corporate_price': None,
                    'insurance_price': None,
                    'effective_from': None,
                    'effective_to': None,
                    'note': 'No pricing tiers configured; run seed_general_prices'
                }
                
        except Exception as e:
            self.logger.error(f"Error getting pricing summary: {str(e)}", exc_info=True)
            return {}


# Global instance
pricing_engine = PricingEngineService()


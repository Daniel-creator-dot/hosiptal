"""
World-Class Flexible Pricing System
Set different prices for Cash, Insurance, and Corporate clients
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from .models import BaseModel, ServiceCode
from .models_insurance_companies import InsuranceCompany


class PricingCategory(BaseModel):
    """
    Pricing Categories - Different price tiers (Cash, Insurance, Corporate, etc.)
    """
    CATEGORY_TYPE_CHOICES = [
        ('cash', 'Cash Payment'),
        ('insurance', 'Insurance'),
        ('corporate', 'Corporate'),
        ('government', 'Government'),
        ('discount', 'Discounted Rate'),
        ('premium', 'Premium Rate'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=200, unique=True, 
                           help_text="Name of pricing category (e.g., 'Cash Patients', 'NHIS', 'Corporate XYZ')")
    code = models.CharField(max_length=50, unique=True,
                           help_text="Short code (e.g., 'CASH', 'NHIS', 'CORP-XYZ')")
    category_type = models.CharField(max_length=20, choices=CATEGORY_TYPE_CHOICES, default='cash')
    
    # Description
    description = models.TextField(blank=True, 
                                  help_text="Description of this pricing category")
    
    # Linked Insurance Company (optional)
    insurance_company = models.ForeignKey('InsuranceCompany', on_delete=models.SET_NULL, 
                                         null=True, blank=True, related_name='pricing_categories',
                                         help_text="Link to insurance company if applicable")
    
    # Default Discount/Markup
    default_discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('-100'))],
        help_text="Default discount % (negative = markup). E.g., 10 = 10% discount, -20 = 20% markup"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=100, 
                                   help_text="Priority order for display (lower = higher priority)")
    
    # Colors for UI
    color_code = models.CharField(max_length=7, default='#3b82f6',
                                  help_text="Hex color code for UI display (e.g., #3b82f6)")
    
    class Meta:
        ordering = ['priority', 'name']
        verbose_name = 'Pricing Category'
        verbose_name_plural = 'Pricing Categories'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['category_type']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    @property
    def services_count(self):
        """Count services with prices in this category"""
        return ServicePrice.objects.filter(
            pricing_category=self,
            is_deleted=False
        ).count()


class ServicePrice(BaseModel):
    """
    Service Prices - Prices for each service in each pricing category
    """
    # Service and Category
    service_code = models.ForeignKey(ServiceCode, on_delete=models.CASCADE, 
                                    related_name='flexible_prices')
    pricing_category = models.ForeignKey(PricingCategory, on_delete=models.CASCADE,
                                        related_name='service_prices')
    
    # Price
    price = models.DecimalField(max_digits=10, decimal_places=2,
                               validators=[MinValueValidator(Decimal('0.00'))],
                               help_text="Price in GHS for this service in this category")
    
    # Effective Period
    effective_from = models.DateField(default=timezone.now,
                                     help_text="Date this price becomes effective")
    effective_to = models.DateField(null=True, blank=True,
                                   help_text="Date this price expires (leave blank for no expiry)")
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Notes
    notes = models.TextField(blank=True, help_text="Internal notes about this price")
    
    class Meta:
        ordering = ['-effective_from', 'service_code', 'pricing_category']
        unique_together = ['service_code', 'pricing_category', 'effective_from']
        verbose_name = 'Service Price'
        verbose_name_plural = 'Service Prices'
        indexes = [
            models.Index(fields=['service_code', 'pricing_category']),
            models.Index(fields=['pricing_category', 'is_active']),
            models.Index(fields=['effective_from', 'effective_to']),
        ]
    
    def __str__(self):
        return f"{self.service_code.description} - {self.pricing_category.name}: GHS {self.price}"
    
    @property
    def is_current(self):
        """Check if this price is currently valid"""
        today = timezone.now().date()
        
        if not self.is_active:
            return False
        
        if self.effective_from > today:
            return False
        
        if self.effective_to and self.effective_to < today:
            return False
        
        return True
    
    @classmethod
    def get_price(cls, service_code, pricing_category, date=None):
        """
        Get the active price for a service in a pricing category
        Returns the price or None if not found
        """
        if date is None:
            date = timezone.now().date()
        
        price_obj = cls.objects.filter(
            service_code=service_code,
            pricing_category=pricing_category,
            is_active=True,
            effective_from__lte=date,
            is_deleted=False
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=date)
        ).order_by('-effective_from').first()
        
        if price_obj:
            return price_obj.price
        return None
    
    @classmethod
    def get_price_by_payer_type(cls, service_code, payer_type='cash', insurance_company=None, date=None):
        """
        Get price based on payer type
        """
        if date is None:
            date = timezone.now().date()
        
        # Try to find exact pricing category
        category = None
        
        if insurance_company and payer_type in ['insurance', 'nhis', 'private']:
            # Try to find category linked to this insurance company
            category = PricingCategory.objects.filter(
                insurance_company=insurance_company,
                is_active=True,
                is_deleted=False
            ).first()
        
        if not category:
            # Fallback to category type
            category = PricingCategory.objects.filter(
                category_type=payer_type,
                is_active=True,
                is_deleted=False
            ).order_by('priority').first()
        
        if not category:
            # Final fallback to cash
            category = PricingCategory.objects.filter(
                category_type='cash',
                is_active=True,
                is_deleted=False
            ).first()
        
        if category:
            return cls.get_price(service_code, category, date)
        
        return None


class PriceHistory(BaseModel):
    """
    Price History - Track all price changes for auditing
    """
    ACTION_CHOICES = [
        ('created', 'Price Created'),
        ('updated', 'Price Updated'),
        ('deleted', 'Price Deleted'),
        ('expired', 'Price Expired'),
    ]
    
    # Reference
    service_price = models.ForeignKey(ServicePrice, on_delete=models.CASCADE,
                                     related_name='history', null=True, blank=True)
    service_code = models.ForeignKey(ServiceCode, on_delete=models.CASCADE,
                                    related_name='price_history')
    pricing_category = models.ForeignKey(PricingCategory, on_delete=models.CASCADE,
                                        related_name='price_history')
    
    # Action
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='created')
    
    # Price Data
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                   help_text="Previous price")
    new_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                   help_text="New price")
    
    # User who made the change
    changed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, 
                                  null=True, blank=True, related_name='price_changes')
    
    # Notes
    notes = models.TextField(blank=True, help_text="Reason for price change")
    
    class Meta:
        ordering = ['-created']
        verbose_name = 'Price History'
        verbose_name_plural = 'Price Histories'
        indexes = [
            models.Index(fields=['service_code', '-created']),
            models.Index(fields=['pricing_category', '-created']),
        ]
    
    def __str__(self):
        return f"{self.service_code.code} - {self.action} at {self.created}"


class BulkPriceUpdate(BaseModel):
    """
    Bulk Price Updates - Track bulk price changes
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Update Information
    name = models.CharField(max_length=200, help_text="Name/description of this bulk update")
    pricing_category = models.ForeignKey(PricingCategory, on_delete=models.CASCADE,
                                        related_name='bulk_updates', null=True, blank=True,
                                        help_text="Target pricing category (leave blank for all)")
    
    # Update Type
    update_type = models.CharField(max_length=20, choices=[
        ('percentage', 'Percentage Change'),
        ('fixed', 'Fixed Amount Change'),
        ('set_price', 'Set Specific Prices'),
    ], default='percentage')
    
    # Update Value
    percentage_change = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'),
                                           help_text="% change (e.g., 10 = increase by 10%, -10 = decrease by 10%)")
    fixed_amount_change = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                             help_text="Fixed amount change (e.g., 5 = add GHS 5, -5 = subtract GHS 5)")
    
    # Effective Date
    effective_date = models.DateField(default=timezone.now,
                                     help_text="When the new prices become effective")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    services_affected = models.IntegerField(default=0, help_text="Number of services affected")
    
    # Processing
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='bulk_price_updates')
    
    # Notes
    notes = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
        verbose_name = 'Bulk Price Update'
        verbose_name_plural = 'Bulk Price Updates'
    
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
    
    def execute(self, user=None):
        """Execute the bulk price update"""
        from django.db import transaction
        
        try:
            with transaction.atomic():
                self.status = 'processing'
                self.save(update_fields=['status'])
                
                # Get services to update
                if self.pricing_category:
                    service_prices = ServicePrice.objects.filter(
                        pricing_category=self.pricing_category,
                        is_active=True,
                        is_deleted=False
                    )
                else:
                    service_prices = ServicePrice.objects.filter(
                        is_active=True,
                        is_deleted=False
                    )
                
                count = 0
                for sp in service_prices:
                    old_price = sp.price
                    
                    if self.update_type == 'percentage':
                        new_price = old_price * (Decimal('1') + (self.percentage_change / Decimal('100')))
                    elif self.update_type == 'fixed':
                        new_price = old_price + self.fixed_amount_change
                    else:
                        continue  # Skip for set_price type (requires manual prices)
                    
                    # Ensure price is not negative
                    if new_price < 0:
                        new_price = Decimal('0.00')
                    
                    # Round to 2 decimal places
                    new_price = round(new_price, 2)
                    
                    # Update price
                    sp.price = new_price
                    sp.effective_from = self.effective_date
                    sp.save(update_fields=['price', 'effective_from'])
                    
                    # Create history
                    PriceHistory.objects.create(
                        service_price=sp,
                        service_code=sp.service_code,
                        pricing_category=sp.pricing_category,
                        action='updated',
                        old_price=old_price,
                        new_price=new_price,
                        changed_by=user,
                        notes=f"Bulk update: {self.name}"
                    )
                    
                    count += 1
                
                # Mark as completed
                self.status = 'completed'
                self.services_affected = count
                self.processed_at = timezone.now()
                self.processed_by = user
                self.save(update_fields=['status', 'services_affected', 'processed_at', 'processed_by'])
                
                return True, f"Successfully updated {count} prices"
        
        except Exception as e:
            self.status = 'failed'
            self.error_message = str(e)
            self.save(update_fields=['status', 'error_message'])
            return False, str(e)
























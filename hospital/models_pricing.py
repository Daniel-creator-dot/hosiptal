"""
Pricing Configuration System
Centralized place to manage and tweak prices for all services
"""
from django.db import models
from decimal import Decimal
from .models import BaseModel, ServiceCode, Payer


class DefaultPrice(BaseModel):
    """Default prices for services (independent of payer)"""
    SERVICE_CHOICES = [
        ('registration', 'Patient Registration'),
        ('consultation_general', 'General Consultation'),
        ('consultation_specialist', 'Specialist Consultation'),
        ('vital_signs', 'Vital Signs Recording'),
        ('lab_test', 'Laboratory Test'),
        ('imaging', 'Imaging Study'),
        ('pharmacy', 'Pharmacy Dispensing'),
        ('admission', 'Admission Fee'),
        ('bed_day', 'Bed Day Charge'),
    ]
    
    service_code = models.CharField(max_length=50, choices=SERVICE_CHOICES, unique=True)
    description = models.CharField(max_length=200)
    default_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='GHS', help_text="Currency code (GHS, USD, etc.)")
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['service_code']
        verbose_name = 'Default Price'
        verbose_name_plural = 'Default Prices'
    
    def __str__(self):
        return f"{self.get_service_code_display()} - {self.default_price} {self.currency}"
    
    @classmethod
    def get_price(cls, service_code, default=Decimal('0.00')):
        """Get price for a service code"""
        try:
            price_obj = cls.objects.get(service_code=service_code, is_active=True, is_deleted=False)
            return price_obj.default_price
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_price(cls, service_code, price, description=None):
        """Set or update price for a service code"""
        price_obj, created = cls.objects.update_or_create(
            service_code=service_code,
            is_deleted=False,
            defaults={
                'default_price': price,
                'description': description or cls.get_service_code_display_choices()[service_code],
                'is_active': True,
            }
        )
        return price_obj
    
    @staticmethod
    def get_service_code_display_choices():
        """Get dictionary of service code choices"""
        return dict(DefaultPrice.SERVICE_CHOICES)


class PayerPrice(BaseModel):
    """Payer-specific pricing (overrides default prices for specific payers)"""
    payer = models.ForeignKey(Payer, on_delete=models.CASCADE, related_name='payer_prices')
    service_code = models.CharField(max_length=50, choices=DefaultPrice.SERVICE_CHOICES)
    custom_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='GHS')
    is_active = models.BooleanField(default=True)
    effective_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ['payer', 'service_code']
        ordering = ['payer', 'service_code']
        verbose_name = 'Payer Price'
        verbose_name_plural = 'Payer Prices'
    
    def __str__(self):
        return f"{self.payer.name} - {self.get_service_code_display()} - {self.custom_price} {self.currency}"
    
    @classmethod
    def get_price(cls, payer, service_code):
        """Get payer-specific price, or fallback to default"""
        from django.utils import timezone
        today = timezone.now().date()
        
        # Try to get payer-specific price
        try:
            from django.db.models import Q
            payer_price = cls.objects.filter(
                payer=payer,
                service_code=service_code,
                is_active=True,
                is_deleted=False,
                effective_date__lte=today,
            ).filter(
                Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)
            ).first()
            
            if payer_price:
                return payer_price.custom_price
        except (cls.DoesNotExist, cls.MultipleObjectsReturned):
            pass
        
        # Fallback to default price
        return DefaultPrice.get_price(service_code)


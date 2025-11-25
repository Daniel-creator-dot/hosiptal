"""
💰 COMPREHENSIVE SERVICE PRICING SYSTEM
Manage prices for all hospital services
Lab | Pharmacy | Imaging | Consultations | Procedures
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal

from .models import BaseModel, Department


class ServicePriceList(BaseModel):
    """
    Master price list for all hospital services
    Allows different pricing for different payers (cash, insurance, etc.)
    """
    PAYER_TYPES = [
        ('cash', 'Cash Payment'),
        ('nhis', 'NHIS'),
        ('private_insurance', 'Private Insurance'),
        ('corporate', 'Corporate'),
        ('staff', 'Staff Discount'),
    ]
    
    payer_type = models.CharField(max_length=20, choices=PAYER_TYPES, default='cash')
    name = models.CharField(max_length=200, help_text="Price list name")
    description = models.TextField(blank=True)
    effective_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Discount percentage
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Overall discount % (e.g., 10.00 for 10%)"
    )
    
    class Meta:
        ordering = ['-created']
        verbose_name = 'Service Price List'
        verbose_name_plural = 'Service Price Lists'
    
    def __str__(self):
        return f"{self.name} ({self.get_payer_type_display()})"


class ConsultationPrice(BaseModel):
    """Consultation/Visit prices"""
    ENCOUNTER_TYPES = [
        ('outpatient', 'Outpatient Consultation'),
        ('inpatient', 'Inpatient Daily Care'),
        ('er', 'Emergency Visit'),
        ('specialist', 'Specialist Consultation'),
        ('followup', 'Follow-up Visit'),
    ]
    
    price_list = models.ForeignKey(
        ServicePriceList, 
        on_delete=models.CASCADE, 
        related_name='consultation_prices'
    )
    encounter_type = models.CharField(max_length=20, choices=ENCOUNTER_TYPES)
    department = models.ForeignKey(
        Department, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text="Specific department (optional)"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        ordering = ['encounter_type']
        unique_together = ['price_list', 'encounter_type', 'department']
    
    def __str__(self):
        dept = f" - {self.department.name}" if self.department else ""
        return f"{self.get_encounter_type_display()}{dept}: GHS {self.price}"


class ImagingPrice(BaseModel):
    """Imaging/Radiology prices"""
    IMAGING_TYPES = [
        ('xray', 'X-Ray'),
        ('ct', 'CT Scan'),
        ('mri', 'MRI'),
        ('ultrasound', 'Ultrasound'),
        ('mammography', 'Mammography'),
        ('fluoroscopy', 'Fluoroscopy'),
        ('dexa', 'DEXA Scan'),
    ]
    
    price_list = models.ForeignKey(
        ServicePriceList, 
        on_delete=models.CASCADE, 
        related_name='imaging_prices'
    )
    imaging_type = models.CharField(max_length=20, choices=IMAGING_TYPES)
    body_part = models.CharField(max_length=100, help_text="e.g., Chest, Abdomen, Brain")
    description = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        ordering = ['imaging_type', 'body_part']
    
    def __str__(self):
        return f"{self.get_imaging_type_display()} - {self.body_part}: GHS {self.price}"


class ProcedurePrice(BaseModel):
    """Medical procedure prices"""
    PROCEDURE_CATEGORIES = [
        ('minor_surgery', 'Minor Surgery'),
        ('major_surgery', 'Major Surgery'),
        ('dental', 'Dental Procedure'),
        ('ophthalmic', 'Ophthalmic Procedure'),
        ('endoscopy', 'Endoscopy'),
        ('biopsy', 'Biopsy'),
        ('injection', 'Injection'),
        ('wound_care', 'Wound Care'),
        ('catheterization', 'Catheterization'),
        ('other', 'Other Procedure'),
    ]
    
    price_list = models.ForeignKey(
        ServicePriceList, 
        on_delete=models.CASCADE, 
        related_name='procedure_prices'
    )
    category = models.CharField(max_length=20, choices=PROCEDURE_CATEGORIES)
    procedure_name = models.CharField(max_length=200)
    procedure_code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Additional costs
    includes_anesthesia = models.BooleanField(default=False)
    estimated_duration_minutes = models.PositiveIntegerField(default=30)
    
    class Meta:
        ordering = ['category', 'procedure_name']
    
    def __str__(self):
        return f"{self.procedure_code} - {self.procedure_name}: GHS {self.price}"


class BedPrice(BaseModel):
    """Hospital bed/ward prices"""
    BED_TYPES = [
        ('general_ward', 'General Ward'),
        ('semi_private', 'Semi-Private Room'),
        ('private', 'Private Room'),
        ('vip', 'VIP Suite'),
        ('icu', 'ICU'),
        ('nicu', 'NICU'),
        ('maternity', 'Maternity'),
    ]
    
    price_list = models.ForeignKey(
        ServicePriceList, 
        on_delete=models.CASCADE, 
        related_name='bed_prices'
    )
    bed_type = models.CharField(max_length=20, choices=BED_TYPES)
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        ordering = ['bed_type']
        unique_together = ['price_list', 'bed_type']
    
    def __str__(self):
        return f"{self.get_bed_type_display()}: GHS {self.price_per_day}/day"


class ServicePackage(BaseModel):
    """
    Pre-defined service packages at discounted rates
    e.g., Antenatal Package, Surgical Package
    """
    name = models.CharField(max_length=200)
    description = models.TextField()
    package_code = models.CharField(max_length=50, unique=True)
    
    # Package details
    included_services = models.JSONField(
        default=list,
        help_text="List of included services with codes"
    )
    
    # Pricing
    regular_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Sum of individual service prices"
    )
    package_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Discounted package price"
    )
    
    # Validity
    valid_from = models.DateField(default=timezone.now)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - GHS {self.package_price}"
    
    @property
    def discount_amount(self):
        return self.regular_price - self.package_price
    
    @property
    def discount_percentage(self):
        if self.regular_price > 0:
            return (self.discount_amount / self.regular_price) * 100
        return Decimal('0.00')


# Helper functions
def get_service_price(service_type, service_id, payer_type='cash'):
    """
    Get price for any service based on payer type
    
    Args:
        service_type: 'lab', 'drug', 'imaging', 'consultation', 'procedure'
        service_id: ID of the service
        payer_type: 'cash', 'nhis', 'private_insurance', etc.
    
    Returns:
        Decimal: Price for the service
    """
    from .models import LabTest, Drug
    
    # Get active price list for payer type
    try:
        price_list = ServicePriceList.objects.filter(
            payer_type=payer_type,
            is_active=True,
            effective_date__lte=timezone.now().date()
        ).order_by('-effective_date').first()
        
        if not price_list:
            # Use cash price list as default
            price_list = ServicePriceList.objects.filter(
                payer_type='cash',
                is_active=True
            ).first()
    except:
        price_list = None
    
    base_price = Decimal('0.00')
    
    if service_type == 'lab':
        try:
            test = LabTest.objects.get(id=service_id)
            base_price = test.price
        except:
            pass
            
    elif service_type == 'drug':
        try:
            drug = Drug.objects.get(id=service_id)
            base_price = getattr(drug, 'unit_price', Decimal('0.00'))
        except:
            pass
            
    elif service_type == 'imaging':
        # Get from ImagingPrice model
        pass
        
    elif service_type == 'consultation':
        # Get from ConsultationPrice model
        if price_list:
            try:
                consultation_price = ConsultationPrice.objects.filter(
                    price_list=price_list
                ).first()
                if consultation_price:
                    base_price = consultation_price.price
            except:
                pass
    
    # Apply discount if applicable
    if price_list and price_list.discount_percentage > 0:
        discount = base_price * (price_list.discount_percentage / 100)
        base_price = base_price - discount
    
    return base_price


# Export
__all__ = [
    'ServicePriceList',
    'ConsultationPrice',
    'ImagingPrice',
    'ProcedurePrice',
    'BedPrice',
    'ServicePackage',
    'get_service_price',
]


























"""
Walk-in Pharmacy Sales Module
Allows customers to purchase medication directly without a prescription
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal
from .models import BaseModel


class WalkInPharmacySale(BaseModel):
    """
    Direct pharmacy sales for walk-in customers
    No prescription required - over-the-counter or direct sales
    """
    CUSTOMER_TYPE_CHOICES = [
        ('walkin', 'Walk-in Customer'),
        ('registered', 'Registered Patient'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Customer Information
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='walkin')
    patient = models.ForeignKey('Patient', on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='walkin_purchases',
                                help_text="Link to patient if they're registered")
    customer_name = models.CharField(max_length=200, help_text="Name for walk-in customers")
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_address = models.TextField(blank=True)
    
    # Sale Information
    sale_number = models.CharField(max_length=50, unique=True, editable=False)
    sale_date = models.DateTimeField(default=timezone.now)
    
    # Staff
    served_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True,
                                  related_name='pharmacy_sales')
    
    # Financial
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Status
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    is_dispensed = models.BooleanField(default=False)
    dispensed_at = models.DateTimeField(null=True, blank=True)
    dispensed_by = models.ForeignKey('Staff', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='dispensed_walkin_sales')
    
    # Notes
    notes = models.TextField(blank=True)
    counselling_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-sale_date']
        verbose_name = "Walk-in Pharmacy Sale"
        verbose_name_plural = "Walk-in Pharmacy Sales"
        indexes = [
            models.Index(fields=['-sale_date', 'payment_status']),
            models.Index(fields=['sale_number']),
            models.Index(fields=['customer_phone']),
        ]
    
    def __str__(self):
        return f"{self.sale_number} - {self.customer_name}"
    
    def save(self, *args, **kwargs):
        """Generate sale number if not provided"""
        if not self.sale_number:
            self.sale_number = self.generate_sale_number()
        
        # Calculate amount due
        self.amount_due = self.total_amount - self.amount_paid
        
        # Update payment status based on amounts
        if self.amount_paid >= self.total_amount:
            self.payment_status = 'paid'
        elif self.amount_paid > 0:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'pending'
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_sale_number():
        """Generate unique sale number"""
        from datetime import datetime
        prefix = "PS"  # Pharmacy Sale
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # Get count for today
        today = timezone.now().date()
        count = WalkInPharmacySale.objects.filter(
            sale_date__date=today
        ).count() + 1
        
        return f"{prefix}{timestamp}{count:04d}"
    
    def calculate_totals(self):
        """Calculate sale totals from line items"""
        from django.db.models import Sum
        
        items_total = self.items.filter(is_deleted=False).aggregate(
            total=Sum('line_total')
        )['total'] or Decimal('0.00')
        
        self.subtotal = items_total
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount
        self.amount_due = self.total_amount - self.amount_paid
        self.save()


class WalkInPharmacySaleItem(BaseModel):
    """
    Individual items/medications in a walk-in sale
    """
    sale = models.ForeignKey(WalkInPharmacySale, on_delete=models.CASCADE, related_name='items')
    drug = models.ForeignKey('Drug', on_delete=models.PROTECT)
    
    # Quantity and Pricing
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Batch tracking (for inventory)
    batch_number = models.CharField(max_length=50, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Instructions
    dosage_instructions = models.TextField(blank=True, 
                                          help_text="How to take the medication")
    
    class Meta:
        ordering = ['created']
        verbose_name = "Walk-in Sale Item"
        verbose_name_plural = "Walk-in Sale Items"
    
    def __str__(self):
        return f"{self.drug.name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        """Calculate line total"""
        self.line_total = Decimal(str(self.quantity)) * self.unit_price
        super().save(*args, **kwargs)
        
        # Update sale totals
        self.sale.calculate_totals()
    
    def reduce_stock(self):
        """Reduce pharmacy stock when item is dispensed"""
        from .models import PharmacyStock
        from django.db.models import F
        
        # Find available stock (FIFO - first expiring first)
        stocks = PharmacyStock.objects.filter(
            drug=self.drug,
            quantity_on_hand__gt=0,
            is_deleted=False
        ).order_by('expiry_date')
        
        remaining_qty = self.quantity
        
        for stock in stocks:
            if remaining_qty <= 0:
                break
            
            if stock.quantity_on_hand >= remaining_qty:
                # This stock can fulfill the remaining quantity
                stock.quantity_on_hand = F('quantity_on_hand') - remaining_qty
                stock.save()
                remaining_qty = 0
            else:
                # Use all of this stock and continue
                remaining_qty -= stock.quantity_on_hand
                stock.quantity_on_hand = 0
                stock.save()
        
        if remaining_qty > 0:
            # Not enough stock - log warning
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Insufficient stock for {self.drug.name}. "
                f"Requested: {self.quantity}, Short: {remaining_qty}"
            )


"""
Revenue Stream Tracking
Track revenue by department and service type
Business Intelligence for financial monitoring
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from .models import BaseModel, Department
from .models_accounting_advanced import Revenue


class RevenueStream(BaseModel):
    """
    Define revenue streams/sources
    """
    STREAM_TYPE_CHOICES = [
        ('clinical', 'Clinical Services'),
        ('diagnostic', 'Diagnostic Services'),
        ('pharmacy', 'Pharmacy Sales'),
        ('administrative', 'Administrative Fees'),
        ('other', 'Other Revenue'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    stream_type = models.CharField(max_length=30, choices=STREAM_TYPE_CHOICES)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Targets
    monthly_target = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    annual_target = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['code']
        verbose_name = 'Revenue Stream'
        verbose_name_plural = 'Revenue Streams'
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class DepartmentRevenue(BaseModel):
    """
    Track revenue by department
    Auto-aggregated from transactions
    """
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='revenue_records')
    revenue_stream = models.ForeignKey(RevenueStream, on_delete=models.CASCADE, related_name='department_revenues')
    
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Count of transactions
    transaction_count = models.IntegerField(default=1)
    
    # Source tracking
    source_type = models.CharField(max_length=50, blank=True)  # 'consultation', 'lab_test', 'pharmacy_sale', etc.
    
    class Meta:
        ordering = ['-date', 'department']
        verbose_name = 'Department Revenue'
        verbose_name_plural = 'Department Revenues'
    
    def __str__(self):
        return f"{self.department.name} - {self.revenue_stream.name} - GHS {self.amount}"


# Extend existing Revenue model to track source
def add_revenue_source_tracking():
    """
    Add source tracking fields to existing Revenue model
    """
    if not hasattr(Revenue, 'revenue_stream'):
        Revenue.add_to_class(
            'revenue_stream',
            models.ForeignKey(
                RevenueStream,
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name='revenue_entries'
            )
        )
    
    if not hasattr(Revenue, 'department'):
        Revenue.add_to_class(
            'department',
            models.ForeignKey(
                Department,
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name='department_revenues'
            )
        )
    
    if not hasattr(Revenue, 'service_type'):
        Revenue.add_to_class(
            'service_type',
            models.CharField(
                max_length=50,
                blank=True,
                choices=[
                    ('consultation', 'Consultation'),
                    ('laboratory', 'Laboratory Test'),
                    ('pharmacy', 'Pharmacy Sale'),
                    ('imaging', 'Imaging/Radiology'),
                    ('dental', 'Dental Service'),
                    ('gynecology', 'Gynecology Service'),
                    ('surgery', 'Surgical Procedure'),
                    ('admission', 'Admission Fee'),
                    ('emergency', 'Emergency Service'),
                    ('outpatient', 'Outpatient Service'),
                    ('other', 'Other Service'),
                ]
            )
        )


# Call to add fields
add_revenue_source_tracking()





















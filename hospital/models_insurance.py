"""
Insurance Claims Management Models
World-class insurance tracking system for automatic claim generation
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
from .models import BaseModel, Patient, Invoice, InvoiceLine, Encounter, Payer, ServiceCode


class InsuranceClaimItem(BaseModel):
    """
    Individual insurance claim item - tracks each service/procedure billed to insurance
    Automatically created when a patient with insurance receives a service
    """
    CLAIM_STATUS_CHOICES = [
        ('pending', 'Pending Submission'),
        ('submitted', 'Submitted to Insurance'),
        ('processing', 'Processing'),
        ('approved', 'Approved'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid in Full'),
        ('rejected', 'Rejected'),
        ('reversed', 'Reversed'),
    ]
    
    # Patient and insurance information
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='insurance_claims')
    payer = models.ForeignKey(Payer, on_delete=models.PROTECT, related_name='claim_items')
    patient_insurance_id = models.CharField(max_length=100, verbose_name="Patient Insurance ID/Member Number")
    
    # Service information
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='claim_items', null=True, blank=True)
    invoice_line = models.ForeignKey(InvoiceLine, on_delete=models.CASCADE, related_name='claim_items', null=True, blank=True)
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, related_name='claim_items', null=True, blank=True)
    
    # Service details
    service_code = models.ForeignKey(ServiceCode, on_delete=models.PROTECT, related_name='claim_items', null=True, blank=True)
    service_description = models.CharField(max_length=500)
    service_date = models.DateField(help_text="Date service was provided")
    
    # Financial information
    billed_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), 
                                         help_text="Amount approved by insurance")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),
                                     help_text="Amount actually paid by insurance")
    
    # Claim tracking
    claim_status = models.CharField(max_length=20, choices=CLAIM_STATUS_CHOICES, default='pending')
    claim_reference = models.CharField(max_length=100, blank=True, 
                                      help_text="Reference number from insurance company")
    
    # Monthly aggregation
    monthly_claim = models.ForeignKey('MonthlyInsuranceClaim', on_delete=models.SET_NULL, 
                                     related_name='claim_items', null=True, blank=True,
                                     help_text="Monthly claim this item belongs to")
    
    # Dates
    submitted_date = models.DateField(null=True, blank=True, 
                                     help_text="Date claim was submitted to insurance")
    approved_date = models.DateField(null=True, blank=True,
                                    help_text="Date claim was approved by insurance")
    paid_date = models.DateField(null=True, blank=True,
                                help_text="Date payment was received from insurance")
    
    # Notes and rejection reasons
    rejection_reason = models.TextField(blank=True, 
                                       help_text="Reason if claim was rejected")
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-service_date', '-created']
        indexes = [
            models.Index(fields=['patient', 'service_date']),
            models.Index(fields=['payer', 'claim_status']),
            models.Index(fields=['monthly_claim']),
            models.Index(fields=['claim_status', 'service_date']),
        ]
        verbose_name = 'Insurance Claim Item'
        verbose_name_plural = 'Insurance Claim Items'
    
    def __str__(self):
        return f"Claim: {self.patient.full_name} - {self.service_description} - {self.billed_amount} GHS"
    
    @property
    def outstanding_amount(self):
        """Calculate outstanding amount (billed - paid)"""
        return self.billed_amount - self.paid_amount
    
    @property
    def is_paid(self):
        """Check if claim is fully paid"""
        return self.paid_amount >= self.billed_amount or self.claim_status == 'paid'
    
    @property
    def is_submitted(self):
        """Check if claim has been submitted"""
        return self.claim_status in ['submitted', 'processing', 'approved', 'partially_paid', 'paid']
    
    def mark_as_submitted(self, claim_reference=None):
        """Mark claim as submitted to insurance"""
        self.claim_status = 'submitted'
        self.submitted_date = timezone.now().date()
        if claim_reference:
            self.claim_reference = claim_reference
        self.save(update_fields=['claim_status', 'submitted_date', 'claim_reference'])
    
    def mark_as_approved(self, approved_amount=None):
        """Mark claim as approved by insurance"""
        self.claim_status = 'approved'
        self.approved_date = timezone.now().date()
        if approved_amount is not None:
            self.approved_amount = approved_amount
        self.save(update_fields=['claim_status', 'approved_date', 'approved_amount'])
    
    def mark_as_paid(self, paid_amount=None):
        """Mark claim as paid by insurance"""
        if paid_amount is not None:
            self.paid_amount = paid_amount
        else:
            self.paid_amount = self.approved_amount or self.billed_amount
        
        if self.paid_amount >= self.billed_amount:
            self.claim_status = 'paid'
        elif self.paid_amount > 0:
            self.claim_status = 'partially_paid'
        
        self.paid_date = timezone.now().date()
        self.save(update_fields=['claim_status', 'paid_amount', 'paid_date'])
    
    def mark_as_rejected(self, reason=None):
        """Mark claim as rejected"""
        self.claim_status = 'rejected'
        if reason:
            self.rejection_reason = reason
        self.save(update_fields=['claim_status', 'rejection_reason'])


class MonthlyInsuranceClaim(BaseModel):
    """
    Aggregated monthly insurance claims by payer
    Used for generating monthly reports and submitting to insurance companies
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('ready_for_submission', 'Ready for Submission'),
        ('submitted', 'Submitted'),
        ('processing', 'Processing'),
        ('partially_paid', 'Partially Paid'),
        ('fully_paid', 'Fully Paid'),
        ('closed', 'Closed'),
    ]
    
    # Identification
    claim_number = models.CharField(max_length=50, unique=True, 
                                   help_text="Monthly claim number (auto-generated)")
    payer = models.ForeignKey(Payer, on_delete=models.PROTECT, related_name='monthly_claims')
    
    # Period
    claim_month = models.IntegerField(choices=[(i, i) for i in range(1, 13)], 
                                     help_text="Month (1-12)")
    claim_year = models.IntegerField(help_text="Year (e.g., 2025)")
    
    # Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    
    # Financial summary
    total_items = models.IntegerField(default=0, help_text="Total number of claim items")
    total_billed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_approved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    # Submission tracking
    submission_date = models.DateField(null=True, blank=True,
                                      help_text="Date claim was submitted to insurance")
    submission_reference = models.CharField(max_length=100, blank=True,
                                           help_text="Reference number from insurance company")
    
    # Payment tracking
    payment_date = models.DateField(null=True, blank=True,
                                   help_text="Date payment was received")
    payment_reference = models.CharField(max_length=100, blank=True,
                                        help_text="Payment reference number")
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-claim_year', '-claim_month', '-created']
        unique_together = ['payer', 'claim_month', 'claim_year']
        indexes = [
            models.Index(fields=['payer', 'claim_year', 'claim_month']),
            models.Index(fields=['status']),
        ]
        verbose_name = 'Monthly Insurance Claim'
        verbose_name_plural = 'Monthly Insurance Claims'
    
    def __str__(self):
        return f"Monthly Claim {self.claim_number} - {self.payer.name} - {self.get_month_display()} {self.claim_year}"
    
    def save(self, *args, **kwargs):
        if not self.claim_number:
            self.claim_number = self.generate_claim_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_claim_number():
        """Generate unique monthly claim number"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"MCLM{timestamp}"
    
    @property
    def outstanding_amount(self):
        """Calculate outstanding amount (billed - paid)"""
        return self.total_billed_amount - self.total_paid_amount
    
    @property
    def month_display(self):
        """Display month name"""
        from datetime import datetime
        try:
            dt = datetime(self.claim_year, self.claim_month, 1)
            return dt.strftime('%B')
        except:
            return f"Month {self.claim_month}"
    
    def calculate_totals(self):
        """Recalculate totals from claim items"""
        items = self.claim_items.all()
        self.total_items = items.count()
        self.total_billed_amount = sum(item.billed_amount for item in items)
        self.total_approved_amount = sum(item.approved_amount for item in items)
        self.total_paid_amount = sum(item.paid_amount for item in items)
        self.save(update_fields=['total_items', 'total_billed_amount', 
                                'total_approved_amount', 'total_paid_amount'])
    
    def add_claim_items(self, claim_items):
        """Add claim items to this monthly claim"""
        for item in claim_items:
            item.monthly_claim = self
            item.save(update_fields=['monthly_claim'])
        self.calculate_totals()
    
    def mark_as_submitted(self, submission_reference=None):
        """Mark monthly claim as submitted"""
        self.status = 'submitted'
        self.submission_date = timezone.now().date()
        if submission_reference:
            self.submission_reference = submission_reference
        
        # Mark all claim items as submitted if not already
        for item in self.claim_items.filter(claim_status='pending'):
            item.mark_as_submitted()
        
        self.save(update_fields=['status', 'submission_date', 'submission_reference'])
    
    def mark_as_paid(self, payment_reference=None):
        """Mark monthly claim as fully paid"""
        self.status = 'fully_paid'
        self.payment_date = timezone.now().date()
        if payment_reference:
            self.payment_reference = payment_reference
        self.save(update_fields=['status', 'payment_date', 'payment_reference'])

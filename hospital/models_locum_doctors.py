"""
Locum Doctor Service Tracking and Payment Models
Tracks services provided by visiting/locum doctors and manages their payments
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from .models import BaseModel, Staff, Patient, Encounter


class LocumDoctorService(BaseModel):
    """
    Tracks services provided by locum/visiting doctors
    Each service represents a consultation or specialist service
    """
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('processed', 'Payment Processed'),
        ('paid', 'Paid'),
    ]
    
    # Doctor information
    doctor = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='locum_services',
                               limit_choices_to={'profession__in': ['doctor', 'specialist']})
    
    # Service information
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='locum_services')
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='locum_services', null=True, blank=True)
    service_date = models.DateField(default=timezone.now)
    service_type = models.CharField(max_length=100, help_text="e.g., Consultation, Specialist Service")
    service_description = models.TextField(blank=True)
    
    # Financial information
    service_charge = models.DecimalField(max_digits=12, decimal_places=2, 
                                        help_text="Total charge for the service")
    doctor_payment = models.DecimalField(max_digits=12, decimal_places=2,
                                        help_text="50% of service charge - payment to doctor")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                    help_text="Tax on cash payments above 2000 GHS")
    net_payment = models.DecimalField(max_digits=12, decimal_places=2,
                                     help_text="Net payment after tax")
    
    # Payment information
    payment_method = models.CharField(max_length=20, choices=[
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
    ], default='bank_transfer')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='locum_payments_processed')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-service_date', 'doctor']
        verbose_name = 'Locum Doctor Service'
        verbose_name_plural = 'Locum Doctor Services'
    
    def __str__(self):
        return f"{self.doctor.user.get_full_name()} - {self.service_type} ({self.service_date})"
    
    def save(self, *args, **kwargs):
        """Calculate doctor payment (50% of service charge) and tax"""
        # Doctor gets 50% of service charge
        self.doctor_payment = self.service_charge * Decimal('0.5')
        
        # Tax calculation: Only for cash payments above 2000 GHS
        if self.payment_method == 'cash' and self.doctor_payment > Decimal('2000.00'):
            # Calculate tax (assuming a tax rate - you can adjust this)
            # For now, using a simple percentage (e.g., 5% on amount above 2000)
            taxable_amount = self.doctor_payment - Decimal('2000.00')
            tax_rate = Decimal('0.05')  # 5% tax rate - adjust as needed
            self.tax_amount = taxable_amount * tax_rate
        else:
            self.tax_amount = Decimal('0.00')
        
        # Net payment after tax
        self.net_payment = self.doctor_payment - self.tax_amount
        
        super().save(*args, **kwargs)
    
    def mark_as_paid(self, payment_date=None, payment_reference='', paid_by=None, notes=''):
        """Mark service as paid"""
        self.payment_status = 'paid'
        self.payment_date = payment_date or timezone.now().date()
        self.payment_reference = payment_reference
        self.paid_by = paid_by
        if notes:
            self.notes = notes
        self.save()


class LocumDoctorPaymentBatch(BaseModel):
    """
    Batch payment record for multiple locum doctor services
    Allows accountants to process payments for multiple services at once
    """
    batch_number = models.CharField(max_length=50, unique=True)
    doctor = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='locum_payment_batches')
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Financial summary
    total_services = models.PositiveIntegerField(default=0)
    total_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_doctor_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_net_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Payment information
    payment_method = models.CharField(max_length=20, choices=[
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
    ], default='bank_transfer')
    payment_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('paid', 'Paid'),
    ], default='pending')
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='locum_batches_processed')
    notes = models.TextField(blank=True)
    
    # Related services
    services = models.ManyToManyField(LocumDoctorService, related_name='payment_batches')
    
    class Meta:
        ordering = ['-period_end', 'doctor']
        verbose_name = 'Locum Doctor Payment Batch'
        verbose_name_plural = 'Locum Doctor Payment Batches'
    
    def __str__(self):
        return f"Batch {self.batch_number} - {self.doctor.user.get_full_name()} ({self.period_start} to {self.period_end})"
    
    @staticmethod
    def generate_batch_number():
        """Generate unique batch number"""
        from datetime import datetime
        prefix = "LOCUM"
        year = datetime.now().year
        month = datetime.now().month
        
        last_batch = LocumDoctorPaymentBatch.objects.filter(
            batch_number__startswith=f"{prefix}{year}{month:02d}"
        ).order_by('-batch_number').first()
        
        if last_batch and last_batch.batch_number:
            try:
                last_num = int(last_batch.batch_number.replace(f"{prefix}{year}{month:02d}", ""))
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{year}{month:02d}{new_num:05d}"
    
    def save(self, *args, **kwargs):
        if not self.batch_number:
            self.batch_number = self.generate_batch_number()
        
        # Calculate totals from services if they exist
        if self.pk and self.services.exists():
            services = self.services.all()
            self.total_services = services.count()
            self.total_service_charge = sum(s.service_charge for s in services)
            self.total_doctor_payment = sum(s.doctor_payment for s in services)
            self.total_tax = sum(s.tax_amount for s in services)
            self.total_net_payment = sum(s.net_payment for s in services)
        
        super().save(*args, **kwargs)


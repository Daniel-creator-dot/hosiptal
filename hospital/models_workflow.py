"""
Patient Workflow and Process Management Models
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from model_utils.models import TimeStampedModel
from .models import BaseModel, Patient, Encounter, Staff, Department, Ward, Bed, Invoice


class PatientFlowStage(BaseModel):
    """Patient flow stages/steps"""
    STAGE_TYPES = [
        ('registration', 'Registration'),
        ('triage', 'Triage'),
        ('vitals', 'Vital Signs'),
        ('consultation', 'Consultation'),
        ('laboratory', 'Laboratory'),
        ('imaging', 'Imaging'),
        ('pharmacy', 'Pharmacy'),
        ('treatment', 'Treatment'),
        ('admission', 'Admission'),
        ('billing', 'Billing'),
        ('payment', 'Payment'),
        ('discharge', 'Discharge'),
    ]
    
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='flow_stages')
    stage_type = models.CharField(max_length=30, choices=STAGE_TYPES)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ], default='pending')
    
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    
    notes = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=[
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('stat', 'STAT'),
    ], default='routine')
    
    class Meta:
        ordering = ['encounter', 'created']
    
    def __str__(self):
        return f"{self.encounter.patient.full_name} - {self.get_stage_type_display()} - {self.get_status_display()}"
    
    def start(self, staff=None):
        """Start this stage"""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        if staff:
            self.completed_by = staff
        self.save()
    
    def complete(self, staff=None):
        """Complete this stage"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if staff:
            self.completed_by = staff
        self.save()


class WorkflowTemplate(BaseModel):
    """Template for standard workflows"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    encounter_type = models.CharField(max_length=20, choices=Encounter.ENCOUNTER_TYPES)
    stages = models.JSONField(default=list)  # List of stage types in order
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_encounter_type_display()})"


class PaymentRequest(BaseModel):
    """Payment requests for cashiers"""
    PAYMENT_TYPES = [
        ('full', 'Full Payment'),
        ('partial', 'Partial Payment'),
        ('installment', 'Installment'),
    ]
    
    request_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='payment_requests')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='payment_requests')
    
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='full')
    
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_payment_requests')
    requested_at = models.DateTimeField(default=timezone.now)
    
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending Payment'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='pending')
    
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_payments')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    insurance_authorization_number = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Payment Request {self.request_number} - GHS {self.requested_amount}"
    
    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self.generate_request_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_request_number():
        """Generate unique payment request number"""
        from datetime import datetime
        prefix = "PAY"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"


class Bill(BaseModel):
    """Bills issued to patients (separate from invoices for workflow)"""
    BILL_TYPES = [
        ('cash', 'Cash Bill'),
        ('insurance', 'Insurance Bill'),
        ('mixed', 'Mixed (Cash + Insurance)'),
    ]
    
    bill_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey('Invoice', on_delete=models.CASCADE, related_name='bills', null=True, blank=True)
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='bills', null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='bills')
    
    bill_type = models.CharField(max_length=20, choices=BILL_TYPES, default='cash')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    insurance_covered = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    patient_portion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_bills')
    issued_at = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], default='draft')
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-issued_at']
    
    def __str__(self):
        return f"Bill {self.bill_number} - {self.patient.full_name} - GHS {self.total_amount}"
    
    def save(self, *args, **kwargs):
        if not self.bill_number:
            self.bill_number = self.generate_bill_number()
        
        # Auto-calculate patient portion before saving (prevents double-save)
        self.patient_portion = self.total_amount - self.insurance_covered
        if self.patient_portion < 0:
            self.patient_portion = 0
        
        # Sync with invoice if exists
        if self.invoice:
            # Ensure bill total matches invoice total
            self.total_amount = self.invoice.total_amount
            self.patient_portion = self.total_amount - self.insurance_covered
            if self.patient_portion < 0:
                self.patient_portion = 0
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_bill_number():
        """Generate unique bill number with microseconds and random component"""
        from datetime import datetime
        import random
        prefix = "BIL"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')  # Added %f for microseconds
        random_suffix = random.randint(10, 99)  # Add random 2-digit number for extra uniqueness
        return f"{prefix}{timestamp}{random_suffix}"


class CashierSession(BaseModel):
    """Cashier working sessions for cash reconciliation"""
    session_number = models.CharField(max_length=50, unique=True)
    cashier = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cashier_sessions')
    
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    total_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_refunds = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_transactions = models.PositiveIntegerField(default=0)
    
    status = models.CharField(max_length=20, choices=[
        ('open', 'Open'),
        ('closed', 'Closed'),
    ], default='open')
    
    notes = models.TextField(blank=True, help_text="General session notes")
    daily_cash_notes = models.TextField(blank=True, help_text="Notes to match cash sales - updated throughout the day")
    
    class Meta:
        ordering = ['-opened_at']
    
    def __str__(self):
        return f"Session {self.session_number} - {self.cashier.username} - {self.opened_at.date()}"
    
    def save(self, *args, **kwargs):
        if not self.session_number:
            self.session_number = self.generate_session_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_session_number():
        """Generate unique session number"""
        from datetime import datetime
        prefix = "SES"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"
    
    def calculate_totals(self):
        """Calculate session totals from transactions - ALL payment methods"""
        from .models_accounting import Transaction
        from django.db import models as db_models
        from decimal import Decimal
        
        # Get all transactions for this session
        transactions = Transaction.objects.filter(
            processed_by=self.cashier,
            transaction_date__gte=self.opened_at,
            transaction_date__lte=self.closed_at if self.closed_at else timezone.now(),
            is_deleted=False
        )
        
        # Calculate total payments (ALL payment methods)
        payments = transactions.filter(transaction_type='payment_received')
        self.total_payments = payments.aggregate(
            total=db_models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Calculate total refunds (ALL payment methods)
        refunds = transactions.filter(transaction_type='refund_issued')
        self.total_refunds = refunds.aggregate(
            total=db_models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Calculate expected cash (only cash payments)
        cash_payments = payments.filter(payment_method='cash')
        cash_payments_total = cash_payments.aggregate(
            total=db_models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        cash_refunds = refunds.filter(payment_method='cash')
        cash_refunds_total = cash_refunds.aggregate(
            total=db_models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        self.expected_cash = self.opening_cash + cash_payments_total - cash_refunds_total
        
        # Count total transactions
        self.total_transactions = transactions.count()
        
        self.save(update_fields=['total_payments', 'total_refunds', 'expected_cash', 'total_transactions'])


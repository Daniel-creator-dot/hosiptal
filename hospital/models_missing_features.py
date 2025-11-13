"""
Missing Features Implementation
Additional models for features not yet implemented
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from model_utils.models import TimeStampedModel
from .models import BaseModel, Patient, Encounter, Staff, Drug, Prescription, Order, LabResult, Invoice, InvoiceLine, Payer


# ==================== PHARMACY ENHANCEMENTS ====================

class Supplier(BaseModel):
    """Pharmacy suppliers/vendors"""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class PurchaseOrder(BaseModel):
    """Pharmacy purchase orders"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    order_date = models.DateField(default=date.today)
    expected_delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_pos')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-order_date']
    
    def __str__(self):
        return f"PO {self.po_number} - {self.supplier.name}"
    
    def save(self, *args, **kwargs):
        if not self.po_number:
            self.po_number = self.generate_po_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_po_number():
        """Generate unique PO number"""
        from datetime import datetime
        prefix = "PO"
        year = datetime.now().year
        month = datetime.now().month
        last_po = PurchaseOrder.objects.filter(
            po_number__startswith=f"{prefix}{year}{month:02d}"
        ).order_by('-po_number').first()
        
        if last_po and last_po.po_number:
            try:
                last_num = int(last_po.po_number.replace(f"{prefix}{year}{month:02d}", ""))
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        return f"{prefix}{year}{month:02d}{new_num:05d}"


class PurchaseOrderLine(BaseModel):
    """Purchase order line items"""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    received_quantity = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['created']
    
    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.drug.name}"
    
    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        # Recalculate PO total
        if self.purchase_order:
            self.purchase_order.total_amount = sum([line.line_total for line in self.purchase_order.lines.filter(is_deleted=False)])
            self.purchase_order.save()


class GoodsReceiptNote(BaseModel):
    """Goods Receipt Note (GRN) for received items"""
    grn_number = models.CharField(max_length=50, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='grns')
    receipt_date = models.DateField(default=date.today)
    received_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    invoice_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-receipt_date']
    
    def __str__(self):
        return f"GRN {self.grn_number} - {self.purchase_order.po_number}"
    
    def save(self, *args, **kwargs):
        if not self.grn_number:
            self.grn_number = self.generate_grn_number()
        super().save(*args, **kwargs)
        # Update PO status
        if self.purchase_order:
            self.purchase_order.status = 'received'
            self.purchase_order.save()
    
    @staticmethod
    def generate_grn_number():
        """Generate unique GRN number"""
        from datetime import datetime
        prefix = "GRN"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"


class GRNLine(BaseModel):
    """GRN line items"""
    grn = models.ForeignKey(GoodsReceiptNote, on_delete=models.CASCADE, related_name='lines')
    po_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT)
    quantity_received = models.PositiveIntegerField()
    batch_number = models.CharField(max_length=50)
    expiry_date = models.DateField()
    location = models.CharField(max_length=100, default='Main Pharmacy')
    
    class Meta:
        ordering = ['created']
    
    def __str__(self):
        return f"{self.grn.grn_number} - {self.po_line.drug.name}"


class DrugInteraction(BaseModel):
    """Drug-drug interactions database"""
    SEVERITY_CHOICES = [
        ('contraindicated', 'Contraindicated'),
        ('major', 'Major'),
        ('moderate', 'Moderate'),
        ('minor', 'Minor'),
    ]
    
    drug1 = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='interactions_as_drug1')
    drug2 = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name='interactions_as_drug2')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    description = models.TextField()
    clinical_significance = models.TextField(blank=True)
    management = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['drug1', 'drug2']
        ordering = ['severity', 'drug1']
    
    def __str__(self):
        return f"{self.drug1.name} + {self.drug2.name} ({self.get_severity_display()})"


class Dispensing(BaseModel):
    """Pharmacy dispensing records"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('dispensed', 'Dispensed'),
        ('partial', 'Partially Dispensed'),
        ('cancelled', 'Cancelled'),
    ]
    
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='dispensings')
    stock = models.ForeignKey('PharmacyStock', on_delete=models.PROTECT, related_name='dispensings')
    quantity_dispensed = models.PositiveIntegerField()
    batch_number = models.CharField(max_length=50)
    dispensing_date = models.DateTimeField(default=timezone.now)
    dispensed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-dispensing_date']
    
    def __str__(self):
        patient_name = self.prescription.order.encounter.patient.full_name if self.prescription.order.encounter else "Unknown"
        return f"Dispensing - {patient_name} - {self.prescription.drug.name}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update stock on hand
        if self.status == 'dispensed':
            self.stock.quantity_on_hand -= self.quantity_dispensed
            self.stock.save()


# ==================== BILLING ENHANCEMENTS ====================

class Refund(BaseModel):
    """Refund processing"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processed', 'Processed'),
        ('cancelled', 'Cancelled'),
    ]
    
    refund_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='refunds')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    refund_method = models.CharField(max_length=20, choices=[
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_note', 'Credit Note'),
    ], default='cash')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_refunds')
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Refund {self.refund_number} - GHS {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.refund_number:
            self.refund_number = self.generate_refund_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_refund_number():
        """Generate unique refund number"""
        from datetime import datetime
        prefix = "REF"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"


class Remittance(BaseModel):
    """Insurance remittance posting"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('posted', 'Posted'),
        ('rejected', 'Rejected'),
    ]
    
    remittance_number = models.CharField(max_length=50, unique=True)
    # Use string reference to avoid circular import - ClaimsBatch is in models_advanced
    claims_batch = models.ForeignKey('ClaimsBatch', on_delete=models.CASCADE, related_name='remittances', null=True, blank=True)
    payer = models.ForeignKey(Payer, on_delete=models.CASCADE, related_name='remittances')
    remittance_date = models.DateField(default=date.today)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    received_amount = models.DecimalField(max_digits=12, decimal_places=2)
    adjustment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-remittance_date']
    
    def __str__(self):
        return f"Remittance {self.remittance_number} - {self.payer.name}"
    
    def save(self, *args, **kwargs):
        if not self.remittance_number:
            self.remittance_number = self.generate_remittance_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_remittance_number():
        """Generate unique remittance number"""
        from datetime import datetime
        prefix = "REM"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{prefix}{timestamp}"


class RemittanceLine(BaseModel):
    """Remittance line items"""
    remittance = models.ForeignKey(Remittance, on_delete=models.CASCADE, related_name='lines')
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='remittance_lines')
    claim_number = models.CharField(max_length=100, blank=True)
    billed_amount = models.DecimalField(max_digits=10, decimal_places=2)
    allowed_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    adjustment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    denial_code = models.CharField(max_length=20, blank=True)
    denial_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['created']
    
    def __str__(self):
        return f"{self.remittance.remittance_number} - Invoice {self.invoice.invoice_number}"


# ==================== LAB ENHANCEMENTS ====================

class CriticalResultAlert(BaseModel):
    """Critical lab result alerts"""
    STATUS_CHOICES = [
        ('pending', 'Pending Notification'),
        ('notified', 'Notified'),
        ('acknowledged', 'Acknowledged'),
    ]
    
    lab_result = models.ForeignKey(LabResult, on_delete=models.CASCADE, related_name='critical_alerts')
    alert_level = models.CharField(max_length=20, choices=[
        ('critical', 'Critical'),
        ('panic', 'Panic Value'),
        ('warning', 'Warning'),
    ])
    notified_to = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='critical_alerts')
    notified_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Critical Alert - {self.lab_result.test.name} - {self.lab_result.order.encounter.patient.full_name}"


class LabAnalyzerInterface(BaseModel):
    """Lab analyzer interface configuration"""
    analyzer_name = models.CharField(max_length=100)
    interface_type = models.CharField(max_length=20, choices=[
        ('csv', 'CSV Import'),
        ('hl7', 'HL7'),
        ('fhir', 'FHIR'),
        ('api', 'REST API'),
        ('ftp', 'FTP'),
    ])
    connection_string = models.TextField(blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['analyzer_name']
    
    def __str__(self):
        return f"{self.analyzer_name} ({self.get_interface_type_display()})"


# ==================== NURSING ENHANCEMENTS ====================

class ObservationChart(BaseModel):
    """Nursing observation charts (obs charts)"""
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='observation_charts')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='observation_charts')
    chart_date = models.DateField(default=date.today)
    time_slot = models.CharField(max_length=10)  # 6am, 12pm, 6pm, 12am, etc.
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pulse = models.PositiveIntegerField(null=True, blank=True)
    systolic_bp = models.PositiveIntegerField(null=True, blank=True)
    diastolic_bp = models.PositiveIntegerField(null=True, blank=True)
    respiratory_rate = models.PositiveIntegerField(null=True, blank=True)
    spo2 = models.PositiveIntegerField(null=True, blank=True)
    pain_score = models.IntegerField(null=True, blank=True)
    recorded_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-chart_date', 'time_slot']
        unique_together = ['encounter', 'chart_date', 'time_slot']
    
    def __str__(self):
        return f"Obs Chart - {self.patient.full_name} - {self.chart_date} {self.time_slot}"


# ==================== PATIENT PORTAL & MESSAGING ====================

class PatientPortalAccess(BaseModel):
    """Patient portal access management"""
    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='portal_access')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_portal')
    is_active = models.BooleanField(default=True)
    activated_at = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Portal Access - {self.patient.full_name}"


class StaffMessage(BaseModel):
    """Secure staff messaging system"""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], default='normal')
    related_object_id = models.UUIDField(null=True, blank=True)
    related_object_type = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Message: {self.subject} - {self.sender.username} to {self.recipient.username}"


class ReferrerPortal(BaseModel):
    """Referrer/GP portal access"""
    referrer_name = models.CharField(max_length=200)
    organization = models.CharField(max_length=200, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    license_number = models.CharField(max_length=100, blank=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='referrer_portal')
    is_active = models.BooleanField(default=True)
    registration_date = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['referrer_name']
    
    def __str__(self):
        return f"Referrer: {self.referrer_name}"


# Forward reference for ClaimsBatch - use string reference in ForeignKey
# ClaimsBatch is imported from models_advanced at runtime if needed


# Forward reference for PharmacyStock - use string reference in ForeignKey  
# PharmacyStock is in models.py - Django will resolve at runtime


"""
World-Class Payment Verification System
Ensures payment before lab results release or pharmacy dispensing
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal
import qrcode
from io import BytesIO
from django.core.files import File
import logging

from .models import BaseModel, Patient, Encounter
from .models_workflow import Bill

logger = logging.getLogger(__name__)


class ServicePaymentRequirement(BaseModel):
    """
    Defines which services require payment before delivery
    """
    SERVICE_TYPES = [
        ('lab_test', 'Laboratory Test'),
        ('lab_result', 'Laboratory Result Release'),
        ('pharmacy_prescription', 'Pharmacy Prescription'),
        ('pharmacy_otc', 'Pharmacy OTC Sale'),
        ('imaging_study', 'Imaging Study'),
        ('procedure', 'Medical Procedure'),
        ('consultation', 'Consultation Fee'),
    ]
    
    service_type = models.CharField(max_length=30, choices=SERVICE_TYPES, unique=True)
    requires_prepayment = models.BooleanField(default=True, help_text="Must pay before service delivery")
    allow_credit = models.BooleanField(default=False, help_text="Allow credit for this service")
    credit_limit_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    grace_period_hours = models.PositiveIntegerField(default=0, help_text="Hours to pay after service")
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['service_type']
    
    def __str__(self):
        return f"{self.get_service_type_display()} - {'Prepayment Required' if self.requires_prepayment else 'Credit Allowed'}"


class PaymentVerification(BaseModel):
    """
    Track payment verification for service delivery
    """
    VERIFICATION_STATUS = [
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    
    # Reference to payment receipt
    receipt = models.ForeignKey('hospital.PaymentReceipt', on_delete=models.CASCADE, related_name='verifications')
    
    # What service is being accessed
    service_type = models.CharField(max_length=30, choices=ServicePaymentRequirement.SERVICE_TYPES)
    lab_result = models.ForeignKey('hospital.LabResult', on_delete=models.CASCADE, null=True, blank=True, related_name='payment_verifications')
    prescription = models.ForeignKey('hospital.Prescription', on_delete=models.CASCADE, null=True, blank=True, related_name='payment_verifications')
    imaging_study = models.ForeignKey('hospital.ImagingStudy', on_delete=models.CASCADE, null=True, blank=True, related_name='payment_verifications')
    
    # Verification details
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='payment_verifications')
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS, default='pending')
    verification_method = models.CharField(max_length=20, choices=[
        ('manual', 'Manual Entry'),
        ('qr_scan', 'QR Code Scan'),
        ('barcode', 'Barcode Scan'),
        ('receipt_number', 'Receipt Number'),
    ], default='manual')
    
    # Scanner information
    scanned_data = models.TextField(blank=True, help_text="QR/Barcode data")
    
    # Rejection reason
    rejection_reason = models.TextField(blank=True)
    
    # Audit trail
    verification_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"{self.get_service_type_display()} - Receipt {self.receipt.receipt_number} - {self.verification_status}"
    
    def verify(self, user, notes=''):
        """Mark as verified"""
        self.verification_status = 'verified'
        self.verified_by = user
        self.verified_at = timezone.now()
        self.verification_notes = notes
        self.save()
        
        # Update service delivery status
        if self.lab_result:
            self.lab_result.payment_verified = True
            self.lab_result.can_release = True
            self.lab_result.save()
        elif self.prescription:
            self.prescription.payment_verified = True
            self.prescription.can_dispense = True
            self.prescription.save()
    
    def reject(self, user, reason):
        """Reject verification"""
        self.verification_status = 'rejected'
        self.verified_by = user
        self.verified_at = timezone.now()
        self.rejection_reason = reason
        self.save()


class LabResultRelease(BaseModel):
    """
    Track lab result releases - requires payment verification
    """
    RELEASE_STATUS = [
        ('pending_payment', 'Pending Payment'),
        ('ready_for_release', 'Ready for Release'),
        ('released', 'Released to Patient'),
        ('emailed', 'Emailed to Patient'),
    ]
    
    lab_result = models.OneToOneField('hospital.LabResult', on_delete=models.CASCADE, related_name='release_record')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_result_releases')
    
    # Payment tracking
    payment_receipt = models.ForeignKey('hospital.PaymentReceipt', on_delete=models.SET_NULL, null=True, blank=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    payment_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_lab_payments')
    
    # Release tracking
    release_status = models.CharField(max_length=30, choices=RELEASE_STATUS, default='pending_payment')
    released_to = models.CharField(max_length=200, blank=True, help_text="Name of person who collected")
    released_to_relationship = models.CharField(max_length=100, blank=True, help_text="Relationship to patient")
    released_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='released_lab_results')
    released_at = models.DateTimeField(null=True, blank=True)
    
    # Identification verification
    id_type = models.CharField(max_length=50, blank=True, help_text="e.g., National ID, Passport")
    id_number = models.CharField(max_length=100, blank=True)
    
    # Delivery method
    delivery_method = models.CharField(max_length=20, choices=[
        ('in_person', 'Collected in Person'),
        ('email', 'Emailed'),
        ('proxy', 'Collected by Proxy'),
    ], default='in_person')
    
    release_notes = models.TextField(blank=True)
    sent_to_cashier_at = models.DateTimeField(null=True, blank=True)
    sent_to_cashier_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_cashier_tickets_sent')
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Lab Result Release: {self.lab_result.test.name} - {self.patient.full_name} - {self.release_status}"
    
    def can_release(self):
        """Check if result can be released"""
        return self.payment_receipt is not None and self.payment_verified_at is not None
    
    def mark_released(self, user, released_to_name, relationship='Self', id_type='', id_number='', notes=''):
        """Mark result as released"""
        self.release_status = 'released'
        self.released_to = released_to_name
        self.released_to_relationship = relationship
        self.released_by = user
        self.released_at = timezone.now()
        self.id_type = id_type
        self.id_number = id_number
        self.release_notes = notes
        self.save()


class PharmacyDispensing(BaseModel):
    """
    Track pharmacy drug dispensing - requires payment verification
    """
    DISPENSING_STATUS = [
        ('pending_payment', 'Pending Payment'),
        ('ready_to_dispense', 'Ready to Dispense'),
        ('partially_dispensed', 'Partially Dispensed'),
        ('fully_dispensed', 'Fully Dispensed'),
        ('cancelled', 'Cancelled'),
    ]
    
    prescription = models.OneToOneField('hospital.Prescription', on_delete=models.CASCADE, related_name='dispensing_record')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='pharmacy_dispensing')
    
    # Drug substitution - when pharmacy changes drug (e.g. generic substitute, stock availability)
    substitute_drug = models.ForeignKey(
        'hospital.Drug',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispensing_substitutions',
        help_text='If set, dispense this drug instead of the prescribed drug'
    )
    
    # Payment tracking
    payment_receipt = models.ForeignKey('hospital.PaymentReceipt', on_delete=models.SET_NULL, null=True, blank=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    payment_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_pharmacy_payments')
    
    # Dispensing tracking
    dispensing_status = models.CharField(max_length=30, choices=DISPENSING_STATUS, default='pending_payment')
    quantity_ordered = models.PositiveIntegerField()
    quantity_dispensed = models.PositiveIntegerField(default=0)
    dispensed_by = models.ForeignKey('hospital.Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='dispensed_medications')
    dispensed_at = models.DateTimeField(null=True, blank=True)
    
    # Instructions given to patient
    dispensing_instructions = models.TextField(blank=True, help_text="Instructions given to patient")
    counselling_given = models.BooleanField(default=False)
    counselled_by = models.ForeignKey('hospital.Staff', on_delete=models.SET_NULL, null=True, blank=True, related_name='counselled_patients')
    
    dispensing_notes = models.TextField(blank=True)

    # Stock reduction tracking - set when pharmacy stock was reduced (e.g. at Send to Payer)
    stock_reduced_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    @property
    def drug_to_dispense(self):
        """Drug actually dispensed - substitute if set, otherwise prescribed drug"""
        return self.substitute_drug if self.substitute_drug_id else (self.prescription.drug if self.prescription_id else None)
    
    def __str__(self):
        drug = self.drug_to_dispense
        drug_name = drug.name if drug else 'Unknown'
        return f"Dispensing: {drug_name} - {self.patient.full_name} - {self.dispensing_status}"
    
    def can_dispense(self):
        """Check if drugs can be dispensed"""
        return self.payment_receipt is not None and self.payment_verified_at is not None
    
    @property
    def is_dispensed(self):
        """Return True if medication has been dispensed (fully or partially)"""
        return self.dispensing_status in ['partially_dispensed', 'fully_dispensed']
    
    def mark_dispensed(self, user, quantity, instructions='', notes=''):
        """Mark prescription as dispensed"""
        self.quantity_dispensed += quantity
        self._sync_status_from_numbers()
        
        self.dispensed_by = user.staff if hasattr(user, 'staff') else None
        self.dispensed_at = timezone.now()
        self.dispensing_instructions = instructions
        self.dispensing_notes = notes
        self.save()

    def _sync_status_from_numbers(self):
        """Ensure dispensing_status matches quantities/payment."""
        ordered = self.quantity_ordered or 0
        dispensed = self.quantity_dispensed or 0

        if dispensed >= ordered and ordered > 0:
            self.dispensing_status = 'fully_dispensed'
        elif dispensed > 0:
            self.dispensing_status = 'partially_dispensed'
        elif self.payment_receipt and self.dispensing_status == 'pending_payment':
            self.dispensing_status = 'ready_to_dispense'

    def save(self, *args, **kwargs):
        self._sync_status_from_numbers()
        super().save(*args, **kwargs)


class ImagingRelease(BaseModel):
    """
    Track imaging study releases - requires payment verification
    Similar to LabResultRelease but for imaging studies
    """
    RELEASE_STATUS = [
        ('pending_payment', 'Pending Payment'),
        ('ready_for_release', 'Ready for Release'),
        ('released', 'Released to Patient'),
        ('emailed', 'Emailed to Patient'),
    ]
    
    imaging_study = models.OneToOneField('hospital.ImagingStudy', on_delete=models.CASCADE, related_name='release_record')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='imaging_releases')
    
    # Payment tracking
    payment_receipt = models.ForeignKey('hospital.PaymentReceipt', on_delete=models.SET_NULL, null=True, blank=True)
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    payment_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_imaging_payments')
    
    # Release tracking
    release_status = models.CharField(max_length=30, choices=RELEASE_STATUS, default='pending_payment')
    released_to = models.CharField(max_length=200, blank=True, help_text="Name of person who collected")
    released_to_relationship = models.CharField(max_length=100, blank=True, help_text="Relationship to patient")
    released_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='released_imaging_studies')
    released_at = models.DateTimeField(null=True, blank=True)
    
    # Identification verification
    id_type = models.CharField(max_length=50, blank=True, help_text="e.g., National ID, Passport")
    id_number = models.CharField(max_length=100, blank=True)
    
    # Delivery method
    delivery_method = models.CharField(max_length=20, choices=[
        ('in_person', 'Collected in Person'),
        ('email', 'Emailed'),
        ('proxy', 'Collected by Proxy'),
    ], default='in_person')
    
    release_notes = models.TextField(blank=True)
    sent_to_cashier_at = models.DateTimeField(null=True, blank=True)
    sent_to_cashier_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='imaging_cashier_tickets_sent')
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"Imaging Release: {self.imaging_study.study_type or 'Imaging Study'} - {self.patient.full_name} - {self.release_status}"
    
    def can_release(self):
        """Check if imaging study can be released"""
        return self.payment_receipt is not None and self.payment_verified_at is not None
    
    def mark_released(self, user, released_to_name, relationship='Self', id_type='', id_number='', notes=''):
        """Mark imaging study as released"""
        self.release_status = 'released'
        self.released_to = released_to_name
        self.released_to_relationship = relationship
        self.released_by = user
        self.released_at = timezone.now()
        self.id_type = id_type
        self.id_number = id_number
        self.release_notes = notes
        self.save()


class PharmacyDispenseHistory(BaseModel):
    """
    Immutable audit log for every dispensing action
    """
    dispensing_record = models.ForeignKey(
        PharmacyDispensing,
        on_delete=models.CASCADE,
        related_name='history_entries'
    )
    prescription = models.ForeignKey(
        'hospital.Prescription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispense_history'
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pharmacy_dispense_history_records'
    )
    patient_name = models.CharField(max_length=255, blank=True)
    drug = models.ForeignKey(
        'hospital.Drug',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pharmacy_dispense_history_records'
    )
    drug_name = models.CharField(max_length=255)
    quantity_dispensed = models.PositiveIntegerField()
    instructions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    counselling_given = models.BooleanField(default=False)
    dispensed_by = models.ForeignKey(
        'hospital.Staff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pharmacy_dispense_actions'
    )
    dispensed_by_name = models.CharField(max_length=255, blank=True)
    payment_receipt = models.ForeignKey(
        'hospital.PaymentReceipt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pharmacy_dispense_history_entries'
    )
    dispensed_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-dispensed_at', '-created']
    
    def __str__(self):
        return f"{self.drug_name} - {self.patient_name or 'Unknown Patient'} ({self.quantity_dispensed})"


class PharmacyStockDeductionLog(BaseModel):
    """
    Records one stock decrement per dispense/backfill source so we never double-deduct
    the same sale line when re-running backfills or mixing live dispense with corrections.
    """

    SOURCE_DISPENSE_HISTORY = 'dispense_history'
    SOURCE_PHARMACY_DISPENSING = 'pharmacy_dispensing'
    SOURCE_WALKIN_SALE_ITEM = 'walkin_sale_item'

    SOURCE_CHOICES = [
        (SOURCE_DISPENSE_HISTORY, 'Dispense history row'),
        (SOURCE_PHARMACY_DISPENSING, 'Pharmacy dispensing record (API / no history)'),
        (SOURCE_WALKIN_SALE_ITEM, 'Walk-in prescribe sale line'),
    ]

    source_type = models.CharField(max_length=32, choices=SOURCE_CHOICES, db_index=True)
    source_id = models.UUIDField(db_index=True, help_text='PK of the history / dispensing / sale item row')
    drug = models.ForeignKey(
        'hospital.Drug',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_deduction_logs',
    )
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created']
        constraints = [
            models.UniqueConstraint(
                fields=['source_type', 'source_id'],
                name='uniq_pharmacy_stock_deduction_source',
            ),
        ]

    def __str__(self):
        return f"{self.source_type} {self.source_id} x{self.quantity}"


class ReceiptQRCode(BaseModel):
    """
    QR codes for receipts - enables quick scanning
    """
    receipt = models.OneToOneField('hospital.PaymentReceipt', on_delete=models.CASCADE, related_name='qr_code')
    qr_code_data = models.TextField(help_text="Data encoded in QR code")
    qr_code_image = models.ImageField(upload_to='receipt_qr_codes/', null=True, blank=True)
    
    # Verification count
    scan_count = models.PositiveIntegerField(default=0)
    last_scanned_at = models.DateTimeField(null=True, blank=True)
    last_scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created']
    
    def __str__(self):
        return f"QR Code for Receipt {self.receipt.receipt_number}"
    
    def generate_qr_code(self):
        """Generate QR code image"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(self.qr_code_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        filename = f'receipt_qr_{self.receipt.receipt_number}.png'
        self.qr_code_image.save(filename, File(buffer), save=False)
        buffer.close()
    
    def record_scan(self, user):
        """Record when QR code is scanned"""
        self.scan_count += 1
        self.last_scanned_at = timezone.now()
        self.last_scanned_by = user
        self.save()









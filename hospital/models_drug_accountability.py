"""
World-Class Drug Accountability System
Complete tracking of drug administration, returns, and inventory movements
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Sum, F, Q
from decimal import Decimal
from datetime import date, timedelta
from .models import BaseModel, Staff, Patient, Drug, Prescription
from .models_procurement import Store, InventoryItem
from .models_inventory_advanced import InventoryTransaction
from .models_advanced import MedicationAdministrationRecord
from .models_payment_verification import PharmacyDispensing


# ==================== DRUG RETURN SYSTEM ====================

class DrugReturn(BaseModel):
    """
    Return drugs to pharmacy/inventory - for mistakenly dispensed or unpaid drugs
    Complete accountability with full audit trail
    """
    RETURN_REASONS = [
        ('mistakenly_dispensed', 'Mistakenly Dispensed'),
        ('unpaid', 'Unpaid - Patient Could Not Pay'),
        ('patient_refused', 'Patient Refused Medication'),
        ('wrong_drug', 'Wrong Drug Dispensed'),
        ('expired_drug', 'Expired Drug Found'),
        ('damaged', 'Damaged Drug'),
        ('over_dispensed', 'Over Dispensed Quantity'),
        ('prescription_cancelled', 'Prescription Cancelled'),
        ('patient_discharged', 'Patient Discharged Before Administration'),
        ('other', 'Other (Specify in Notes)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed - Returned to Inventory'),
        ('cancelled', 'Cancelled'),
    ]
    
    return_number = models.CharField(max_length=50, unique=True, db_index=True)
    return_date = models.DateTimeField(default=timezone.now, db_index=True)
    
    # Source of return
    prescription = models.ForeignKey(Prescription, on_delete=models.PROTECT, related_name='drug_returns', null=True, blank=True)
    dispensing_record = models.ForeignKey(PharmacyDispensing, on_delete=models.PROTECT, related_name='drug_returns', null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='drug_returns')
    
    # Drug details
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name='returns')
    batch_number = models.CharField(max_length=50, blank=True, db_index=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Quantities
    quantity_returned = models.PositiveIntegerField()
    quantity_original = models.PositiveIntegerField(help_text="Original quantity dispensed")
    
    # Return details
    return_reason = models.CharField(max_length=50, choices=RETURN_REASONS)
    reason_details = models.TextField(blank=True, help_text="Detailed reason for return")
    
    # Financial impact
    original_unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at time of dispensing")
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Amount to refund to patient")
    return_to_inventory = models.BooleanField(default=True, help_text="Return drug to inventory stock")
    
    # Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    requested_by = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='requested_drug_returns')
    requested_at = models.DateTimeField(default=timezone.now)
    
    approved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_drug_returns')
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    rejected_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='rejected_drug_returns')
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    processed_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_drug_returns')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Inventory tracking
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='drug_returns')
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='drug_returns', null=True, blank=True)
    inventory_transaction = models.ForeignKey(InventoryTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='drug_return')
    
    # Additional tracking
    notes = models.TextField(blank=True)
    condition_on_return = models.CharField(max_length=50, choices=[
        ('good', 'Good Condition'),
        ('damaged', 'Damaged'),
        ('expired', 'Expired'),
        ('opened', 'Opened Package'),
        ('sealed', 'Sealed/Unopened'),
    ], default='sealed')
    
    class Meta:
        ordering = ['-return_date', '-created']
        verbose_name = 'Drug Return'
        verbose_name_plural = 'Drug Returns'
        indexes = [
            models.Index(fields=['-return_date', 'status']),
            models.Index(fields=['patient', '-return_date']),
            models.Index(fields=['drug', '-return_date']),
            models.Index(fields=['status', '-return_date']),
        ]
    
    def __str__(self):
        return f"Return {self.return_number} - {self.drug.name} x{self.quantity_returned}"
    
    def save(self, *args, **kwargs):
        if not self.return_number:
            self.return_number = self.generate_return_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_return_number():
        """Generate unique return number"""
        from datetime import datetime
        prefix = "DR-RET"
        today = datetime.now()
        date_str = today.strftime('%Y%m%d')
        
        count = DrugReturn.objects.filter(
            return_number__startswith=f"{prefix}-{date_str}"
        ).count()
        
        return f"{prefix}-{date_str}-{count + 1:05d}"
    
    def approve(self, staff, notes=''):
        """Approve the return request"""
        if self.status != 'pending':
            raise ValueError("Only pending returns can be approved")
        
        self.status = 'approved'
        self.approved_by = staff
        self.approved_at = timezone.now()
        self.approval_notes = notes
        self.save()
    
    def reject(self, staff, reason):
        """Reject the return request"""
        if self.status != 'pending':
            raise ValueError("Only pending returns can be rejected")
        
        self.status = 'rejected'
        self.rejected_by = staff
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.save()
    
    def process_return(self, staff):
        """
        Process the return - add back to inventory and create transaction record
        This is the critical accountability step
        """
        if self.status != 'approved':
            raise ValueError("Return must be approved before processing")
        
        if not self.return_to_inventory:
            # Just mark as completed without inventory adjustment
            self.status = 'completed'
            self.processed_by = staff
            self.processed_at = timezone.now()
            self.save()
            return
        
        # Find or create inventory item
        from .models_procurement import InventoryItem, Store
        
        # Get pharmacy store - prefer "Main Pharmacy Store" (PHARM) for prescriptions
        pharmacy_store = Store.objects.filter(
            store_type='pharmacy',
            code='PHARM',
            is_deleted=False
        ).first()
        
        # Fallback to any pharmacy store if PHARM doesn't exist
        if not pharmacy_store:
            pharmacy_store = Store.objects.filter(
                store_type='pharmacy',
                is_deleted=False
            ).first()
        
        if not pharmacy_store:
            raise ValueError("Pharmacy store not found. Please create a pharmacy store first.")
        
        # Find inventory item for this drug
        inventory_item = InventoryItem.objects.filter(
            store=pharmacy_store,
            drug=self.drug,
            is_deleted=False
        ).first()
        
        if not inventory_item:
            # Create inventory item if it doesn't exist
            inventory_item = InventoryItem.objects.create(
                store=pharmacy_store,
                drug=self.drug,
                item_name=f"{self.drug.name} {self.drug.strength} {self.drug.form}",
                item_code=f"DRUG-{self.drug.id}",
                quantity_on_hand=0,
                unit_cost=self.original_unit_price,
                unit_of_measure='units',
            )
        
        # Record quantity before
        quantity_before = inventory_item.quantity_on_hand
        
        # Add quantity back to inventory
        inventory_item.quantity_on_hand += self.quantity_returned
        inventory_item.save()
        
        quantity_after = inventory_item.quantity_on_hand
        
        # Create inventory transaction record
        transaction = InventoryTransaction.objects.create(
            transaction_type='return_from_dept',
            transaction_date=timezone.now(),
            inventory_item=inventory_item,
            store=pharmacy_store,
            quantity=self.quantity_returned,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            unit_cost=self.original_unit_price,
            total_value=self.quantity_returned * self.original_unit_price,
            performed_by=staff,
            reference_number=self.return_number,
            batch_number=self.batch_number,
            notes=f"Drug return: {self.get_return_reason_display()}. {self.reason_details}",
            reason=f"Return from patient: {self.patient.full_name}. {self.get_return_reason_display()}",
        )
        
        # Link transaction
        self.inventory_transaction = transaction
        self.inventory_item = inventory_item
        self.store = pharmacy_store
        
        # Mark as completed
        self.status = 'completed'
        self.processed_by = staff
        self.processed_at = timezone.now()
        self.save()
        
        return transaction


# ==================== DRUG ADMINISTRATION INVENTORY TRACKING ====================

class DrugAdministrationInventory(BaseModel):
    """
    Track inventory reduction when drugs are administered to patients via MAR
    Links MAR records to inventory transactions for complete accountability
    """
    mar_record = models.OneToOneField(
        MedicationAdministrationRecord,
        on_delete=models.CASCADE,
        related_name='inventory_tracking'
    )
    
    # Drug and prescription details
    prescription = models.ForeignKey(Prescription, on_delete=models.PROTECT, related_name='administration_inventory')
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name='administration_inventory')
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='drug_administrations')
    
    # Inventory details
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='administrations', null=True, blank=True)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='drug_administrations', null=True, blank=True)
    
    # Quantity tracking
    quantity_administered = models.PositiveIntegerField(help_text="Quantity of drug units administered")
    batch_number = models.CharField(max_length=50, blank=True, db_index=True)
    
    # Inventory transaction
    inventory_transaction = models.ForeignKey(
        InventoryTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drug_administration'
    )
    
    # Financial tracking
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost per unit at time of administration")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total cost of administered drug")
    
    # Administration details
    administered_by = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='drug_administrations')
    administered_at = models.DateTimeField(default=timezone.now, db_index=True)
    
    # Location tracking
    ward = models.CharField(max_length=100, blank=True, help_text="Ward/location where drug was administered")
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-administered_at']
        verbose_name = 'Drug Administration Inventory'
        verbose_name_plural = 'Drug Administration Inventory Records'
        indexes = [
            models.Index(fields=['-administered_at', 'patient']),
            models.Index(fields=['drug', '-administered_at']),
            models.Index(fields=['batch_number']),
        ]
    
    def __str__(self):
        return f"{self.drug.name} - {self.patient.full_name} - {self.quantity_administered} units"
    
    @classmethod
    def create_from_mar(cls, mar_record, staff, quantity=None):
        """
        Create inventory tracking record when drug is administered via MAR
        This reduces inventory and creates transaction record
        """
        if mar_record.status != 'given':
            raise ValueError("MAR record must be in 'given' status")
        
        prescription = mar_record.prescription
        drug = prescription.drug
        patient = mar_record.patient
        
        # Determine quantity to reduce
        if quantity is None:
            # Try to parse quantity from dose_given or use prescription quantity
            try:
                # Simple parsing - can be enhanced
                quantity = prescription.quantity
            except:
                quantity = 1
        
        # Get pharmacy store for prescriptions - prefers Main Pharmacy Store (PHARM)
        pharmacy_store = Store.get_pharmacy_store_for_prescriptions()
        
        if not pharmacy_store:
            raise ValueError("Pharmacy store not found. Please create a pharmacy store first.")
        
        # Find inventory item
        inventory_item = InventoryItem.objects.filter(
            store=pharmacy_store,
            drug=drug,
            is_deleted=False
        ).first()
        
        if not inventory_item:
            # Create inventory item if it doesn't exist
            inventory_item = InventoryItem.objects.create(
                store=pharmacy_store,
                drug=drug,
                item_name=f"{drug.name} {drug.strength} {drug.form}",
                item_code=f"DRUG-{drug.id}",
                quantity_on_hand=0,
                unit_cost=drug.cost_price or Decimal('0.00'),
                unit_of_measure='units',
            )
        
        # Check if enough stock
        if inventory_item.quantity_on_hand < quantity:
            raise ValueError(
                f"Insufficient stock. Available: {inventory_item.quantity_on_hand}, "
                f"Required: {quantity}"
            )
        
        # Record quantity before
        quantity_before = inventory_item.quantity_on_hand
        
        # Reduce inventory
        inventory_item.quantity_on_hand -= quantity
        inventory_item.save()
        
        quantity_after = inventory_item.quantity_on_hand
        
        # Get unit cost
        unit_cost = inventory_item.unit_cost or drug.cost_price or Decimal('0.00')
        total_cost = quantity * unit_cost
        
        # Create inventory transaction
        transaction = InventoryTransaction.objects.create(
            transaction_type='issue',
            transaction_date=timezone.now(),
            inventory_item=inventory_item,
            store=pharmacy_store,
            quantity=-quantity,  # Negative for issue
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            unit_cost=unit_cost,
            total_value=total_cost,
            performed_by=staff,
            reference_number=f"MAR-{mar_record.id}",
            batch_number=mar_record.prescription.drug.name,  # Can be enhanced
            notes=f"Drug administered to patient {patient.full_name} via MAR",
            reason=f"Medication administration: {drug.name}",
            from_location=pharmacy_store.name,
            to_location=mar_record.encounter.ward.name if hasattr(mar_record.encounter, 'ward') and mar_record.encounter.ward else "Ward",
        )
        
        # Get ward name
        ward_name = ""
        if hasattr(mar_record.encounter, 'ward') and mar_record.encounter.ward:
            ward_name = mar_record.encounter.ward.name
        elif hasattr(mar_record.encounter, 'department') and mar_record.encounter.department:
            ward_name = mar_record.encounter.department.name
        
        # Create administration inventory record
        admin_inv = cls.objects.create(
            mar_record=mar_record,
            prescription=prescription,
            drug=drug,
            patient=patient,
            inventory_item=inventory_item,
            store=pharmacy_store,
            quantity_administered=quantity,
            batch_number="",  # Can be enhanced with batch tracking
            inventory_transaction=transaction,
            unit_cost=unit_cost,
            total_cost=total_cost,
            administered_by=staff,
            administered_at=mar_record.administered_time or timezone.now(),
            ward=ward_name,
            notes=f"Administered via MAR: {mar_record.notes}",
        )
        
        return admin_inv


# ==================== INVENTORY HISTORY VIEW MODEL ====================

class InventoryHistorySummary(BaseModel):
    """
    Summary view for inventory history - helps with reporting
    This is a denormalized view for performance
    """
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='history_summaries')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='history_summaries')
    
    # Period
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(db_index=True)
    
    # Quantities
    opening_balance = models.IntegerField(default=0)
    receipts = models.IntegerField(default=0)
    issues = models.IntegerField(default=0)
    transfers_in = models.IntegerField(default=0)
    transfers_out = models.IntegerField(default=0)
    returns = models.IntegerField(default=0)
    adjustments = models.IntegerField(default=0)
    closing_balance = models.IntegerField(default=0)
    
    # Financial
    opening_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receipts_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    issues_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Metadata
    transaction_count = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-period_start', 'inventory_item']
        unique_together = ['inventory_item', 'period_start', 'period_end']
        verbose_name = 'Inventory History Summary'
        verbose_name_plural = 'Inventory History Summaries'
        indexes = [
            models.Index(fields=['-period_start', 'store']),
            models.Index(fields=['inventory_item', '-period_start']),
        ]
    
    def __str__(self):
        return f"{self.inventory_item.item_name} - {self.period_start} to {self.period_end}"








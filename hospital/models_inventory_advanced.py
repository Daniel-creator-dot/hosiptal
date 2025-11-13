"""
World-Class Inventory Management System
State-of-the-art features for complete supply chain accountability
"""
import uuid
from django.db import models
from django.utils import timezone
from django.db.models import Sum, F, Q
from decimal import Decimal
from datetime import date, timedelta
from .models import BaseModel, Staff, Department
from .models_procurement import Store, InventoryItem, InventoryCategory


# ==================== ADVANCED INVENTORY TRACKING ====================

class InventoryTransaction(BaseModel):
    """Complete audit trail of all inventory movements - World-Class Tracking"""
    TRANSACTION_TYPES = [
        ('receipt', 'Receipt (Goods Received)'),
        ('issue', 'Issue (Goods Issued)'),
        ('transfer_out', 'Transfer Out'),
        ('transfer_in', 'Transfer In'),
        ('adjustment', 'Stock Adjustment'),
        ('return', 'Return to Supplier'),
        ('return_from_dept', 'Return from Department'),
        ('disposal', 'Disposal/Wastage'),
        ('damaged', 'Damaged'),
        ('expired', 'Expired'),
        ('theft', 'Theft/Loss'),
        ('found', 'Found (Unrecorded Stock)'),
    ]
    
    transaction_number = models.CharField(max_length=50, unique=True, db_index=True)
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES, db_index=True)
    transaction_date = models.DateTimeField(default=timezone.now, db_index=True)
    
    # Item details
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name='transactions')
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='inventory_transactions')
    
    # Quantity tracking
    quantity = models.IntegerField(help_text="Positive for additions, negative for deductions")
    quantity_before = models.PositiveIntegerField(help_text="Stock level before transaction")
    quantity_after = models.PositiveIntegerField(help_text="Stock level after transaction")
    
    # Financial tracking
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_value = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Traceability
    performed_by = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='inventory_transactions')
    approved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_inventory_transactions')
    
    # References to source documents
    reference_number = models.CharField(max_length=100, blank=True, db_index=True, help_text="PO, Transfer, or other ref")
    procurement_request = models.ForeignKey('ProcurementRequest', on_delete=models.SET_NULL, null=True, blank=True)
    store_transfer = models.ForeignKey('StoreTransfer', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Batch/Lot tracking
    batch_number = models.CharField(max_length=50, blank=True, db_index=True)
    lot_number = models.CharField(max_length=50, blank=True, db_index=True)
    
    # Additional tracking
    notes = models.TextField(blank=True)
    reason = models.TextField(blank=True, help_text="Reason for adjustment/disposal/etc")
    
    # Location tracking (for transfers)
    from_location = models.CharField(max_length=200, blank=True)
    to_location = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['-transaction_date', '-created']
        verbose_name = 'Inventory Transaction'
        verbose_name_plural = 'Inventory Transactions'
        indexes = [
            models.Index(fields=['-transaction_date', 'store']),
            models.Index(fields=['inventory_item', '-transaction_date']),
            models.Index(fields=['transaction_type', '-transaction_date']),
        ]
    
    def __str__(self):
        return f"{self.transaction_number} - {self.get_transaction_type_display()}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_number:
            self.transaction_number = self.generate_transaction_number()
        
        # Calculate total value
        self.total_value = abs(self.quantity) * self.unit_cost
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_transaction_number():
        """Generate unique transaction number"""
        from datetime import datetime
        prefix = "INV-TXN"
        today = datetime.now()
        date_str = today.strftime('%Y%m%d')
        
        # Count transactions for today
        count = InventoryTransaction.objects.filter(
            transaction_number__startswith=f"{prefix}-{date_str}"
        ).count()
        
        return f"{prefix}-{date_str}-{count + 1:05d}"


class InventoryBatch(BaseModel):
    """Batch/Lot tracking for items with expiry dates - Critical for Medical Supplies"""
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='batches')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='inventory_batches')
    
    batch_number = models.CharField(max_length=50, db_index=True)
    lot_number = models.CharField(max_length=50, blank=True, db_index=True)
    serial_number = models.CharField(max_length=50, blank=True, unique=True)
    
    # Quantities
    quantity_received = models.PositiveIntegerField()
    quantity_remaining = models.PositiveIntegerField()
    
    # Dates
    received_date = models.DateField(default=date.today)
    manufacturing_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    
    # Financial
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Supplier info
    supplier_name = models.CharField(max_length=200, blank=True)
    purchase_order_number = models.CharField(max_length=50, blank=True)
    
    # Status
    is_quarantined = models.BooleanField(default=False, help_text="Quarantined for quality check")
    is_expired = models.BooleanField(default=False, db_index=True)
    is_recalled = models.BooleanField(default=False, help_text="Batch recalled by supplier")
    
    quarantine_reason = models.TextField(blank=True)
    recall_reason = models.TextField(blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['expiry_date', '-received_date']
        verbose_name = 'Inventory Batch'
        verbose_name_plural = 'Inventory Batches'
        unique_together = ['inventory_item', 'batch_number', 'store']
        indexes = [
            models.Index(fields=['expiry_date', 'is_expired']),
            models.Index(fields=['batch_number']),
        ]
    
    def __str__(self):
        return f"{self.inventory_item.item_name} - Batch {self.batch_number}"
    
    def is_expiring_soon(self, days=30):
        """Check if batch is expiring within specified days"""
        if not self.expiry_date:
            return False
        return (self.expiry_date - date.today()).days <= days
    
    def days_until_expiry(self):
        """Get days until expiry"""
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days
    
    def check_expired(self):
        """Check and mark if expired"""
        if self.expiry_date and self.expiry_date < date.today():
            self.is_expired = True
            self.save()
            return True
        return False


class StockAlert(BaseModel):
    """Real-time stock alerts - Proactive Inventory Management"""
    ALERT_TYPES = [
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('overstock', 'Overstock'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('reorder_point', 'Reorder Point Reached'),
        ('batch_recalled', 'Batch Recalled'),
        ('quarantined', 'Item Quarantined'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium', db_index=True)
    
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='alerts')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='stock_alerts')
    batch = models.ForeignKey(InventoryBatch, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')
    
    message = models.TextField()
    current_quantity = models.IntegerField()
    recommended_action = models.TextField(blank=True)
    
    # Status
    is_acknowledged = models.BooleanField(default=False, db_index=True)
    acknowledged_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_stock_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_stock_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created', 'severity']
        verbose_name = 'Stock Alert'
        verbose_name_plural = 'Stock Alerts'
        indexes = [
            models.Index(fields=['-created', 'severity']),
            models.Index(fields=['is_acknowledged', 'is_resolved']),
        ]
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.inventory_item.item_name}"
    
    def acknowledge(self, staff):
        """Acknowledge the alert"""
        self.is_acknowledged = True
        self.acknowledged_by = staff
        self.acknowledged_at = timezone.now()
        self.save()
    
    def resolve(self, staff, notes=''):
        """Mark alert as resolved"""
        self.is_resolved = True
        self.resolved_by = staff
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()


class InventoryCount(BaseModel):
    """Physical stock counts/audits - Ensure Accuracy"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    count_number = models.CharField(max_length=50, unique=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='inventory_counts')
    count_date = models.DateField(default=date.today)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Who conducted the count
    conducted_by = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='conducted_counts')
    verified_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_counts')
    
    # Type of count
    is_full_count = models.BooleanField(default=True, help_text="Full count vs cycle count")
    category_filter = models.ForeignKey(InventoryCategory, on_delete=models.SET_NULL, null=True, blank=True, help_text="For partial counts")
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    # Summary
    total_items_counted = models.PositiveIntegerField(default=0)
    items_with_variance = models.PositiveIntegerField(default=0)
    total_variance_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['-count_date', '-created']
        verbose_name = 'Inventory Count'
        verbose_name_plural = 'Inventory Counts'
    
    def __str__(self):
        return f"{self.count_number} - {self.store.name} ({self.count_date})"
    
    def save(self, *args, **kwargs):
        if not self.count_number:
            self.count_number = self.generate_count_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_count_number():
        """Generate unique count number"""
        from datetime import datetime
        prefix = "COUNT"
        year = datetime.now().year
        month = datetime.now().month
        
        count = InventoryCount.objects.filter(
            count_number__startswith=f"{prefix}{year}{month:02d}"
        ).count()
        
        return f"{prefix}{year}{month:02d}{count + 1:04d}"
    
    def start_count(self):
        """Start the counting process"""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save()
    
    def complete_count(self):
        """Complete the count and calculate variances"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        
        # Calculate summaries
        lines = self.lines.filter(is_deleted=False)
        self.total_items_counted = lines.count()
        self.items_with_variance = lines.filter(has_variance=True).count()
        self.total_variance_value = lines.aggregate(
            total=Sum('variance_value')
        )['total'] or Decimal('0.00')
        
        self.save()


class InventoryCountLine(BaseModel):
    """Individual items in a stock count"""
    count = models.ForeignKey(InventoryCount, on_delete=models.CASCADE, related_name='lines')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    
    # System vs actual
    system_quantity = models.PositiveIntegerField(help_text="Quantity per system")
    counted_quantity = models.PositiveIntegerField(help_text="Actual physical count")
    variance = models.IntegerField(default=0, help_text="Counted - System")
    
    # Financial impact
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    variance_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    has_variance = models.BooleanField(default=False, db_index=True)
    
    # Reconciliation
    is_reconciled = models.BooleanField(default=False)
    reconciled_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    reconciliation_notes = models.TextField(blank=True)
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['inventory_item__item_name']
        verbose_name = 'Inventory Count Line'
        verbose_name_plural = 'Inventory Count Lines'
    
    def __str__(self):
        return f"{self.inventory_item.item_name} - Count: {self.counted_quantity}"
    
    def save(self, *args, **kwargs):
        # Calculate variance
        self.variance = self.counted_quantity - self.system_quantity
        self.has_variance = self.variance != 0
        self.variance_value = abs(self.variance) * self.unit_cost
        
        super().save(*args, **kwargs)


class InventoryRequisition(BaseModel):
    """Departments request items from stores - Formal Request Process"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('partially_issued', 'Partially Issued'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent/Emergency'),
    ]
    
    requisition_number = models.CharField(max_length=50, unique=True, db_index=True)
    requesting_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='inventory_requisitions')
    requested_by = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name='inventory_requisitions')
    requested_from_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='requisitions')
    
    request_date = models.DateTimeField(default=timezone.now)
    required_by_date = models.DateField(null=True, blank=True, help_text="When items are needed")
    
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    
    # Approval workflow
    approved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requisitions')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    issued_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_requisitions')
    issued_at = models.DateTimeField(null=True, blank=True)
    
    received_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_requisitions')
    received_at = models.DateTimeField(null=True, blank=True)
    
    purpose = models.TextField(help_text="Purpose/justification for requisition")
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-request_date']
        verbose_name = 'Inventory Requisition'
        verbose_name_plural = 'Inventory Requisitions'
        indexes = [
            models.Index(fields=['-request_date', 'status']),
            models.Index(fields=['requesting_department', '-request_date']),
        ]
    
    def __str__(self):
        return f"{self.requisition_number} - {self.requesting_department.name}"
    
    def save(self, *args, **kwargs):
        if not self.requisition_number:
            self.requisition_number = self.generate_requisition_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_requisition_number():
        """Generate unique requisition number"""
        from datetime import datetime
        prefix = "REQ"
        year = datetime.now().year
        
        count = InventoryRequisition.objects.filter(
            requisition_number__startswith=f"{prefix}{year}"
        ).count()
        
        return f"{prefix}{year}{count + 1:06d}"


class InventoryRequisitionLine(BaseModel):
    """Items requested in a requisition"""
    requisition = models.ForeignKey(InventoryRequisition, on_delete=models.CASCADE, related_name='lines')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    
    quantity_requested = models.PositiveIntegerField()
    quantity_approved = models.PositiveIntegerField(default=0)
    quantity_issued = models.PositiveIntegerField(default=0)
    
    unit_of_measure = models.CharField(max_length=20, default='units')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['created']
        verbose_name = 'Requisition Line'
        verbose_name_plural = 'Requisition Lines'
    
    def __str__(self):
        return f"{self.inventory_item.item_name} - Qty: {self.quantity_requested}"
    
    def is_fully_issued(self):
        return self.quantity_issued >= self.quantity_approved


# Add permissions to ProcurementRequest if not already there
from .models_procurement import ProcurementRequest, StoreTransfer

# Ensure Store model has permissions for inventory management


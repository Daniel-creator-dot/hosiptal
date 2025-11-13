"""
State-of-the-Art Procurement and Inventory Management System
Centralized procurement with multi-level approval workflow
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date
from decimal import Decimal
from model_utils.models import TimeStampedModel
from .models import BaseModel, Staff, Department, Drug
from .models_missing_features import Supplier


# ==================== STORE & INVENTORY MODULE ====================

class InventoryCategory(BaseModel):
    """Categories for inventory items (Pharmacy, Equipment, Supplies, Furniture, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_for_pharmacy = models.BooleanField(default=False, help_text="If True, items in this category are considered pharmacy/pharmaceutical items")
    display_order = models.PositiveIntegerField(default=0, help_text="Order for display in dropdowns")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Inventory Category'
        verbose_name_plural = 'Inventory Categories'
    
    def __str__(self):
        return self.name


class Store(BaseModel):
    """Central stores/inventory locations"""
    STORE_TYPES = [
        ('main', 'Main Store'),
        ('pharmacy', 'Pharmacy Store'),
        ('ward', 'Ward Store'),
        ('lab', 'Laboratory Store'),
        ('ot', 'Operating Theatre Store'),
        ('general', 'General Store'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    store_type = models.CharField(max_length=20, choices=STORE_TYPES)
    location = models.CharField(max_length=200, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='stores')
    manager = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_stores')
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Store'
        verbose_name_plural = 'Stores'
    
    def __str__(self):
        return f"{self.name} ({self.get_store_type_display()})"
    
    def get_total_items(self):
        """Get total number of items in this store"""
        return self.inventory_items.filter(is_deleted=False).count()
    
    def get_total_value(self):
        """Get total inventory value"""
        from django.db.models import Sum, F
        result = self.inventory_items.filter(
            is_deleted=False,
            quantity_on_hand__gt=0
        ).aggregate(
            total=Sum(F('quantity_on_hand') * F('unit_cost'))
        )
        return result['total'] or Decimal('0.00')


class InventoryItem(BaseModel):
    """Items in store inventory (can be drugs, supplies, equipment, etc.)"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='inventory_items')
    category = models.ForeignKey(InventoryCategory, on_delete=models.PROTECT, related_name='items', null=True, blank=True, help_text="Category helps organize items (Pharmacy, Equipment, Supplies, etc.)")
    item_name = models.CharField(max_length=200)
    item_code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    
    # Link to drug if applicable (for pharmacy)
    drug = models.ForeignKey(Drug, on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_items')
    
    # Inventory tracking
    quantity_on_hand = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    reorder_quantity = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_of_measure = models.CharField(max_length=20, default='units')
    
    # Supplier information
    preferred_supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['item_name']
        unique_together = ['store', 'item_code']
        verbose_name = 'Inventory Item'
        verbose_name_plural = 'Inventory Items'
    
    def __str__(self):
        return f"{self.item_name} ({self.store.name})"
    
    def generate_item_code(self):
        """Generate automatic item code based on category, store, and sequence"""
        # Get prefix from category code if available
        prefix = ""
        if self.category and self.category.code:
            prefix = self.category.code[:4].upper()  # Use first 4 chars of category code
        elif self.store and self.store.code:
            prefix = self.store.code[:3].upper()  # Fallback to store code
        else:
            prefix = "ITEM"
        
        # Get store code
        if self.store and self.store.code:
            store_code = self.store.code[:3].upper()
        else:
            store_code = "GEN"
        
        # Generate sequential number
        # Count existing items with same prefix in same store
        import re
        pattern = f'^{re.escape(prefix)}-{re.escape(store_code)}-'
        existing_items = InventoryItem.objects.filter(
            store=self.store,
            item_code__iregex=pattern
        ).exclude(pk=self.pk if self.pk else None)
        
        # Try to find next available number
        max_num = 0
        for item in existing_items:
            if item.item_code:
                try:
                    # Extract number from code like "PHARM-PHARM-000001"
                    parts = item.item_code.split('-')
                    if len(parts) >= 3:
                        num = int(parts[-1])
                        if num > max_num:
                            max_num = num
                except (ValueError, IndexError):
                    pass
        
        next_num = max_num + 1
        return f"{prefix}-{store_code}-{next_num:06d}"
    
    def save(self, *args, **kwargs):
        """Auto-generate item code if not provided"""
        if not self.item_code or self.item_code.strip() == '':
            # Generate code
            max_attempts = 10
            attempt = 0
            while attempt < max_attempts:
                code = self.generate_item_code()
                # Check if code already exists in this store
                exists = InventoryItem.objects.filter(
                    store=self.store,
                    item_code=code,
                    is_deleted=False
                ).exclude(pk=self.pk if self.pk else None).exists()
                
                if not exists:
                    self.item_code = code
                    break
                attempt += 1
            
            # If still no code, use a UUID-based fallback
            if not self.item_code or self.item_code.strip() == '':
                import uuid
                prefix = self.category.code[:4].upper() if (self.category and self.category.code) else "ITEM"
                store_code = self.store.code[:3].upper() if (self.store and self.store.code) else "GEN"
                self.item_code = f"{prefix}-{store_code}-{str(uuid.uuid4())[:8].upper()}"
        
        super().save(*args, **kwargs)
    
    def needs_reorder(self):
        """Check if item needs reordering"""
        return self.quantity_on_hand <= self.reorder_level and self.is_active
    
    def get_total_value(self):
        """Calculate total inventory value"""
        return self.quantity_on_hand * self.unit_cost


class StoreTransfer(BaseModel):
    """Transfer items between stores (e.g., Main Store to Pharmacy)"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('in_transit', 'In Transit'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    transfer_number = models.CharField(max_length=50, unique=True)
    from_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='transfers_out')
    to_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='transfers_in')
    transfer_date = models.DateField(default=date.today)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    requested_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='requested_transfers')
    approved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    approved_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transfers')
    received_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-transfer_date', '-created']
        verbose_name = 'Store Transfer'
        verbose_name_plural = 'Store Transfers'
    
    def __str__(self):
        return f"TRF {self.transfer_number} - {self.from_store.name} → {self.to_store.name}"
    
    def save(self, *args, **kwargs):
        if not self.transfer_number:
            self.transfer_number = self.generate_transfer_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_transfer_number():
        """Generate unique transfer number"""
        from datetime import datetime
        prefix = "TRF"
        year = datetime.now().year
        last_transfer = StoreTransfer.objects.filter(
            transfer_number__startswith=f"{prefix}{year}"
        ).order_by('-transfer_number').first()
        
        if last_transfer:
            try:
                last_num = int(last_transfer.transfer_number.replace(f"{prefix}{year}", ""))
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        return f"{prefix}{year}{new_num:06d}"
    
    def complete_transfer(self, staff):
        """Complete the transfer and update inventory"""
        if self.status != 'approved':
            raise ValueError("Transfer must be approved before completion")
        
        # Process each line item
        for line in self.lines.filter(is_deleted=False):
            # Decrease from_store inventory
            from_item = InventoryItem.objects.filter(
                store=self.from_store,
                item_code=line.item_code,
                is_deleted=False
            ).first()
            
            if from_item and from_item.quantity_on_hand >= line.quantity:
                from_item.quantity_on_hand -= line.quantity
                from_item.save()
                
                # Increase to_store inventory
                lookup_kwargs = {
                    'store': self.to_store,
                    'item_code': line.item_code,
                    'is_deleted': False
                }
                to_item = InventoryItem.objects.filter(**lookup_kwargs).first()
                
                if to_item:
                    to_item.quantity_on_hand += line.quantity
                    to_item.save()
                else:
                    InventoryItem.objects.create(
                        store=self.to_store,
                        item_name=line.item_name,
                        item_code=line.item_code,
                        quantity_on_hand=line.quantity,
                        unit_cost=line.unit_cost,
                        unit_of_measure=line.unit_of_measure,
                    )
        
        self.status = 'completed'
        self.received_by = staff
        self.received_at = timezone.now()
        self.save()


class StoreTransferLine(BaseModel):
    """Store transfer line items"""
    transfer = models.ForeignKey(StoreTransfer, on_delete=models.CASCADE, related_name='lines')
    item_code = models.CharField(max_length=50)
    item_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    unit_of_measure = models.CharField(max_length=20, default='units')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['created']
        verbose_name = 'Store Transfer Line'
        verbose_name_plural = 'Store Transfer Lines'


# ==================== PROCUREMENT REQUEST MODULE ====================

class ProcurementRequest(BaseModel):
    """Internal procurement requests from departments/stores"""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('admin_approved', 'Admin Approved'),
        ('accounts_approved', 'Accounts Approved'),
        ('payment_processed', 'Payment Processed'),
        ('ordered', 'Ordered'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    request_number = models.CharField(max_length=50, unique=True)
    requested_by_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='procurement_requests')
    requested_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name='procurement_requests')
    request_date = models.DateField(default=date.today)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Approval workflow
    admin_approved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_approved_procurements')
    admin_approved_at = models.DateTimeField(null=True, blank=True)
    admin_rejection_reason = models.TextField(blank=True)
    
    accounts_approved_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='accounts_approved_procurements')
    accounts_approved_at = models.DateTimeField(null=True, blank=True)
    accounts_rejection_reason = models.TextField(blank=True)
    
    # Financial
    estimated_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    approved_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Purchase order linkage
    purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='procurement_requests')
    
    notes = models.TextField(blank=True)
    justification = models.TextField(blank=True)  # Why this procurement is needed
    
    class Meta:
        ordering = ['-request_date', '-created']
        verbose_name = 'Procurement Request'
        verbose_name_plural = 'Procurement Requests'
        permissions = [
            ('can_approve_procurement_admin', 'Can approve procurement requests (Admin level)'),
            ('can_approve_procurement_accounts', 'Can approve procurement requests (Accounts level)'),
        ]
    
    def __str__(self):
        return f"PR {self.request_number} - {self.requested_by_store.name}"
    
    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self.generate_request_number()
        
        # Calculate estimated total from line items
        if self.pk:
            from django.db.models import Sum, F
            total = self.items.filter(is_deleted=False).aggregate(
                total=Sum(F('quantity') * F('estimated_unit_price'))
            )['total'] or Decimal('0.00')
            self.estimated_total = total
        
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_request_number():
        """Generate unique procurement request number"""
        from datetime import datetime
        prefix = "PR"
        year = datetime.now().year
        last_request = ProcurementRequest.objects.filter(
            request_number__startswith=f"{prefix}{year}"
        ).order_by('-request_number').first()
        
        if last_request:
            try:
                last_num = int(last_request.request_number.replace(f"{prefix}{year}", ""))
                new_num = last_num + 1
            except ValueError:
                new_num = 1
        else:
            new_num = 1
        return f"{prefix}{year}{new_num:06d}"
    
    def submit(self):
        """Submit request for approval"""
        if self.status == 'draft':
            self.status = 'submitted'
            self.save()
    
    def approve_by_admin(self, admin_staff):
        """Admin approval"""
        if self.status != 'submitted':
            raise ValueError("Request must be submitted before admin approval")
        
        self.status = 'admin_approved'
        self.admin_approved_by = admin_staff
        self.admin_approved_at = timezone.now()
        self.save()
    
    def approve_by_accounts(self, accounts_staff):
        """Accounts approval"""
        if self.status != 'admin_approved':
            raise ValueError("Request must be admin-approved before accounts approval")
        
        self.status = 'accounts_approved'
        self.accounts_approved_by = accounts_staff
        self.accounts_approved_at = timezone.now()
        self.save()
    
    def reject_by_admin(self, admin_staff, reason):
        """Admin rejection"""
        self.status = 'cancelled'
        self.admin_rejection_reason = reason
        self.save()
    
    def reject_by_accounts(self, accounts_staff, reason):
        """Accounts rejection"""
        self.status = 'cancelled'
        self.accounts_rejection_reason = reason
        self.save()
    
    def process_payment(self, staff):
        """Mark payment as processed"""
        if self.status != 'accounts_approved':
            raise ValueError("Request must be accounts-approved before payment processing")
        
        self.status = 'payment_processed'
        self.save()
    
    def mark_as_received(self, staff):
        """Mark items as received and update inventory"""
        if self.status not in ['ordered', 'payment_processed']:
            raise ValueError("Request must be ordered or payment processed before receiving")
        
        # Update inventory for each item
        for item in self.items.filter(is_deleted=False):
            # Get or create inventory item
            lookup_kwargs = {
                'store': self.requested_by_store,
                'item_code': item.item_code if item.item_code else item.item_name,
                'is_deleted': False
            }
            
            inventory_item = InventoryItem.objects.filter(**lookup_kwargs).first()
            
            if inventory_item:
                # Update quantity and cost (weighted average)
                total_qty = inventory_item.quantity_on_hand + item.quantity
                total_cost = (inventory_item.quantity_on_hand * inventory_item.unit_cost) + (item.quantity * item.estimated_unit_price)
                inventory_item.quantity_on_hand = total_qty
                inventory_item.unit_cost = total_cost / total_qty if total_qty > 0 else inventory_item.unit_cost
                inventory_item.save()
            else:
                # Create new inventory item
                InventoryItem.objects.create(
                    store=self.requested_by_store,
                    item_name=item.item_name,
                    item_code=item.item_code if item.item_code else item.item_name,
                    drug=item.drug,
                    quantity_on_hand=item.quantity,
                    unit_cost=item.estimated_unit_price,
                    unit_of_measure=item.unit_of_measure,
                    preferred_supplier=item.preferred_supplier,
                )
        
        self.status = 'received'
        self.save()


class ProcurementRequestItem(BaseModel):
    """Items in procurement request"""
    request = models.ForeignKey(ProcurementRequest, on_delete=models.CASCADE, related_name='items')
    
    # Item details
    item_name = models.CharField(max_length=200)
    item_code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    drug = models.ForeignKey(Drug, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Quantities and pricing
    quantity = models.PositiveIntegerField()
    unit_of_measure = models.CharField(max_length=20, default='units')
    estimated_unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Specifications
    specifications = models.TextField(blank=True)
    preferred_supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Receiving
    received_quantity = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['created']
        verbose_name = 'Procurement Request Item'
        verbose_name_plural = 'Procurement Request Items'
    
    def __str__(self):
        return f"{self.item_name} - {self.quantity} {self.unit_of_measure}"
    
    def generate_item_code(self):
        """Generate automatic item code if not provided"""
        # Generate code based on item name and request number
        if not self.item_code or self.item_code.strip() == '':
            if self.request and self.request.request_number:
                # Use request number prefix (first 6 chars)
                prefix = self.request.request_number[:6].upper()
                # Use first 4 chars of item name
                item_prefix = ''.join([c for c in self.item_name[:4].upper() if c.isalnum()])
                if not item_prefix:
                    item_prefix = "ITEM"
                # Sequential number based on position in request
                try:
                    position = list(self.request.items.filter(is_deleted=False).values_list('pk', flat=True)).index(self.pk) + 1 if self.pk else 0
                except (ValueError, AttributeError):
                    position = 0
                if position == 0:
                    position = self.request.items.filter(is_deleted=False).count() + 1
                return f"{prefix}-{item_prefix}-{position:03d}"
            else:
                # Fallback if no request yet
                item_prefix = ''.join([c for c in self.item_name[:4].upper() if c.isalnum()]) or "ITEM"
                import uuid
                return f"PR-{item_prefix}-{str(uuid.uuid4())[:6].upper()}"
        return self.item_code
    
    def save(self, *args, **kwargs):
        """Auto-generate item code and calculate line total"""
        # Auto-generate item code if not provided
        if not self.item_code or self.item_code.strip() == '':
            self.item_code = self.generate_item_code()
        
        # Calculate line total
        self.line_total = self.quantity * self.estimated_unit_price
        
        super().save(*args, **kwargs)


# Supplier is in models_missing_features.py
# Use forward reference as string 'Supplier' in ForeignKey - Django resolves at runtime


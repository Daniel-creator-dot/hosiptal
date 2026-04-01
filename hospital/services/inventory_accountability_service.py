"""
World-Class Inventory Accountability Service
Ensures all inventory movements are properly tracked with complete audit trail
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError

from ..models_procurement import Store, InventoryItem
from ..models_inventory_advanced import InventoryTransaction
from ..models import Drug, Staff

logger = logging.getLogger(__name__)


class InventoryAccountabilityService:
    """
    Service for managing inventory with complete accountability
    All inventory movements create proper transaction records
    """
    
    @staticmethod
    @db_transaction.atomic
    def receive_from_supplier(
        inventory_item,
        quantity,
        unit_cost,
        staff,
        reference_number='',
        batch_number='',
        expiry_date=None,
        supplier_name='',
        notes=''
    ):
        """
        Record receipt of items from supplier
        Creates inventory transaction and updates stock
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")
        
        if unit_cost < 0:
            raise ValidationError("Unit cost cannot be negative")
        
        # Record quantity before
        quantity_before = inventory_item.quantity_on_hand
        
        # Calculate new quantity and weighted average cost
        total_qty = quantity_before + quantity
        total_cost_before = quantity_before * inventory_item.unit_cost
        total_cost_new = quantity * unit_cost
        new_unit_cost = (total_cost_before + total_cost_new) / total_qty if total_qty > 0 else unit_cost
        
        # Update inventory
        inventory_item.quantity_on_hand = total_qty
        inventory_item.unit_cost = new_unit_cost
        inventory_item.save()
        
        quantity_after = inventory_item.quantity_on_hand
        
        # Create transaction record
        inv_transaction = InventoryTransaction.objects.create(
            transaction_type='receipt',
            transaction_date=timezone.now(),
            inventory_item=inventory_item,
            store=inventory_item.store,
            quantity=quantity,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            unit_cost=unit_cost,
            total_value=quantity * unit_cost,
            performed_by=staff,
            approved_by=staff,  # Can be changed to require separate approval
            reference_number=reference_number,
            batch_number=batch_number,
            notes=f"Received from supplier: {supplier_name}. {notes}",
            reason=f"Goods received from supplier",
        )
        
        logger.info(
            f"✅ Received {quantity} units of {inventory_item.item_name} "
            f"from supplier. Transaction: {inv_transaction.transaction_number}"
        )
        
        return inv_transaction
    
    @staticmethod
    @db_transaction.atomic
    def issue_to_department(
        inventory_item,
        quantity,
        staff,
        department_name='',
        reference_number='',
        notes='',
        reason=''
    ):
        """
        Issue items from inventory to department
        Creates transaction record and reduces stock
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")
        
        if inventory_item.quantity_on_hand < quantity:
            raise ValidationError(
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
        unit_cost = inventory_item.unit_cost or Decimal('0.00')
        total_value = quantity * unit_cost
        
        # Create transaction record
        inv_transaction = InventoryTransaction.objects.create(
            transaction_type='issue',
            transaction_date=timezone.now(),
            inventory_item=inventory_item,
            store=inventory_item.store,
            quantity=-quantity,  # Negative for issue
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            unit_cost=unit_cost,
            total_value=total_value,
            performed_by=staff,
            reference_number=reference_number,
            notes=f"Issued to department: {department_name}. {notes}",
            reason=reason or f"Issue to {department_name}",
            from_location=inventory_item.store.name,
            to_location=department_name,
        )
        
        logger.info(
            f"✅ Issued {quantity} units of {inventory_item.item_name} "
            f"to {department_name}. Transaction: {inv_transaction.transaction_number}"
        )
        
        return inv_transaction
    
    @staticmethod
    @db_transaction.atomic
    def transfer_between_stores(
        from_item,
        to_store,
        quantity,
        staff,
        reference_number='',
        notes='',
        to_item=None
    ):
        """
        Transfer items between stores
        Creates transaction records for both stores
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")
        
        if from_item.quantity_on_hand < quantity:
            raise ValidationError(
                f"Insufficient stock. Available: {from_item.quantity_on_hand}, "
                f"Required: {quantity}"
            )
        
        # Record quantities before
        from_quantity_before = from_item.quantity_on_hand
        
        # Reduce from source store
        from_item.quantity_on_hand -= quantity
        from_item.save()
        
        from_quantity_after = from_item.quantity_on_hand
        
        # Get or create destination item
        if to_item is None:
            to_item = InventoryItem.objects.filter(
                store=to_store,
                drug=from_item.drug,
                is_deleted=False
            ).first()
            
            if to_item is None:
                # Create new inventory item in destination store
                to_item = InventoryItem.objects.create(
                    store=to_store,
                    drug=from_item.drug,
                    category=from_item.category,
                    item_name=from_item.item_name,
                    item_code=from_item.item_code,
                    description=from_item.description,
                    quantity_on_hand=0,
                    unit_cost=from_item.unit_cost,
                    unit_of_measure=from_item.unit_of_measure,
                    preferred_supplier=from_item.preferred_supplier,
                    is_active=True,  # Ensure item is active so it shows in inventory list
                )
        
        to_quantity_before = to_item.quantity_on_hand
        
        # Add to destination store
        to_item.quantity_on_hand += quantity
        # Update cost using weighted average
        if to_item.quantity_on_hand > 0:
            total_cost_before = to_quantity_before * to_item.unit_cost
            total_cost_new = quantity * from_item.unit_cost
            to_item.unit_cost = (total_cost_before + total_cost_new) / to_item.quantity_on_hand
        to_item.save()
        
        to_quantity_after = to_item.quantity_on_hand
        
        unit_cost = from_item.unit_cost or Decimal('0.00')
        total_value = quantity * unit_cost
        
        # Create transaction for source store (transfer out)
        transfer_out = InventoryTransaction.objects.create(
            transaction_type='transfer_out',
            transaction_date=timezone.now(),
            inventory_item=from_item,
            store=from_item.store,
            quantity=-quantity,
            quantity_before=from_quantity_before,
            quantity_after=from_quantity_after,
            unit_cost=unit_cost,
            total_value=total_value,
            performed_by=staff,
            reference_number=reference_number,
            notes=f"Transferred to {to_store.name}. {notes}",
            reason=f"Transfer to {to_store.name}",
            from_location=from_item.store.name,
            to_location=to_store.name,
        )
        
        # Create transaction for destination store (transfer in)
        transfer_in = InventoryTransaction.objects.create(
            transaction_type='transfer_in',
            transaction_date=timezone.now(),
            inventory_item=to_item,
            store=to_store,
            quantity=quantity,
            quantity_before=to_quantity_before,
            quantity_after=to_quantity_after,
            unit_cost=unit_cost,
            total_value=total_value,
            performed_by=staff,
            reference_number=reference_number,
            notes=f"Transferred from {from_item.store.name}. {notes}",
            reason=f"Transfer from {from_item.store.name}",
            from_location=from_item.store.name,
            to_location=to_store.name,
        )
        
        logger.info(
            f"✅ Transferred {quantity} units of {from_item.item_name} "
            f"from {from_item.store.name} to {to_store.name}. "
            f"Transactions: {transfer_out.transaction_number}, {transfer_in.transaction_number}"
        )
        
        return transfer_out, transfer_in
    
    @staticmethod
    @db_transaction.atomic
    def return_to_inventory(
        inventory_item,
        quantity,
        staff,
        return_reason='',
        reference_number='',
        batch_number='',
        notes=''
    ):
        """
        Return items to inventory (e.g., from department or patient return)
        Creates transaction record and increases stock
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")
        
        # Record quantity before
        quantity_before = inventory_item.quantity_on_hand
        
        # Add to inventory
        inventory_item.quantity_on_hand += quantity
        inventory_item.save()
        
        quantity_after = inventory_item.quantity_on_hand
        
        # Get unit cost
        unit_cost = inventory_item.unit_cost or Decimal('0.00')
        total_value = quantity * unit_cost
        
        # Create transaction record
        inv_transaction = InventoryTransaction.objects.create(
            transaction_type='return_from_dept',
            transaction_date=timezone.now(),
            inventory_item=inventory_item,
            store=inventory_item.store,
            quantity=quantity,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            unit_cost=unit_cost,
            total_value=total_value,
            performed_by=staff,
            reference_number=reference_number,
            batch_number=batch_number,
            notes=f"Return to inventory. Reason: {return_reason}. {notes}",
            reason=return_reason or "Return to inventory",
        )
        
        logger.info(
            f"✅ Returned {quantity} units of {inventory_item.item_name} "
            f"to inventory. Transaction: {inv_transaction.transaction_number}"
        )
        
        return inv_transaction
    
    @staticmethod
    @db_transaction.atomic
    def adjust_stock(
        inventory_item,
        adjustment_quantity,
        staff,
        reason='',
        reference_number='',
        notes=''
    ):
        """
        Adjust stock (for discrepancies, found items, etc.)
        Positive quantity = increase, negative = decrease
        """
        if adjustment_quantity == 0:
            raise ValidationError("Adjustment quantity cannot be zero")
        
        # Record quantity before
        quantity_before = inventory_item.quantity_on_hand
        
        # Calculate new quantity
        new_quantity = quantity_before + adjustment_quantity
        
        if new_quantity < 0:
            raise ValidationError(
                f"Adjustment would result in negative stock. "
                f"Current: {quantity_before}, Adjustment: {adjustment_quantity}"
            )
        
        # Update inventory
        inventory_item.quantity_on_hand = new_quantity
        inventory_item.save()
        
        quantity_after = inventory_item.quantity_on_hand
        
        # Get unit cost
        unit_cost = inventory_item.unit_cost or Decimal('0.00')
        total_value = abs(adjustment_quantity) * unit_cost
        
        # Create transaction record
        inv_transaction = InventoryTransaction.objects.create(
            transaction_type='adjustment',
            transaction_date=timezone.now(),
            inventory_item=inventory_item,
            store=inventory_item.store,
            quantity=adjustment_quantity,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            unit_cost=unit_cost,
            total_value=total_value,
            performed_by=staff,
            reference_number=reference_number,
            notes=f"Stock adjustment. {notes}",
            reason=reason or "Stock adjustment",
        )
        
        logger.info(
            f"✅ Adjusted stock of {inventory_item.item_name} by {adjustment_quantity}. "
            f"Transaction: {inv_transaction.transaction_number}"
        )
        
        return inv_transaction
    
    @staticmethod
    def get_inventory_history(inventory_item, start_date=None, end_date=None):
        """
        Get complete history of inventory transactions for an item
        """
        queryset = InventoryTransaction.objects.filter(
            inventory_item=inventory_item,
            is_deleted=False
        ).select_related(
            'performed_by',
            'approved_by',
            'store'
        ).order_by('-transaction_date')
        
        if start_date:
            queryset = queryset.filter(transaction_date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(transaction_date__lte=end_date)
        
        return queryset
    
    @staticmethod
    def get_store_history(store, start_date=None, end_date=None):
        """
        Get complete history of all transactions for a store
        """
        queryset = InventoryTransaction.objects.filter(
            store=store,
            is_deleted=False
        ).select_related(
            'inventory_item',
            'performed_by',
            'approved_by'
        ).order_by('-transaction_date')
        
        if start_date:
            queryset = queryset.filter(transaction_date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(transaction_date__lte=end_date)
        
        return queryset








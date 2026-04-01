# 🎯 Proper Store Transfer Logic - Complete Guide

## Overview

This document describes the comprehensive, robust store transfer logic implemented in the system. The transfer logic ensures data integrity, proper item matching, and complete audit trails.

---

## 🔄 Transfer Workflow

### 1. **Create Transfer Request**
- User selects source store and destination store
- Adds line items (item name, code, quantity, unit cost)
- Transfer status: `pending`

### 2. **Approve Transfer**
- System validates:
  - All items exist in source store
  - Sufficient stock available
  - Items can be matched properly
- Transfer status: `approved` or `in_transit`

### 3. **Complete Transfer**
- System processes transfer:
  - Reduces quantity from source store
  - Adds quantity to destination store
  - Creates/updates inventory items
  - Creates audit trail transactions
- Transfer status: `completed`

---

## 🎯 Item Matching Strategy

The system uses a **multi-strategy approach** to find items, ensuring transfers work even if item codes differ between stores:

### **Strategy 1: Item Code Match (Primary)**
```python
InventoryItem.objects.filter(
    store=source_store,
    item_code=line.item_code,
    is_deleted=False
).first()
```
- **Use case**: When items have consistent codes across stores
- **Priority**: Highest

### **Strategy 2: Item Name Exact Match**
```python
InventoryItem.objects.filter(
    store=source_store,
    item_name__iexact=line.item_name.strip(),
    is_deleted=False
).first()
```
- **Use case**: When item codes differ but names match exactly
- **Priority**: High

### **Strategy 3: Item Name Partial Match**
```python
InventoryItem.objects.filter(
    store=source_store,
    item_name__icontains=line.item_name.strip(),
    is_deleted=False
).first()
```
- **Use case**: When names are similar but not exact
- **Priority**: Medium

### **Strategy 4: Drug Match (For Destination)**
```python
InventoryItem.objects.filter(
    store=destination_store,
    drug=from_item.drug,
    is_deleted=False
).first()
```
- **Use case**: When transferring pharmacy items linked to drugs
- **Priority**: Medium (destination only)

---

## ✅ Validation Logic

### **Pre-Approval Validation**
Before approving a transfer, the system validates:

1. **Item Existence**
   - Item must exist in source store
   - Uses multi-strategy matching (code → name → partial name)

2. **Stock Availability**
   - Source store must have sufficient quantity
   - Checks: `from_item.quantity_on_hand >= line.quantity`

3. **Store Validity**
   - Both stores must be active and not deleted
   - Source and destination must be different

### **Pre-Completion Validation**
Before completing a transfer, the system validates:

1. **Transfer Status**
   - Must be `approved` or `in_transit`
   - Cannot complete `pending` or `cancelled` transfers

2. **Staff Authorization**
   - Staff member must be provided
   - Staff must exist and be active

3. **All Line Items**
   - All items must pass validation
   - All errors collected before processing

---

## 🔒 Transaction Safety

### **Database Transactions**
All transfers use `@transaction.atomic()` to ensure:
- **Atomicity**: All items transfer or none do
- **Consistency**: Database remains in valid state
- **Rollback**: On any error, entire transfer is rolled back

```python
with transaction.atomic():
    # Process all line items
    for item_data in line_items_data:
        # Transfer item
        InventoryAccountabilityService.transfer_between_stores(...)
    
    # Update transfer status
    self.status = 'completed'
    self.save()
```

---

## 📊 Inventory Updates

### **Source Store (From Store)**
1. **Reduce Quantity**
   ```python
   from_item.quantity_on_hand -= quantity
   from_item.save()
   ```

2. **Create Transaction Record**
   - Type: `transfer_out`
   - Quantity: Negative (e.g., -10)
   - Records: quantity_before, quantity_after

### **Destination Store (To Store)**
1. **Find or Create Item**
   - Tries to find existing item
   - Creates new item if not found
   - Copies metadata from source item

2. **Add Quantity**
   ```python
   to_item.quantity_on_hand += quantity
   ```

3. **Update Unit Cost (Weighted Average)**
   ```python
   total_cost_before = to_quantity_before * to_item.unit_cost
   total_cost_new = quantity * from_item.unit_cost
   to_item.unit_cost = (total_cost_before + total_cost_new) / to_item.quantity_on_hand
   ```

4. **Create Transaction Record**
   - Type: `transfer_in`
   - Quantity: Positive (e.g., +10)
   - Records: quantity_before, quantity_after

---

## 📝 Audit Trail

Every transfer creates comprehensive audit records:

### **Transfer Record**
- Transfer number (auto-generated: `TRF2024000001`)
- From store → To store
- Status tracking (pending → approved → completed)
- Requested by, approved by, received by
- Timestamps for each stage

### **Transaction Records**
- **Source Store Transaction**:
  - Type: `transfer_out`
  - Reference: Transfer number
  - Notes: "Transferred to [destination]"
  
- **Destination Store Transaction**:
  - Type: `transfer_in`
  - Reference: Transfer number
  - Notes: "Transferred from [source]"

### **Inventory Item History**
- Quantity before/after for both stores
- Unit cost tracking
- Full transaction history

---

## 🚨 Error Handling

### **Validation Errors**
- Collected before processing
- All errors shown at once
- Prevents partial transfers

### **Processing Errors**
- Transaction rollback on any error
- Detailed error messages
- Logging for debugging

### **Common Error Scenarios**

1. **Item Not Found**
   ```
   Error: "Source item 'Paracetamol 500mg' (Code: PARA-001) not found in Main Store"
   Solution: Check item name/code matches, verify item exists in source store
   ```

2. **Insufficient Stock**
   ```
   Error: "Insufficient stock for 'Paracetamol 500mg'. Available: 50, Required: 100"
   Solution: Reduce transfer quantity or restock source store
   ```

3. **Invalid Status**
   ```
   Error: "Transfer must be approved before completion. Current status: pending"
   Solution: Approve transfer first
   ```

---

## 💡 Best Practices

### **1. Item Naming Consistency**
- Use consistent item names across stores
- Prefer item codes for exact matching
- Link items to Drug model when possible

### **2. Transfer Approval**
- Always validate before approval
- Check stock levels before creating transfer
- Verify item codes/names match

### **3. Transfer Completion**
- Complete transfers promptly after approval
- Verify received quantities match transfer
- Review transaction records

### **4. Error Recovery**
- Check validation errors carefully
- Fix source data before retrying
- Use transaction history for audit

---

## 🔧 Implementation Details

### **Key Files**
- `hospital/models_procurement.py` - `StoreTransfer.complete_transfer()`
- `hospital/views_store_transfer_enhanced.py` - Approval and completion views
- `hospital/services/inventory_accountability_service.py` - Core transfer logic

### **Key Methods**
- `StoreTransfer.complete_transfer(staff)` - Main transfer logic
- `InventoryAccountabilityService.transfer_between_stores()` - Core transfer service
- `StoreTransfer.generate_transfer_number()` - Auto-number generation

---

## 📈 Transfer Status Flow

```
pending → approved → in_transit → completed
   ↓         ↓           ↓
cancelled  cancelled  cancelled
```

### **Status Descriptions**
- **pending**: Transfer created, awaiting approval
- **approved**: Transfer approved, ready to process
- **in_transit**: Items being moved (optional status)
- **completed**: Transfer completed, inventory updated
- **cancelled**: Transfer cancelled, no changes made

---

## ✅ Summary

The proper transfer logic ensures:
- ✅ **Data Integrity**: Atomic transactions prevent partial updates
- ✅ **Item Matching**: Multi-strategy matching finds items reliably
- ✅ **Validation**: Comprehensive pre-flight checks
- ✅ **Audit Trail**: Complete transaction history
- ✅ **Error Handling**: Clear errors with rollback safety
- ✅ **Flexibility**: Works with varying item codes/names

This implementation provides a robust, production-ready store transfer system.

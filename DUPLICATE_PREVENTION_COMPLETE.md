# 🔒 Duplicate Invoice Line Prevention - Complete Solution

## Overview

Comprehensive solution to prevent duplicate medication/service entries in invoices. This includes database-level checks, model-level validation, service-level logic, and cleanup tools.

---

## 🛡️ **Protection Layers**

### **Layer 1: Model-Level Protection** (`InvoiceLine.save()`)

The `InvoiceLine` model's `save()` method now includes duplicate prevention:

```python
# Before saving, checks if a line with the same service_code already exists
# If found, merges quantities instead of creating duplicate
```

**Features:**
- ✅ Checks for existing lines with same service_code before saving
- ✅ Merges quantities automatically
- ✅ Uses database locking to prevent race conditions
- ✅ Updates description to reflect total quantity
- ✅ Handles prescription linking intelligently

### **Layer 2: Service-Level Protection** (`AutoBillingService`)

Enhanced `create_pharmacy_bill()` and `create_lab_bill()` methods:

**Pharmacy Billing:**
- Checks for existing invoice lines with same service_code
- Merges all prescriptions of the same drug into ONE line
- Prevents duplicates even if:
  - Same prescription billed multiple times
  - Multiple prescriptions for same drug
  - Same drug prescribed multiple times

**Lab Billing:**
- Similar duplicate prevention logic
- Merges multiple tests of same type

### **Layer 3: Utility Functions** (`utils_invoice_line.py`)

Safe creation utility:
```python
from hospital.utils_invoice_line import create_or_merge_invoice_line

invoice_line, created = create_or_merge_invoice_line(
    invoice=invoice,
    service_code=service_code,
    quantity=quantity,
    unit_price=unit_price,
    description=description,
    prescription=prescription
)
```

**Use this utility** for all new invoice line creation to ensure duplicates are prevented.

---

## 🧹 **Cleanup Tools**

### **1. Fix Existing Duplicates**

```bash
# Preview what will be fixed (dry-run)
python manage.py fix_duplicate_invoice_lines --dry-run --verbose

# Fix all duplicates
python manage.py fix_duplicate_invoice_lines

# Fix specific invoice
python manage.py fix_duplicate_invoice_lines --invoice INV2025010100001

# Detailed output
python manage.py fix_duplicate_invoice_lines --verbose
```

**What it does:**
- Finds all invoices with duplicate service_code entries
- Merges quantities into single line
- Updates descriptions
- Recalculates invoice totals
- Marks duplicate lines as deleted (soft delete)

### **2. Audit Billing System**

```bash
# Audit all invoices for duplicates
python manage.py audit_billing --fix
```

---

## 🔍 **How Duplicate Prevention Works**

### **Scenario 1: Same Drug Prescribed Multiple Times**

**Before:**
```
Invoice Line 1: ACECLOFENAC 100MG x1 - GHS 0.00
Invoice Line 2: ACECLOFENAC 100MG x1 - GHS 0.00
Invoice Line 3: ACECLOFENAC 100MG x1 - GHS 0.00
```

**After:**
```
Invoice Line 1: ACECLOFENAC 100MG x3 - GHS 0.00
```

### **Scenario 2: Same Prescription Billed Multiple Times**

**Protection:**
- Checks if line with same service_code exists
- If exists, updates quantity instead of creating new line
- Prevents accidental duplicate billing

### **Scenario 3: Multiple Prescriptions for Same Drug**

**Protection:**
- All prescriptions of same drug merged into one line
- Quantity is sum of all prescriptions
- Description shows total quantity

---

## 🔧 **Database Constraints**

### **Indexes Added:**

```python
class Meta:
    indexes = [
        models.Index(fields=['invoice', 'service_code', 'is_deleted']),
        models.Index(fields=['prescription', 'is_deleted']),
    ]
```

These indexes:
- Speed up duplicate detection queries
- Improve performance when checking for existing lines
- Ensure efficient lookups

---

## 📋 **Best Practices**

### **1. Always Use Safe Creation**

**❌ Don't:**
```python
InvoiceLine.objects.create(invoice=..., service_code=..., ...)
```

**✅ Do:**
```python
from hospital.utils_invoice_line import create_or_merge_invoice_line
invoice_line, created = create_or_merge_invoice_line(...)
```

### **2. Check for Duplicates Before Creation**

```python
existing = InvoiceLine.objects.filter(
    invoice=invoice,
    service_code=service_code,
    is_deleted=False
).first()

if existing:
    # Merge instead of create
    existing.quantity += new_quantity
    existing.save()
```

### **3. Use Database Transactions**

```python
with transaction.atomic():
    # Check and create/merge in transaction
    # Prevents race conditions
```

---

## 🚨 **What Changed**

### **Files Modified:**

1. **`hospital/models.py`**
   - Added duplicate prevention in `InvoiceLine.save()`
   - Added database indexes
   - Enhanced Meta class

2. **`hospital/services/auto_billing_service.py`**
   - Fixed `create_pharmacy_bill()` duplicate logic
   - Fixed `create_lab_bill()` duplicate logic
   - Added proper merging logic

3. **`hospital/utils_invoice_line.py`** (NEW)
   - Safe invoice line creation utility
   - Merge logic reusable across codebase

4. **`hospital/management/commands/fix_duplicate_invoice_lines.py`** (NEW)
   - Command to fix existing duplicates
   - Dry-run support
   - Detailed reporting

---

## ✅ **Testing**

### **Test Duplicate Prevention:**

1. Prescribe same drug multiple times
2. Check invoice - should see ONE line with total quantity

3. Try to bill same prescription twice
4. Check invoice - should NOT create duplicate

5. Create multiple prescriptions for same drug
6. All should merge into one invoice line

### **Run Cleanup:**

```bash
# First, see what duplicates exist
python manage.py fix_duplicate_invoice_lines --dry-run --verbose

# Then fix them
python manage.py fix_duplicate_invoice_lines
```

---

## 📊 **Monitoring**

### **Check for Duplicates:**

```python
from hospital.models import InvoiceLine
from django.db.models import Count

# Find invoices with duplicate service codes
duplicates = InvoiceLine.objects.filter(
    is_deleted=False
).values(
    'invoice', 'service_code'
).annotate(
    count=Count('id')
).filter(count__gt=1)

print(f"Found {duplicates.count()} duplicate groups")
```---## 🎯 **Result****Before:**
- ❌ Duplicate lines for same medication
- ❌ Multiple entries for same service
- ❌ Confusing invoices
- ❌ Incorrect totals**After:**
- ✅ One line per service_code per invoice
- ✅ Quantities properly merged
- ✅ Clean, accurate invoices
- ✅ Correct totals automatically calculated---## 🔐 **Security**- ✅ Database-level locking prevents race conditions
- ✅ Transaction-safe operations
- ✅ Soft delete (preserves audit trail)
- ✅ Comprehensive logging---## 📝 **Next Steps**1. **Run Cleanup:**
   ```bash
   python manage.py fix_duplicate_invoice_lines --dry-run
   python manage.py fix_duplicate_invoice_lines
   ```2. **Monitor:**
   - Check for duplicates periodically
   - Review invoices after cleanup
   - Verify totals are correct3. **Update Code:**
   - Use `create_or_merge_invoice_line()` utility
   - Replace direct `InvoiceLine.objects.create()` calls
   - Add duplicate checks before creation---**Status:** ✅ **COMPLETE** - Duplicate prevention implemented at multiple layers with cleanup tools available.
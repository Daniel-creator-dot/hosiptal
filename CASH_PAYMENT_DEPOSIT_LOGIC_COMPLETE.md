# Cash Payment & Deposit Logic - Complete Review & Implementation

## Executive Summary

Comprehensive review and enhancement of cash payment logic to ensure:
1. ✅ Deposits are credited to patient account when received
2. ✅ Deposits are automatically debited when cash invoices are issued
3. ✅ Deposits are NOT applied to insurance/corporate invoices
4. ✅ Proper accounting entries throughout the flow

---

## Complete Flow Diagram

### **Phase 1: Patient Makes Deposit (Before Service)**

```
PATIENT MAKES DEPOSIT
    ↓
PatientDeposit Created
    - deposit_amount: GHS 500
    - available_balance: GHS 500
    - status: 'active'
    ↓
ACCOUNTING ENTRY (Signal: create_accounting_entries_for_deposit)
    Dr. Cash Account (Asset)          GHS 500
    Cr. Patient Deposits (Liability) GHS 500
    ↓
✅ Deposit credited to patient account
✅ Patient.deposit_balance = GHS 500
```

**Key Points:**
- Deposit is a **liability** (money owed to patient until services are provided)
- Cash account increases (asset)
- Patient deposit balance increases
- Available for use when services are charged

---

### **Phase 2: Patient Flow - Services Charged Incrementally**

```
TRIAGE → CONSULTATION → LAB → PHARMACY → DISCHARGE
    ↓         ↓           ↓        ↓          ↓
Service   Service    Service   Service   Invoice
Added     Added      Added     Added     Finalized
    ↓         ↓           ↓        ↓          ↓
Invoice    Invoice    Invoice   Invoice   Status =
Line      Line       Line      Line      'issued'
Created   Created    Created   Created   (Signal fires)
    ↓         ↓           ↓        ↓          ↓
Invoice    Invoice    Invoice   Invoice   Deposits
Totals    Totals     Totals    Totals    Applied
Updated   Updated    Updated   Updated   (if cash)
```

**Incremental Invoice Creation:**
1. **Triage/Registration:**
   - Invoice created with status='draft'
   - Payer = Cash (if no insurance)
   - Invoice line added for registration fee
   - Invoice totals calculated
   - Status remains 'draft'

2. **Consultation:**
   - Same invoice (encounter-based)
   - Invoice line added for consultation
   - Invoice totals recalculated
   - Status remains 'draft'

3. **Lab/Pharmacy:**
   - Same invoice
   - Invoice lines added
   - Invoice totals recalculated
   - Status remains 'draft'

4. **Finalization:**
   - `_finalize_invoice()` called
   - Status changed to 'issued'
   - Invoice totals finalized
   - **Signal fires:** `auto_apply_deposits_to_invoice`

---

### **Phase 3: Deposit Application (When Invoice Issued)**

```
INVOICE STATUS = 'issued' (Cash Invoice)
    ↓
SIGNAL: auto_apply_deposits_to_invoice
    ↓
CHECK PAYER TYPE
    ├─ Cash → Apply Deposits ✅
    └─ Insurance/Corporate → Skip ❌
    ↓
GET PATIENT'S ACTIVE DEPOSITS
    - status='active'
    - available_balance > 0
    - Order by deposit_date (FIFO)
    ↓
APPLY DEPOSITS (Up to invoice balance)
    For each deposit:
        amount_to_apply = min(deposit.available_balance, invoice.balance)
        deposit.apply_to_invoice(invoice, amount_to_apply)
        ↓
        UPDATE DEPOSIT:
            - used_amount += amount_to_apply
            - available_balance -= amount_to_apply
            - status = 'fully_used' if balance = 0
        ↓
        UPDATE INVOICE:
            - balance -= amount_to_apply
            - status = 'paid' if balance = 0
            - status = 'partially_paid' if balance < total
        ↓
        CREATE PaymentReceipt:
            - payment_method = 'deposit'
            - amount_paid = amount_to_apply
        ↓
        ACCOUNTING ENTRY (Signal: create_accounting_entries_for_application)
            Dr. Patient Deposits (Liability)  GHS X
            Cr. Revenue Account (Revenue)       GHS X
    ↓
✅ Deposit debited from patient account
✅ Invoice balance reduced
✅ Revenue recognized
```

**Key Points:**
- Deposits applied **automatically** when cash invoice is issued
- Applied in **FIFO order** (oldest deposits first)
- Applied up to invoice balance or deposit balance (whichever is smaller)
- Multiple deposits can be applied to one invoice
- One deposit can be applied to multiple invoices (if balance remains)

---

## Critical Logic Rules

### **Rule 1: Deposits ONLY Apply to Cash Invoices** ✅

```python
# In signals_patient_deposits.py
if payer_type not in ['cash', None]:
    # Skip deposit application for insurance/corporate
    return
```

**Why:**
- Insurance/corporate invoices are billed to the company
- Patient deposits are for cash payments only
- Prevents incorrect accounting

---

### **Rule 2: Deposits Applied When Invoice Status = 'issued'** ✅

```python
# Signal triggers when:
if instance.status != 'issued':
    return
```

**Why:**
- Draft invoices may have incomplete charges
- Only finalized invoices should have deposits applied
- Ensures accurate balance calculations

---

### **Rule 3: FIFO Deposit Application** ✅

```python
deposits = PatientDeposit.objects.filter(
    ...
).order_by('deposit_date')  # Oldest first
```

**Why:**
- Prevents deposits from expiring unused
- Ensures oldest deposits are used first
- Better cash flow management

---

### **Rule 4: Automatic Balance Updates** ✅

```python
# Deposit balance updated
self.used_amount += amount
self.available_balance -= amount

# Invoice balance updated
invoice.balance -= amount
```

**Why:**
- Real-time balance tracking
- Accurate patient account status
- Prevents over-application

---

## Accounting Entries Summary

### **1. Deposit Received**

```
Dr. Cash Account (Asset)              GHS 500
Cr. Patient Deposits (Liability)      GHS 500
```

**Effect:**
- Cash increases (asset)
- Liability increases (owe patient services)
- No revenue yet (services not provided)

---

### **2. Deposit Applied to Invoice**

```
Dr. Patient Deposits (Liability)      GHS 300
Cr. Revenue Account (Revenue)          GHS 300
```

**Effect:**
- Liability decreases (services provided)
- Revenue increases (services earned)
- Cash already received (no cash movement)

---

### **3. Invoice Payment (If Balance Remains)**

If invoice balance > 0 after deposit application:

```
Dr. Cash Account (Asset)              GHS 200
Cr. Revenue Account (Revenue)         GHS 200
```

**Effect:**
- Additional cash received
- Revenue increases
- Invoice fully paid

---

## Code Implementation

### **1. Deposit Application Signal** (`hospital/signals_patient_deposits.py`)

```python
@receiver(post_save, sender='hospital.Invoice')
def auto_apply_deposits_to_invoice(sender, instance, created, **kwargs):
    """
    Automatically apply patient deposits to invoices when they are issued
    IMPORTANT: Deposits are ONLY applied to CASH invoices
    """
    # Only apply to issued invoices
    if instance.status != 'issued':
        return
    
    # CRITICAL: Only apply to cash invoices
    payer_type = instance.payer.payer_type if hasattr(instance.payer, 'payer_type') else None
    if payer_type not in ['cash', None]:
        return  # Skip insurance/corporate invoices
    
    # Get patient's active deposits (FIFO)
    deposits = PatientDeposit.objects.filter(
        patient=instance.patient,
        status='active',
        available_balance__gt=0
    ).order_by('deposit_date')
    
    # Apply deposits up to invoice balance
    for deposit in deposits:
        if instance.balance <= 0:
            break
        amount_to_apply = min(deposit.available_balance, instance.balance)
        if amount_to_apply > 0:
            deposit.apply_to_invoice(instance, amount_to_apply)
```

---

### **2. Deposit Creation Accounting** (`hospital/signals_patient_deposits.py`)

```python
@receiver(post_save, sender='hospital.PatientDeposit')
def create_accounting_entries_for_deposit(sender, instance, created, **kwargs):
    """
    Create accounting entries when deposit is received
    Dr. Cash, Cr. Patient Deposits (Liability)
    """
    if not created:
        return
    
    # Dr. Cash Account
    # Cr. Patient Deposits Account (Liability)
    # Creates Transaction and Journal Entry
```

---

### **3. Deposit Application Accounting** (`hospital/signals_patient_deposits.py`)

```python
@receiver(post_save, sender='hospital.DepositApplication')
def create_accounting_entries_for_application(sender, instance, created, **kwargs):
    """
    Create accounting entries when deposit is applied
    Dr. Patient Deposits (Liability), Cr. Revenue
    """
    if not created:
        return
    
    # Dr. Patient Deposits Account (Liability decreases)
    # Cr. Revenue Account (Revenue increases)
    # Creates Revenue entry and Journal Entry
```

---

## Patient Flow Integration

### **Incremental Invoice Updates**

During patient flow, services are added incrementally:

1. **Service Added** → Invoice line created
2. **Invoice Totals Calculated** → `invoice.calculate_totals()`
3. **Invoice Saved** → Status may still be 'draft'
4. **Finalization** → `_finalize_invoice()` sets status='issued'
5. **Signal Fires** → Deposits automatically applied

**Key Functions:**
- `add_consultation_charge()` - Adds consultation to invoice
- `AutoBillingService.create_pharmacy_bill()` - Adds pharmacy to invoice
- `AutoBillingService._finalize_invoice()` - Sets status='issued'
- `invoice.calculate_totals()` - Recalculates balance

---

## Testing Scenarios

### **Scenario 1: Deposit Covers Full Invoice**

1. Patient deposits GHS 500
2. Services charged: GHS 300
3. Invoice issued → Deposit applied: GHS 300
4. Result:
   - Invoice balance: GHS 0 (paid)
   - Deposit balance: GHS 200 (remaining)
   - Invoice status: 'paid'

---

### **Scenario 2: Deposit Partially Covers Invoice**

1. Patient deposits GHS 200
2. Services charged: GHS 500
3. Invoice issued → Deposit applied: GHS 200
4. Result:
   - Invoice balance: GHS 300 (remaining)
   - Deposit balance: GHS 0 (fully used)
   - Invoice status: 'partially_paid'
   - Patient pays remaining GHS 300

---

### **Scenario 3: Multiple Deposits Applied**

1. Patient deposits: GHS 100, GHS 200, GHS 150
2. Services charged: GHS 350
3. Invoice issued → Deposits applied (FIFO):
   - Deposit 1: GHS 100
   - Deposit 2: GHS 200
   - Deposit 3: GHS 50 (partial)
4. Result:
   - Invoice balance: GHS 0 (paid)
   - Deposit 1: Fully used
   - Deposit 2: Fully used
   - Deposit 3: GHS 100 remaining

---

### **Scenario 4: Insurance Invoice (No Deposit Application)**

1. Patient deposits GHS 500
2. Patient has insurance
3. Services charged: GHS 300
4. Invoice issued with insurance payer
5. Result:
   - Deposit NOT applied (insurance invoice)
   - Invoice balance: GHS 300 (billed to insurance)
   - Deposit balance: GHS 500 (still available for cash services)

---

## Status: ✅ COMPLETE

All cash payment and deposit logic has been reviewed and enhanced:

1. ✅ Deposits credited when received
2. ✅ Deposits debited when cash invoices issued
3. ✅ Deposits NOT applied to insurance/corporate invoices
4. ✅ Proper accounting entries throughout
5. ✅ FIFO deposit application
6. ✅ Automatic balance updates
7. ✅ Real-time patient account tracking

The system now properly handles:
- Cash payments with deposits
- Incremental service charges during patient flow
- Automatic deposit application
- Proper accounting separation (cash vs insurance/corporate)



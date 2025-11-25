# 🏥 Insurance & Corporate Payments - Complete Guide

## Overview

Your HMS has a **world-class insurance and corporate billing system** that automatically tracks claims, manages payments, and handles monthly submissions to insurance companies.

---

## 🔍 System Architecture

### 1. **Payer Types**

Your system supports 4 types of payers:

```python
PAYER_TYPES = [
    ('nhis', 'NHIS'),                    # National Health Insurance Scheme
    ('private', 'Private Insurance'),     # Private insurance companies
    ('cash', 'Cash'),                    # Direct cash payments
    ('corporate', 'Corporate'),          # Corporate/Company accounts
]
```

---

## 💳 How Insurance Works

### **Step 1: Patient Registration with Insurance**

When a patient registers or visits, they can be linked to an insurance/corporate payer:

```python
# Patient model has insurance fields
patient.primary_insurance = Payer.objects.get(name="XYZ Insurance")
patient.insurance_id = "POL123456"
patient.insurance_member_id = "MEM789"
```

**Key Fields:**
- `primary_insurance` → Links to Payer (Insurance Company)
- `insurance_id` → Policy number
- `insurance_member_id` → Member ID/Card number
- `insurance_group_number` → Group number (for corporate)

---

### **Step 2: Service Pricing by Payer**

Different payers have different prices for the same service:

```python
# PriceBook model - Different prices for different payers
PriceBook:
    - payer: NHIS
    - service_code: "CONS001" (Consultation)
    - unit_price: 50.00 GHS
    
PriceBook:
    - payer: Private Insurance ABC
    - service_code: "CONS001" (Consultation)
    - unit_price: 150.00 GHS
    
PriceBook:
    - payer: Corporate XYZ
    - service_code: "CONS001" (Consultation)
    - unit_price: 120.00 GHS
```

**Benefits:**
- ✅ NHIS pays lower negotiated rates
- ✅ Private insurance pays standard rates
- ✅ Corporate accounts have custom rates
- ✅ Cash patients pay full price

---

### **Step 3: Automatic Claim Creation**

When a service is provided to an insured patient, the system **automatically creates insurance claim items**:

```python
# When invoice is created for insured patient
InsuranceClaimItem.objects.create(
    patient=patient,
    payer=patient.primary_insurance,  # XYZ Insurance
    patient_insurance_id=patient.insurance_id,  # POL123456
    invoice=invoice,
    invoice_line=invoice_line,
    service_code=service_code,  # CONS001
    service_description="Consultation",
    service_date=today,
    billed_amount=150.00,  # Price from PriceBook
    claim_status='pending'
)
```

**Workflow:**
1. Patient visits → Gets consultation
2. System checks: Patient has insurance ✅
3. System creates invoice with insurance payer's prices
4. **Automatically creates InsuranceClaimItem** (claim)
5. Claim starts in 'pending' status

---

### **Step 4: Monthly Claim Aggregation**

Claims are **automatically grouped by month and payer** for bulk submission:

```python
MonthlyInsuranceClaim:
    claim_number: "MCLM20251107120000"
    payer: "XYZ Private Insurance"
    claim_month: 11
    claim_year: 2025
    status: 'draft'
    total_items: 250  # 250 claims this month
    total_billed_amount: 45,000.00 GHS
    total_approved_amount: 0.00
    total_paid_amount: 0.00
```

**Features:**
- ✅ One monthly claim per payer
- ✅ Automatic aggregation of all services
- ✅ Status tracking (draft → submitted → processing → paid)
- ✅ Financial summary

---

## 🔄 Insurance Claims Workflow

### **Full Lifecycle:**

```
┌─────────────────────────────────────────────────────────────┐
│  1. PATIENT VISIT WITH INSURANCE                            │
│     - Patient has active insurance                          │
│     - Service provided (consultation, lab, medication)      │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  2. AUTOMATIC CLAIM CREATION                                │
│     - InsuranceClaimItem created automatically              │
│     - Status: 'pending'                                     │
│     - Linked to invoice and patient                         │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  3. MONTHLY AGGREGATION                                     │
│     - Claims grouped by month + payer                       │
│     - MonthlyInsuranceClaim created                         │
│     - All individual claims linked to monthly claim         │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  4. SUBMISSION TO INSURANCE                                 │
│     - Export monthly claim report                           │
│     - Submit to insurance company                           │
│     - Mark as 'submitted'                                   │
│     - Insurance company reference number recorded           │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  5. INSURANCE PROCESSING                                    │
│     - Insurance reviews claims                              │
│     - Status: 'processing'                                  │
│     - Some approved, some rejected                          │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  6. APPROVAL & PAYMENT                                      │
│     - Approved claims marked 'approved'                     │
│     - Rejected claims marked 'rejected' (with reason)       │
│     - Payment received from insurance                       │
│     - Claims marked 'paid'                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏢 How Corporate Works

Corporate accounts work **exactly like insurance**, but for company employees:

### **Setup:**

```python
# Create Corporate Payer
corporate_payer = Payer.objects.create(
    name="ABC Company Ltd",
    payer_type='corporate'
)

# Create custom pricing for this corporate
PriceBook.objects.create(
    payer=corporate_payer,
    service_code=consultation_code,
    unit_price=120.00  # Negotiated corporate rate
)
```

### **When Employee Visits:**

```python
# Employee patient record
employee = Patient.objects.create(
    first_name="John",
    last_name="Doe",
    primary_insurance=corporate_payer,  # ABC Company
    insurance_id="EMP2025001",  # Employee ID
    insurance_group_number="ABC-GROUP-001"
)
```

**Workflow:**
1. Employee visits hospital
2. Shows employee ID
3. System uses corporate rates from PriceBook
4. Creates claim against corporate account
5. Monthly bill sent to company
6. Company pays in bulk

---

## 📊 Insurance Claim Item Model

```python
InsuranceClaimItem:
    # Patient & Insurance
    patient: Patient
    payer: Payer (Insurance/Corporate)
    patient_insurance_id: "POL123456"
    
    # Service Details
    service_code: ServiceCode
    service_description: "Consultation"
    service_date: 2025-11-07
    
    # Financial
    billed_amount: 150.00 GHS
    approved_amount: 150.00 GHS
    paid_amount: 150.00 GHS
    
    # Status Tracking
    claim_status: 'pending' | 'submitted' | 'processing' | 
                  'approved' | 'paid' | 'rejected'
    claim_reference: "INS-REF-12345"
    
    # Dates
    submitted_date: 2025-11-30
    approved_date: 2025-12-15
    paid_date: 2025-12-20
    
    # Monthly Grouping
    monthly_claim: MonthlyInsuranceClaim
    
    # Rejection
    rejection_reason: "Service not covered"
```

---

## 📅 Monthly Insurance Claim Model

```python
MonthlyInsuranceClaim:
    # Identification
    claim_number: "MCLM20251107120000"
    payer: Payer (Insurance Company)
    
    # Period
    claim_month: 11 (November)
    claim_year: 2025
    
    # Status
    status: 'draft' | 'ready_for_submission' | 'submitted' | 
            'processing' | 'partially_paid' | 'fully_paid'
    
    # Financial Summary
    total_items: 250
    total_billed_amount: 45,000.00 GHS
    total_approved_amount: 43,000.00 GHS
    total_paid_amount: 43,000.00 GHS
    
    # Submission
    submission_date: 2025-11-30
    submission_reference: "INS-SUB-2025-11-001"
    
    # Payment
    payment_date: 2025-12-20
    payment_reference: "PAY-2025-12-001"
```

---

## 🎯 Key Features

### **1. Automatic Claim Generation**
- ✅ Claims created automatically when service is provided
- ✅ No manual data entry required
- ✅ Links to patient, invoice, and service

### **2. Monthly Aggregation**
- ✅ All claims grouped by month and payer
- ✅ Easy bulk submission
- ✅ Financial summaries automatic

### **3. Multi-Status Tracking**
- ✅ Track each claim through lifecycle
- ✅ Pending → Submitted → Processing → Approved → Paid
- ✅ Handle rejections with reasons

### **4. Different Pricing**
- ✅ Each payer can have different prices
- ✅ Negotiated rates for NHIS, Corporate
- ✅ Standard rates for private insurance
- ✅ Full price for cash

### **5. Outstanding Amount Tracking**
- ✅ Real-time tracking of unpaid claims
- ✅ Approved but not paid
- ✅ Submitted but not approved

---

## 🖥️ User Interface

### **Access Points:**

1. **Insurance Dashboard**
   - URL: `/hms/insurance/` or `/hms/claims/`
   - View: All claims, statistics, monthly summaries

2. **Claims List**
   - URL: `/hms/insurance/claims/`
   - Filter by: Status, Payer, Date range
   - Search: Patient name, claim reference

3. **Monthly Claims**
   - URL: `/hms/insurance/monthly-claims/`
   - View aggregated monthly claims
   - Submit to insurance companies

4. **Create Claim from Invoice**
   - URL: `/hms/claims/create/invoice/<invoice_id>/`
   - Manual claim creation (if auto failed)

---

## 📝 Common Workflows

### **Workflow 1: Patient with NHIS**

```python
# 1. Patient Registration
patient = Patient(
    first_name="Kwame",
    primary_insurance=nhis_payer,
    insurance_id="NHIS123456"
)

# 2. Patient visits for consultation
encounter = Encounter.objects.create(
    patient=patient,
    encounter_type='outpatient'
)

# 3. Invoice created (uses NHIS prices from PriceBook)
invoice = Invoice.objects.create(
    patient=patient,
    payer=nhis_payer,  # NHIS
    total_amount=50.00  # NHIS rate (not 150.00 cash rate)
)

# 4. Claim automatically created
claim = InsuranceClaimItem.objects.create(
    patient=patient,
    payer=nhis_payer,
    billed_amount=50.00,
    claim_status='pending'
)

# 5. End of month: Grouped into monthly claim
monthly_claim = MonthlyInsuranceClaim.objects.get(
    payer=nhis_payer,
    claim_month=11,
    claim_year=2025
)
monthly_claim.add_claim_items([claim])

# 6. Submit to NHIS
monthly_claim.mark_as_submitted(
    submission_reference="NHIS-2025-11-001"
)

# 7. NHIS pays
monthly_claim.mark_as_paid(
    payment_reference="NHIS-PAY-2025-12-001"
)
```

---

### **Workflow 2: Corporate Employee**

```python
# 1. Employee visits
employee = Patient(
    first_name="Ama",
    primary_insurance=abc_company,  # Corporate payer
    insurance_id="EMP2025001"
)

# 2. Gets lab test
invoice = Invoice.objects.create(
    patient=employee,
    payer=abc_company,  # Company pays
    total_amount=200.00  # Corporate rate
)

# 3. Claim auto-created
claim = InsuranceClaimItem.objects.create(
    patient=employee,
    payer=abc_company,
    billed_amount=200.00,
    claim_status='pending'
)

# 4. End of month: Send bill to company
monthly_claim = MonthlyInsuranceClaim.objects.get(
    payer=abc_company,
    claim_month=11,
    claim_year=2025
)
# Total: All employees' services for the month

# 5. Company pays in bulk
monthly_claim.mark_as_paid()
```

---

## 💰 Financial Benefits

### **For Hospital:**
1. ✅ **Guaranteed Payments** - Insurance contracts ensure payment
2. ✅ **Bulk Payments** - Receive large monthly payments
3. ✅ **Reduced Bad Debt** - Insurance pays for most services
4. ✅ **Corporate Accounts** - Steady income from company contracts

### **For Patients:**
1. ✅ **Reduced Out-of-Pocket** - Insurance covers costs
2. ✅ **Access to Care** - Don't need cash upfront
3. ✅ **Employer Benefits** - Corporate insurance from job

### **For Insurance Companies:**
1. ✅ **Organized Claims** - Monthly batch submissions
2. ✅ **Clear Documentation** - All services tracked
3. ✅ **Easy Reconciliation** - Detailed reports

---

## 🔍 Reporting & Analytics

Your system can generate:

1. **Claims by Status Report**
   - How many pending, submitted, paid, rejected

2. **Payer Performance Report**
   - Which payers pay fastest
   - Which reject most claims

3. **Outstanding Claims Report**
   - Total money owed by each payer
   - Aging analysis (30, 60, 90 days)

4. **Monthly Summary**
   - Total claims per month
   - Total revenue from insurance vs cash

---

## 🎯 Key Advantages of Your System

### **1. Automation**
- ❌ **Old Way:** Manual claim forms, Excel sheets
- ✅ **Your Way:** Automatic claim creation when service provided

### **2. Integration**
- ❌ **Old Way:** Separate billing and claims systems
- ✅ **Your Way:** Claims linked to invoices, patients, services

### **3. Tracking**
- ❌ **Old Way:** Hard to track claim status
- ✅ **Your Way:** Real-time status tracking

### **4. Reporting**
- ❌ **Old Way:** Manual reports, time-consuming
- ✅ **Your Way:** Automatic monthly summaries

### **5. Multi-Payer Support**
- ✅ NHIS (government insurance)
- ✅ Private insurance companies
- ✅ Corporate accounts
- ✅ Cash patients

---

## 📚 Summary

Your HMS has a **complete insurance and corporate billing system**:

### **Insurance Flow:**
```
Patient Visit → Auto Claim Creation → Monthly Aggregation 
→ Submit to Insurance → Approval → Payment Received
```

### **Corporate Flow:**
```
Employee Visit → Auto Claim Creation → Monthly Bill 
→ Send to Company → Company Bulk Payment
```

### **Key Models:**
- `Payer` - Insurance companies / Corporate accounts
- `PriceBook` - Different prices for different payers
- `InsuranceClaimItem` - Individual claim for each service
- `MonthlyInsuranceClaim` - Aggregated monthly claims

### **Key Features:**
- ✅ Automatic claim creation
- ✅ Monthly aggregation
- ✅ Multi-payer support
- ✅ Different pricing per payer
- ✅ Status tracking
- ✅ Financial reporting

**Your system handles everything from patient registration to insurance payment automatically!** 🎉

---

*For more details, check the code in:*
- `hospital/models.py` - Payer, PriceBook, Invoice models
- `hospital/models_insurance.py` - InsuranceClaimItem, MonthlyInsuranceClaim
- `hospital/views_insurance.py` - Claims management views

























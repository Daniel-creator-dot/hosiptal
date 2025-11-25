# 🏥 Insurance vs Corporate - Quick Reference

## 🆚 Side-by-Side Comparison

| Feature | Insurance (NHIS/Private) | Corporate Account |
|---------|-------------------------|-------------------|
| **Who Pays?** | Insurance Company | Employer/Company |
| **Who Benefits?** | Individual patients | Company employees |
| **Pricing** | Negotiated rates (NHIS lower) | Custom corporate rates |
| **ID Required** | Insurance card/Policy # | Employee ID |
| **Payment Frequency** | Monthly bulk payment | Monthly corporate invoice |
| **Claim Process** | Submit to insurance company | Submit to company finance dept |
| **Approval Needed?** | Yes (insurance reviews) | Sometimes (company pre-approval) |
| **Rejection Rate** | Higher (coverage limits) | Lower (pre-negotiated) |

---

## 📋 Example Scenarios

### Scenario 1: NHIS Patient

```
👤 Patient: Kwame Mensah
💳 Insurance: NHIS (National Health Insurance)
📋 Service: General Consultation
💰 Standard Price: 150 GHS
💰 NHIS Price: 50 GHS ✅

Flow:
1. Kwame shows NHIS card
2. System uses NHIS pricing (50 GHS)
3. Claim auto-created
4. Grouped with other NHIS claims for the month
5. Submitted to NHIS at month end
6. NHIS pays hospital in bulk
7. Kwame pays nothing or small co-pay
```

---

### Scenario 2: Private Insurance Patient

```
👤 Patient: Ama Osei
💳 Insurance: Prudential Insurance
📋 Service: Lab Test (FBC)
💰 Standard Price: 80 GHS
💰 Prudential Price: 80 GHS (full rate)
💰 Patient Co-pay: 20% = 16 GHS

Flow:
1. Ama shows Prudential insurance card
2. System uses Prudential pricing (80 GHS)
3. Patient pays 16 GHS co-pay (20%)
4. Claim created for 64 GHS (80%)
5. Submitted to Prudential monthly
6. Prudential pays 64 GHS
```

---

### Scenario 3: Corporate Employee

```
👤 Patient: Kofi Asante
🏢 Employer: ABC Company Ltd
📋 Service: Full Medical Checkup
💰 Standard Price: 500 GHS
💰 Corporate Price: 400 GHS (negotiated)

Flow:
1. Kofi shows ABC Company employee ID
2. System uses corporate rate (400 GHS)
3. Claim auto-created
4. Grouped with other ABC employees' services
5. Monthly bill sent to ABC Company
6. Company finance pays 400 GHS
7. Kofi pays nothing (benefit)
```

---

### Scenario 4: Cash Patient

```
👤 Patient: Yaw Boateng
💳 Insurance: None
📋 Service: Consultation + Medication
💰 Standard Price: 200 GHS

Flow:
1. Yaw has no insurance
2. System uses full standard prices
3. Yaw pays 200 GHS immediately
4. No claim created
5. Transaction complete
```

---

## 🏢 Corporate Account Setup

### Step 1: Create Corporate Payer
```python
abc_company = Payer.objects.create(
    name="ABC Company Ltd",
    payer_type='corporate',
    is_active=True
)
```

### Step 2: Set Corporate Pricing
```python
# Consultation
PriceBook.objects.create(
    payer=abc_company,
    service_code=consultation_code,
    unit_price=120.00  # Instead of 150.00 standard
)

# Lab Tests
PriceBook.objects.create(
    payer=abc_company,
    service_code=fbc_code,
    unit_price=60.00  # Instead of 80.00 standard
)
```

### Step 3: Register Employees
```python
employee = Patient.objects.create(
    first_name="Kofi",
    last_name="Asante",
    primary_insurance=abc_company,
    insurance_id="EMP2025001",  # Employee ID
    insurance_group_number="ABC-GROUP-001"
)
```

### Step 4: Monthly Billing
```
End of Month:
- System generates MonthlyInsuranceClaim
- Total: All employees' services
- Invoice sent to ABC Company
- Company pays in bulk (e.g., 50,000 GHS for 25 employees)
```

---

## 💡 Real-World Examples

### Example 1: NHIS Maternity Package

```
Service Package: Antenatal + Delivery
NHIS Coverage: 90% covered
Patient Co-pay: 10%

Standard Price: 2,000 GHS
NHIS Price: 500 GHS (negotiated)
NHIS Pays: 450 GHS (90%)
Patient Pays: 50 GHS (10%)

Monthly Claim:
- 100 maternity cases
- Hospital bills NHIS: 45,000 GHS
- Patients paid: 5,000 GHS
- Total collected: 50,000 GHS
```

---

### Example 2: Bank Corporate Account

```
Bank XYZ - 200 employees
Corporate Rate: 20% discount on all services
Monthly Average: 250,000 GHS

November 2025:
- 50 consultations @ 120 GHS = 6,000 GHS
- 30 lab tests @ 64 GHS = 1,920 GHS
- 20 medications @ avg 150 GHS = 3,000 GHS
- 5 admissions @ 5,000 GHS = 25,000 GHS
TOTAL: 35,920 GHS

Invoice sent to Bank XYZ
Payment received in 30 days
```

---

### Example 3: Mixed Payment

```
Patient: Ama (has NHIS + works for Corporate)
Service: Surgery (10,000 GHS standard)

Option 1: Use NHIS
- NHIS covers: 3,000 GHS
- Patient pays: 7,000 GHS

Option 2: Use Corporate Insurance
- Corporate covers: 8,000 GHS
- Patient pays: 2,000 GHS ✅ Better!

System allows: Choose best coverage for patient
```

---

## 📊 Monthly Claim Summary Example

### NHIS Monthly Claim - November 2025

```
Claim Number: MCLM20251130001
Payer: National Health Insurance Scheme
Period: November 2025

Services Provided:
┌─────────────────────┬─────────┬──────────┬─────────────┐
│ Service Type        │ Count   │ Standard │ NHIS Price  │
├─────────────────────┼─────────┼──────────┼─────────────┤
│ Consultations       │ 450     │ 67,500   │ 22,500      │
│ Lab Tests           │ 300     │ 24,000   │ 15,000      │
│ Medications         │ 250     │ 37,500   │ 25,000      │
│ Admissions          │ 20      │ 100,000  │ 60,000      │
│ Surgeries           │ 5       │ 50,000   │ 30,000      │
└─────────────────────┴─────────┴──────────┴─────────────┘

TOTALS:
- Total Services: 1,025
- Standard Value: 279,000 GHS
- NHIS Rates: 152,500 GHS (45% discount)
- Submitted: November 30, 2025
- Expected Payment: December 20, 2025
```

---

### Corporate Monthly Bill - ABC Company

```
Invoice Number: INV20251130ABC
Company: ABC Company Ltd
Period: November 2025
Employees: 45

Services by Employee:
┌──────────────┬─────────────────────┬──────────┐
│ Employee ID  │ Services            │ Amount   │
├──────────────┼─────────────────────┼──────────┤
│ EMP001       │ Consultation + Lab  │ 180 GHS  │
│ EMP002       │ Medication          │ 80 GHS   │
│ EMP003       │ Full Checkup        │ 400 GHS  │
│ ...          │ ...                 │ ...      │
│ EMP045       │ Consultation        │ 120 GHS  │
└──────────────┴─────────────────────┴──────────┘

TOTALS:
- Total Employees Served: 45
- Total Services: 78
- Standard Value: 28,000 GHS
- Corporate Rates: 22,400 GHS (20% discount)
- Payment Terms: Net 30 days
- Due Date: December 30, 2025
```

---

## 🎯 Key Differences Summary

### Insurance (NHIS/Private):
- ✅ **Patient-focused** - Individual coverage
- ✅ **Coverage limits** - Some services not covered
- ✅ **Claim approval** - Insurance reviews each claim
- ✅ **Varied prices** - NHIS cheaper, private standard
- ✅ **Patient co-pay** - Patient pays percentage
- ⚠️ **Rejection risk** - Claims can be rejected

### Corporate:
- ✅ **Employee benefit** - Company provides coverage
- ✅ **Pre-negotiated** - All services pre-approved
- ✅ **Bulk billing** - One bill for all employees
- ✅ **Custom rates** - Negotiated discount (usually 10-30%)
- ✅ **Zero co-pay** - Employees pay nothing (usually)
- ✅ **Faster payment** - Companies pay reliably

---

## 🚀 Quick Access

### URLs:
- **Insurance Claims:** `http://127.0.0.1:8000/hms/claims/`
- **Monthly Claims:** `http://127.0.0.1:8000/hms/insurance/monthly-claims/`
- **Payer Management:** `http://127.0.0.1:8000/admin/hospital/payer/`
- **Price Books:** `http://127.0.0.1:8000/admin/hospital/pricebook/`

### Admin Access:
- **Create Payer:** Admin → Hospital → Payers → Add
- **Set Pricing:** Admin → Hospital → Price Books → Add
- **View Claims:** Admin → Hospital → Insurance Claim Items

---

## 📝 Best Practices

### For Insurance:
1. ✅ Always verify insurance status before service
2. ✅ Check coverage limits
3. ✅ Get pre-approval for expensive services
4. ✅ Submit claims monthly
5. ✅ Follow up on rejections

### For Corporate:
1. ✅ Maintain employee list with company
2. ✅ Verify employment status
3. ✅ Set spending limits per employee
4. ✅ Send detailed monthly reports
5. ✅ Invoice promptly

---

## 💰 Revenue Impact

### Example Hospital Monthly Revenue:

```
November 2025 Revenue Breakdown:

NHIS Claims:        152,500 GHS  (45% of services)
Private Insurance:   85,000 GHS  (25% of services)
Corporate Accounts:  67,200 GHS  (20% of services)
Cash Patients:       33,600 GHS  (10% of services)
─────────────────────────────────────────────────
TOTAL:              338,300 GHS

Insurance/Corporate: 90% of revenue ✅
Cash: Only 10% of revenue
```

**Benefit:** Hospital doesn't rely on cash payments!

---

*For complete details, see: `INSURANCE_AND_CORPORATE_GUIDE.md`*

























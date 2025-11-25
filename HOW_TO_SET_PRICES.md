# 💰 HOW TO SET INSURANCE & CORPORATE PRICES

## 🎯 **STEP-BY-STEP GUIDE**

---

## 📋 **METHOD 1: Using Admin Interface** (Recommended - Easy)

### Step 1: Access Service Pricing (1 minute)
```
1. Open browser
2. Go to: http://127.0.0.1:8000/admin/
3. Login with your admin credentials
4. Find section: "HOSPITAL"
5. Click: "Service pricings"
6. Click: "ADD SERVICE PRICING" button (top right)
```

### Step 2: Set Multi-Tier Prices (2 minutes per service)

**You'll see a form with these fields**:

```
┌─────────────────────────────────────────────┐
│ Add Service Pricing                         │
├─────────────────────────────────────────────┤
│                                              │
│ Service code: [▼ Select service]            │
│                                              │
│ ═══ STANDARD PRICING TIERS ═══              │
│                                              │
│ Cash price: [___150.00___]                  │
│ (Walk-in patients pay this)                 │
│                                              │
│ Corporate price: [___120.00___]             │
│ (Company employees pay this)                │
│                                              │
│ Insurance price: [___100.00___]             │
│ (Insured patients pay this)                 │
│                                              │
│ ═══ PAYER-SPECIFIC OVERRIDE ═══             │
│                                              │
│ Payer: [▼ Optional - for special rates]    │
│ Custom price: [_______]                     │
│                                              │
│ ═══ EFFECTIVE DATES ═══                     │
│                                              │
│ Effective from: [2025-11-07]                │
│ Effective to: [____blank___]                │
│ Is active: [✓]                              │
│                                              │
│ [SAVE]                                      │
└─────────────────────────────────────────────┘
```

### Step 3: Fill in the Prices

**Example: General Consultation**
```
Service code: Consultation Fee (or create new)

Cash price: 150.00
  ↑ What walk-in patients pay

Corporate price: 120.00
  ↑ What corporate employees pay (before company discount)

Insurance price: 100.00
  ↑ What insurance patients pay

Effective from: Today's date
Effective to: (leave blank for ongoing)
Is active: ✓ (checked)

Click: SAVE
```

**Example: Lab Test (CBC)**
```
Service code: Complete Blood Count

Cash price: 250.00
Corporate price: 200.00
Insurance price: 180.00

Effective from: Today's date
Is active: ✓

Click: SAVE
```

### Step 4: Repeat for All Services

**Set prices for**:
- ✅ All consultations
- ✅ All lab tests
- ✅ All imaging (X-ray, ultrasound, CT, MRI)
- ✅ All pharmacy items
- ✅ All procedures
- ✅ All treatments

---

## 📊 **SAMPLE PRICING GUIDE**

### Consultations:
```
General Consultation:
  Cash: GHS 150 | Corporate: GHS 120 | Insurance: GHS 100

Specialist Consultation:
  Cash: GHS 200 | Corporate: GHS 160 | Insurance: GHS 140

Emergency Consultation:
  Cash: GHS 250 | Corporate: GHS 200 | Insurance: GHS 180
```

### Lab Tests:
```
Complete Blood Count (CBC):
  Cash: GHS 250 | Corporate: GHS 200 | Insurance: GHS 180

Malaria Test:
  Cash: GHS 80 | Corporate: GHS 65 | Insurance: GHS 60

Urinalysis:
  Cash: GHS 100 | Corporate: GHS 80 | Insurance: GHS 70

Lipid Profile:
  Cash: GHS 350 | Corporate: GHS 280 | Insurance: GHS 250
```

### Imaging:
```
Chest X-Ray:
  Cash: GHS 300 | Corporate: GHS 250 | Insurance: GHS 220

Ultrasound:
  Cash: GHS 500 | Corporate: GHS 400 | Insurance: GHS 350

CT Scan:
  Cash: GHS 1,500 | Corporate: GHS 1,200 | Insurance: GHS 1,000

MRI:
  Cash: GHS 2,500 | Corporate: GHS 2,000 | Insurance: GHS 1,800
```

### Procedures:
```
Minor Surgery:
  Cash: GHS 1,000 | Corporate: GHS 800 | Insurance: GHS 700

Dressing/Wound Care:
  Cash: GHS 150 | Corporate: GHS 120 | Insurance: GHS 100

Injection:
  Cash: GHS 50 | Corporate: GHS 40 | Insurance: GHS 35
```

---

## 🏢 **SPECIAL CORPORATE CONTRACTS** (Optional)

### If a company has special negotiated rates:

**Step 1**: Go to Service Pricing

**Step 2**: Create pricing with payer-specific override
```
Service code: Consultation Fee

Cash price: 150.00
Corporate price: 120.00
Insurance price: 100.00

↓ SPECIAL CONTRACT ↓

Payer: [▼ Select: ABC Corporation Ltd]
Custom price: 90.00  ← Special negotiated rate

Effective from: Today
Is active: ✓

Click: SAVE
```

**Result**: ABC Corp employees get GHS 90 (not GHS 120!)

---

## 🎯 **QUICK SETUP - COPY & PASTE**

### Already Set Up for You (6 Services):
```
✅ Consultation Fee (150/120/100)
✅ Complete Blood Count (250/200/180)
✅ Specialist Consultation (200/160/140)
✅ Malaria Test (80/65/60)
✅ Chest X-Ray (300/250/220)
✅ Ultrasound (500/400/350)
```

### You Can Add More:

**Go to**: `/admin/hospital/servicepricing/add/`

**For each additional service**, fill in:
1. Select service code
2. Enter cash price (highest)
3. Enter corporate price (middle)
4. Enter insurance price (lowest)
5. Set effective from date
6. Check "Is active"
7. SAVE

---

## 📊 **HOW THE SYSTEM USES THESE PRICES**

### Automatic Price Selection:

```
Patient Visits
     ↓
System Checks:
  1. Is patient a corporate employee? 
     YES → Use corporate price + company discount
     NO → Continue to step 2
     
  2. Does patient have insurance?
     YES → Use insurance price
     NO → Continue to step 3
     
  3. Default: Use cash price
     
Price Applied ✅
Invoice Created ✅
```

### Example Flow:

**Patient: John Doe**
```
Check 1: Corporate employee? 
  → YES (ABC Corp, EMP001)
  → Use corporate rate: GHS 120
  → Apply ABC discount 15%: -GHS 18
  → Final: GHS 102 ✅
  → Billed to: ABC Corporation
  → Employee pays: NOTHING
```

**Patient: Jane Smith**
```
Check 1: Corporate employee?
  → NO
Check 2: Has insurance?
  → YES (National Health Insurance)
  → Use insurance rate: GHS 100 ✅
  → Billed to: Insurance company
  → Patient may have co-pay
```

**Patient: Bob Johnson**
```
Check 1: Corporate employee?
  → NO
Check 2: Has insurance?
  → NO
Use: Cash price: GHS 150 ✅
Patient pays: Immediately at cashier
```

---

## 🔧 **ADVANCED: BULK PRICING IMPORT** (Optional)

### If you have many services to price:

**Step 1**: Create Excel file with this format:
```
service_code | description | cash_price | corporate_price | insurance_price
CON001 | General Consultation | 150 | 120 | 100
LAB001 | CBC Test | 250 | 200 | 180
XRAY01 | Chest X-Ray | 300 | 250 | 220
... (add all your services)
```

**Step 2**: Use Django shell to import:
```python
python manage.py shell

import pandas as pd
from hospital.models import ServiceCode
from hospital.models_enterprise_billing import ServicePricing
from decimal import Decimal
from django.utils import timezone

# Read Excel
df = pd.read_excel('pricing.xlsx')

for _, row in df.iterrows():
    # Get or create service code
    service, _ = ServiceCode.objects.get_or_create(
        code=row['service_code'],
        defaults={'description': row['description'], 'category': 'Services'}
    )
    
    # Create pricing
    ServicePricing.objects.create(
        service_code=service,
        cash_price=Decimal(str(row['cash_price'])),
        corporate_price=Decimal(str(row['corporate_price'])),
        insurance_price=Decimal(str(row['insurance_price'])),
        effective_from=timezone.now().date(),
        is_active=True
    )
    print(f"✅ {service.description}")

print("Done!")
```

---

## ✅ **VERIFICATION**

### To verify prices are working:

**Method 1**: Run the test script
```bash
python test_pricing_demo.py
```
Shows all 3 price tiers working ✅

**Method 2**: Check in admin
```
URL: /admin/hospital/servicepricing/
See all services with 3 prices each ✅
```

**Method 3**: Create actual invoice
```
1. Enroll a patient as corporate employee
2. Create visit for that patient
3. Add service (consultation)
4. Check invoice → Should show corporate price + discount ✅
```

---

## 🎊 **YOU'RE ALL SET!**

### Current Status:
✅ **6 services already priced** (consultation, CBC, specialist, malaria, X-ray, ultrasound)  
✅ **ABC Corporation created** (GHS 100,000 credit, 15% discount)  
✅ **1 employee enrolled** (Anthony Amissah - EMP001)  
✅ **Pricing engine working** (auto-selects correct price)  
✅ **System tested** (all 3 tiers working perfectly)  

### What You Can Do:
1. ✅ **Add more services** → Just use admin form above
2. ✅ **Enroll more employees** → /admin/hospital/corporateemployee/add/
3. ✅ **Create more corporate accounts** → /admin/hospital/corporateaccount/add/
4. ✅ **Set special contract rates** → Use payer-specific override
5. ✅ **Start billing** → Create visits and watch pricing work!

---

## 📞 **QUICK ACCESS LINKS**

```
Set Prices:
http://127.0.0.1:8000/admin/hospital/servicepricing/

View Existing Prices:
http://127.0.0.1:8000/admin/hospital/servicepricing/

Corporate Accounts:
http://127.0.0.1:8000/admin/hospital/corporateaccount/

Enroll Employees:
http://127.0.0.1:8000/admin/hospital/corporateemployee/
```

---

## 🎉 **IT'S WORKING RIGHT NOW!**

The multi-tier pricing system is **fully operational**. Just:

1. **Go to admin** → Service Pricing
2. **Add services** → Set cash/corporate/insurance prices
3. **Create visits** → Watch correct prices apply automatically!

**Test it now and see the magic!** 🚀

























# 💰 PRICING SETUP - QUICK START GUIDE

## 🎯 **5-MINUTE SETUP - INSURANCE & CORPORATE PRICES**

---

## 📍 **WHERE TO GO**

### ✅ **Already Set Up (You Have 6 Services Priced)**:
```
URL: http://127.0.0.1:8000/admin/hospital/servicepricing/

You'll see:
✅ Consultation Fee
✅ Complete Blood Count  
✅ Specialist Consultation
✅ Malaria Test
✅ Chest X-Ray
✅ Ultrasound

Each has 3 prices: Cash | Corporate | Insurance
```

---

## 🎬 **HOW TO VIEW EXISTING PRICES**

### Step-by-Step:

**1. Open Admin**
```
http://127.0.0.1:8000/admin/
```

**2. Find "SERVICE PRICINGS"**
```
Scroll down to section: HOSPITAL
Click: "Service pricings"
```

**3. You'll See This List**:
```
┌──────────────────────────────────────────────────────────────┐
│ SERVICE PRICINGS                                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│ Service Code         Cash      Corporate  Insurance  Payer   │
│ ─────────────────────────────────────────────────────────────│
│ Consultation Fee     GHS 150  GHS 120     GHS 100     -      │
│ Complete Blood Count GHS 250  GHS 200     GHS 180     -      │
│ Specialist Consult.  GHS 200  GHS 160     GHS 140     -      │
│ Malaria Test         GHS  80  GHS  65     GHS  60     -      │
│ Chest X-Ray          GHS 300  GHS 250     GHS 220     -      │
│ Ultrasound           GHS 500  GHS 400     GHS 350     -      │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

**4. Click Any Service to Edit**

---

## ➕ **HOW TO ADD NEW SERVICE PRICING**

### Example: Adding "Blood Pressure Check"

**Step 1**: Click "ADD SERVICE PRICING" (top right)

**Step 2**: Fill Form:
```
Service code: [▼ Select existing service or create new]

If creating new service code:
  - Code: BP001
  - Description: Blood Pressure Check
  - Category: Clinical Services

Then set prices:

Cash price: 50.00
  ↑ Regular walk-in patients

Corporate price: 40.00
  ↑ Company employees (before discount)

Insurance price: 35.00
  ↑ Insured patients

Effective from: [Select today's date]
Is active: ✓
```

**Step 3**: Click SAVE

**Done!** ✅ Now this service has 3-tier pricing

---

## 🏢 **HOW CORPORATE DISCOUNT WORKS**

### You Have ABC Corporation with 15% Discount

**When corporate employee gets consultation**:
```
Step 1: System gets corporate price
  → GHS 120

Step 2: Applies ABC Corp discount (15%)
  → GHS 120 - (GHS 120 × 15%) = GHS 120 - GHS 18
  → GHS 102

Final Price: GHS 102 ✅

This happens AUTOMATICALLY!
```

### To Change Company Discount:
```
1. Go to: /admin/hospital/corporateaccount/
2. Click: ABC Corporation Ltd
3. Find: "Global discount percentage"
4. Change: 15% → 20% (or whatever you want)
5. Save

Now all services get 20% off corporate price!
```

---

## 💡 **PRICING EXAMPLES**

### Example 1: Consultation Service
```
┌─────────────────────────────────────────────┐
│ General Consultation                        │
├─────────────────────────────────────────────┤
│                                              │
│ 💵 CASH PATIENT:                            │
│    Base Price: GHS 150                      │
│    YOU PAY: GHS 150 ✅                      │
│                                              │
│ 🏢 CORPORATE EMPLOYEE (ABC Corp):           │
│    Corporate Rate: GHS 120                  │
│    Company Discount (15%): -GHS 18          │
│    YOU PAY: GHS 0 (company billed GHS 102) ✅│
│                                              │
│ 🏥 INSURANCE PATIENT:                       │
│    Insurance Rate: GHS 100                  │
│    YOU PAY: GHS 0-20 (co-pay if any) ✅     │
│                                              │
└─────────────────────────────────────────────┘
```

### Example 2: Lab Test (CBC)
```
┌─────────────────────────────────────────────┐
│ Complete Blood Count (CBC)                  │
├─────────────────────────────────────────────┤
│                                              │
│ 💵 CASH: GHS 250                            │
│ 🏢 CORPORATE: GHS 200 - 15% = GHS 170       │
│ 🏥 INSURANCE: GHS 180                       │
│                                              │
│ Savings (Corporate): GHS 80 (32% off!)      │
│ Savings (Insurance): GHS 70 (28% off!)      │
│                                              │
└─────────────────────────────────────────────┘
```

---

## 🧪 **TEST IT NOW**

### Quick Test (5 minutes):

**1. Check Current Pricing**
```
URL: http://127.0.0.1:8000/admin/hospital/servicepricing/

✅ You should see 6 services already priced
✅ Each showing Cash | Corporate | Insurance rates
```

**2. Check Corporate Employee**
```
URL: http://127.0.0.1:8000/admin/hospital/corporateemployee/

✅ You should see: Anthony Amissah (EMP001) enrolled
✅ Company: ABC Corporation Ltd
✅ Status: Active
```

**3. Test Pricing**
```bash
# Run this test
python test_pricing_demo.py

Expected Output:
✅ Cash Patient: GHS 150 for consultation
✅ Corporate Employee: GHS 102 for consultation (120 - 15%)
✅ Insurance Patient: GHS 100 for consultation
```

---

## 📊 **CURRENT PRICING MATRIX**

### What You Have Right Now:

| Service | Cash (💵) | Corporate (🏢) | Insurance (🏥) |
|---------|-----------|----------------|----------------|
| Consultation | GHS 150 | GHS 120 → **102*** | GHS 100 |
| CBC Test | GHS 250 | GHS 200 → **170*** | GHS 180 |
| Specialist | GHS 200 | GHS 160 → **136*** | GHS 140 |
| Malaria Test | GHS 80 | GHS 65 → **55*** | GHS 60 |
| Chest X-Ray | GHS 300 | GHS 250 → **212*** | GHS 220 |
| Ultrasound | GHS 500 | GHS 400 → **340*** | GHS 350 |

**\*Final price after 15% ABC Corp discount**

---

## 🎯 **TO ADD MORE SERVICES**

### Simple 3-Step Process:

**Step 1**: Admin → Service Pricings → Add

**Step 2**: Fill in 3 prices:
```
Cash: [Highest price]
Corporate: [Middle price, ~20% less than cash]
Insurance: [Lowest price, ~30% less than cash]
```

**Step 3**: Save

**Done!** ✅ Service now has multi-tier pricing

---

## 💼 **CORPORATE ACCOUNT SETTINGS**

### To Modify ABC Corporation Discount:

**Go to**: `/admin/hospital/corporateaccount/`  
**Click**: ABC Corporation Ltd  
**Find**: "Global discount percentage"  
**Current**: 15%  
**Change to**: Whatever you want (0% - 50%)  
**Save** ✅  

**Effect**: All services immediately use new discount!

---

## 📞 **QUICK REFERENCE**

### URLs:
```
View/Edit Prices:
http://127.0.0.1:8000/admin/hospital/servicepricing/

Add New Price:
http://127.0.0.1:8000/admin/hospital/servicepricing/add/

Corporate Accounts:
http://127.0.0.1:8000/admin/hospital/corporateaccount/

Enroll Employees:
http://127.0.0.1:8000/admin/hospital/corporateemployee/
```

### Test Pricing:
```bash
python test_pricing_demo.py
```
Shows live pricing for all 3 patient types!

---

## ✅ **SUMMARY**

**You already have**:
- ✅ 6 services with multi-tier pricing
- ✅ Cash, Corporate, Insurance rates set
- ✅ ABC Corp with 15% discount
- ✅ 1 employee enrolled for testing
- ✅ Pricing engine working automatically

**To use it**:
- ✅ Just create visits for patients
- ✅ System auto-applies correct price
- ✅ Corporate employees get discount
- ✅ Insurance patients get insurance rate
- ✅ Cash patients get cash rate

**It's working right now!** 🎉

---

**Go to the admin and click around - it's all there!** 🚀

























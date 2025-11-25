# 🚀 Lab System Quick Start Guide

## ⚡ **Get Started in 5 Minutes!**

### **Step 1: Run Migrations** (2 minutes)

```bash
cd C:\Users\user\chm
python manage.py makemigrations hospital
python manage.py migrate
```

### **Step 2: Load Initial Data** (1 minute)

```bash
python setup_lab_system.py
```

This creates:
- ✅ 5 Lab Categories (Chemistry, Hematology, etc.)
- ✅ 6 Specimen Types (Blood, Urine, etc.)
- ✅ 20+ Common Tests
- ✅ 1 Test Panel (Lipid Profile)

### **Step 3: Access the System** (30 seconds)

Open browser and go to:
```
http://127.0.0.1:8000/hms/lab/
```

### **Step 4: Try It Out!** (2 minutes)

#### **A. Create a Lab Requisition**
1. Go to: http://127.0.0.1:8000/hms/lab/requisition/create/?patient=<patient_id>
2. Select tests or panels
3. Add clinical indication
4. Submit

#### **B. Collect a Specimen**
1. Go to: http://127.0.0.1:8000/hms/lab/specimen/collect/
2. Select patient and order
3. Choose specimen type
4. Record collection
5. Get accession number: `ACC-20251104-0001`

#### **C. Process a Test**
1. Go to: http://127.0.0.1:8000/hms/lab/result/<result_id>/process/
2. Enter result value
3. Check reference range
4. Flag if abnormal
5. Verify and save

---

## 🎯 **Key Features You Can Use Right Now**

### ✅ **Specimen Tracking**
- Auto-generated accession numbers
- Quality checks (hemolysis, volume, etc.)
- Rejection with reasons
- Storage tracking

### ✅ **Test Management**
- Individual tests and panels
- Pricing and discounts
- TAT tracking
- Fasting requirements

### ✅ **Quality Control**
- Equipment tracking
- QC test recording
- Pass/Fail status
- Calibration schedules

### ✅ **Results Management**
- Reference ranges
- Critical value alerts
- SMS notifications
- Result verification

### ✅ **Inventory**
- Reagent tracking
- Expiry monitoring
- Stock alerts
- Cost tracking

---

## 📊 **System Overview**

```
Lab Workflow:
┌─────────────────┐
│ Doctor Orders   │ → Lab Requisition Created
│ Lab Tests       │
└─────────────────┘
        ↓
┌─────────────────┐
│ Specimen        │ → Accession Number Generated
│ Collected       │
└─────────────────┘
        ↓
┌─────────────────┐
│ Lab Receives    │ → Quality Check → Accept/Reject
│ Specimen        │
└─────────────────┘
        ↓
┌─────────────────┐
│ Tech Processes  │ → Results Entered
│ Test            │
└─────────────────┘
        ↓
┌─────────────────┐
│ Results         │ → Check Reference Range
│ Verified        │    → Flag Abnormals
└─────────────────┘    → Send Critical Alerts
        ↓
┌─────────────────┐
│ Clinician       │ → Interpret Results
│ Reviews         │    → Make Decisions
└─────────────────┘
```

---

## 🔗 **Important URLs**

| Function | URL |
|----------|-----|
| **Lab Dashboard** | `/hms/lab/` |
| **Collect Specimen** | `/hms/lab/specimen/collect/` |
| **All Specimens** | `/hms/lab/specimens/` |
| **Create Requisition** | `/hms/lab/requisition/create/` |
| **QC Dashboard** | `/hms/lab/qc/` |
| **Equipment** | `/hms/lab/equipment/` |
| **Reagents** | `/hms/lab/reagents/` |
| **Django Admin** | `/admin/` |

---

## 🛠️ **Quick Admin Setup**

### **Add Reference Ranges**

1. Go to: `http://127.0.0.1:8000/admin/`
2. Navigate to: `Hospital → Reference Ranges`
3. Click "Add Reference Range"
4. Fill in:
   - Test: Select test
   - Gender: Both/Male/Female
   - Age: Min and Max years
   - Low Value: Lower limit
   - High Value: Upper limit
   - Units: mg/dL, mmol/L, etc.
   - Critical Low: Panic low value
   - Critical High: Panic high value
5. Save

**Example: Glucose Reference Range**
```
Test: Glucose (Fasting)
Gender: Both
Age Min: 18
Age Max: 65
Low Value: 70
High Value: 100
Units: mg/dL
Critical Low: 40
Critical High: 500
```

### **Add Lab Equipment**

1. Go to: `Hospital → Lab Equipment`
2. Click "Add Lab Equipment"
3. Fill in:
   - Name: "Hematology Analyzer"
   - Equipment ID: "HEMA-001"
   - Category: "Analyzer"
   - Manufacturer: "Sysmex"
   - Model: "XN-1000"
   - Serial Number: "ABC123456"
   - Location: "Main Lab"
   - Status: "Operational"
   - Next Calibration: 30 days from now
   - Next Maintenance: 90 days from now
4. Save

---

## 💡 **Pro Tips**

### **1. Test Ordering**
- Use **panels** instead of individual tests for common combinations
- Save 20-30% with panel pricing
- Faster ordering for staff

### **2. Specimen Collection**
- Always use correct tube types
- Label BEFORE collection
- Print accession labels immediately
- Transport within time limits

### **3. Quality Control**
- Run QC BEFORE patient samples
- Document all failures
- Take corrective actions
- Never release results if QC failed

### **4. Critical Values**
- System auto-detects based on reference ranges
- Sends SMS to ordering doctor
- Document phone notification
- Ensure timely action

### **5. Inventory Management**
- Check reagent expiry weekly
- Reorder when stock reaches reorder level
- Rotate stock (FIFO)
- Document lot numbers

---

## 📱 **SMS Notifications**

The system automatically sends SMS for:

1. **Critical Results** → Ordering doctor
2. **Results Ready** → Patient
3. **Specimen Rejected** → Requesting physician

**Setup SMS:**
Already configured! Uses existing SMS service.

**To test:**
1. Enter critical result (e.g., Glucose > 500)
2. Verify patient has phone number
3. Check SMS logs in admin

---

## 🎓 **Training Your Staff**

### **Phlebotomists Need to Know:**
- How to create specimens
- Tube types and colors
- Labeling requirements
- Transport protocols

### **Lab Technicians Need to Know:**
- Specimen reception
- Quality checks
- Test processing
- Result entry
- QC procedures

### **Pathologists Need to Know:**
- Result verification
- Critical value protocols
- Interpretation guidelines
- Reporting requirements

### **Lab Manager Needs to Know:**
- Dashboard monitoring
- Equipment management
- Inventory control
- QC oversight
- Report generation

---

## ❓ **Common Questions**

**Q: Can I modify existing tests?**  
A: Yes, go to Django Admin → Lab Tests → Edit

**Q: How do I add new tests?**  
A: Admin → Lab Tests → Add Lab Test

**Q: Where do I see pending specimens?**  
A: Lab Dashboard shows pending specimens list

**Q: How do I reject a specimen?**  
A: Specimen Reception page → Select "Reject" → Choose reason

**Q: Can I create custom panels?**  
A: Yes, Admin → Lab Test Panels → Add Panel → Select tests

**Q: How do I generate reports?**  
A: Coming soon! Currently view data in dashboard/admin

**Q: What if QC fails?**  
A: Document corrective action, rerun QC, do not release patient results until QC passes

**Q: How do I handle STAT orders?**  
A: Mark priority as "STAT" when creating requisition

---

## 🔧 **Troubleshooting**

### **Problem: Can't create specimen**
**Solution:**
- Check if order exists
- Verify specimen type is active
- Ensure patient record is complete

### **Problem: Reference range not showing**
**Solution:**
- Go to Admin → Reference Ranges
- Verify range exists for the test
- Check age/gender matches patient
- Ensure "is_active" is checked

### **Problem: SMS not sending**
**Solution:**
- Check patient phone number format
- Verify SMS service is configured
- Check SMS logs in admin
- Ensure sufficient SMS balance

### **Problem: Equipment shows as "Down"**
**Solution:**
- Update equipment status in admin
- Run QC test to verify functionality
- Contact maintenance if needed

---

## 📚 **Full Documentation**

For complete details, see:
- **COMPREHENSIVE_LAB_SYSTEM_GUIDE.md** - Full system documentation
- **Django Admin** - Model documentation
- **Help tooltips** - In-app guidance

---

## ✅ **Success Checklist**

After setup, you should have:

- [ ] Migrations applied successfully
- [ ] Initial data loaded (categories, specimens, tests)
- [ ] Lab dashboard accessible
- [ ] At least one test panel created
- [ ] Reference ranges configured for common tests
- [ ] Lab equipment registered
- [ ] Staff trained on basic workflows
- [ ] SMS notifications working
- [ ] First specimen successfully processed

---

## 🎉 **You're Ready!**

Your comprehensive lab system is now operational!

**Start processing lab tests with:**
- ✅ Better tracking
- ✅ Improved quality
- ✅ Faster TAT
- ✅ Complete documentation
- ✅ Regulatory compliance

**Need help?** Check the full guide or contact support.

---

*Quick Start Guide v1.0*  
*Last Updated: November 4, 2025*
































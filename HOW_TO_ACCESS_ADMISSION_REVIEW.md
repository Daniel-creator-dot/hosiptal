# 🎯 HOW TO ACCESS: Add Notes & Drugs for Admitted Patients

## 📍 **WHERE TO GO:**

### **Option 1: Direct URL (Fastest)**

If you have an admission encounter ID:
```
http://127.0.0.1:8000/hms/admission-review/{encounter-id}/
```

Replace `{encounter-id}` with actual UUID of an admission encounter.

---

### **Option 2: Through Dashboard (Recommended)**

**Step-by-Step:**

1. **Go to Admitted Patients Dashboard:**
   ```
   http://127.0.0.1:8000/hms/admitted-patients/
   ```

2. **You'll see a list of ALL admitted patients:**
   ```
   ┌────────────────────────────────────────────┐
   │ Admitted Patients Dashboard                │
   ├────────────────────────────────────────────┤
   │ Patient Name    | Duration | Diagnosis     │
   ├────────────────────────────────────────────┤
   │ John Doe        | Day 3    | HTN    [Review]│
   │ Jane Smith      | Day 1    | Pneum. [Review]│
   │ Bob Wilson      | Day 5    | DM     [Review]│
   └────────────────────────────────────────────┘
   ```

3. **Click the [Review] button** for any patient

4. **You'll see the Admission Review page with 3 big buttons:**
   ```
   ┌─────────────────────────────────────────────┐
   │ JOHN DOE - Day 3 of Admission               │
   ├─────────────────────────────────────────────┤
   │                                             │
   │  [📝 Add Progress Note]                     │
   │  [💊 Add Medication]                        │
   │  [📋 Update Status]                         │
   │                                             │
   └─────────────────────────────────────────────┘
   ```

---

## 📝 **HOW TO ADD NOTES:**

### **Step 1: Click "Add Progress Note" Button**

### **Step 2: Fill in SOAP Format:**

Modal opens with these fields:

```
┌──────────────────────────────────────────────┐
│ Add Progress Note                            │
├──────────────────────────────────────────────┤
│                                              │
│ Subjective (Patient's complaints):          │
│ ┌──────────────────────────────────────┐    │
│ │ Patient reports fever improving...   │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ Objective (Your findings):                  │
│ ┌──────────────────────────────────────┐    │
│ │ Temp 37.5°C, BP 130/85...           │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ Assessment (Your conclusion):               │
│ ┌──────────────────────────────────────┐    │
│ │ Infection responding to antibiotics  │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ Plan (What to do next):                     │
│ ┌──────────────────────────────────────┐    │
│ │ Continue current treatment...        │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ Additional Notes:                           │
│ ┌──────────────────────────────────────┐    │
│ │ Patient stable, no concerns          │    │
│ └──────────────────────────────────────┘    │
│                                              │
│        [Cancel]  [Save Progress Note]       │
└──────────────────────────────────────────────┘
```

### **Step 3: Click "Save Progress Note"**

✅ Note saved!  
✅ Next shift can now read it!

---

## 💊 **HOW TO ADD MEDICATIONS:**

### **Step 1: Click "Add Medication" Button**

### **Step 2: Fill in Prescription Details:**

Modal opens with these fields:

```
┌──────────────────────────────────────────────┐
│ Add Medication                               │
├──────────────────────────────────────────────┤
│                                              │
│ Select Medication:                           │
│ ┌──────────────────────────────────────┐    │
│ │ [Amlodipine 10mg Tablet        ▼]   │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ Dosage Instructions:                        │
│ ┌──────────────────────────────────────┐    │
│ │ 1 tablet                             │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ Frequency:                                  │
│ ┌──────────────────────────────────────┐    │
│ │ [Once daily                    ▼]   │    │
│ └──────────────────────────────────────┘    │
│                                              │
│ Quantity:  [30]  Duration: [30] days        │
│                                              │
│ Route:                                      │
│ ┌──────────────────────────────────────┐    │
│ │ [Oral                          ▼]   │    │
│ └──────────────────────────────────────┘    │
│                                              │
│        [Cancel]  [Add Medication]           │
└──────────────────────────────────────────────┘
```

**Frequency Options:**
- Once daily
- Twice daily
- Three times daily
- Four times daily
- As needed (PRN)
- Every 4/6/8 hours

**Route Options:**
- Oral
- IV (Intravenous)
- IM (Intramuscular)
- SC (Subcutaneous)
- Topical
- Inhaled

### **Step 3: Click "Add Medication"**

✅ Medication added!  
✅ Shows in "Current Medications" section!  
✅ Next shift will see it marked as "New"!

---

## 📋 **WHAT YOU'LL SEE ON THE PAGE:**

After adding notes and medications, the review page shows:

```
┌─────────────────────────────────────────────────────┐
│ ADMISSION REVIEW - John Doe                         │
│ Day 3, 12 hours since admission                     │
├─────────────────────────────────────────────────────┤
│ Quick Actions:                                      │
│ [📝 Add Progress Note] [💊 Add Med] [📋 Update]     │
├─────────────────────────────────────────────────────┤
│                                                     │
│ CURRENT STATUS:                                     │
│  Diagnosis: Hypertensive crisis                     │
│  Chief Complaint: Severe headache                   │
│                                                     │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                     │
│ PROGRESS NOTES (For Next Shift): ← YOUR NOTES HERE │
│  ┌────────────────────────────────────────────┐    │
│  │ [Latest] Nov 10, 14:00 by Dr. Smith        │    │
│  │ S: Patient reports headache improving      │    │
│  │ O: BP 150/95 (down from 180/110)          │    │
│  │ A: HTN crisis improving                    │    │
│  │ P: Continue current meds, monitor BP       │    │
│  └────────────────────────────────────────────┘    │
│                                                     │
│  ┌────────────────────────────────────────────┐    │
│  │ Nov 10, 08:00 by Dr. Jones                 │    │
│  │ S: Severe headache, blurred vision         │    │
│  │ O: BP 180/110, temp 37.0                   │    │
│  │ A: Hypertensive crisis                     │    │
│  │ P: Started Amlodipine, close monitoring    │    │
│  └────────────────────────────────────────────┘    │
│                                                     │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                     │
│ CURRENT MEDICATIONS: ← YOUR MEDICATIONS HERE        │
│  • Amlodipine 10mg - Once daily (Oral)             │
│  • Hydrochlorothiazide 25mg - Once daily (Oral)    │
│  • Aspirin 75mg - Once daily (Oral)                │
│                                                     │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                     │
│ LATEST VITALS:                                      │
│  🌡️ Temp: 37.2°C                                    │
│  💓 BP: 150/95 mmHg                                 │
│  ❤️ HR: 78 bpm                                      │
│  💨 SpO2: 98%                                       │
│                                                     │
│ RECENT LAB RESULTS:                                 │
│  • CBC: WBC 12.5 (H) - Abnormal                    │
│  • BMP: All normal                                  │
└─────────────────────────────────────────────────────┘
```

---

## 🔍 **WHERE NOTES & DRUGS APPEAR:**

### **1. On the Patient's Review Page:**
- Shows immediately after saving
- Listed chronologically

### **2. In Shift Handover Report:**
```
http://127.0.0.1:8000/hms/shift-handover-report/
```
- Shows under each patient
- NEW medications marked with badge
- Progress notes from last 8 hours highlighted

### **3. In Patient Consultation History:**
```
http://127.0.0.1:8000/hms/patient/{patient-id}/consultation-history/
```
- All notes visible
- Complete medication history

---

## 🎯 **QUICK TEST:**

### **Test Adding a Note:**

1. Go to: `http://127.0.0.1:8000/hms/admitted-patients/`
2. Click any [Review] button
3. Click [📝 Add Progress Note]
4. Fill in:
   - **S:** "Patient feels better"
   - **O:** "Vitals stable"
   - **A:** "Improving"
   - **P:** "Continue treatment"
5. Click "Save Progress Note"
6. ✅ See it appear in "Progress Notes" section!

### **Test Adding a Medication:**

1. On same page, click [💊 Add Medication]
2. Select drug: "Amoxicillin 500mg"
3. Dosage: "1 tablet"
4. Frequency: "Three times daily"
5. Quantity: 21
6. Duration: 7 days
7. Route: "Oral"
8. Click "Add Medication"
9. ✅ See it appear in "Current Medications" section!

---

## 🔄 **WORKFLOW EXAMPLE:**

```
START:
  └─> Go to: http://127.0.0.1:8000/hms/admitted-patients/
      │
      ├─> See list of admitted patients
      │
      ├─> Click [Review] for "John Doe"
      │
      └─> Admission Review Page Opens
          │
          ├─> See current status
          ├─> See all previous notes
          ├─> See current medications
          │
          ├─> OPTION 1: Add Progress Note
          │   └─> Click [📝 Add Progress Note]
          │       └─> Fill SOAP fields
          │           └─> Save ✅
          │
          ├─> OPTION 2: Add Medication
          │   └─> Click [💊 Add Medication]
          │       └─> Select drug & details
          │           └─> Save ✅
          │
          └─> OPTION 3: Update Status
              └─> Click [📋 Update Status]
                  └─> Update diagnosis
                      └─> Save ✅

NEXT SHIFT:
  └─> Go to: http://127.0.0.1:8000/hms/shift-handover-report/
      │
      └─> See "John Doe" with your notes & medications
          └─> Perfect handover! ✅
```

---

## 📱 **MAIN URLS:**

```
1. Admitted Patients List:
   http://127.0.0.1:8000/hms/admitted-patients/

2. Review Patient:
   http://127.0.0.1:8000/hms/admission-review/{encounter-id}/

3. Shift Handover:
   http://127.0.0.1:8000/hms/shift-handover-report/
```

---

## ✅ **SUMMARY:**

**Where to add notes:**
- Admitted Patients → Click Review → Click "Add Progress Note"

**Where to add drugs:**
- Admitted Patients → Click Review → Click "Add Medication"

**Where to see them:**
- On the review page (immediate)
- In shift handover report (for next shift)
- In patient history (for investigation)

---

**Start here:** `http://127.0.0.1:8000/hms/admitted-patients/`

**Click [Review] → See 3 big buttons → Add notes & drugs!** 🎯






















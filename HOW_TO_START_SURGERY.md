# How to Start a Planned Surgery - Complete Guide

## Overview
This guide walks you through the complete process of scheduling and starting a planned surgery in the Hospital Management System (HMS).

---

## Method 1: Create Surgery Encounter (Quick Method)

### Step 1: Navigate to Encounters
1. Go to **Dashboard** → **Encounters** → **New Encounter**
2. Or directly visit: `http://localhost:8000/hospital/encounters/new/`

### Step 2: Fill Out the Encounter Form
```
Required Fields:
- Patient: Select patient from dropdown
- Encounter Type: Select "Surgery"
- Status: "Active"
- Chief Complaint: "Planned surgery - [procedure name]"
- Provider: Select the surgeon
- Location: Select operating theater/surgical ward

Optional Fields:
- Diagnosis: Pre-operative diagnosis
- Notes: Surgical plan, anesthesia type, etc.
```

### Step 3: Create the Encounter
- Click **Save** or **Create Encounter**
- The surgery encounter is now created
- You'll be redirected to the encounter detail page

### Step 4: Start the Surgery
Once on the encounter detail page, you can:
- Record vital signs
- Add surgical notes
- Order lab tests if needed
- Document the procedure

---

## Method 2: Quick Visit from Patient Profile

### Step 1: Find the Patient
1. Go to **Patients** → **Patient List**
2. Search for the patient by name or MRN
3. Click on the patient name to view their profile

### Step 2: Create Quick Visit
1. On the patient detail page, look for **"Quick Visit"** or **"New Encounter"** button
2. Click the button
3. Select **Encounter Type: Surgery**
4. Enter **Chief Complaint**: e.g., "Planned appendectomy"
5. Click **Create Visit**

---

## Method 3: Admin Panel (For Advanced Users)

### Step 1: Access Admin Panel
1. Navigate to: `http://localhost:8000/admin/`
2. Login with admin credentials
   - Username: `admin`
   - Password: `admin123`

### Step 2: Create Encounter
1. Go to **Hospital** → **Encounters**
2. Click **Add Encounter** (top right)
3. Fill in the form:
   ```
   Patient: [Select patient]
   Encounter type: Surgery
   Status: Active
   Started at: [Select date/time]
   Location: [Operating room/theater]
   Provider: [Surgeon]
   Chief complaint: Planned surgery
   Diagnosis: [Pre-op diagnosis]
   Notes: [Surgical details]
   ```
4. Click **Save**

---

## Pre-Surgery Checklist

Before starting a surgery, ensure the following are completed:

### ✅ Patient Preparation
- [ ] Patient registered in system
- [ ] Pre-operative assessment completed
- [ ] Consent forms signed (document in notes)
- [ ] Allergies documented
- [ ] Current medications listed
- [ ] Fasting status confirmed

### ✅ Medical Records
- [ ] Recent vital signs recorded
- [ ] Lab results available (if required)
- [ ] Imaging studies reviewed (if required)
- [ ] Blood type verified (if applicable)
- [ ] Pre-op diagnosis documented

### ✅ Surgical Team
- [ ] Surgeon assigned as provider
- [ ] Anesthesiologist identified
- [ ] Nursing staff assigned
- [ ] Operating room scheduled

### ✅ Equipment & Supplies
- [ ] Operating theater assigned (location field)
- [ ] Surgical instruments prepared
- [ ] Anesthesia equipment ready
- [ ] Emergency equipment available

---

## During Surgery Workflow

### 1. Record Vital Signs
```
Navigate to: Encounter Detail → Add Vital Signs
Record:
- Blood Pressure
- Heart Rate
- Temperature
- SpO2 (Oxygen Saturation)
- Respiratory Rate
- Consciousness Level
```

### 2. Document Surgical Procedure
```
Navigate to: Encounter Detail → Edit/Update
Add to Notes:
- Procedure performed
- Findings
- Complications (if any)
- Blood loss
- Duration
- Anesthesia details
```

### 3. Update Diagnosis
```
Update the Diagnosis field with:
- Post-operative diagnosis
- ICD codes (if applicable)
- Procedure codes
```

### 4. Add Orders (If Needed)
```
Navigate to: Encounter Detail → Orders → New Order
Add:
- Post-op medications
- Lab tests (post-op bloodwork)
- Imaging studies
- Special instructions
```

---

## Post-Surgery Completion

### Step 1: Update Encounter Status
1. Go to the encounter detail page
2. Click **Edit Encounter** or **Complete Encounter**
3. Update fields:
   ```
   Status: Completed
   Ended at: [Current date/time]
   Diagnosis: [Final/post-op diagnosis]
   Notes: [Add surgical summary]
   ```

### Step 2: Recovery Documentation
- Record post-operative vital signs
- Document recovery room time
- Note any complications
- Plan for discharge or admission

### Step 3: Follow-up Planning
- Schedule follow-up appointments
- Create discharge instructions
- Plan for post-op care
- Arrange physical therapy (if needed)

---

## API Method (For Developers)

### Create Surgery Encounter via API
```bash
# POST request to create encounter
curl -X POST http://localhost:8000/api/hospital/encounters/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "patient": 1,
    "encounter_type": "surgery",
    "status": "active",
    "chief_complaint": "Planned laparoscopic cholecystectomy",
    "provider": 2,
    "location": 3,
    "diagnosis": "Cholelithiasis",
    "notes": "Patient consented for surgery under general anesthesia"
  }'
```

### Response
```json
{
  "id": 123,
  "patient": 1,
  "encounter_type": "surgery",
  "status": "active",
  "started_at": "2025-11-13T10:00:00Z",
  "chief_complaint": "Planned laparoscopic cholecystectomy",
  ...
}
```

---

## Quick Reference: URLs

| Action | URL |
|--------|-----|
| Create New Encounter | `/hospital/encounters/new/` |
| Encounter List | `/hospital/encounters/` |
| Patient List | `/hospital/patients/` |
| Patient Detail | `/hospital/patients/<patient_id>/` |
| Encounter Detail | `/hospital/encounters/<encounter_id>/` |
| Admin Panel | `/admin/` |
| API Encounters | `/api/hospital/encounters/` |

---

## Encounter Types Available

The system supports 4 encounter types:

1. **Outpatient** - Regular clinic visits
2. **Inpatient** - Hospital admissions
3. **Emergency (ER)** - Emergency department visits
4. **Surgery** - Planned and emergency surgeries ✅

---

## Tips & Best Practices

### 📝 Documentation
- Use clear, concise chief complaints
- Document all surgical details in notes
- Include pre-op and post-op diagnoses
- Record any complications immediately

### 👥 Team Communication
- Assign the primary surgeon as provider
- Note all team members in the notes
- Document handoffs clearly
- Include contact information

### ⏰ Timing
- Record accurate start and end times
- Document delays and reasons
- Track anesthesia time separately
- Note recovery room time

### 📊 Data Quality
- Use standardized procedure names
- Include procedure codes when available
- Document all medications given
- Record all fluids and blood products

### 🔒 Safety
- Verify patient identity
- Confirm surgical site
- Document timeout procedure
- Record all counts (sponges, instruments)

---

## Troubleshooting

### Issue: Can't find "Surgery" option
**Solution**: Make sure you're using the correct encounter form. The encounter type dropdown should show:
- Outpatient
- Inpatient
- Emergency
- Surgery ✅

### Issue: No patients showing in dropdown
**Solution**: 
1. Ensure patients are registered in the system
2. Check that patients are not marked as deleted
3. Verify you have proper permissions

### Issue: Can't assign operating room
**Solution**:
1. Ensure wards/locations are created in admin panel
2. Create an "Operating Theater" or "Surgery" ward
3. Assign it in the location field

### Issue: Provider dropdown is empty
**Solution**:
1. Ensure staff members are registered
2. Create surgeon profiles in admin panel
3. Link users to staff profiles

---

## Example: Complete Surgery Flow

### 1. Pre-Op (Day Before)
```
Patient: John Doe (MRN: PMC12345)
Procedure: Laparoscopic Appendectomy
Surgeon: Dr. Smith
Scheduled: Tomorrow, 8:00 AM
```

**Actions:**
- Create encounter with type "Surgery"
- Document pre-op diagnosis: "Acute appendicitis"
- Record pre-op vitals
- Note allergies and medications
- Confirm fasting status

### 2. Day of Surgery
```
Time: 7:30 AM - Patient arrives
Time: 8:00 AM - Surgery starts
Time: 9:15 AM - Surgery ends
```

**Actions:**
- Update encounter with "Started at" time
- Record intra-op vitals every 15 minutes
- Document procedure details in notes
- Record medications and fluids given

### 3. Post-Op
```
Time: 9:15 AM - Recovery room
Time: 11:00 AM - Transferred to ward
```

**Actions:**
- Update diagnosis to post-op: "Status post appendectomy"
- Record recovery vitals
- Document post-op orders
- Complete encounter with end time
- Add discharge or admission notes

---

## Contact & Support

For technical issues or questions:
- Check system logs in admin panel
- Review Django error logs
- Contact system administrator
- Refer to HMS documentation

---

*Last Updated: November 2025*  
*HMS Version: 1.0*  
*Status: Production Ready ✅*


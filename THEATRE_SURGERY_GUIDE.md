# 🏥 HOW TO SEND PATIENTS TO THEATRE/SURGERY

**Your HMS already has a complete theatre management system!**

---

## 🎯 QUICK ANSWER

### **Method 1: Using Django Admin (Easiest)**
```
1. Go to: http://127.0.0.1:8000/admin/hospital/theatreschedule/
2. Click "Add Theatre Schedule"
3. Fill in:
   - Patient: Select patient
   - Encounter: Select encounter
   - Theatre Name: e.g., "Theatre 1", "OT 1"
   - Procedure: e.g., "Appendectomy", "Cesarean Section"
   - Scheduled Start: Date & Time
   - Scheduled End: Date & Time
   - Surgeon: Select surgeon
   - Anaesthetist: Select (optional)
   - Scrub Nurse: Select (optional)
   - Status: "Scheduled"
4. Click "Save"
✅ Patient scheduled for theatre!
```

---

### **Method 2: View Theatre Schedule**
```
Go to: http://127.0.0.1:8000/hms/theatre/

You'll see:
- All scheduled procedures
- Theatre timeline
- Patient details
- Surgical team
- Status tracking
```

---

## 📋 COMPLETE THEATRE WORKFLOW

### **Step 1: Patient Needs Surgery**
```
Doctor examines patient
→ Determines surgery needed
→ Creates order: type="procedure"
```

### **Step 2: Schedule Theatre**
```
Go to Django Admin
→ Theatre Schedules
→ Add Theatre Schedule
→ Fill details:
   - Patient
   - Procedure name
   - Theatre (Theatre 1, OT 1, etc.)
   - Date & Time
   - Surgical team
→ Save
```

### **Step 3: Pre-Operative Preparation**
```
System automatically creates:
- Surgical Safety Checklist
- Pre-op assessment form
- Consent forms
```

### **Step 4: Day of Surgery**
```
View schedule: /hms/theatre/
→ See patient on schedule
→ Mark as "In Progress" when surgery starts
→ Mark as "Completed" when done
```

### **Step 5: Post-Operative Care**
```
Update status
→ Record outcome
→ Transfer to recovery
→ Billing for procedure
```

---

## 🏥 THEATRE SYSTEM FEATURES

### **What's Already Built:**

**1. TheatreSchedule Model**
- Patient tracking
- Encounter linking
- Theatre name/room
- Procedure details
- Scheduled times
- Actual times
- Surgical team (Surgeon, Anaesthetist, Nurse)
- Status tracking
- Notes

**2. SurgicalChecklist Model**
- Pre-operative checks
- Pre-incision checks
- Sign-out checks
- WHO Surgical Safety Checklist compliant

**3. AnaesthesiaRecord Model**
- Anaesthetist tracking
- Anaesthesia type
- Medications used
- Vital signs during surgery
- Complications tracking

**4. Theatre Schedule View**
- Visual timeline
- Color-coded by status
- Grouped by theatre
- Date range filtering

---

## 📊 THEATRE STATUSES

### **scheduled** (Blue)
- Surgery planned
- Team assigned
- Theatre booked
- Awaiting surgery date

### **in_progress** (Green, Animated)
- Surgery currently happening
- Patient in theatre
- Team operating

### **completed** (Gray)
- Surgery finished
- Patient in recovery
- Outcome recorded

### **cancelled** (Red)
- Surgery cancelled
- Reason documented
- Rescheduling may be needed

---

## 🎯 CREATING A THEATRE SCHEDULE

### **Required Information:**

**Patient Details:**
- Patient (select from list)
- Encounter (select patient's encounter)

**Procedure Details:**
- Procedure name (e.g., "Appendectomy")
- Theatre name (e.g., "Theatre 1", "OT 1", "Main Theatre")

**Timing:**
- Scheduled Start (Date & Time)
- Scheduled End (Date & Time)

**Surgical Team:**
- Surgeon (required)
- Anaesthetist (optional)
- Scrub Nurse (optional)

**Status:**
- "Scheduled" (for new bookings)

---

## 💡 EXAMPLE: Scheduling an Appendectomy

### **Scenario:**
Patient John Doe needs emergency appendectomy

### **Steps:**

**1. Access Admin Panel:**
```
http://127.0.0.1:8000/admin/hospital/theatreschedule/add/
```

**2. Fill Form:**
```
Patient: John Doe (PMC2025001)
Encounter: Select his current encounter
Theatre Name: Theatre 1
Procedure: Emergency Appendectomy
Scheduled Start: 2025-11-08 14:00
Scheduled End: 2025-11-08 16:00
Surgeon: Dr. Smith
Anaesthetist: Dr. Johnson
Status: Scheduled
```

**3. Save:**
```
Click "Save" button
✅ Surgery scheduled!
```

**4. View Schedule:**
```
Go to: /hms/theatre/
See: John Doe scheduled for 14:00-16:00 in Theatre 1
```

**5. On Surgery Day:**
```
Update status to "In Progress" at 14:00
Update to "Completed" at 16:00
```

---

## 🏥 THEATRE NAMES (Examples)

You can use any theatre name you want:
- Theatre 1, Theatre 2, Theatre 3
- OT 1, OT 2 (Operating Theatre)
- Main Theatre
- Emergency Theatre
- Minor Procedures Room
- Labour Ward Theatre
- Dental Theatre

**Note:** Theatre names are free text, so use whatever naming convention your hospital uses!

---

## 📱 ACCESS POINTS

### **View Theatre Schedule:**
```
http://127.0.0.1:8000/hms/theatre/
```

### **Add New Schedule (Admin):**
```
http://127.0.0.1:8000/admin/hospital/theatreschedule/add/
```

### **View All Schedules (Admin):**
```
http://127.0.0.1:8000/admin/hospital/theatreschedule/
```

---

## 🎨 THEATRE SCHEDULE DISPLAY

**The schedule shows:**
- Timeline view by theatre
- Color-coded by status
- Patient details
- Procedure name
- Time slots
- Surgical team
- Real-time status

**Features:**
- Filter by date range
- Group by theatre
- Status badges
- Team information
- Patient links

---

## 🚀 QUICK GUIDE

### **To Schedule a Patient for Surgery:**

**Option A: Django Admin (Recommended)**
1. Go to `/admin/hospital/theatreschedule/add/`
2. Select patient
3. Enter procedure details
4. Set date/time
5. Assign surgical team
6. Save

**Option B: API (For Integration)**
```
POST /api/hospital/theatre-schedules/
{
    "patient": <patient_id>,
    "encounter": <encounter_id>,
    "procedure": "Appendectomy",
    "theatre_name": "Theatre 1",
    "scheduled_start": "2025-11-08T14:00:00Z",
    "scheduled_end": "2025-11-08T16:00:00Z",
    "surgeon": <surgeon_id>,
    "status": "scheduled"
}
```

---

## ✅ WHAT YOU HAVE

**Theatre Management:**
✅ Schedule surgeries
✅ Assign surgical team
✅ Track theatre utilization
✅ Visual timeline
✅ Status tracking
✅ Surgical checklists
✅ Anaesthesia records
✅ Complete audit trail

**System Status:**
✅ Models created
✅ Views working
✅ Templates available
✅ Admin interface configured
✅ API endpoints available
✅ Ready to use!

---

## 🎊 RESULT

**To send a patient to theatre:**

# 1. Go to Admin: /admin/hospital/theatreschedule/add/
# 2. Select patient and details
# 3. Set date/time and team
# 4. Save
# ✅ Done!

**View schedule:** http://127.0.0.1:8000/hms/theatre/

**It's that simple!** 🏥✨

---

**Need help? The system is already built and ready to use!**
























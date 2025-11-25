# Quick Start: Queue Management

## 🚀 **Accessing the Queue System**

**URL:** http://127.0.0.1:8000/hms/queues/

### ⚠️ **Requirements:**
- ✅ You must be **logged in**
- ✅ Navigate through the application or login at: http://127.0.0.1:8000/admin/login/

---

## 📺 **What You'll See**

### **Top Section - Filters**
```
┌─────────────────────────────────────────────┐
│ [Select Department ▼] [Filter] [Refresh]   │
└─────────────────────────────────────────────┘
```

### **Main Display - Queue Cards**

**Waiting Patients:**
```
┌───────────────────────────────────────┐
│  #001  👤 John Doe (PMC123456)       │
│  ⏱ Wait: 15 min  🏥 Consultation      │
│  🔴 STAT Priority                     │
│  [Call] [Skip] [Complete]            │
└───────────────────────────────────────┘

┌───────────────────────────────────────┐
│  #002  👤 Jane Smith (PMC123457)     │
│  ⏱ Wait: 5 min   🏥 Laboratory       │
│  🟡 Urgent Priority                   │
│  [Call] [Skip] [Complete]            │
└───────────────────────────────────────┘
```

**In Progress:**
```
┌───────────────────────────────────────┐
│  #003  👤 Bob Johnson (PMC123458)    │
│  ⏱ In progress: 10 min               │
│  🏥 Consultation                      │
│  ✅ Being Served                      │
│  [Complete] [Skip]                   │
└───────────────────────────────────────┘
```

---

## 🎮 **Quick Actions**

### **1. Call Next Patient** (Most Common)
```
Click: [Call Next] button at top
↓
First waiting patient → In Progress
↓
Their queue number displays prominently
```

### **2. Call Specific Patient**
```
Find patient card → Click [Call]
↓
Patient status → In Progress
```

### **3. Complete Service**
```
Patient card (In Progress) → Click [Complete]
↓
Patient removed from queue
↓
Ready for next patient
```

### **4. Skip Patient**
```
Patient card → Click [Skip]
↓
Patient marked as skipped
↓
Next patient auto-called
```

---

## 🏥 **Department Examples**

### **Consultation Queue**
Patients waiting to see doctor:
- Filter: Select "Consultation" department
- Shows: All patients in consultation queue
- Action: Doctor calls next patient

### **Laboratory Queue**
Patients for lab tests:
- Filter: Select "Laboratory" department  
- Shows: Patients with lab orders
- Action: Lab tech calls patient for sample

### **Pharmacy Queue**
Patients picking up meds:
- Filter: Select "Pharmacy" department
- Shows: Patients with prescriptions
- Action: Pharmacist calls patient

### **Emergency/Triage**
Special urgent queue:
- URL: http://127.0.0.1:8000/hms/triage/
- Shows: Emergency patients by severity
- Auto-sorted by triage level

---

## 🎨 **Color Codes**

| Color | Meaning |
|-------|---------|
| 🔴 Red border | STAT Priority (Emergency) |
| 🟡 Orange border | Waiting patient |
| 🟢 Green border | In Progress |
| 🔵 Blue number | Queue number |

---

## ⚡ **Priority System**

### **When to Use Each Priority:**

**🔴 STAT (Immediate)**
- Medical emergencies
- Severe pain
- Life-threatening
- Example: Chest pain, severe bleeding

**🟡 Urgent**
- Needs quick attention
- Moderate symptoms
- Can wait 5-15 minutes
- Example: High fever, moderate pain

**🟢 Normal**
- Standard appointments
- Regular consultations
- Routine procedures
- Example: Follow-ups, check-ups

---

## 📱 **Mobile Access**

The queue system works on:
- ✅ Desktop computers
- ✅ Tablets (perfect for clinic use)
- ✅ Mobile phones
- ✅ Large displays (waiting room TVs)

---

## 🔄 **Typical Workflow**

### **Receptionist:**
```
1. Patient arrives
2. Create/open encounter
3. Assign to department
   → Patient auto-added to queue
4. Inform patient of queue number
```

### **Nurse/Doctor:**
```
1. Open queue page: /hms/queues/
2. Filter by your department
3. Click "Call Next"
4. See patient (status: In Progress)
5. Provide care
6. Click "Complete"
7. Repeat
```

### **Lab/Pharmacy/Radiology:**
```
1. Open queue for your dept
2. Call next patient
3. Perform service
4. Complete
```

---

## 🆘 **Troubleshooting**

### **Problem: No patients showing**

✅ **Solutions:**
- Check department filter (select correct dept)
- Verify patients have active encounters
- Ensure patients assigned to your department
- Refresh the page

### **Problem: Can't call patient**

✅ **Solutions:**
- Complete current "In Progress" patient first
- Only one patient can be "In Progress" at a time
- Check you're logged in with correct role
- Refresh page

### **Problem: Wrong order**

✅ **Explanation:**
- Queue order: STAT → Urgent → Normal
- Within priority: First come, first served
- This is correct behavior!

---

## 💡 **Pro Tips**

### **Tip 1: Use Filters**
Filter by department to see only YOUR queue:
```
Dropdown: [Consultation ▼] → Click [Filter]
```

### **Tip 2: Auto-Refresh**
For display screens:
- Enable auto-refresh (if available)
- Updates every 30-60 seconds
- Perfect for waiting room displays

### **Tip 3: Keyboard Shortcuts** (if implemented)
- Press `N` for "Next"
- Press `C` for "Complete"  
- Press `R` for "Refresh"

### **Tip 4: Multiple Queues**
Patient can be in multiple queues:
- Lab + Pharmacy + X-ray simultaneously
- Each department manages independently

---

## 📊 **At a Glance**

| Feature | Status |
|---------|--------|
| View queues | ✅ Working |
| Call patients | ✅ Working |
| Filter by dept | ✅ Working |
| Priority levels | ✅ Working |
| Auto-ordering | ✅ Working |
| Mobile support | ✅ Working |
| Real-time updates | ✅ Working |

---

## 🎯 **Quick Start Steps**

1. **Login** to system
2. **Go to:** http://127.0.0.1:8000/hms/queues/
3. **Select** your department
4. **Click** "Call Next"
5. **Provide** service
6. **Click** "Complete"
7. **Repeat!**

---

## 📞 **Need More Help?**

- **Full Guide:** See `QUEUE_MANAGEMENT_GUIDE.md`
- **Video Tutorial:** Ask admin for training
- **Support:** Contact IT department

---

## ✅ **System Ready!**

**Your queue management system is:**
- ✅ Fully functional
- ✅ Ready to use
- ✅ Accessible at: http://127.0.0.1:8000/hms/queues/

**Just login and start managing your patient queue!** 🎉

---

**Quick Reference**  
**URL:** http://127.0.0.1:8000/hms/queues/  
**Login:** http://127.0.0.1:8000/admin/login/  
**Status:** ✅ Operational

































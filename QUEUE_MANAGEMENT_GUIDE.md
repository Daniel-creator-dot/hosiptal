# Queue Management System - User Guide

## 📋 **Queue System Overview**

The Queue Management System helps manage patient flow through different departments in the hospital.

**Access URL:** http://127.0.0.1:8000/hms/queues/

---

## 🎯 **What the Queue System Does**

### **Purpose:**
- Track patients waiting for services
- Manage patient flow through departments
- Call patients in order
- Monitor wait times
- Prioritize urgent cases

### **Key Features:**
✅ Real-time queue display  
✅ Department-based filtering  
✅ Priority levels (Normal, Urgent, STAT)  
✅ Call next patient  
✅ Skip or complete patients  
✅ Wait time tracking  
✅ Auto-refresh capability  

---

## 📊 **Queue Display Page**

### **URL:** `/hms/queues/`

### **What You See:**

1. **Filter Section**
   - Department dropdown
   - Location filter
   - Refresh button

2. **Queue Cards**
   - Queue number (large, prominent)
   - Patient name and MRN
   - Priority level (badge)
   - Status (Waiting/In Progress)
   - Department
   - Wait time
   - Action buttons

3. **Statistics**
   - Total patients waiting
   - Average wait time
   - Patients by department

---

## 🚦 **Queue Statuses**

| Status | Description | Color |
|--------|-------------|-------|
| **Waiting** | Patient in queue | Yellow/Orange |
| **In Progress** | Currently being served | Green |
| **Completed** | Service finished | - (removed from display) |
| **Skipped** | Patient skipped/not present | - (removed from display) |

---

## ⚡ **Priority Levels**

| Priority | Description | When to Use |
|----------|-------------|-------------|
| **Normal** | Standard priority | Regular appointments |
| **Urgent** | Needs quick attention | Moderate pain, follow-ups |
| **STAT** | Immediate attention | Emergencies, critical cases |

---

## 🎮 **How to Use the Queue System**

### **1. View Queues**

**Access the page:**
```
http://127.0.0.1:8000/hms/queues/
```

**Filter by department:**
- Select department from dropdown
- Click "Filter"
- See only that department's queue

### **2. Call Next Patient**

**Method 1 - Call Button:**
1. Find patient in queue
2. Click "**Call**" button
3. Patient status changes to "In Progress"
4. Queue number displayed prominently

**Method 2 - Call Next:**
1. Click "**Call Next**" at top of page
2. System automatically calls first waiting patient
3. Follows priority order (STAT → Urgent → Normal)

### **3. Complete Patient**

When service is done:
1. Find patient with "In Progress" status
2. Click "**Complete**" button
3. Patient removed from queue
4. Next patient can be called

### **4. Skip Patient**

If patient is absent:
1. Find patient in queue
2. Click "**Skip**" button
3. Patient moved to skipped status
4. Next patient automatically called

### **5. Add Patient to Queue**

**From encounter:**
1. Create or open encounter
2. Assign to department
3. Patient automatically added to queue

**Manual addition:**
1. Click "**Add to Queue**" button
2. Select patient/encounter
3. Choose department
4. Set priority level
5. Submit

---

## 🏥 **Common Workflows**

### **Workflow 1: Consultation Queue**

```
1. Patient registers at reception
2. Triage nurse creates encounter
3. Patient added to consultation queue
4. Doctor calls next patient
5. Doctor completes consultation
6. Patient marked as complete
```

### **Workflow 2: Laboratory Queue**

```
1. Doctor orders lab tests
2. Patient sent to lab (added to lab queue)
3. Lab tech calls patient
4. Sample collected
5. Patient completed in queue
```

### **Workflow 3: Pharmacy Queue**

```
1. Prescription created
2. Patient sent to pharmacy queue
3. Pharmacist calls patient
4. Medication dispensed
5. Patient completed
```

### **Workflow 4: Emergency (STAT)**

```
1. Emergency patient arrives
2. Triage nurse sets priority to STAT
3. Patient jumps to front of queue
4. Immediately called for service
5. Urgent care provided
```

---

## 📱 **Department Queues**

Common departments with queues:

- **Consultation** - Doctor appointments
- **Triage** - Initial assessment
- **Laboratory** - Lab tests
- **Radiology** - X-rays, scans
- **Pharmacy** - Medication pickup
- **Emergency** - ER patients
- **Dental** - Dental procedures
- **Physiotherapy** - PT sessions

---

## 🎨 **Visual Indicators**

### **Border Colors:**
- **Orange** - Waiting patient
- **Green** - In progress
- **Red** - STAT priority
- **Yellow** - Urgent priority

### **Badges:**
- **Queue Number** - Blue, large font
- **Priority** - Color-coded badge
- **Status** - Text badge
- **Department** - Gray badge

### **Wait Time:**
- **< 15 min** - Normal (gray)
- **15-30 min** - Warning (orange)
- **> 30 min** - Alert (red)

---

## ⚙️ **Settings & Options**

### **Auto-Refresh:**
Enable auto-refresh to keep queue updated:
- Set refresh interval (30s, 60s, 2min)
- Toggle on/off
- Useful for display screens

### **Sound Notifications:**
- Enable sound when calling patient
- Audible alert in waiting area
- Configurable volume

### **Display Mode:**
- **Grid View** - Cards layout
- **List View** - Compact table
- **Large Display** - TV screen mode

---

## 🔧 **Troubleshooting**

### **Issue: Patient not showing in queue**

**Solution:**
1. Check if encounter is active
2. Verify department assignment
3. Check queue filters
4. Ensure patient status is not "Completed"

### **Issue: Can't call next patient**

**Solution:**
1. Complete current "In Progress" patient first
2. Check if any patients are waiting
3. Verify you have permissions
4. Refresh the page

### **Issue: Wrong queue order**

**Solution:**
1. Queue follows priority: STAT → Urgent → Normal
2. Within same priority: First come, first served
3. Check priority levels
4. Refresh to update order

### **Issue: Patient stuck "In Progress"**

**Solution:**
1. Click "Complete" button
2. Or manually update queue status
3. Check encounter status
4. Contact admin if persists

---

## 📊 **Queue Statistics**

### **Available Metrics:**

1. **Total Waiting** - Current queue size
2. **Average Wait Time** - Mean waiting time
3. **Longest Wait** - Maximum wait time
4. **Patients Served Today** - Completed count
5. **By Department** - Queue distribution
6. **By Priority** - Priority breakdown

### **View Statistics:**
- Displayed at top of queue page
- Updated in real-time
- Export to reports

---

## 👥 **User Roles**

### **Who Can Use Queues:**

**Receptionist:**
- View all queues
- Add patients to queues
- Call patients

**Nurse:**
- View queues
- Set priorities
- Call next patient
- Complete patients

**Doctor:**
- View own department queue
- Call patients
- Complete consultations

**Lab Tech / Pharmacist / Radiologist:**
- View department-specific queue
- Call patients
- Complete services

**Admin:**
- Full access to all queues
- Modify queue settings
- View statistics

---

## 🚀 **Best Practices**

### **For Reception:**
1. ✅ Add patients to correct department queue
2. ✅ Set appropriate priority levels
3. ✅ Inform patients of queue number
4. ✅ Update patient if queue is long

### **For Clinical Staff:**
1. ✅ Check queue regularly
2. ✅ Call patients in order
3. ✅ Mark as complete when done
4. ✅ Skip no-show patients promptly
5. ✅ Handle STAT priorities immediately

### **For Management:**
1. ✅ Monitor wait times
2. ✅ Balance staff across departments
3. ✅ Review queue statistics daily
4. ✅ Optimize department capacity
5. ✅ Address long wait times

---

## 📱 **Mobile Access**

Queue system is mobile-responsive:
- View queues on tablets
- Call patients from mobile devices
- Perfect for walking doctors/nurses
- Real-time updates

---

## 🔗 **Quick Links**

| Page | URL | Purpose |
|------|-----|---------|
| Queue Display | `/hms/queues/` | View all queues |
| Add to Queue | `/hms/queues/new/` | Manually add patient |
| Triage Queue | `/hms/triage/` | Triage-specific queue |
| Queue API | `/hms/api/queues/data/` | JSON data for integrations |

---

## 💡 **Tips & Tricks**

### **Tip 1: Use Keyboard Shortcuts**
- Press **N** to call next patient
- Press **R** to refresh queue
- Press **F** to focus on filters

### **Tip 2: Large Display Mode**
- Use for waiting room TV
- Shows queue numbers clearly
- Auto-refreshes every 30 seconds
- No action buttons (view only)

### **Tip 3: Priority Management**
- Set STAT for emergencies only
- Use Urgent for moderate cases
- Most patients should be Normal
- Avoid queue jumping unless necessary

### **Tip 4: Multi-Department**
- Patients can be in multiple queues
- Lab + Pharmacy + X-ray simultaneously
- Each department manages their own
- Track patient journey

### **Tip 5: End of Day**
- Complete all patients
- Clear queue before closing
- Check for no-shows
- Reset for next day

---

## 📞 **Support**

### **Common Questions:**

**Q: How long do patients typically wait?**  
A: Varies by department, check statistics

**Q: Can I reorder the queue?**  
A: Use priority levels, not manual reordering

**Q: What if patient leaves?**  
A: Mark as "Skipped"

**Q: Can family see queue status?**  
A: Display in waiting area, not public access

**Q: How to handle emergencies?**  
A: Use STAT priority, goes to front

---

## ✅ **Quick Start Checklist**

- [ ] Access queue page: `/hms/queues/`
- [ ] Filter by your department
- [ ] Click "Call Next" for first patient
- [ ] Patient status shows "In Progress"
- [ ] Provide service
- [ ] Click "Complete" when done
- [ ] Repeat for next patient

---

## 🎉 **Summary**

**The Queue System:**
- ✅ Organizes patient flow
- ✅ Reduces waiting confusion
- ✅ Prioritizes urgent cases
- ✅ Tracks wait times
- ✅ Improves efficiency
- ✅ Enhances patient experience

**Access Now:**
👉 http://127.0.0.1:8000/hms/queues/

---

**Last Updated:** November 2025  
**Version:** 1.0  
**Status:** ✅ Operational

































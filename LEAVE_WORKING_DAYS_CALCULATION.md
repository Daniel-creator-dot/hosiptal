# 📅 Leave Working Days Calculation (Weekends Excluded)

## ✅ **IMPLEMENTED: Automatic Weekend Exclusion**

The leave management system now **automatically excludes weekends** (Saturday & Sunday) when calculating leave periods. Only **working days (Monday-Friday)** are counted.

---

## 🔧 **How It Works**

### **Backend Calculation**

**New Method: `LeaveRequest.calculate_working_days()`**

```python
@staticmethod
def calculate_working_days(start_date, end_date):
    """Calculate working days between two dates (excluding weekends)"""
    from datetime import timedelta
    
    if start_date > end_date:
        return 0
    
    working_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Monday = 0, Sunday = 6
        # Count only Monday-Friday (0-4)
        if current_date.weekday() < 5:
            working_days += 1
        current_date += timedelta(days=1)
    
    return working_days
```

**Logic:**
- ✅ Monday (0) to Friday (4) = **Working Days** (counted)
- ❌ Saturday (5) & Sunday (6) = **Weekends** (NOT counted)

---

## 📍 **Where It's Used**

### **1. Staff Self-Service Leave Request**
- **View:** `hospital/views_staff_portal.py` → `staff_leave_request_create()`
- **Template:** `hospital/templates/hospital/staff_leave_request_create.html`
- **Calculation:** Backend + JavaScript real-time preview

### **2. Admin Manual Leave Creation**
- **View:** `hospital/views_hr.py` → `create_leave_for_staff()`
- **Template:** `hospital/templates/hospital/create_leave_for_staff.html`
- **Calculation:** Backend + JavaScript real-time preview

---

## 🎯 **Examples**

### **Example 1: Simple Week**
```
Start Date: Monday, Nov 4, 2025
End Date:   Friday, Nov 8, 2025

Days Counted:
✅ Monday    = 1
✅ Tuesday   = 1
✅ Wednesday = 1
✅ Thursday  = 1
✅ Friday    = 1

Total: 5 working days
```

### **Example 2: Full Week Including Weekend**
```
Start Date: Monday, Nov 4, 2025
End Date:   Sunday, Nov 10, 2025

Days Counted:
✅ Monday    = 1
✅ Tuesday   = 1
✅ Wednesday = 1
✅ Thursday  = 1
✅ Friday    = 1
❌ Saturday  = 0 (weekend)
❌ Sunday    = 0 (weekend)

Total: 5 working days (not 7!)
```

### **Example 3: Two Weeks**
```
Start Date: Monday, Nov 4, 2025
End Date:   Friday, Nov 15, 2025

Days Counted:
Week 1: Mon-Fri     = 5 days
❌ Weekend 1        = 0 days
Week 2: Mon-Fri     = 5 days

Total: 10 working days (not 12!)
```

### **Example 4: Mid-Week to Mid-Week**
```
Start Date: Wednesday, Nov 6, 2025
End Date:   Tuesday, Nov 12, 2025

Days Counted:
Wed, Thu, Fri       = 3 days
❌ Weekend          = 0 days
Mon, Tue            = 2 days

Total: 5 working days
```

---

## 🖥️ **Frontend Features**

### **Real-Time JavaScript Calculator**

Both leave request forms now include **live day calculation**:

**Features:**
- ✅ Automatic calculation as you select dates
- ✅ Shows "X working day(s)" with weekend note
- ✅ Color-coded alert (green success box)
- ✅ Updates instantly on date change

**Example Display:**
```
📊 Total Working Days: 5 working day(s)
Weekends (Sat & Sun) excluded automatically
```

---

## 📋 **User Interface Updates**

### **Staff Leave Request Form**

**Added Info Box:**
```
ℹ️ Working Days Calculation
Note: Leave days are calculated based on working days only 
(Monday-Friday). Weekends (Saturday & Sunday) are automatically 
excluded from the count.
```

**Updated Instructions:**
- ✅ "Leave days count working days only - weekends excluded automatically"
- ✅ Clear indication in all help text
- ✅ Real-time preview shows working days

### **Admin Leave Creation Form**

**Enhanced Display:**
```
📊 Total Working Days: X working day(s) (weekends excluded)
```

**Features:**
- ✅ Auto-updates on date selection
- ✅ Shows leave balance comparison
- ✅ Clear weekend exclusion note

---

## 🎓 **Benefits**

### **For Staff:**
1. ✅ **Fair Leave Counting** - Only work days are deducted from balance
2. ✅ **Clear Visibility** - See exactly how many days you're requesting
3. ✅ **No Surprises** - Real-time calculation before submission

### **For HR/Admin:**
1. ✅ **Accurate Tracking** - Leave balances reflect actual working days
2. ✅ **Easy Management** - Auto-calculation reduces errors
3. ✅ **Better Planning** - Clear visibility of staff availability

### **For Organization:**
1. ✅ **Industry Standard** - Aligns with global HR best practices
2. ✅ **Consistent** - Same calculation everywhere in the system
3. ✅ **Transparent** - Staff understand how leave is counted

---

## 🧪 **Testing**

### **Test Case 1: Normal Week (Mon-Fri)**
```
Input:  Start = Monday, End = Friday
Expect: 5 working days
Result: ✅ Pass
```

### **Test Case 2: Including Weekend**
```
Input:  Start = Friday, End = Monday
Expect: 2 working days (Fri + Mon, weekend excluded)
Result: ✅ Pass
```

### **Test Case 3: Full Week**
```
Input:  Start = Monday, End = Sunday
Expect: 5 working days
Result: ✅ Pass
```

### **Test Case 4: Weekend Only**
```
Input:  Start = Saturday, End = Sunday
Expect: 0 working days
Result: ✅ Pass
```

---

## 🔍 **Technical Details**

### **Day of Week Values (Python)**
```python
Monday    = 0
Tuesday   = 1
Wednesday = 2
Thursday  = 3
Friday    = 4
Saturday  = 5  ← Weekend (excluded)
Sunday    = 6  ← Weekend (excluded)
```

### **Day of Week Values (JavaScript)**
```javascript
Sunday    = 0  ← Weekend (excluded)
Monday    = 1
Tuesday   = 2
Wednesday = 3
Thursday  = 4
Friday    = 5
Saturday  = 6  ← Weekend (excluded)
```

**Note:** Python and JavaScript use different indexing for days!

---

## 📱 **SMS Notifications**

When leave is approved/rejected, the SMS shows **working days**:

```
✅ APPROVED: Your leave request (LVE20251104...) for 
5 working days from 2025-11-04 to 2025-11-08 has been approved.
```

**Key Point:** The number shown in SMS is **working days only**.

---

## 🚀 **Future Enhancements (Optional)**

### **Public Holidays Integration**
```python
# Could add public holiday exclusion:
def calculate_working_days_with_holidays(start, end):
    days = calculate_working_days(start, end)
    holidays = get_public_holidays_between(start, end)
    return days - len(holidays)
```

### **Custom Work Schedules**
```python
# Could support custom work weeks (e.g., Sun-Thu in Middle East):
def calculate_working_days_custom(start, end, work_days=[0,1,2,3,4]):
    # work_days = list of working weekday numbers
    pass
```

---

## ✅ **Status: FULLY IMPLEMENTED**

- ✅ Backend calculation method
- ✅ Staff self-service form (backend + frontend)
- ✅ Admin manual leave form (backend + frontend)
- ✅ Real-time JavaScript preview
- ✅ User interface updates and info boxes
- ✅ Consistent across all leave creation points

---

## 📞 **Support**

For questions or issues with leave calculation:
1. Check the help text in the form
2. Contact HR department
3. Review this documentation

**Remember:** Only Monday-Friday count as working days. Weekends are always excluded! 📅✨

































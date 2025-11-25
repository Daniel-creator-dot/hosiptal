# ✅ Leave Approval - View All Statuses Feature

## 🎯 **What's New**

You can now easily view **all leave request statuses** with a beautiful, intuitive filter system!

### **Quick Status Tabs:**
- 🟡 **Pending** - Awaiting approval
- 🟢 **Approved** - Already approved leaves
- 🔴 **Rejected** - Declined requests
- ⚫ **Cancelled** - Cancelled by staff/admin
- 🔵 **All** - Every leave request

**Each tab shows a badge with the count!**

---

## 🎨 **New User Interface**

### **Before:**
- Dropdown filter (hard to see counts)
- Only showed pending by default
- No visual indication of counts

### **After:**
```
┌─────────────────────────────────────────────────────────┐
│  [Pending 5] [Approved 12] [Rejected 2] [Cancelled 1] [All 20]  │
└─────────────────────────────────────────────────────────┘
```

**Features:**
✅ One-click filtering  
✅ Color-coded buttons  
✅ Live counts for each status  
✅ Active tab highlighted  
✅ Responsive design  

---

## 📍 **How to Use**

### **Access the Page:**
```
http://127.0.0.1:8000/hms/hr/leave/approvals/
```

### **Filter by Status:**

#### **View Pending Leaves (Default):**
- Page loads showing pending requests automatically
- Click **"Pending"** button (yellow) anytime to return

#### **View Approved Leaves:**
- Click the green **"Approved"** button
- See all approved leave requests
- Each shows:
  - ✅ Staff name & department
  - ✅ Leave type & dates
  - ✅ Number of working days
  - ✅ Who approved it
  - ✅ When it was approved

#### **View Rejected Leaves:**
- Click the red **"Rejected"** button
- See all rejected requests with rejection reasons

#### **View Cancelled Leaves:**
- Click the grey **"Cancelled"** button
- See all cancelled requests

#### **View All Leaves:**
- Click the blue **"All"** button
- See every leave request regardless of status

---

## 🔍 **What You Can See**

### **For Each Leave Request:**

| Column | Information |
|--------|-------------|
| **Request #** | Unique leave request number (e.g., LVE20251103...) |
| **Staff Name** | Full name + profession |
| **Department** | Staff's department |
| **Leave Type** | Annual, Sick, Maternity, etc. |
| **Start Date** | First day of leave |
| **End Date** | Last day of leave |
| **Days** | Working days (weekends excluded!) |
| **Status** | Color-coded badge |
| **Actions** | View details / Approve / Reject buttons |

---

## 🎭 **Actions by Status**

### **Pending Requests:**
```
[✓ Approve] [✗ Reject] [👁 Details]
```
- ✅ **Approve** - Approve the leave (sends SMS)
- ❌ **Reject** - Reject with reason (sends SMS)
- 👁️ **Details** - View full information

### **Approved/Rejected/Cancelled:**
```
[👁 View]
```
- 👁️ **View** - See full details and history

---

## 📊 **Status Counts**

Each filter button shows a **live count badge**:

```
Pending [5]    - 5 requests awaiting decision
Approved [12]  - 12 approved leaves
Rejected [2]   - 2 rejected requests
Cancelled [1]  - 1 cancelled leave
All [20]       - 20 total requests
```

**Counts update automatically after approving/rejecting!**

---

## 🎯 **Use Cases**

### **As a Manager:**

#### **Daily Morning Routine:**
1. Go to: `http://127.0.0.1:8000/hms/hr/leave/approvals/`
2. Check **Pending** tab (default view)
3. Review and approve/reject new requests
4. Click **Approved** to confirm processed leaves

#### **Monthly Review:**
1. Click **"All"** button
2. Review all leave patterns
3. Export data if needed
4. Check department leave balance

#### **Audit Trail:**
1. Click **"Approved"** to see who you approved
2. Click **"Rejected"** to review rejection reasons
3. Verify compliance with leave policies

---

## 💡 **Tips**

### **Tip 1: Quick Access**
Bookmark different status views:
```
Pending:   http://127.0.0.1:8000/hms/hr/leave/approvals/?status=pending
Approved:  http://127.0.0.1:8000/hms/hr/leave/approvals/?status=approved
All:       http://127.0.0.1:8000/hms/hr/leave/approvals/?status=all
```

### **Tip 2: Department Filtering**
- **Admins/Superusers:** See all departments
- **Department Managers:** Only see your department's requests

### **Tip 3: Sorting**
All requests are sorted by **submission date** (newest first)

### **Tip 4: Count Badge**
Use the count badges to prioritize:
- High **Pending** count = Need to review urgently
- High **Approved** count = Good response time

---

## 🎨 **Color Coding**

### **Status Badges in Table:**
- 🟡 **Yellow** = Pending (warning - needs action)
- 🟢 **Green** = Approved (success)
- 🔴 **Red** = Rejected (danger)
- ⚫ **Grey** = Cancelled (secondary)
- 🔵 **Blue** = Draft (info)

### **Filter Buttons:**
- **Active tab:** Solid color with white text
- **Inactive tabs:** Outline style with colored border

---

## 📱 **Mobile Responsive**

The filter tabs stack vertically on mobile devices:
```
┌──────────────┐
│ Pending [5]  │
├──────────────┤
│ Approved [12]│
├──────────────┤
│ Rejected [2] │
├──────────────┤
│ Cancelled [1]│
├──────────────┤
│ All [20]     │
└──────────────┘
```

---

## 🔧 **Technical Details**

### **View Logic:**
- Default filter: `pending`
- URL parameter: `?status=approved`
- Query optimization: Uses `select_related()` for performance
- Department filtering: Automatic based on user role

### **Counts:**
- Real-time calculation
- Filtered by department (if manager)
- Cached per request (no extra queries)

### **Files Modified:**
1. ✅ `hospital/views_hr.py` - Enhanced `leave_approval_list()` view
2. ✅ `hospital/templates/hospital/leave_approval_list.html` - New tab UI

---

## ✅ **Status: LIVE**

✅ View pending leaves  
✅ View approved leaves  
✅ View rejected leaves  
✅ View cancelled leaves  
✅ View all leaves  
✅ Live count badges  
✅ Color-coded interface  
✅ Mobile responsive  
✅ Department filtering  
✅ One-click switching  

**Ready to use now!** 🚀

---

## 🎯 **Quick Start**

**1. Go to leave approvals:**
```
http://127.0.0.1:8000/hms/hr/leave/approvals/
```

**2. Click the green "Approved" button**

**3. See all approved leaves!** ✅

---

## 📞 **Examples**

### **Example 1: View This Month's Approved Leaves**
```
1. Go to: /hms/hr/leave/approvals/
2. Click "Approved" button (green)
3. See all approved leaves sorted by date
4. Review who's on leave and when
```

### **Example 2: Find a Specific Rejected Request**
```
1. Go to: /hms/hr/leave/approvals/
2. Click "Rejected" button (red)
3. Browse the list
4. Click "View" to see rejection reason
```

### **Example 3: Monthly Report**
```
1. Click "All" button
2. See complete leave history
3. Export to Excel (if needed)
4. Analyze patterns
```

---

**Now you have complete visibility of all leave requests! 🎉**

































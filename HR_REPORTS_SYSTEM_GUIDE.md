# 📊 **HR Reports & Analytics System - Complete Guide**

## ✅ **SYSTEM CREATED & READY!**

A comprehensive HR Reports system has been created where **ALL HR reports are centralized in one place**.

---

## 🎯 **Main HR Reports Dashboard**

### **Access URL:**
```
http://127.0.0.1:8000/hms/hr/reports/
```

### **Or From HR Dashboard:**
1. Go to: `http://127.0.0.1:8000/hms/hr/`
2. Click the green **"HR Reports & Analytics"** button in Quick Actions

---

## 📋 **Available Reports**

### **1. Staff List Report** 📑
**URL:** `/hms/hr/reports/staff/`

**Features:**
- ✅ Complete staff directory
- ✅ Filter by Department
- ✅ Filter by Profession  
- ✅ Filter by Status (Active/Inactive)
- ✅ Export to CSV or Excel

**Shows:**
- Employee ID
- Name
- Department
- Profession
- Email
- Phone
- Date Joined
- Status
- Actions (View Details)

---

### **2. Leave Report** 📅
**URL:** `/hms/hr/reports/leave/`

**Features:**
- ✅ All leave requests with status
- ✅ Filter by Status (Pending/Approved/Rejected)
- ✅ Filter by Leave Type
- ✅ Filter by Department
- ✅ Filter by Date Range
- ✅ Export to CSV or Excel
- ✅ Summary cards (Pending, Approved, Rejected, Total Days)

**Shows:**
- Request Number
- Staff Name
- Department
- Leave Type
- Start & End Dates
- Working Days (weekends excluded!)
- Status
- Approved By & Date

---

### **3. Attendance Report** ⏰
**URL:** `/hms/hr/reports/attendance/`

**Features:**
- ✅ Daily attendance records
- ✅ Filter by Date Range
- ✅ Filter by Department
- ✅ Export to CSV
- ✅ Summary cards (Present, Absent, Late)

**Shows:**
- Date
- Staff Name
- Department
- Check In Time
- Check Out Time
- Status (Present/Absent/Late)
- Notes

---

### **4. Payroll Report** 💰
**URL:** `/hms/hr/reports/payroll/`

**Features:**
- ✅ Salary payments summary
- ✅ Filter by Payroll Period
- ✅ Filter by Department
- ✅ Export to CSV
- ✅ Summary cards (Total Gross, Deductions, Net Pay)

**Shows:**
- Employee ID
- Staff Name
- Department
- Gross Pay
- Total Deductions
- Net Pay
- Payment Status

---

### **5. Training Report** 📚
**URL:** `/hms/hr/reports/training/`

**Features:**
- ✅ Staff training records
- ✅ Filter by Year
- ✅ Filter by Department
- ✅ Export to CSV
- ✅ Summary cards (Total Trainings, Completed)

**Shows:**
- Staff Name
- Department
- Training Title
- Training Type
- Date
- Duration (hours)
- Provider
- Status

---

### **6. Performance Report** ⭐
**URL:** `/hms/hr/reports/performance/`

**Features:**
- ✅ Performance reviews and ratings
- ✅ Filter by Year
- ✅ Filter by Department
- ✅ Export to CSV
- ✅ Summary cards (Total Reviews, Average Rating)

**Shows:**
- Staff Name
- Department
- Review Date
- Review Period
- Overall Rating (out of 5)
- Reviewer
- Recommendation

---

## 🎨 **HR Reports Dashboard Features**

### **Summary Cards (Top of Dashboard):**
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ Total Staff │ Pending     │ On Leave    │ Contracts   │
│     31      │ Leaves      │ Today       │ Expiring    │
│             │     2       │     0       │     1       │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

### **Report Categories (Color-Coded Cards):**
- 🔵 **Staff Reports** - Blue card with staff count
- 🟢 **Leave Reports** - Green card with leave stats
- 🔷 **Attendance Reports** - Cyan card
- 🟡 **Payroll Reports** - Yellow card with total amount
- ⚫ **Training Reports** - Grey card with training count
- 🔴 **Performance Reports** - Red card with review count

### **Quick Stats:**
- Staff by Department (Top 10)
- Staff by Profession (Top 10)

---

## 📥 **Export Features**

### **Available Export Formats:**

#### **CSV Export (Always Available):**
- Click "Export" button
- Select "CSV Format"
- Downloads instantly
- Opens in Excel, Google Sheets, etc.

#### **Excel Export (If openpyxl installed):**
- Click "Export" button
- Select "Excel Format"
- Downloads .xlsx file
- Professional formatting
- Auto-adjusted column widths
- Styled headers

### **To Install Excel Support:**
```bash
pip install openpyxl
```

---

## 🎯 **How to Use**

### **Step 1: Access HR Reports**

**Option A - From HR Dashboard:**
1. Go to: `http://127.0.0.1:8000/hms/hr/`
2. Look in "Quick Actions" section
3. Click green **"HR Reports & Analytics"** button

**Option B - Direct URL:**
```
http://127.0.0.1:8000/hms/hr/reports/
```

### **Step 2: Choose a Report**
Click on any of the 6 report cards:
- Staff List Report
- Leave Report
- Attendance Report
- Payroll Report
- Training Report
- Performance Report

### **Step 3: Apply Filters** (Optional)
Each report has relevant filters:
- Department
- Date Range
- Status
- Year
- etc.

### **Step 4: Export** (Optional)
Click the "Export" dropdown and choose format:
- CSV (always available)
- Excel (if installed)

---

## 📊 **Use Cases**

### **Use Case 1: Monthly HR Review**
```
1. Go to HR Reports Dashboard
2. Check summary cards for overview
3. Click "Leave Report"
4. Filter by current month
5. Export to Excel
6. Review with management
```

### **Use Case 2: Department Analysis**
```
1. Go to "Staff List Report"
2. Filter by specific department
3. Export staff list
4. Go to "Performance Report"
5. Filter same department
6. Compare performance ratings
```

### **Use Case 3: Payroll Audit**
```
1. Go to "Payroll Report"
2. Select specific period
3. Review totals (Gross, Deductions, Net)
4. Filter by department if needed
5. Export to CSV for accounting
```

### **Use Case 4: Training Compliance**
```
1. Go to "Training Report"
2. Filter by current year
3. Check completed vs total
4. Export list of staff needing training
```

### **Use Case 5: Leave Planning**
```
1. Go to "Leave Report"
2. Filter "Approved" status
3. Check upcoming approved leaves
4. Plan staffing accordingly
```

---

## 🎨 **Visual Features**

### **Dashboard:**
- Color-coded report cards
- Interactive hover effects
- Badge counts on each card
- Quick stats tables
- Responsive design

### **Individual Reports:**
- Summary cards at top
- Filter section (collapsible cards)
- Export dropdown buttons
- Sortable data tables
- Status badges (color-coded)
- Empty state messages with icons
- Breadcrumb navigation

---

## 🔐 **Security & Permissions**

### **Who Can Access:**
- ✅ **HR Staff** - Full access to all reports
- ✅ **Admin/Superuser** - Full access to all reports
- ❌ **Other Staff** - No access (redirected to login)

### **Department Filtering:**
- **Superusers:** See ALL departments
- **Department Managers:** See their department only (where applicable)

---

## 📁 **Files Created**

### **Backend:**
```
hospital/views_hr_reports.py
  - hr_reports_dashboard()
  - staff_list_report()
  - leave_report()
  - attendance_report()
  - payroll_report()
  - training_report()
  - performance_report()
  - Export functions (CSV/Excel)
```

### **Frontend Templates:**
```
hospital/templates/hospital/hr_reports_dashboard.html
hospital/templates/hospital/reports/staff_list_report.html
hospital/templates/hospital/reports/leave_report.html
hospital/templates/hospital/reports/attendance_report.html
hospital/templates/hospital/reports/payroll_report.html
hospital/templates/hospital/reports/training_report.html
hospital/templates/hospital/reports/performance_report.html
```

### **URLs:**
```
/hms/hr/reports/                 - Main Dashboard
/hms/hr/reports/staff/            - Staff List
/hms/hr/reports/leave/            - Leave Report
/hms/hr/reports/attendance/       - Attendance Report
/hms/hr/reports/payroll/          - Payroll Report
/hms/hr/reports/training/         - Training Report
/hms/hr/reports/performance/      - Performance Report
```

---

## ✅ **Status: FULLY OPERATIONAL**

✅ Main HR Reports Dashboard created  
✅ 6 comprehensive reports ready  
✅ Export functionality (CSV/Excel)  
✅ Filtering on all reports  
✅ Summary cards with statistics  
✅ Mobile-responsive design  
✅ Secure (HR/Admin only)  
✅ Added to HR Dashboard (green button)  
✅ All URLs configured  
✅ System check passed - no errors  

---

## 🚀 **Try It Now!**

### **Quick Start:**
1. Go to: `http://127.0.0.1:8000/hms/hr/`
2. Click **"HR Reports & Analytics"** (green button)
3. Explore the 6 available reports
4. Try filtering and exporting!

---

## 💡 **Tips**

1. **Bookmark the Dashboard:**
   ```
   http://127.0.0.1:8000/hms/hr/reports/
   ```

2. **Use Filters First:**
   - Apply filters before exporting
   - Exports use the filtered data

3. **Export Regularly:**
   - Monthly staff reports
   - Quarterly training compliance
   - Annual performance summaries

4. **Compare Across Departments:**
   - Use department filter
   - Export each department separately
   - Compare metrics

5. **Date Ranges Matter:**
   - Leave Report: Use date range for specific periods
   - Attendance: Check weekly/monthly patterns

---

## 📞 **Support**

**If reports aren't showing data:**
1. Check that you have data in the system
2. Try clearing filters
3. Check date ranges
4. Verify you have proper permissions

**For Excel export issues:**
```bash
pip install openpyxl
```

---

**All HR reports are now centralized in one professional dashboard!** 📊✨

**Access it from HR Dashboard → "HR Reports & Analytics" button** 🎯

































# Admin Leave Management - Put Staff on Leave

## 🎯 **Admin Manual Leave Creation Feature**

As an admin, you can now **manually create and manage leave requests** for any staff member directly!

---

## 🚀 **How to Access**

### **Method 1: From HR Dashboard**
```
1. Login as Admin
2. Go to: http://127.0.0.1:8000/hms/hr/
3. Click the YELLOW button: "Put Staff on Leave"
```

### **Method 2: Direct URL**
```
http://127.0.0.1:8000/hms/hr/leave/create-for-staff/
```

### **Method 3: From Leave Approvals**
```
1. Go to: http://127.0.0.1:8000/hms/hr/leave/approvals/
2. Click: "Create Leave for Staff" button
```

---

## 📋 **Step-by-Step Process**

### **Step 1: Select Staff Member**
- Dropdown shows all active staff
- **Organized by department** for easy finding
- Each option shows:
  - Staff name
  - Profession (Doctor, Nurse, etc.)
  - Department

**Example:**
```
John Doe - Doctor (Emergency Department)
Jane Smith - Nurse (ICU)
```

### **Step 2: View Leave Balance (Auto-displayed)**
When you select a staff member, their current leave balance appears:
```
Leave Balance:
Annual: 15 days | Sick: 10 days | Casual: 5 days
```

### **Step 3: Select Leave Type**
Choose from **10 leave types**, organized in categories:

**Regular Leave:**
- 📅 Annual Leave (Vacation)
- 🏥 Sick Leave (Medical)
- ☕ Casual Leave (Personal)

**Special Leave:**
- 🚨 Emergency Leave
- 👶 Maternity Leave
- 👨‍👦 Paternity Leave
- 🕊️ Bereavement Leave
- 📚 Study Leave

**Other:**
- ⏰ Compensatory Leave (Time Off)
- 💼 Unpaid Leave

### **Step 4: Choose Dates**
- **Start Date**: First day of leave
- **End Date**: Last day of leave (inclusive)

**Auto-calculation:**
- System automatically calculates total days
- Shows: "📊 Total Days: X day(s)"

### **Step 5: Provide Reason**
Enter a detailed reason:
```
Example: "Family emergency - father hospitalized"
Example: "Medical procedure scheduled"
Example: "Annual vacation - approved by department head"
```

### **Step 6: Admin Options**

**⚡ Auto-Approve Option:**
- ✅ **Checked**: Leave immediately approved, no workflow
- ❌ **Unchecked**: Leave created as "Pending", goes through normal approval

**When to Auto-Approve:**
- Emergency situations
- Compassionate leave
- Pre-approved requests
- Medical emergencies
- Management-directed leave

**When NOT to Auto-Approve:**
- Regular vacation requests
- When you want manager to review
- When coverage needs to be arranged

### **Step 7: Submit**
Click **"Create Leave Request"** button

**Result:**
- Leave request created ✅
- If auto-approved: Status = Approved, balance deducted
- If not: Status = Pending, awaits approval
- Staff can see it in their dashboard

---

## 💡 **Use Cases & Examples**

### **Example 1: Emergency Medical Leave**
```
Staff: Dr. John Doe
Situation: Sudden illness, needs immediate sick leave
Action: Create sick leave + Auto-approve ✅
Days: 3 days
Reason: "Acute illness - unable to work"
Result: Immediately approved, balance deducted
```

### **Example 2: Planned Maternity Leave**
```
Staff: Nurse Jane Smith
Situation: Maternity leave starting next month
Action: Create maternity leave (No auto-approve)
Days: 90 days
Reason: "Maternity leave as per policy"
Result: Created as pending for HR review
```

### **Example 3: Compassionate Leave**
```
Staff: Lab Tech Bob Johnson
Situation: Family bereavement
Action: Create bereavement leave + Auto-approve ✅
Days: 5 days
Reason: "Family bereavement - father passed away"
Result: Immediately approved
```

### **Example 4: Study Leave for Conference**
```
Staff: Dr. Sarah Williams
Situation: Attending medical conference
Action: Create study leave (No auto-approve)
Days: 3 days
Reason: "Attending cardiology conference in Accra"
Result: Pending for department head approval
```

---

## 🎨 **Interface Features**

### **Smart Staff Selection:**
- Grouped by department
- Searchable dropdown
- Shows profession and department
- Easy to find staff

### **Real-Time Leave Balance Display:**
- Shows immediately when staff selected
- Color-coded badges:
  - Blue = Annual leave
  - Green = Sick leave
  - Info = Casual leave

### **Auto-Calculate Days:**
- Enter start and end dates
- System calculates total days
- Shows before submission
- No manual calculation needed

### **Visual Indicators:**
- ⚠️ Yellow "Put Staff on Leave" button (prominent)
- ⚡ Auto-approve toggle (large switch)
- 📊 Days calculator
- Color-coded balances

---

## 🔐 **Security & Permissions**

**Who Can Access:**
- ✅ Admin users (is_staff=True)
- ✅ HR group members
- ❌ Regular staff (cannot access)
- ❌ Managers (can only approve, not create)

**What They Can Do:**
- Create leave for ANY staff member
- Auto-approve immediately
- Override leave balance limits
- Create backdated leave (if needed)

---

## 📊 **Admin vs Staff Request Comparison**

| Feature | Staff Request | Admin Create |
|---------|---------------|--------------|
| Who creates | Staff themselves | Admin/HR |
| For whom | Own leave | Any staff |
| Auto-approve | No | Yes (option) |
| Balance check | Enforced | Advisory |
| Workflow | Must submit | Can skip |
| Backdating | Not allowed | Allowed |
| Attachments | Can upload | Not required |

---

## 🔄 **Workflow Options**

### **Option A: With Approval Workflow**
```
Admin creates leave
    ↓
Status: Pending
    ↓
Manager approves
    ↓
Status: Approved
    ↓
Balance deducted
```

### **Option B: Auto-Approve (Immediate)**
```
Admin creates leave + Auto-approve ✅
    ↓
Status: Approved (immediately)
    ↓
Balance deducted (immediately)
    ↓
Staff can see approved leave
```

---

## ⚠️ **Important Notes**

### **Balance Handling:**
1. System **shows** leave balance for reference
2. Admin **can create** even if balance is insufficient
3. Balance **only deducted** when approved
4. Unpaid/special leaves **don't** affect balance

### **Staff Notification:**
1. Staff sees leave in their dashboard
2. Status shows "Created by Admin"
3. Staff cannot edit admin-created leaves
4. Staff can view details

### **Best Practices:**
1. ✅ Always provide clear reason
2. ✅ Check balance before approving
3. ✅ Use auto-approve for emergencies only
4. ✅ Let workflow handle routine requests
5. ✅ Document special circumstances

---

## 🆘 **Common Scenarios**

### **Scenario 1: Emergency Medical Leave**
```
When: Staff falls ill and cannot login
Action: 
1. Admin creates sick leave
2. Select dates based on medical note
3. Auto-approve ✅
4. Notify staff
```

### **Scenario 2: Maternity Leave (Planned)**
```
When: Staff going on maternity leave
Action:
1. Create maternity leave (90 days)
2. Do NOT auto-approve
3. Let HR verify and approve
4. Arrange coverage
```

### **Scenario 3: Bereavement Leave**
```
When: Staff has family emergency
Action:
1. Create bereavement leave
2. Auto-approve ✅ (compassionate)
3. Grant 3-5 days
4. Follow up with staff
```

### **Scenario 4: Backdated Leave**
```
When: Staff was sick but forgot to request
Action:
1. Create sick leave with past dates
2. Add reason: "Backdated - was sick"
3. Auto-approve ✅
4. Adjust balance manually if needed
```

---

## 📱 **Quick Access Locations**

The "Put Staff on Leave" feature is accessible from:

1. **HR Dashboard** (Main button - Yellow/Warning colored)
   ```
   http://127.0.0.1:8000/hms/hr/
   ```

2. **Leave Approval List** (Top right button)
   ```
   http://127.0.0.1:8000/hms/hr/leave/approvals/
   ```

3. **Direct Link** (Bookmark this!)
   ```
   http://127.0.0.1:8000/hms/hr/leave/create-for-staff/
   ```

---

## 💡 **Pro Tips for Admins**

### **Tip 1: Check Balance First**
```
Select staff → See balance → Decide leave type
```

### **Tip 2: Use Auto-Approve Wisely**
```
✅ Emergency: Auto-approve
✅ Bereavement: Auto-approve
❌ Vacation: Use workflow
❌ Study leave: Use workflow
```

### **Tip 3: Calculate Days**
```
Enter dates → See auto-calculated days → Verify before submit
```

### **Tip 4: Document Well**
```
Always provide detailed reason
Staff will see this reason
Future reference for records
```

### **Tip 5: Department Organization**
```
Staff grouped by department in dropdown
Easy to find specific staff
Can filter visually
```

---

## 🎓 **Training Guide**

### **For HR Staff:**

**Daily Tasks:**
1. Check HR Dashboard
2. Review pending leave requests
3. Create emergency leaves as needed
4. Monitor leave balances

**Emergency Protocol:**
1. Receive emergency notification
2. Go to "Put Staff on Leave"
3. Select staff
4. Create leave with auto-approve
5. Inform relevant parties

**Monthly Tasks:**
1. Review all leave requests
2. Verify balances
3. Plan coverage
4. Generate reports

---

## 📊 **Reports & Tracking**

**After Creating Leave:**
- View in "All Leave Requests"
- Track approval status
- Monitor balance impact
- Generate leave reports

**Staff Can See:**
- Leave appears in their dashboard
- Can view details
- Cannot edit
- Shows "Admin Created"

---

## ✅ **Feature Checklist**

What admins can do:
- [x] Select any staff member
- [x] View their leave balance
- [x] Choose any leave type
- [x] Set any dates (including backdated)
- [x] Auto-approve immediately
- [x] Or send for approval workflow
- [x] See auto-calculated days
- [x] Create without balance limits
- [x] Grouped staff by department

---

## 🎉 **Summary**

**You Now Have:**
✅ **Easy Access** - Yellow button on HR Dashboard  
✅ **Staff Selection** - Grouped by department  
✅ **Balance Display** - Shows real-time balances  
✅ **Auto-Approve** - Skip workflow for emergencies  
✅ **Day Calculator** - Auto-calculates leave days  
✅ **All Leave Types** - 10 types with icons  
✅ **Smart Interface** - Professional, easy to use  

**Access Now:**
👉 http://127.0.0.1:8000/hms/hr/leave/create-for-staff/

**Or from HR Dashboard:**
👉 http://127.0.0.1:8000/hms/hr/
(Click the yellow "Put Staff on Leave" button)

---

**Your admin leave creation feature is ready to use!** 🎊

**Version**: 1.0  
**Status**: ✅ Production Ready  
**Updated**: November 2025

































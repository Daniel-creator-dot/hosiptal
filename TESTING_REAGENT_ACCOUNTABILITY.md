# 🧪 Testing Reagent Accountability System

## ✅ **To See the Changes:**

### **1. Clear Browser Cache**
- Press `Ctrl + Shift + R` (Windows) or `Cmd + Shift + R` (Mac) to hard refresh
- Or clear browser cache completely

### **2. Login as Lab Technician**
- Login with a user that has `profession = 'lab_technician'`
- Go to: `/hms/lab/reagents/transaction/`

### **3. What You Should See:**

#### **If logged in as Lab Technician:**
- ✅ **Yellow warning banner** at top: "Accountability Required"
- ✅ **Transaction Type** dropdown is **DISABLED** and locked to "Used"
- ✅ **Accountability Section** is **VISIBLE** (yellow background)
- ✅ **Patient Selection** section with searchable patient list
- ✅ **Lab Result Selection** section (optional)
- ✅ **Purpose field** (required, with placeholder text)

#### **If logged in as Inventory Manager/Admin:**
- ✅ **Transaction Type** dropdown is **ENABLED** with all options
- ✅ **Accountability Section** appears when "Used" is selected
- ✅ Can select other transaction types (Received, Expired, etc.)

### **4. Test the Restrictions:**

**As Lab Technician:**
1. Try to change transaction type → Should be disabled
2. Try to submit without patient → Should show error
3. Try to submit without purpose → Should show error
4. Try to use more than available → Should show validation error

**As Inventory Manager:**
1. Can select "Received" → No accountability section
2. Can select "Used" → Accountability section appears
3. Can add quantities freely

### **5. Verify Database:**
After recording a transaction, check:
```python
from hospital.models_lab_management import ReagentTransaction
transaction = ReagentTransaction.objects.latest('created')
print(f"Patient: {transaction.patient}")
print(f"Purpose: {transaction.purpose}")
print(f"Lab Result: {transaction.lab_result}")
print(f"Performed By: {transaction.performed_by}")
```

---

## 🔍 **Troubleshooting:**

### **If you don't see the changes:**

1. **Check your user role:**
   ```python
   # In Django shell
   from hospital.models import Staff
   staff = Staff.objects.get(user__username='YOUR_USERNAME')
   print(staff.profession)  # Should be 'lab_technician'
   ```

2. **Check template is loading:**
   - View page source → Look for "Accountability Required" text
   - Check browser console for JavaScript errors

3. **Check server logs:**
   ```bash
   docker-compose logs web --tail 100
   ```

4. **Force template reload:**
   - Restart Django server
   - Clear Django template cache (if using)

---

## 📋 **Quick Test Checklist:**

- [ ] Logged in as lab technician
- [ ] Navigate to `/hms/lab/reagents/transaction/`
- [ ] See yellow warning banner
- [ ] Transaction type is disabled/locked
- [ ] Accountability section is visible
- [ ] Patient list is shown
- [ ] Purpose field is visible and required
- [ ] Cannot submit without patient
- [ ] Cannot submit without purpose

---

**If still not working, please provide:**
1. Your user's profession (from Staff model)
2. Browser console errors (F12 → Console)
3. Any error messages on the page











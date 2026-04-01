# 👨‍⚕️ Add Dr. Kwadwo Ayisi - Medical Director

## Quick Solution

You've already created a username and password. Now we need to add the complete staff profile. Here are **two easy options**:

---

## Option 1: Use the Script (Easiest) ✅

### Quick Add with Script

**Windows:**
```bash
ADD_DR_KWADWO_AYISI.bat
```

This will automatically:
- ✅ Find or create the user account
- ✅ Add all staff details
- ✅ Set Employee ID: SPE-DOC-0001
- ✅ Assign to Specialist Clinic department
- ✅ Set as Medical Director and Administrator
- ✅ Add admin privileges

**If you know the username you created:**
```bash
# Docker
docker-compose exec web python manage.py add_medical_director_kwadwo --username YOUR_USERNAME

# Local
python manage.py add_medical_director_kwadwo --username YOUR_USERNAME
```

**To update existing profile:**
```bash
docker-compose exec web python manage.py add_medical_director_kwadwo --username YOUR_USERNAME --update
```

---

## Option 2: Use Web Interface ✅

### Step-by-Step Guide

1. **Go to Staff Creation Form:**
   ```
   http://localhost:8000/hms/hr/staff/new/
   ```
   
   Or: HR Dashboard → "Add Staff" button

2. **Fill in the Form:**

   **Section 1: User Account**
   - **Username:** [The username you already created]
   - **Password:** [Leave blank if password already set]
   - **First Name:** `Kwadwo`
   - **Last Name:** `Ayisi`
   - **Email:** [Their email address]

   **Section 2: Employment Details**
   - **Employee ID:** `SPE-DOC-0001`
   - **Profession:** `Doctor`
   - **Department:** Select `Specialist Clinic` (or create if doesn't exist)
   - **Specialization:** `Medical Director and Administrator`
   - **Date of Joining:** [Today's date or start date]

   **Section 3: Personal Information**
   - **Date of Birth:** [Calculate: 68 years old = approximately 1956]
   - **Gender:** Select appropriate
   - **Phone Number:** `0246979797`

3. **Click "Save"**

4. **Set Admin Privileges:**
   - Go to: Admin → Users
   - Find the user
   - Check "Superuser status" and "Staff status"
   - Save

5. **Add to Groups:**
   - Still in the user edit page
   - Scroll to "Groups" section
   - Add to:
     - ✅ Admin
     - ✅ Medical Director
     - ✅ Doctor

---

## Option 3: Use Admin Interface ✅

### Django Admin Method

1. **Go to Admin:**
   ```
   http://localhost:8000/admin/
   ```

2. **Navigate to Staff:**
   - Click "Hospital" → "Staffs" → "Add Staff"

3. **Fill in Details:**
   - **User:** Select the user you created
   - **Employee ID:** `SPE-DOC-0001`
   - **Profession:** `Doctor`
   - **Department:** Specialist Clinic
   - **Phone Number:** `0246979797`
   - **Specialization:** `Medical Director and Administrator`
   - Fill other details as needed

4. **Save**

---

## ✅ What Will Be Added

### Staff Information:
- ✅ **Employee ID:** SPE-DOC-0001
- ✅ **Name:** Dr. Kwadwo Ayisi
- ✅ **Department:** Specialist Clinic
- ✅ **Profession:** Doctor
- ✅ **Position:** Medical Director and Administrator
- ✅ **Phone:** 0246979797
- ✅ **Age:** 68 years
- ✅ **All privileges:** Admin, Medical Director

### Privileges:
- ✅ Superuser access
- ✅ Staff access
- ✅ Admin group
- ✅ Medical Director group
- ✅ Doctor group
- ✅ Procurement approval permissions

---

## 🔍 Finding the User You Created

If you forgot the username, you can search:

```bash
# In Django shell
docker-compose exec web python manage.py shell

# Then run:
from django.contrib.auth.models import User
users = User.objects.filter(is_staff=True, is_active=True)
for u in users:
    print(f"Username: {u.username}, Name: {u.get_full_name()}, Email: {u.email}")
```

---

## ✅ Verification

After adding, verify everything is correct:

```bash
docker-compose exec web python manage.py shell -c "from hospital.models import Staff; staff = Staff.objects.filter(employee_id='SPE-DOC-0001').first(); print('✅ Found!' if staff else '❌ Not found'); print(f'Name: {staff.user.get_full_name() if staff else \"N/A\"}'); print(f'Department: {staff.department.name if staff and staff.department else \"N/A\"}'); print(f'Employee ID: {staff.employee_id if staff else \"N/A\"}')"
```

---

## 📝 Summary

**Recommended:** Use Option 1 (the script) - it's the fastest and most complete!

Just run:
```bash
ADD_DR_KWADWO_AYISI.bat
```

It will handle everything automatically! 🎉

---

**Date:** 2025-01-27  
**Status:** Ready to use





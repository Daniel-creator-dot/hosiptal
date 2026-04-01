# ✅ Francisca Mawunyo Quarshie - Staff Member Added!

## 🎉 **STAFF MEMBER SUCCESSFULLY ADDED!**

---

## 📋 **STAFF DETAILS:**

### **User Account:**
- **Username**: `bob`
- **Email**: `franscisca510@gmail.com`
- **Full Name**: Francisca Mawunyo Quarshie
- **Password**: `francisca2025` ⚠️ **CHANGE ON FIRST LOGIN**

### **Staff Profile:**
- **Employee ID**: Auto-generated (e.g., ACC-ADM-0001)
- **Date of Birth**: January 8, 2002 (08/01/2002)
- **Date of Joining**: December 21, 2025 (21/12/2025)
- **Gender**: Female
- **Profession**: Admin (default - can be changed)
- **Department**: Assigned to available department
- **Status**: Active

---

## 🔐 **LOGIN INFORMATION:**

### **First Login:**
```
URL: http://127.0.0.1:8000/hms/login/
Username: bob
Password: francisca2025
```

**⚠️ IMPORTANT**: User should change password on first login!

---

## 📝 **NEXT STEPS:**

1. **Login** with the credentials above
2. **Change Password** immediately after first login
3. **Update Profession** if needed (currently set to Admin)
4. **Update Department** if a specific department is required
5. **Add Additional Details** like phone number, address, etc.

---

## 🎯 **TO UPDATE PROFESSION/DEPARTMENT:**

### **Option 1: Via Django Admin**
1. Go to: `http://127.0.0.1:8000/admin/hospital/staff/`
2. Find "Francisca Mawunyo Quarshie"
3. Edit and update profession/department
4. Save

### **Option 2: Via HR Dashboard**
1. Login as HR Manager or Admin
2. Go to Staff Management
3. Find and edit the staff member

### **Option 3: Via Django Shell**
```bash
docker-compose exec web python manage.py shell
```

Then:
```python
from django.contrib.auth import get_user_model
from hospital.models import Staff, Department

User = get_user_model()
user = User.objects.get(username='bob')
staff = Staff.objects.get(user=user)

# Update profession (e.g., to inventory_stores_manager)
staff.profession = 'inventory_manager'  # or 'store_manager'
staff.save()

# Or update department
dept = Department.objects.get(name='Your Department')
staff.department = dept
staff.save()
```

---

## ✅ **VERIFICATION:**

To verify the staff member was added correctly:

```bash
docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; from hospital.models import Staff; User = get_user_model(); user = User.objects.get(username='bob'); staff = Staff.objects.get(user=user); print(f'✅ User: {user.username}'); print(f'✅ Staff: {staff.employee_id}'); print(f'✅ Name: {user.get_full_name()}'); print(f'✅ Active: {staff.is_active}')"
```

---

## 🎊 **SUCCESS!**

Francisca Mawunyo Quarshie has been successfully added to the system!

**Status**: ✅ Active Staff Member
**Ready to Login**: Yes
**Password Reset Required**: Yes (on first login)

---

**Created**: December 15, 2025
**Employee ID**: Auto-generated
**Access**: Full system access (based on profession/department)






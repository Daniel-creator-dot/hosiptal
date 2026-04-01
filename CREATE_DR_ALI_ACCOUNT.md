# ✅ Dr. Ali - Gynecologist Account Creation

## Account Details

**Name:** Dr. Ali  
**Specialty:** Gynecology  
**Date of Birth:** 23/06/1979  
**Username:** `dr.ali`  
**Password:** `dr.ali2025` (⚠️ **CHANGE ON FIRST LOGIN**)

## What Was Created

1. ✅ **User Account** - Django user with staff privileges
2. ✅ **Staff Profile** - Doctor profile linked to Medical Department
3. ✅ **Specialty** - Gynecology specialty (created if doesn't exist)
4. ✅ **Specialist Profile** - Links Dr. Ali to Gynecology specialty

## How to Run

### Option 1: Run the Script (When Database is Available)

```bash
python create_dr_ali_gynecologist.py
```

### Option 2: Manual Creation via Django Shell

If the script fails due to database connection, you can create the account manually:

1. Start Django shell:
```bash
python manage.py shell
```

2. Run these commands:

```python
from django.contrib.auth import get_user_model
from hospital.models import Staff, Department
from hospital.models_specialists import Specialty, SpecialistProfile
from datetime import date

User = get_user_model()

# 1. Create User
user, created = User.objects.get_or_create(
    username='dr.ali',
    defaults={
        'email': 'dr.ali@hospital.com',
        'first_name': 'Ali',
        'last_name': 'Gynecologist',
        'is_staff': True,
        'is_active': True,
    }
)
user.set_password('dr.ali2025')
user.save()

# 2. Get or Create Department
dept = Department.objects.filter(name__icontains='medical').first()
if not dept:
    dept = Department.objects.first()

# 3. Create Staff
staff, created = Staff.objects.get_or_create(
    user=user,
    defaults={
        'profession': 'doctor',
        'department': dept,
        'date_of_birth': date(1979, 6, 23),
        'specialization': 'Gynecology',
        'is_active': True,
    }
)

# 4. Get or Create Specialty
specialty, created = Specialty.objects.get_or_create(
    name='Gynecology',
    defaults={
        'code': 'GYN',
        'description': 'Gynecology and Obstetrics',
        'icon': 'bi-gender-female',
        'is_active': True,
    }
)

# 5. Create Specialist Profile
specialist, created = SpecialistProfile.objects.get_or_create(
    staff=staff,
    defaults={
        'specialty': specialty,
        'qualification': 'MBBS, MRCOG',
        'experience_years': 10,
        'consultation_fee': 100.00,
        'is_active': True,
    }
)

print(f"✅ Account created: {user.get_full_name()}")
print(f"   Username: {user.username}")
print(f"   Password: dr.ali2025")
print(f"   Specialty: {specialty.name}")
```

## Access Information

- **Login URL:** `/hms/login/`
- **Dashboard URL:** `/hms/specialists/my-dashboard/`
- **Username:** `dr.ali`
- **Password:** `dr.ali2025`

## Features Available

Once logged in, Dr. Ali will have access to:

1. ✅ **Specialist Dashboard** - Personalized dashboard with:
   - Pending referrals
   - Active referrals
   - Today's consultations
   - Today's appointments
   - Recent consultations
   - Statistics

2. ✅ **Referral Management** - View and manage patient referrals

3. ✅ **Patient Consultations** - Start new consultations

4. ✅ **Appointment Management** - View and manage appointments

## Important Notes

⚠️ **Security:** The default password should be changed immediately on first login.

📋 **Auto-Redirect:** When Dr. Ali logs in and accesses the main dashboard, he will be automatically redirected to his specialist dashboard.

🔐 **Password Reset:** If needed, password can be reset via the admin panel or password reset functionality.

## Verification

After creation, verify the account:

1. Check user exists: `User.objects.filter(username='dr.ali').exists()`
2. Check staff profile: `Staff.objects.filter(user__username='dr.ali').exists()`
3. Check specialist profile: `SpecialistProfile.objects.filter(staff__user__username='dr.ali').exists()`

## Troubleshooting

If you encounter database connection errors:
1. Ensure PostgreSQL is running
2. Check database credentials in `settings.py`
3. Verify database exists and is accessible
4. Try running via Django shell instead of standalone script





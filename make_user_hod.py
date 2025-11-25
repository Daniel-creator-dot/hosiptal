"""
Make a Staff Member an HOD
Simple script - just change the username and run
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Staff
from hospital.models_hod_simple import HeadOfDepartment

# ============================================
# CHANGE THIS USERNAME:
# ============================================
USERNAME_TO_MAKE_HOD = 'dorcas.adjei'  # <-- CHANGE THIS!
# ============================================

print(f"Making {USERNAME_TO_MAKE_HOD} an HOD...")

try:
    # Get the staff member
    staff = Staff.objects.get(user__username=USERNAME_TO_MAKE_HOD, is_active=True)
    
    # Check if already HOD
    if hasattr(staff, 'hod_designation'):
        print(f"[Already HOD] {staff.user.get_full_name()} is already HOD of {staff.department.name}")
    else:
        # Make them HOD
        hod = HeadOfDepartment.objects.create(
            staff=staff,
            department=staff.department,
            can_manage_schedules=True,
            can_approve_procurement=True,
            can_approve_leave=True,
            is_active=True
        )
        print(f"[SUCCESS] {staff.user.get_full_name()} is now HOD of {staff.department.name}!")
        print(f"")
        print(f"They can now:")
        print(f"  - Access HOD Scheduling at: http://localhost:8000/hms/hod/scheduling/")
        print(f"  - Create and manage staff shifts")
        print(f"  - Approve leave requests")
        print(f"  - Manage department schedules")
    
except Staff.DoesNotExist:
    print(f"[ERROR] Staff member '{USERNAME_TO_MAKE_HOD}' not found!")
    print(f"")
    print(f"Available staff usernames:")
    for s in Staff.objects.filter(is_active=True)[:20]:
        print(f"  - {s.user.username}")
except Exception as e:
    print(f"[ERROR] {str(e)}")

print("")
print("Current HODs:")
print("-" * 50)
hods = HeadOfDepartment.objects.filter(is_active=True, is_deleted=False)
for hod in hods:
    print(f"  {hod.staff.user.username:25} - {hod.department.name}")





















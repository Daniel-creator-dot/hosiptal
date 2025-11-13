"""
Setup Department Heads (HODs)
Designate staff members as Heads of Department
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Staff, Department
from hospital.models_hod_simple import HeadOfDepartment
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType


def setup_permissions():
    """Create necessary permissions"""
    from hospital.models_procurement import ProcurementRequest
    
    ct = ContentType.objects.get_for_model(ProcurementRequest)
    
    # Create permissions
    Permission.objects.get_or_create(
        codename='can_approve_procurement_admin',
        name='Can approve procurement at admin level',
        content_type=ct,
    )
    
    Permission.objects.get_or_create(
        codename='can_approve_procurement_accounts',
        name='Can approve procurement at accounts level',
        content_type=ct,
    )
    
    print("[OK] Permissions created")


def setup_hods():
    """Designate staff as HODs"""
    print("="*70)
    print("SETTING UP DEPARTMENT HEADS (HODs)")
    print("="*70)
    print()
    
    # Get all departments
    departments = Department.objects.all()
    
    if not departments.exists():
        print("[WARNING] No departments found. Please create departments first.")
        return
    
    print(f"Found {departments.count()} departments")
    print()
    
    created_count = 0
    
    for dept in departments:
        # Find senior staff in this department
        senior_staff = Staff.objects.filter(
            department=dept,
            is_active=True,
            is_deleted=False
        ).first()
        
        if senior_staff:
            # Check if already HOD
            if hasattr(senior_staff, 'hod_designation'):
                staff_name = f"{senior_staff.first_name} {senior_staff.last_name}" if hasattr(senior_staff, 'first_name') else str(senior_staff)
                print(f"[SKIP] {staff_name} already HOD of {dept.name}")
                continue
            
            # Create HOD role
            hod = HeadOfDepartment.objects.create(
                staff=senior_staff,
                department=dept,
                can_manage_schedules=True,
                can_approve_procurement=True,
                can_approve_leave=True,
                is_active=True
            )
            
            # Give user admin approval permission for procurement
            if senior_staff.user:
                admin_perm = Permission.objects.get(codename='can_approve_procurement_admin')
                senior_staff.user.user_permissions.add(admin_perm)
            
            staff_name = f"{senior_staff.first_name} {senior_staff.last_name}" if hasattr(senior_staff, 'first_name') else str(senior_staff)
            print(f"[OK] {staff_name} -> HOD of {dept.name}")
            created_count += 1
        else:
            print(f"[SKIP] No active staff found in {dept.name}")
    
    print()
    print("="*70)
    print(f"CREATED: {created_count} Department Heads")
    print("="*70)
    print()
    
    if created_count > 0:
        print("HODs can now:")
        print("  [OK] Create department timetables")
        print("  [OK] Assign staff shifts")
        print("  [OK] Upload duty rosters")
        print("  [OK] Approve procurement requests")
        print()
        print("Access HOD Dashboard:")
        print("  http://127.0.0.1:8000/hms/hod/scheduling/")
    
    print()


def main():
    print()
    setup_permissions()
    print()
    setup_hods()
    print()
    print("="*70)
    print("SETUP COMPLETE!")
    print("="*70)
    print()
    print("Next steps:")
    print("1. Restart server (if needed)")
    print("2. Login as HOD")
    print("3. Visit: http://127.0.0.1:8000/hms/hod/scheduling/")
    print("4. Create timetables and assign shifts!")
    print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


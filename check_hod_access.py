"""
Check HOD Access Script
Verifies that all 4 HODs can access shift/timetable features
"""

import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User
from hospital.models import Staff
from hospital.models_hod_simple import HeadOfDepartment

def check_hod_access(username):
    """Check if a user has HOD access"""
    try:
        user = User.objects.get(username=username)
        print(f"\n{'='*70}")
        print(f"Checking: {user.get_full_name()} ({username})")
        print(f"{'='*70}")
        
        # Check if user has staff record
        if not hasattr(user, 'staff'):
            print("  ❌ No staff record found!")
            return False
        
        staff = user.staff
        print(f"  ✅ Has staff record: {staff.user.get_full_name()}")
        print(f"  ✅ Department: {staff.department.name if staff.department else 'None'}")
        
        # Check if staff has HOD designation
        if not hasattr(staff, 'hod_designation'):
            print("  ❌ No HOD designation found!")
            return False
        
        hod = staff.hod_designation
        print(f"  ✅ Has HOD designation")
        print(f"  ✅ HOD Department: {hod.department.name}")
        print(f"  ✅ is_active: {hod.is_active}")
        print(f"  ✅ can_manage_schedules: {hod.can_manage_schedules}")
        print(f"  ✅ can_approve_procurement: {hod.can_approve_procurement}")
        print(f"  ✅ can_approve_leave: {hod.can_approve_leave}")
        
        # Test the is_hod function
        from hospital.views_hod_scheduling import is_hod
        is_hod_result = is_hod(user)
        print(f"  ✅ is_hod() function returns: {is_hod_result}")
        
        return is_hod_result
        
    except User.DoesNotExist:
        print(f"  ❌ User not found: {username}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*70)
    print(" " * 20 + "HOD ACCESS VERIFICATION")
    print("="*70)
    
    hods_to_check = [
        'gordon.boadu',
        'drnanakofi.yeboah',
        'mary.ellis',
        'evans.oseiasare',
    ]
    
    results = {}
    for username in hods_to_check:
        results[username] = check_hod_access(username)
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for username, has_access in results.items():
        status = "✅ HAS ACCESS" if has_access else "❌ NO ACCESS"
        user = User.objects.get(username=username)
        print(f"  {user.get_full_name()}: {status}")
    
    print(f"\n{'='*70}")
    print(f"Total with access: {sum(results.values())}/{len(results)}")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()

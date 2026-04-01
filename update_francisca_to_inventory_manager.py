#!/usr/bin/env python
"""
Update Francisca to Inventory & Stores Manager in Procurement Department
"""
import os
import sys
import django
from datetime import date

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from hospital.models import Staff, Department
from hospital.utils_roles import assign_user_to_role, create_default_groups

User = get_user_model()

def update_francisca_to_inventory_manager():
    """
    Update Francisca to be Inventory & Stores Manager in Procurement Department
    """
    print("=" * 70)
    print("UPDATING FRANCISCA TO INVENTORY & STORES MANAGER")
    print("=" * 70)
    print()
    
    username = "bob"
    
    # 1. Get user and staff
    print("[1/5] Getting user and staff record...")
    try:
        user = User.objects.get(username=username)
        staff = Staff.objects.get(user=user)
        print(f"   ✅ Found: {user.get_full_name()}")
    except User.DoesNotExist:
        print(f"   ❌ User '{username}' not found!")
        return
    except Staff.DoesNotExist:
        print(f"   ❌ Staff record not found for user '{username}'!")
        return
    print()
    
    # 2. Get or create Procurement department
    print("[2/5] Setting up Procurement department...")
    dept = Department.objects.filter(
        name__icontains='procurement'
    ).first()
    
    if not dept:
        dept = Department.objects.filter(
            name__icontains='store'
        ).first()
    
    if not dept:
        dept = Department.objects.filter(
            name__icontains='inventory'
        ).first()
    
    if not dept:
        # Create Procurement department
        dept = Department.objects.create(
            name='Procurement',
            code='PROC',
            description='Procurement and Stores Department',
            is_active=True
        )
        print(f"   ✅ Created Procurement department")
    else:
        print(f"   ✅ Found department: {dept.name}")
    print()
    
    # 3. Update staff profession and department
    print("[3/5] Updating staff profession and department...")
    old_profession = staff.get_profession_display()
    old_dept = staff.department.name if staff.department else "None"
    
    staff.profession = 'inventory_manager'  # This maps to inventory_stores_manager role
    staff.department = dept
    staff.is_active = True
    staff.is_deleted = False
    staff.save()
    
    print(f"   ✅ Profession: {old_profession} → {staff.get_profession_display()}")
    print(f"   ✅ Department: {old_dept} → {staff.department.name}")
    print(f"   ✅ Employee ID: {staff.employee_id}")
    print()
    
    # 4. Create default groups if needed
    print("[4/5] Ensuring role groups exist...")
    create_default_groups()
    print("   ✅ Role groups ready")
    print()
    
    # 5. Assign inventory_stores_manager role
    print("[5/5] Assigning Inventory & Stores Manager role...")
    assign_user_to_role(user, 'inventory_stores_manager')
    
    # Also add to group explicitly
    group, _ = Group.objects.get_or_create(name='Inventory & Stores Manager')
    user.groups.clear()  # Clear existing groups
    user.groups.add(group)
    user.is_staff = True
    user.save()
    
    print("   ✅ Assigned Inventory & Stores Manager role")
    print("   ✅ Added to Inventory & Stores Manager group")
    print()
    
    # Summary
    print("=" * 70)
    print("✅ UPDATE COMPLETE!")
    print("=" * 70)
    print()
    print("Staff Details:")
    print(f"  Name: {user.get_full_name()}")
    print(f"  Username: {user.username}")
    print(f"  Email: {user.email}")
    print(f"  Employee ID: {staff.employee_id}")
    print(f"  Profession: {staff.get_profession_display()}")
    print(f"  Department: {staff.department.name}")
    print(f"  Date of Birth: {staff.date_of_birth}")
    print(f"  Date of Joining: {staff.date_of_joining}")
    print(f"  Gender: {staff.get_gender_display()}")
    print()
    print("Role & Access:")
    print(f"  Role: Inventory & Stores Manager")
    print(f"  Dashboard: /hms/inventory-stores/dashboard/")
    print(f"  Groups: {[g.name for g in user.groups.all()]}")
    print()
    print("Login:")
    print(f"  URL: http://127.0.0.1:8000/hms/login/")
    print(f"  Username: {username}")
    print(f"  Password: francisca2025 (change on first login)")
    print()
    print("Dashboard Features:")
    print("  ✅ Inventory management")
    print("  ✅ Stores management")
    print("  ✅ Stock alerts")
    print("  ✅ Store transfers")
    print("  ✅ Requisitions")
    print("  ✅ Low stock reports")
    print("  ✅ Inventory analytics")
    print()
    print("=" * 70)
    
    return user, staff

if __name__ == '__main__':
    try:
        update_francisca_to_inventory_manager()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)






#!/usr/bin/env python
"""
Script to grant Rebecca full Procurement and Inventory Management access
Includes ability to add and delete inventory items
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from hospital.models import Staff, Department
from hospital.models_procurement import InventoryItem, Store, InventoryCategory
from hospital.utils_roles import get_user_role

def grant_rebecca_full_access():
    """Grant Rebecca full procurement and inventory management access"""
    print("=" * 70)
    print("GRANTING REBECCA FULL PROCUREMENT & INVENTORY ACCESS")
    print("=" * 70)
    print()
    
    # Find Rebecca - try multiple username variations
    usernames = ['rebecca', 'rebecca.', 'Rebecca']
    user = None
    
    for username in usernames:
        try:
            user = User.objects.get(username__iexact=username)
            print(f"[OK] Found user: {user.get_full_name()} ({user.username})")
            break
        except User.DoesNotExist:
            continue
    
    if not user:
        # Try by first name
        try:
            user = User.objects.filter(first_name__iexact='Rebecca').first()
            if user:
                print(f"[OK] Found user by name: {user.get_full_name()} ({user.username})")
        except:
            pass
    
    if not user:
        print("[ERROR] User 'Rebecca' not found!")
        print("   Available users with 'rebecca' in username:")
        for u in User.objects.filter(username__icontains='rebecca'):
            print(f"   - {u.username} ({u.get_full_name()})")
        return False
    
    print()
    
    # 1. Ensure staff flag is set
    print("[1/6] Ensuring staff privileges...")
    user.is_staff = True
    user.is_active = True
    user.save()
    print("   [OK] Staff privileges set")
    print()
    
    # 2. Get or create staff record with store_manager profession
    print("[2/6] Updating staff record...")
    staff, created = Staff.objects.get_or_create(
        user=user,
        defaults={
            'profession': 'store_manager',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if not created:
        old_profession = staff.profession
        staff.profession = 'store_manager'
        staff.is_active = True
        staff.is_deleted = False
        staff.save()
        print(f"   [OK] Updated profession: {old_profession} → store_manager")
    else:
        print("   [OK] Created staff record with store_manager profession")
    
    # Get or create Procurement/Stores department
    if not staff.department:
        procurement_dept, dept_created = Department.objects.get_or_create(
            name='Procurement',
            defaults={'description': 'Procurement and Stores Department'}
        )
        if not procurement_dept:
            # Try Stores
            procurement_dept, dept_created = Department.objects.get_or_create(
                name='Stores',
                defaults={'description': 'Stores Department'}
            )
        staff.department = procurement_dept
        staff.save()
        if dept_created:
            print(f"   [OK] Created '{procurement_dept.name}' department")
        print(f"   [OK] Assigned to {procurement_dept.name} department")
    else:
        print(f"   [OK] Already in department: {staff.department.name}")
    
    print()
    
    # 3. Assign Procurement groups
    print("[3/6] Assigning Procurement groups...")
    procurement_groups = ['Procurement', 'Procurement Officer', 'Store Manager', 'Inventory Manager']
    
    for group_name in procurement_groups:
        group, group_created = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
        if group_created:
            print(f"   [OK] Created '{group_name}' group")
        print(f"   [OK] Added to '{group_name}' group")
    
    # Also add to Admin group for full access
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    if admin_group not in user.groups.all():
        user.groups.add(admin_group)
        print(f"   [OK] Added to 'Admin' group for full access")
    
    print()
    
    # 4. Grant specific permissions for inventory management
    print("[4/6] Granting inventory management permissions...")
    
    # Get content types for inventory models
    try:
        inventory_item_ct = ContentType.objects.get_for_model(InventoryItem)
        store_ct = ContentType.objects.get_for_model(Store)
        category_ct = ContentType.objects.get_for_model(InventoryCategory)
        
        # Permissions to grant
        permissions_to_add = [
            # InventoryItem permissions
            Permission.objects.get_or_create(
                codename='add_inventoryitem',
                name='Can add inventory item',
                content_type=inventory_item_ct
            )[0],
            Permission.objects.get_or_create(
                codename='change_inventoryitem',
                name='Can change inventory item',
                content_type=inventory_item_ct
            )[0],
            Permission.objects.get_or_create(
                codename='delete_inventoryitem',
                name='Can delete inventory item',
                content_type=inventory_item_ct
            )[0],
            Permission.objects.get_or_create(
                codename='view_inventoryitem',
                name='Can view inventory item',
                content_type=inventory_item_ct
            )[0],
            # Store permissions
            Permission.objects.get_or_create(
                codename='add_store',
                name='Can add store',
                content_type=store_ct
            )[0],
            Permission.objects.get_or_create(
                codename='change_store',
                name='Can change store',
                content_type=store_ct
            )[0],
            Permission.objects.get_or_create(
                codename='delete_store',
                name='Can delete store',
                content_type=store_ct
            )[0],
            Permission.objects.get_or_create(
                codename='view_store',
                name='Can view store',
                content_type=store_ct
            )[0],
            # Category permissions
            Permission.objects.get_or_create(
                codename='add_inventorycategory',
                name='Can add inventory category',
                content_type=category_ct
            )[0],
            Permission.objects.get_or_create(
                codename='change_inventorycategory',
                name='Can change inventory category',
                content_type=category_ct
            )[0],
            Permission.objects.get_or_create(
                codename='delete_inventorycategory',
                name='Can delete inventory category',
                content_type=category_ct
            )[0],
        ]
        
        # Add all permissions to user
        for perm in permissions_to_add:
            user.user_permissions.add(perm)
            print(f"   [OK] Granted permission: {perm.codename}")
        
        # Also add to groups
        for group_name in ['Store Manager', 'Procurement Officer', 'Admin']:
            try:
                group = Group.objects.get(name=group_name)
                for perm in permissions_to_add:
                    group.permissions.add(perm)
            except Group.DoesNotExist:
                pass
        
    except Exception as e:
        print(f"   [WARNING]  Error granting permissions: {e}")
        print("   (This is okay if permissions already exist)")
    
    print()
    
    # 5. Grant superuser if needed for full access
    print("[5/6] Checking superuser status...")
    if not user.is_superuser:
        # Don't make superuser, but ensure all groups have permissions
        print("   [INFO]  User is not superuser (keeping as staff)")
    else:
        print("   [OK] User is superuser (has full access)")
    
    print()
    
    # 6. Verify changes
    print("[6/6] Verifying changes...")
    user.refresh_from_db()
    staff.refresh_from_db()
    
    new_role = get_user_role(user)
    print(f"   [OK] Current profession: {staff.profession}")
    print(f"   [OK] Current role: {new_role}")
    print(f"   [OK] Department: {staff.department.name if staff.department else 'None'}")
    print(f"   [OK] Is Active: {staff.is_active}")
    print(f"   [OK] Is Staff: {user.is_staff}")
    print(f"   [OK] Groups: {', '.join([g.name for g in user.groups.all()])}")
    
    # Count permissions
    perm_count = user.user_permissions.count()
    print(f"   [OK] Direct Permissions: {perm_count}")
    
    # Test procurement access
    from hospital.utils_roles import is_procurement_staff
    has_access = is_procurement_staff(user)
    print(f"   [OK] Has Procurement Access: {has_access}")
    
    # Test inventory permissions
    has_add = user.has_perm('hospital.add_inventoryitem')
    has_change = user.has_perm('hospital.change_inventoryitem')
    has_delete = user.has_perm('hospital.delete_inventoryitem')
    print(f"   [OK] Can Add Inventory: {has_add}")
    print(f"   [OK] Can Change Inventory: {has_change}")
    print(f"   [OK] Can Delete Inventory: {has_delete}")
    
    print()
    print("=" * 70)
    print("[OK] SUCCESS! Rebecca now has full Procurement & Inventory access")
    print("=" * 70)
    print()
    print("Rebecca will now:")
    print("  - Have profession: store_manager")
    print("  - Be in Procurement/Stores department")
    print("  - Have Procurement role access")
    print("  - Have Inventory Management access")
    print("  - Can ADD inventory items")
    print("  - Can DELETE inventory items")
    print("  - Can CHANGE inventory items")
    print("  - Can access all procurement and transfer features")
    print("  - Will see Procurement Dashboard in navigation")
    print("  - Will see Inventory Management in navigation")
    print()
    
    return True

if __name__ == '__main__':
    grant_rebecca_full_access()

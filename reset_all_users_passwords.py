#!/usr/bin/env python
"""
Reset passwords for all staff users (is_staff=True).
Run this from the project root: python reset_all_users_passwords.py
Or via Docker: docker-compose exec web python reset_all_users_passwords.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def reset_all_staff_passwords(default_password='staff123'):
    """Reset passwords for all staff users"""
    print("=" * 70)
    print("RESETTING ALL STAFF USER PASSWORDS")
    print("=" * 70)
    print()
    
    # Get all staff users (is_staff=True)
    staff_users = User.objects.filter(is_staff=True)
    
    print(f"Found {staff_users.count()} staff users")
    print()
    
    updated = 0
    
    for user in staff_users:
        # Reset password
        user.set_password(default_password)
        user.is_active = True
        user.save()
        updated += 1
        print(f"✅ {user.username:20} - {user.get_full_name():30} - Superuser: {user.is_superuser}")
    
    print()
    print("=" * 70)
    print(f"✅ Updated: {updated} staff user passwords")
    print()
    print(f"Default password for all staff: {default_password}")
    print()
    print("All staff can now login with:")
    print(f"  Username: (their username)")
    print(f"  Password: {default_password}")
    print()
    print("=" * 70)
    return updated

if __name__ == '__main__':
    import sys
    
    # Get password from command line or use default
    default_password = sys.argv[1] if len(sys.argv) > 1 else 'staff123'
    
    reset_all_staff_passwords(default_password)















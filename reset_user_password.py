#!/usr/bin/env python
"""
Reset user password script
Usage: python reset_user_password.py <username> <new_password>
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User

def reset_password(username, new_password):
    """Reset a user's password"""
    try:
        user = User.objects.get(username=username)
        user.set_password(new_password)
        user.is_active = True
        user.save()
        print(f"✅ Password reset successfully for user: {username}")
        return True
    except User.DoesNotExist:
        print(f"❌ User '{username}' not found")
        print("\nAvailable users:")
        for u in User.objects.all():
            print(f"  - {u.username}")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def create_superuser_interactive():
    """Create superuser interactively"""
    print("Creating new superuser...")
    username = input("Username: ")
    email = input("Email (optional): ") or ""
    password = input("Password: ")
    confirm = input("Confirm password: ")
    
    if password != confirm:
        print("❌ Passwords don't match!")
        return False
    
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()
        print(f"✅ Superuser '{username}' created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == '__main__':
    if len(sys.argv) == 3:
        username = sys.argv[1]
        password = sys.argv[2]
        reset_password(username, password)
    elif len(sys.argv) == 2 and sys.argv[1] == '--create':
        create_superuser_interactive()
    else:
        print("Usage:")
        print("  Reset password: python reset_user_password.py <username> <new_password>")
        print("  Create user:    python reset_user_password.py --create")
        print()
        print("Or use Django command:")
        print("  python manage.py createsuperuser")
        print("  python manage.py changepassword <username>")








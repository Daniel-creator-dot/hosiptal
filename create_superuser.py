#!/usr/bin/env python3
"""
Create Django superuser programmatically
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

# Default credentials
username = 'admin'
email = 'admin@example.com'
password = 'admin123'  # Change this after first login!

try:
    # Check if user already exists
    if User.objects.filter(username=username).exists():
        print(f"✅ User '{username}' already exists")
        user = User.objects.get(username=username)
        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.save()
        print(f"✅ Password updated for '{username}'")
    else:
        # Create new superuser
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print(f"✅ Superuser '{username}' created successfully!")
    
    print(f"\nLogin credentials:")
    print(f"  Username: {username}")
    print(f"  Password: {password}")
    print(f"\n⚠️  IMPORTANT: Change the password after first login!")
    
except Exception as e:
    print(f"❌ Error creating superuser: {e}")
    sys.exit(1)


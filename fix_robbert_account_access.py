#!/usr/bin/env python
"""
Quick fix: Make Robbert superuser to fix account change forbidden error
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Find Robbert
user = None
for username in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame']:
    try:
        user = User.objects.get(username=username)
        break
    except User.DoesNotExist:
        continue

if not user:
    users = User.objects.filter(username__icontains='robbert')
    if users.exists():
        user = users.first()

if not user:
    print("❌ User 'robbert' not found!")
    sys.exit(1)

print(f"✅ Found user: {user.username}")
print()

# Make superuser
print("Making Robbert a superuser to fix account change access...")
user.is_superuser = True
user.is_staff = True
user.is_active = True
user.save()

print("✅ Done!")
print()
print("Robbert is now:")
print(f"  - is_superuser: {user.is_superuser}")
print(f"  - is_staff: {user.is_staff}")
print(f"  - is_active: {user.is_active}")
print()
print("⚠️  IMPORTANT: Robbert must log out and log back in for changes to take effect!")
print()
print("He should now be able to change accounts without forbidden errors!")







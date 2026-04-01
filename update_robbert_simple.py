#!/usr/bin/env python
"""
Simple script to update Robbert to superuser
Can be run directly or in Docker: docker-compose exec web python update_robbert_simple.py
"""
import os
import sys
import django

# Setup Django
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')

# Add project root to path if needed
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("=" * 70)
print("MAKING ROBBERT A SUPERUSER")
print("=" * 70)
print()

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
    print()
    print("Available users with 'robbert' in username:")
    users = User.objects.filter(username__icontains='robbert')
    for u in users:
        print(f"  - {u.username} ({u.email or 'No email'})")
    sys.exit(1)

print(f"✅ Found user: {user.username}")
print(f"   Email: {user.email or 'No email'}")
print()

# Make superuser
print("Updating user to superuser...")
user.is_superuser = True
user.is_staff = True
user.is_active = True
user.save()

print("✅ Success!")
print()
print("User status:")
print(f"  - is_superuser: {user.is_superuser}")
print(f"  - is_staff: {user.is_staff}")
print(f"  - is_active: {user.is_active}")
print()
print("=" * 70)
print("✅ ROBBERT IS NOW A SUPERUSER!")
print("=" * 70)
print()
print("⚠️  IMPORTANT: Robbert must log out and log back in for changes to take effect!")
print()
print("Robbert can now access:")
print("  ✅ /admin/hospital/cashbook/add/")
print("  ✅ /admin/hospital/account/add/")
print("  ✅ /admin/hospital/insurancereceivable/add/")
print("  ✅ ALL Django admin models (no more forbidden errors!)")
print()







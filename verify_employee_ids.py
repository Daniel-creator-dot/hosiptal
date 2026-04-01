#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Staff
from django.db.models import Q

print("=" * 70)
print("EMPLOYEE ID VERIFICATION")
print("=" * 70)
print()

# Check Ebenezer
try:
    ebenezer = Staff.objects.get(user__username='ebenezer.donkor', is_deleted=False)
    print(f"✅ Ebenezer Donkor:")
    print(f"   Employee ID: {ebenezer.employee_id}")
    print(f"   Profession: {ebenezer.profession}")
    print(f"   Department: {ebenezer.department.name if ebenezer.department else 'None'}")
    print()
except Staff.DoesNotExist:
    print("❌ Ebenezer Donkor not found!")
    print()

# Check staff without IDs
staff_without_ids = Staff.objects.filter(
    Q(employee_id__isnull=True) | Q(employee_id=''),
    is_deleted=False
).count()

print(f"Staff without Employee IDs: {staff_without_ids}")
print()

# Show some example employee IDs
print("Sample Employee IDs:")
sample_staff = Staff.objects.filter(is_deleted=False, employee_id__isnull=False).exclude(employee_id='')[:10]
for staff in sample_staff:
    name = staff.user.get_full_name() if staff.user else "Unknown"
    print(f"  {name}: {staff.employee_id} ({staff.profession})")

print()
print("=" * 70)
if staff_without_ids == 0:
    print("✅ ALL STAFF HAVE EMPLOYEE IDs")
else:
    print(f"⚠️  {staff_without_ids} STAFF MEMBERS NEED EMPLOYEE IDs")
print("=" * 70)






#!/usr/bin/env python
"""
Update Ebenezer to Finance Department
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Staff, Department
from django.contrib.auth.models import User

# Get Ebenezer
user = User.objects.get(username='ebenezer.donkor')
staff = Staff.objects.get(user=user)

# Get or create Finance department
finance_dept = Department.objects.filter(name__icontains='finance').first()
if not finance_dept:
    finance_dept = Department.objects.create(
        name='Finance',
        code='FIN',
        description='Finance and Accounting Department',
        is_active=True
    )
    print(f"Created Finance department: {finance_dept.name}")
else:
    print(f"Found Finance department: {finance_dept.name}")

# Update staff to Finance department
staff.department = finance_dept
staff.save()

print(f"\nEbenezer updated successfully!")
print(f"  Name: {staff.user.get_full_name()}")
print(f"  Department: {staff.department.name}")
print(f"  Profession: {staff.get_profession_display()}")
print(f"  Employee ID: {staff.employee_id}")
print(f"  Groups: {', '.join([g.name for g in user.groups.all()])}")






#!/usr/bin/env python
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User
from hospital.models import Staff
from hospital.utils_roles import get_user_role

user = User.objects.get(username='rebecca')
staff = Staff.objects.get(user=user)
role = get_user_role(user)

print('=== REBECCA STATUS ===')
print(f'Username: {user.username}')
print(f'Full Name: {user.get_full_name()}')
print(f'Email: {user.email}')
print(f'Profession: {staff.profession}')
print(f'Department: {staff.department.name if staff.department else "None"}')
print(f'Role: {role}')
print(f'Is Active: {staff.is_active}')
print(f'Groups: {[g.name for g in user.groups.all()]}')
print('=' * 30)






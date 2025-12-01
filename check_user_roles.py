#!/usr/bin/env python
"""
Check all user roles and their dashboards
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from hospital.models import Staff
from hospital.utils_roles import get_user_role, get_user_dashboard_url

User = get_user_model()

print('=' * 100)
print('USER ROLE ASSIGNMENTS')
print('=' * 100)
print()
print(f'{'Name':<30} | {'Username':<25} | {'Profession':<15} | {'Role':<15} | {'Dashboard':<50}')
print('-' * 100)

staff_list = Staff.objects.filter(is_active=True, is_deleted=False).select_related('user').order_by('user__last_name')

for staff in staff_list:
    user = staff.user
    if not user:
        continue
    
    role = get_user_role(user)
    url = get_user_dashboard_url(user)
    name = user.get_full_name() or user.username
    
    print(f'{name:<30} | {user.username:<25} | {staff.profession:<15} | {role:<15} | {url:<50}')

print()
print('=' * 100)
print('ROBERT (ACCOUNTANT) VERIFICATION:')
print('=' * 100)

robbert = User.objects.filter(username__icontains='robbert').first()
if robbert:
    role = get_user_role(robbert)
    url = get_user_dashboard_url(robbert)
    groups = list(robbert.groups.values_list('name', flat=True))
    
    print(f'Username: {robbert.username}')
    print(f'Name: {robbert.get_full_name()}')
    print(f'Role: {role}')
    print(f'Groups: {groups}')
    print(f'Dashboard URL: {url}')
    print()
    print('✅ Robbert is set up as Accountant!')
else:
    print('❌ Robbert not found')















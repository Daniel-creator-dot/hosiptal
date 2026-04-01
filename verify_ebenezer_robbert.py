#!/usr/bin/env python
"""Quick verification script"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth.models import User
from hospital.models import Staff

robbert = Staff.objects.filter(user__username__icontains='robbert', is_deleted=False).first()
ebenezer = Staff.objects.filter(user__username__icontains='ebenezer', is_deleted=False).first()

print("=" * 70)
print("VERIFICATION: Robbert and Ebenezer Configuration")
print("=" * 70)
print()

if robbert:
    print(f"Robbert:")
    print(f"  Username: {robbert.user.username}")
    print(f"  Department: {robbert.department.name if robbert.department else 'None'}")
    print(f"  Profession: {robbert.profession}")
    print()
else:
    print("Robbert: NOT FOUND")
    print()

if ebenezer:
    print(f"Ebenezer:")
    print(f"  Username: {ebenezer.user.username}")
    print(f"  Department: {ebenezer.department.name if ebenezer.department else 'None'}")
    print(f"  Profession: {ebenezer.profession}")
    print()
else:
    print("Ebenezer: NOT FOUND")
    print()

if robbert and ebenezer:
    same_dept = robbert.department == ebenezer.department if robbert.department and ebenezer.department else False
    same_prof = robbert.profession == ebenezer.profession
    
    print("Status:")
    print(f"  Same Department: {same_dept}")
    print(f"  Same Profession: {same_prof}")
    print()
    
    if same_dept and same_prof:
        print("[OK] Both users are configured correctly!")
    else:
        print("[WARNING] Users are not in sync!")
else:
    print("[ERROR] One or both users not found!")




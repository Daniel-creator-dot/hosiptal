#!/usr/bin/env python
"""Test account staff URL with UUID"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.urls import reverse
from hospital.models import Staff

# Get first account staff member
staff = Staff.objects.filter(
    profession__in=['accountant', 'account_officer', 'account_personnel'],
    is_deleted=False
).first()

if staff:
    try:
        url = reverse('hospital:account_staff_detail', kwargs={'pk': staff.pk})
        print(f"✅ URL works: {url}")
        print(f"Staff ID: {staff.pk}")
        print(f"Staff ID type: {type(staff.pk).__name__}")
        print(f"Staff Name: {staff.user.get_full_name() if staff.user else 'N/A'}")
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("No account staff found")






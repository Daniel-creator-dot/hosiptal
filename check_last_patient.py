#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check the last created patient and their phone number"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient
from django.utils import timezone
from datetime import timedelta

# Get the most recently created patient
last_patient = Patient.objects.filter(
    is_deleted=False,
    created__gte=timezone.now() - timedelta(hours=1)
).order_by('-created').first()

if last_patient:
    print("=" * 80)
    print("Most Recent Patient (Last Hour)")
    print("=" * 80)
    print(f"MRN: {last_patient.mrn}")
    print(f"Name: {last_patient.full_name}")
    print(f"Phone: {last_patient.phone_number or '(No phone number)'}")
    print(f"Created: {last_patient.created}")
    print(f"ID: {last_patient.id}")
    print("=" * 80)
    
    if not last_patient.phone_number:
        print("\n⚠️  WARNING: Patient has no phone number!")
        print("   SMS cannot be sent without a phone number.")
    else:
        print(f"\n✅ Patient has phone number: {last_patient.phone_number}")
        print("   SMS should have been attempted.")
else:
    print("No patients created in the last hour.")

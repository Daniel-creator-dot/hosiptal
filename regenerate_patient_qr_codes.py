#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regenerate QR codes for patients that are missing them"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient, PatientQRCode
from django.utils import timezone
from django.db.models import Q
import secrets

print("=" * 80)
print("Regenerating Patient QR Codes")
print("=" * 80)

# Find patients without QR codes or with incomplete QR codes
# Use Q objects to properly handle null checks
patients_needing_qr = Patient.objects.filter(
    is_deleted=False
).filter(
    Q(qr_profile__isnull=True) |
    Q(qr_profile__qr_code_image__isnull=True) |
    Q(qr_profile__qr_code_data__isnull=True) |
    Q(qr_profile__qr_code_data='') |
    Q(qr_profile__qr_token__isnull=True) |
    Q(qr_profile__qr_token='')
).distinct()

total = patients_needing_qr.count()
print(f"\nFound {total} patients needing QR code generation\n")

if total == 0:
    print("✅ All patients have QR codes!")
    sys.exit(0)

success_count = 0
error_count = 0

for idx, patient in enumerate(patients_needing_qr, 1):
    try:
        print(f"[{idx}/{total}] Processing: {patient.mrn} - {patient.full_name}")
        
        # Get or create QR profile - handle existing records with empty tokens
        try:
            qr_profile = PatientQRCode.objects.get(patient=patient)
        except PatientQRCode.DoesNotExist:
            qr_profile = None
        
        if not qr_profile:
            # Create new QR profile
            qr_profile = PatientQRCode(patient=patient)
            qr_profile.qr_token = secrets.token_urlsafe(32)  # Generate token first
            qr_profile.save()
            print(f"  -> Created new QR profile")
        
        # Fix empty token if needed
        if not qr_profile.qr_token or qr_profile.qr_token == '':
            qr_profile.qr_token = secrets.token_urlsafe(32)
            qr_profile.save(update_fields=['qr_token', 'modified'])
            print(f"  -> Fixed empty token")
        
        # Check if QR code needs generation
        needs_generation = (
            not qr_profile.qr_code_image or 
            not qr_profile.qr_code_data or 
            qr_profile.qr_code_data == ''
        )
        
        if needs_generation:
            print(f"  -> Generating QR code...")
            qr_profile.refresh_qr(force_token=False)  # Don't force token if we just set it
            print(f"  [OK] QR code generated successfully")
            success_count += 1
        else:
            print(f"  [INFO] QR code already exists")
            
    except Exception as e:
        print(f"  [ERROR] Error: {str(e)}")
        error_count += 1
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("Summary")
print("=" * 80)
print(f"Total processed: {total}")
print(f"Successfully generated: {success_count}")
print(f"Errors: {error_count}")
print("=" * 80)

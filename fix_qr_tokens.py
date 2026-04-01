#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix empty qr_token values in PatientQRCode"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import PatientQRCode
import secrets

print("=" * 80)
print("Fixing Empty QR Tokens")
print("=" * 80)

# Find QR codes with empty tokens
empty_tokens = PatientQRCode.objects.filter(
    qr_token__isnull=True
) | PatientQRCode.objects.filter(qr_token='')

total = empty_tokens.count()
print(f"\nFound {total} QR codes with empty tokens\n")

if total == 0:
    print("All QR codes have valid tokens!")
    sys.exit(0)

fixed = 0
for idx, qr in enumerate(empty_tokens, 1):
    try:
        print(f"[{idx}/{total}] Fixing QR code for patient: {qr.patient.mrn if qr.patient else 'Unknown'}")
        qr.qr_token = secrets.token_urlsafe(32)
        qr.save(update_fields=['qr_token', 'modified'])
        print(f"  [OK] Token generated: {qr.qr_token[:16]}...")
        fixed += 1
    except Exception as e:
        print(f"  [ERROR] Failed: {str(e)}")

print(f"\nFixed {fixed} QR codes")
print("=" * 80)

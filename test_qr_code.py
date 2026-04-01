#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test QR code for specific patient"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient, PatientQRCode

patient = Patient.objects.filter(mrn='PMC2026000036').first()
if patient:
    print(f"Patient: {patient.full_name}")
    qr = PatientQRCode.objects.filter(patient=patient).first()
    if qr:
        print(f"QR Profile: EXISTS")
        print(f"QR Image: {'YES' if qr.qr_code_image else 'NO'}")
        print(f"QR Data: {'YES' if qr.qr_code_data else 'NO'}")
        print(f"QR Token: {'YES' if qr.qr_token else 'NO'}")
        if qr.qr_code_data:
            print(f"QR Data Preview: {qr.qr_code_data[:50]}...")
    else:
        print("QR Profile: MISSING")
else:
    print("Patient not found")

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test SMS sending for the last patient"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient
from hospital.services.sms_service import sms_service
from django.utils import timezone
from datetime import timedelta

# Get the most recently created patient
last_patient = Patient.objects.filter(
    is_deleted=False,
    created__gte=timezone.now() - timedelta(hours=1)
).order_by('-created').first()

if last_patient:
    print("=" * 80)
    print(f"Testing SMS for Patient: {last_patient.mrn} - {last_patient.full_name}")
    print(f"Phone Number: {last_patient.phone_number}")
    print("=" * 80)
    
    if not last_patient.phone_number:
        print("\nERROR: Patient has no phone number!")
    else:
        phone_number = (last_patient.phone_number or '').strip()
        print(f"\nAttempting to send SMS to: {phone_number}")
        
        message = (
            f"Welcome to PrimeCare Hospital, {last_patient.first_name}!\n\n"
            f"Your Medical Record Number (MRN): {last_patient.mrn}\n"
            f"Please keep this number for future visits.\n\n"
            f"Thank you for choosing us for your healthcare needs.\n\n"
            f"PrimeCare Hospital"
        )
        
        try:
            sms_log = sms_service.send_sms(
                phone_number=phone_number,
                message=message,
                message_type='patient_registration',
                recipient_name=last_patient.full_name,
                related_object_id=last_patient.id,
                related_object_type='Patient'
            )
            
            print(f"\nSMS Log Created:")
            print(f"  ID: {sms_log.id}")
            print(f"  Status: {sms_log.status}")
            print(f"  Phone: {sms_log.recipient_phone}")
            print(f"  Created: {sms_log.created}")
            
            if sms_log.error_message:
                print(f"  Error: {sms_log.error_message}")
            
            if sms_log.provider_response:
                print(f"  Provider Response: {sms_log.provider_response}")
                
        except Exception as e:
            print(f"\nEXCEPTION occurred: {str(e)}")
            import traceback
            traceback.print_exc()
else:
    print("No patients created in the last hour.")

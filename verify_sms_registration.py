#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Verify SMS functionality after patient registration
"""

import os
import sys
import django

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models import Patient
from hospital.models_advanced import SMSLog
from hospital.services.sms_service import sms_service
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

print("\n" + "="*80)
print("SMS REGISTRATION VERIFICATION")
print("="*80 + "\n")

# 1. Check SMS Configuration
print("1. SMS CONFIGURATION CHECK")
print("-" * 80)
api_key = getattr(settings, 'SMS_API_KEY', None) or os.environ.get('SMS_API_KEY', None)
sender_id = getattr(settings, 'SMS_SENDER_ID', None) or os.environ.get('SMS_SENDER_ID', None)
api_url = getattr(settings, 'SMS_API_URL', None) or os.environ.get('SMS_API_URL', None)

if api_key:
    masked_key = api_key[:10] + '...' if len(api_key) > 10 else api_key
    print(f"[OK] SMS_API_KEY: {masked_key}")
else:
    print("[WARNING] SMS_API_KEY not set - using default (may be invalid)")

if sender_id:
    print(f"[OK] SMS_SENDER_ID: {sender_id}")
else:
    print("[WARNING] SMS_SENDER_ID not set - using default: PrimeCare")

if api_url:
    print(f"[OK] SMS_API_URL: {api_url}")
else:
    print("[INFO] SMS_API_URL not set - using default: https://sms.smsnotifygh.com/smsapi")

print()

# 2. Check Recent Patient Registrations
print("2. RECENT PATIENT REGISTRATIONS (Last 7 days)")
print("-" * 80)
week_ago = timezone.now() - timedelta(days=7)
recent_patients = Patient.objects.filter(
    is_deleted=False,
    created__gte=week_ago
).order_by('-created')[:10]

if not recent_patients:
    print("[INFO] No patients registered in the last 7 days")
else:
    print(f"Found {recent_patients.count()} recent patients:\n")
    for patient in recent_patients:
        phone_status = "[HAS PHONE]" if patient.phone_number and patient.phone_number.strip() else "[NO PHONE]"
        print(f"  - {patient.full_name} ({patient.mrn})")
        print(f"    Created: {patient.created.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Phone: {patient.phone_number or 'Not provided'} {phone_status}")
        
        # Check if SMS was sent for this patient
        sms_log = SMSLog.objects.filter(
            related_object_id=patient.id,
            related_object_type='Patient',
            message_type='patient_registration'
        ).order_by('-created').first()
        
        if sms_log:
            if sms_log.status == 'sent':
                print(f"    SMS: [SENT] at {sms_log.created.strftime('%Y-%m-%d %H:%M:%S')}")
            elif sms_log.status == 'failed':
                print(f"    SMS: [FAILED] - {sms_log.error_message or 'Unknown error'}")
            else:
                print(f"    SMS: [{sms_log.status.upper()}]")
        else:
            print(f"    SMS: [NO LOG FOUND]")
        print()

print()

# 3. Check All Registration SMS Logs
print("3. ALL REGISTRATION SMS LOGS")
print("-" * 80)
all_sms_logs = SMSLog.objects.filter(
    message_type='patient_registration'
).order_by('-created')[:20]

if not all_sms_logs:
    print("[INFO] No registration SMS logs found in database")
else:
    print(f"Found {all_sms_logs.count()} registration SMS logs:\n")
    
    sent_count = 0
    failed_count = 0
    pending_count = 0
    
    for sms in all_sms_logs:
        if sms.status == 'sent':
            sent_count += 1
            status_icon = "[OK]"
        elif sms.status == 'failed':
            failed_count += 1
            status_icon = "[FAILED]"
        else:
            pending_count += 1
            status_icon = "[PENDING]"
        
        print(f"{status_icon} {sms.created.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Phone: {sms.recipient_phone}")
        print(f"   Recipient: {sms.recipient_name or 'N/A'}")
        print(f"   Status: {sms.status}")
        
        if sms.error_message:
            print(f"   Error: {sms.error_message}")
        
        if sms.provider_response:
            import json
            if isinstance(sms.provider_response, dict):
                response_str = json.dumps(sms.provider_response, indent=2)
                if len(response_str) > 200:
                    response_str = response_str[:200] + "..."
                print(f"   Provider: {response_str}")
            else:
                print(f"   Provider: {str(sms.provider_response)[:200]}")
        print()
    
    print(f"Summary: Sent={sent_count}, Failed={failed_count}, Pending={pending_count}")

print()

# 4. Check Recent Failures
print("4. RECENT FAILURES (Last 24 hours)")
print("-" * 80)
yesterday = timezone.now() - timedelta(days=1)
recent_failures = SMSLog.objects.filter(
    message_type='patient_registration',
    status='failed',
    created__gte=yesterday
).order_by('-created')[:10]

if not recent_failures:
    print("[OK] No failed registration SMS in the last 24 hours")
else:
    print(f"[WARNING] Found {recent_failures.count()} failed SMS:\n")
    for sms in recent_failures:
        print(f"  - {sms.created.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Phone: {sms.recipient_phone}")
        print(f"    Error: {sms.error_message or 'Unknown error'}")
        print()

print()

# 5. Test SMS Service (if phone number provided)
print("5. SMS SERVICE TEST")
print("-" * 80)
print("[INFO] To test SMS service, register a new patient with a valid phone number")
print("       Format: +233XXXXXXXXX or 0XXXXXXXXX")
print()
print("Expected behavior:")
print("  1. Patient registration form submitted")
print("  2. Patient record created")
print("  3. SMS log entry created (status: pending)")
print("  4. SMS sent via API")
print("  5. SMS log updated (status: sent or failed)")
print("  6. User sees success/warning message")
print()

# 6. Recommendations
print("6. RECOMMENDATIONS")
print("-" * 80)

if not all_sms_logs:
    print("[ACTION] No SMS logs found. This could mean:")
    print("  - No patients have been registered with phone numbers recently")
    print("  - SMS code is not being triggered")
    print("  - SMS service is failing silently")
    print()
    print("  To verify:")
    print("  1. Register a test patient with a valid phone number")
    print("  2. Check the success/warning message after registration")
    print("  3. Run this script again to see the SMS log")
    print()

if recent_failures:
    print("[ACTION] Recent SMS failures detected. Common causes:")
    print("  - Invalid API key (check SMS_API_KEY setting)")
    print("  - Insufficient SMS account balance")
    print("  - Invalid phone number format")
    print("  - Invalid sender ID")
    print()
    print("  To fix:")
    print("  1. Verify SMS_API_KEY is correct")
    print("  2. Check SMS account balance")
    print("  3. Ensure phone numbers are in format: 233XXXXXXXXX (12 digits)")
    print()

if api_key and api_key == '84c879bb-f9f9-4666-84a8-9f70a9b238cc':
    print("[WARNING] Using default SMS API key. This may be invalid.")
    print("  Set your own SMS_API_KEY in settings or environment variables")
    print()

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80 + "\n")

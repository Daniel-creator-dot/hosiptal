#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Check SMS logs for patient registration
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

from hospital.models_advanced import SMSLog
from django.utils import timezone
from datetime import timedelta

print("\n" + "="*80)
print("PATIENT REGISTRATION SMS LOGS")
print("="*80 + "\n")

# Get recent registration SMS logs
recent_logs = SMSLog.objects.filter(
    message_type='patient_registration'
).order_by('-created')[:10]

if not recent_logs:
    print("[X] No patient registration SMS logs found")
else:
    print(f"Found {recent_logs.count()} recent registration SMS logs:\n")
    
    for sms in recent_logs:
        if sms.status == 'sent':
            status_icon = "[OK]"
        elif sms.status == 'failed':
            status_icon = "[FAILED]"
        else:
            status_icon = "[PENDING]"
        
        print(f"{status_icon} {sms.created.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Phone: {sms.recipient_phone}")
        print(f"   Status: {sms.status}")
        print(f"   Recipient: {sms.recipient_name or 'N/A'}")
        if sms.error_message:
            print(f"   Error: {sms.error_message}")
        if sms.provider_response:
            import json
            if isinstance(sms.provider_response, dict):
                print(f"   Provider Response: {json.dumps(sms.provider_response, indent=2)}")
            else:
                print(f"   Provider Response: {sms.provider_response}")
        print()

# Check for failed SMS in last 24 hours
yesterday = timezone.now() - timedelta(days=1)
failed_recent = SMSLog.objects.filter(
    message_type='patient_registration',
    status='failed',
    created__gte=yesterday
).count()

if failed_recent > 0:
    print(f"\n[WARNING] {failed_recent} failed registration SMS in last 24 hours")
    
    # Show common errors
    failed_logs = SMSLog.objects.filter(
        message_type='patient_registration',
        status='failed',
        created__gte=yesterday
    )[:5]
    
    print("\nCommon errors:")
    for sms in failed_logs:
        print(f"  - {sms.error_message or 'Unknown error'}")

# Summary statistics
total_recent = SMSLog.objects.filter(
    message_type='patient_registration',
    created__gte=yesterday
).count()

sent_recent = SMSLog.objects.filter(
    message_type='patient_registration',
    status='sent',
    created__gte=yesterday
).count()

pending_recent = SMSLog.objects.filter(
    message_type='patient_registration',
    status='pending',
    created__gte=yesterday
).count()

print(f"\n--- Summary (Last 24 hours) ---")
print(f"Total: {total_recent}")
print(f"Sent: {sent_recent}")
print(f"Failed: {failed_recent}")
print(f"Pending: {pending_recent}")

print("\n" + "="*80)









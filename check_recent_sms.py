#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check recent SMS logs for patient registration"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_advanced import SMSLog
from django.utils import timezone
from datetime import timedelta

# Get recent SMS logs (last hour)
recent = SMSLog.objects.filter(
    created__gte=timezone.now() - timedelta(hours=1)
).order_by('-created')[:10]

print("=" * 80)
print("Recent SMS Logs (Last Hour)")
print("=" * 80)

if recent:
    for sms in recent:
        print(f"\nID: {sms.id}")
        print(f"  Phone: {sms.recipient_phone}")
        print(f"  Status: {sms.status}")
        print(f"  Type: {sms.message_type}")
        print(f"  Created: {sms.created}")
        if sms.error_message:
            print(f"  Error: {sms.error_message}")
        if sms.provider_response:
            print(f"  Provider Response: {sms.provider_response}")
        print("-" * 80)
else:
    print("\nNo recent SMS logs found in the last hour.")
    print("\nThis could mean:")
    print("  1. No SMS was attempted")
    print("  2. SMS logs are older than 1 hour")
    print("  3. There was an error before SMS log creation")

# Also check for patient registration SMS specifically
patient_reg_sms = SMSLog.objects.filter(
    message_type='patient_registration',
    created__gte=timezone.now() - timedelta(hours=24)
).order_by('-created')[:5]

print("\n" + "=" * 80)
print("Patient Registration SMS (Last 24 Hours)")
print("=" * 80)

if patient_reg_sms:
    for sms in patient_reg_sms:
        print(f"\nID: {sms.id}")
        print(f"  Phone: {sms.recipient_phone}")
        print(f"  Status: {sms.status}")
        print(f"  Created: {sms.created}")
        if sms.error_message:
            print(f"  Error: {sms.error_message}")
        print("-" * 80)
else:
    print("\nNo patient registration SMS found in the last 24 hours.")

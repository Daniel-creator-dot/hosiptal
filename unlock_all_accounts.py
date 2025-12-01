#!/usr/bin/env python
"""
Unlock all blocked accounts.
This will:
1. Activate all inactive user accounts (is_active=False -> True)
2. Unlock all LoginAttempt records (is_locked, manually_blocked)
3. Reset failed attempt counters

Run this from the project root: python unlock_all_accounts.py
Or via Docker: docker-compose exec web python unlock_all_accounts.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import models
from hospital.models_login_attempts import LoginAttempt

User = get_user_model()

def unlock_all_accounts():
    """Unlock all blocked accounts"""
    print("=" * 70)
    print("UNLOCKING ALL BLOCKED ACCOUNTS")
    print("=" * 70)
    print()
    
    # 1. Activate all inactive users
    inactive_users = User.objects.filter(is_active=False)
    inactive_count = inactive_users.count()
    
    print(f"1. Found {inactive_count} inactive user accounts")
    if inactive_count > 0:
        for user in inactive_users:
            print(f"   ✅ Activating: {user.username}")
        inactive_users.update(is_active=True)
        print(f"   ✅ Activated {inactive_count} user accounts")
    else:
        print("   ✅ No inactive users found")
    print()
    
    # 2. Unlock all LoginAttempt records
    locked_attempts = LoginAttempt.objects.filter(
        is_deleted=False
    ).filter(
        models.Q(is_locked=True) | models.Q(manually_blocked=True)
    )
    locked_count = locked_attempts.count()
    
    print(f"2. Found {locked_count} locked login attempts")
    if locked_count > 0:
        unlocked = 0
        for attempt in locked_attempts:
            if attempt.is_locked or attempt.manually_blocked:
                attempt.unblock(note="Bulk unlock - all accounts unlocked")
                unlocked += 1
                print(f"   ✅ Unlocked: {attempt.username}")
        print(f"   ✅ Unlocked {unlocked} login attempts")
    else:
        print("   ✅ No locked login attempts found")
    print()
    
    # 3. Reset all failed attempt counters
    attempts_with_failures = LoginAttempt.objects.filter(
        is_deleted=False,
        failed_attempts__gt=0
    )
    failure_count = attempts_with_failures.count()
    
    print(f"3. Found {failure_count} login attempts with failed attempts")
    if failure_count > 0:
        for attempt in attempts_with_failures:
            attempt.reset_attempts()
            print(f"   ✅ Reset attempts for: {attempt.username}")
        print(f"   ✅ Reset {failure_count} failed attempt counters")
    else:
        print("   ✅ No failed attempts to reset")
    print()
    
    print("=" * 70)
    print("✅ ALL ACCOUNTS UNLOCKED!")
    print("=" * 70)
    print()
    print(f"Summary:")
    print(f"  - Activated: {inactive_count} user accounts")
    print(f"  - Unlocked: {locked_count} login attempts")
    print(f"  - Reset: {failure_count} failed attempt counters")
    print()
    print("All users can now login!")
    print("=" * 70)
    
    return inactive_count, locked_count, failure_count

if __name__ == '__main__':
    unlock_all_accounts()















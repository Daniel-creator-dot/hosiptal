"""
Script to unlock Adwoa Fosuah's account
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hms.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from hospital.models_login_attempts import LoginAttempt

User = get_user_model()

def unlock_adwoa():
    """Unlock Adwoa Fosuah's account"""
    username = 'adwoa.fosuah'
    
    # Find user
    user = User.objects.filter(username=username).first()
    if not user:
        print(f"❌ User '{username}' not found!")
        return
    
    print(f"✅ Found user: {user.username} ({user.get_full_name()})")
    
    # Activate user
    was_inactive = not user.is_active
    user.is_active = True
    user.save(update_fields=['is_active'])
    if was_inactive:
        print(f"✅ Activated user account")
    else:
        print(f"✅ User account already active")
    
    # Unlock all login attempts for this username (including variations)
    attempts = LoginAttempt.objects.filter(
        username__icontains='adwoa'
    ).exclude(is_deleted=True)
    
    unlocked_count = 0
    for attempt in attempts:
        needs_unlock = False
        
        if attempt.is_locked:
            needs_unlock = True
        if attempt.manually_blocked:
            needs_unlock = True
        if attempt.locked_until and attempt.locked_until > timezone.now():
            needs_unlock = True
        if attempt.failed_attempts > 0:
            needs_unlock = True
        
        if needs_unlock:
            attempt.unblock(note='Unlocked by admin script')
            unlocked_count += 1
            print(f"✅ Unlocked login attempt for: {attempt.username}")
        elif attempt.failed_attempts > 0:
            attempt.failed_attempts = 0
            attempt.save(update_fields=['failed_attempts', 'modified'])
            unlocked_count += 1
            print(f"✅ Reset failed attempts for: {attempt.username}")
    
    print(f"\n✅ Unlocked {unlocked_count} login attempt(s) for Adwoa")
    print(f"✅ Adwoa's account is now fully unlocked and ready to use!")

if __name__ == "__main__":
    unlock_adwoa()















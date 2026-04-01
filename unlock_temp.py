import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hms.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Q
from hospital.models_login_attempts import LoginAttempt

User = get_user_model()

USERNAME = os.environ.get("TARGET_USER", "admin")
NEW_PASSWORD = os.environ.get("TARGET_PASSWORD", "Admin12345!")

def unlock_and_reset(username):
    user = User.objects.filter(username=username).first()
    print(f"Target user: {user}")
    if user:
        user.is_active = True
        user.set_password(NEW_PASSWORD)
        user.save()
        print("✅ Activated and password set.")
    else:
        print("⚠️ User not found; skipping password reset.")

    attempts = LoginAttempt.objects.filter(
        Q(username=username) | Q(username__iexact=username)
    )
    count = 0
    for a in attempts:
        a.is_locked = False
        a.manually_blocked = False
        a.locked_until = None
        a.failed_attempts = 0
        a.save()
        count += 1
    print(f"✅ Unlocked {count} login attempt records for {username}.")

if __name__ == "__main__":
    unlock_and_reset(USERNAME)
    print("Done.")

















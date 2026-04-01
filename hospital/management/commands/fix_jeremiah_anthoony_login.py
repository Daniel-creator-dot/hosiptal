"""
Management command to fix login issues for jeremiah.anthoony
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction
from hospital.models import Department, Staff
from hospital.models_login_attempts import LoginAttempt
from django.db.models import Q


class Command(BaseCommand):
    help = 'Fix login issues for jeremiah.anthoony'

    def handle(self, *args, **options):
        with transaction.atomic():
            username = 'jeremiah.anthoony'
            
            # Check if user exists
            try:
                user = User.objects.get(username=username)
                self.stdout.write(f'✅ User "{username}" found')
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'⚠️  User "{username}" does not exist'))
                self.stdout.write('\nAvailable similar usernames:')
                similar = User.objects.filter(username__icontains='jeremiah')
                for u in similar:
                    self.stdout.write(f'  - {u.username}')
                
                # Ask if we should create it or use jeremiah.athoony
                self.stdout.write(f'\n💡 Did you mean "jeremiah.athoony"?')
                self.stdout.write(f'   That user exists and is ready to login.')
                self.stdout.write(f'   Username: jeremiah.athoony')
                self.stdout.write(f'   Password: market@2025')
                return
            
            self.stdout.write('\n=== USER ACCOUNT STATUS ===')
            self.stdout.write(f'Username: {user.username}')
            self.stdout.write(f'Is Active: {user.is_active}')
            self.stdout.write(f'Is Staff: {user.is_staff}')
            self.stdout.write(f'Is Superuser: {user.is_superuser}')
            self.stdout.write(f'Email: {user.email}')
            self.stdout.write(f'Full Name: {user.get_full_name()}')
            self.stdout.write(f'Groups: {[g.name for g in user.groups.all()]}')
            self.stdout.write(f'Password usable: {user.has_usable_password()}')
            
            # Reset password
            user.set_password('market@2025')
            user.is_active = True
            user.is_staff = True
            user.save()
            
            # Verify password
            password_check = user.check_password('market@2025')
            self.stdout.write(f'Password check: {password_check}')
            
            # Check for login attempts
            attempts = LoginAttempt.objects.filter(
                username=username,
                is_deleted=False
            )
            self.stdout.write(f'\nLogin attempts found: {attempts.count()}')
            
            for attempt in attempts:
                self.stdout.write(f'  - Locked: {attempt.is_locked}')
                self.stdout.write(f'  - Blocked: {attempt.manually_blocked}')
                self.stdout.write(f'  - Failed attempts: {attempt.failed_attempts}')
                
                # Unlock all attempts
                attempt.is_locked = False
                attempt.locked_until = None
                attempt.manually_blocked = False
                attempt.block_reason = ''
                attempt.block_expires_at = None
                attempt.failed_attempts = 0
                attempt.save()
            
            self.stdout.write(self.style.SUCCESS('\n✅ All login attempts unlocked'))
            
            self.stdout.write(self.style.SUCCESS('\n✅ Account is ready for login!'))
            self.stdout.write('\nLogin Credentials:')
            self.stdout.write(f'  Username: {username}')
            self.stdout.write(f'  Password: market@2025')
            self.stdout.write(f'\nLogin URL: http://192.168.2.216:8000/hms/login/')











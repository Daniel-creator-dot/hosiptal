"""
Management command to fix login issues for jeremiah.athoony
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction


class Command(BaseCommand):
    help = 'Fix login issues for jeremiah.athoony'

    def handle(self, *args, **options):
        with transaction.atomic():
            try:
                user = User.objects.get(username='jeremiah.athoony')
                
                self.stdout.write('=== USER ACCOUNT STATUS ===')
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
                try:
                    from hospital.models_login_attempts import LoginAttempt
                    attempts = LoginAttempt.objects.filter(
                        username='jeremiah.athoony',
                        is_deleted=False
                    )
                    self.stdout.write(f'\nLogin attempts found: {attempts.count()}')
                    
                    for attempt in attempts:
                        self.stdout.write(f'  - Locked: {attempt.is_currently_locked()}')
                        self.stdout.write(f'  - Blocked: {attempt.manual_block_active()}')
                        self.stdout.write(f'  - Failed attempts: {attempt.failed_attempts}')
                    
                    # Unlock all attempts
                    for attempt in attempts:
                        attempt.failed_attempts = 0
                        if hasattr(attempt, 'locked_until'):
                            attempt.locked_until = None
                        if hasattr(attempt, 'manual_block'):
                            attempt.manual_block = False
                        if hasattr(attempt, 'manual_block_until'):
                            attempt.manual_block_until = None
                        attempt.save()
                    self.stdout.write(self.style.SUCCESS('\n✅ All login attempts unlocked'))
                    
                except ImportError:
                    self.stdout.write(self.style.WARNING('⚠️  LoginAttempt model not available'))
                
                self.stdout.write(self.style.SUCCESS('\n✅ Account is ready for login!'))
                self.stdout.write('\nLogin Credentials:')
                self.stdout.write(f'  Username: jeremiah.athoony')
                self.stdout.write(f'  Password: market@2025')
                self.stdout.write(f'\nLogin URL: http://192.168.2.216:8000/hms/login/')
                
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR('❌ User jeremiah.athoony not found!'))











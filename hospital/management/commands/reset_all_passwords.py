"""
Django management command to reset all user passwords
This will reset passwords for all users to a default password
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Reset all user passwords to a default password'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='admin123',
            help='Default password to set for all users (default: admin123)',
        )
        parser.add_argument(
            '--username',
            type=str,
            default=None,
            help='Reset password for specific username only',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be reset without actually resetting',
        )

    def handle(self, *args, **options):
        password = options['password']
        username = options['username']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('\n=== Resetting User Passwords ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No passwords will be changed\n'))
        
        # Get users to reset (exclude AnonymousUser - it's not a real user)
        if username:
            users = User.objects.filter(username=username).exclude(username='AnonymousUser')
            if not users.exists():
                self.stdout.write(self.style.ERROR(f'❌ User "{username}" not found'))
                return
        else:
            users = User.objects.all().exclude(username='AnonymousUser')
        
        total_users = users.count()
        self.stdout.write(f'Found {total_users} user(s) to reset\n')
        
        if total_users == 0:
            self.stdout.write(self.style.WARNING('⚠️  No users found'))
            return
        
        # Reset passwords
        reset_count = 0
        for user in users:
            if not dry_run:
                user.set_password(password)
                user.save()
                reset_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Reset password for: {user.username}'))
            else:
                self.stdout.write(f'[DRY RUN] Would reset password for: {user.username}')
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Reset passwords for {reset_count} user(s)'))
            self.stdout.write(f'\nDefault password: {password}')
            self.stdout.write(self.style.WARNING('\n⚠️  IMPORTANT: Change passwords after first login!\n'))
        else:
            self.stdout.write(f'\n[DRY RUN] Would reset passwords for {total_users} user(s)')
            self.stdout.write(f'[DRY RUN] Password would be: {password}\n')


"""
Django Management Command to Unlock All Blocked Accounts
This will:
1. Activate all inactive user accounts (is_active=False -> True)
2. Unlock all LoginAttempt records (is_locked, manually_blocked)
3. Reset failed attempt counters
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Q
from hospital.models_login_attempts import LoginAttempt

User = get_user_model()


class Command(BaseCommand):
    help = 'Unlock all blocked user accounts and reset login attempt locks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be unlocked without actually unlocking',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('UNLOCKING ALL BLOCKED ACCOUNTS'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
        
        # 1. Activate all inactive users
        inactive_users = User.objects.filter(is_active=False)
        inactive_count = inactive_users.count()
        
        self.stdout.write(f'1. Found {inactive_count} inactive user accounts')
        if inactive_count > 0:
            if not dry_run:
                for user in inactive_users:
                    self.stdout.write(f'   ✅ Activating: {user.username}')
                inactive_users.update(is_active=True)
                self.stdout.write(self.style.SUCCESS(f'   ✅ Activated {inactive_count} user accounts'))
            else:
                for user in inactive_users:
                    self.stdout.write(f'   [DRY RUN] Would activate: {user.username}')
                self.stdout.write(f'   [DRY RUN] Would activate {inactive_count} user accounts')
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ No inactive users found'))
        self.stdout.write('')
        
        # 2. Unlock all LoginAttempt records
        locked_attempts = LoginAttempt.objects.filter(
            is_deleted=False
        ).filter(
            Q(is_locked=True) | Q(manually_blocked=True)
        )
        locked_count = locked_attempts.count()
        
        self.stdout.write(f'2. Found {locked_count} locked login attempts')
        if locked_count > 0:
            unlocked = 0
            for attempt in locked_attempts:
                if attempt.is_locked or attempt.manually_blocked:
                    if not dry_run:
                        attempt.unblock(note="Bulk unlock - all accounts unlocked")
                        unlocked += 1
                        self.stdout.write(f'   ✅ Unlocked: {attempt.username}')
                    else:
                        self.stdout.write(f'   [DRY RUN] Would unlock: {attempt.username}')
                        unlocked += 1
            if not dry_run:
                self.stdout.write(self.style.SUCCESS(f'   ✅ Unlocked {unlocked} login attempts'))
            else:
                self.stdout.write(f'   [DRY RUN] Would unlock {unlocked} login attempts')
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ No locked login attempts found'))
        self.stdout.write('')
        
        # 3. Reset all failed attempt counters
        attempts_with_failures = LoginAttempt.objects.filter(
            is_deleted=False,
            failed_attempts__gt=0
        )
        failure_count = attempts_with_failures.count()
        
        self.stdout.write(f'3. Found {failure_count} login attempts with failed attempts')
        if failure_count > 0:
            for attempt in attempts_with_failures:
                if not dry_run:
                    attempt.reset_attempts()
                    self.stdout.write(f'   ✅ Reset attempts for: {attempt.username}')
                else:
                    self.stdout.write(f'   [DRY RUN] Would reset attempts for: {attempt.username}')
            if not dry_run:
                self.stdout.write(self.style.SUCCESS(f'   ✅ Reset {failure_count} failed attempt counters'))
            else:
                self.stdout.write(f'   [DRY RUN] Would reset {failure_count} failed attempt counters')
        else:
            self.stdout.write(self.style.SUCCESS('   ✅ No failed attempts to reset'))
        self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('✅ ALL ACCOUNTS UNLOCKED!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        self.stdout.write('Summary:')
        self.stdout.write(f'  - Activated: {inactive_count} user accounts')
        self.stdout.write(f'  - Unlocked: {locked_count} login attempts')
        self.stdout.write(f'  - Reset: {failure_count} failed attempt counters')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('All users can now login!'))
        self.stdout.write('=' * 70)






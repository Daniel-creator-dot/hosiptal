"""
Django management command to fix all login issues
- Unlocks all locked accounts
- Activates all inactive users
- Resets all failed login attempts
- Creates superuser if needed
- Verifies database connection
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Q
from hospital.models_login_attempts import LoginAttempt
from django.db import connection
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Fix all login issues: unlock accounts, activate users, reset attempts, verify database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-superuser',
            action='store_true',
            help='Create a superuser if none exists',
        )
        parser.add_argument(
            '--superuser-username',
            type=str,
            default='admin',
            help='Username for superuser (default: admin)',
        )
        parser.add_argument(
            '--superuser-password',
            type=str,
            default='admin123',
            help='Password for superuser (default: admin123)',
        )
        parser.add_argument(
            '--superuser-email',
            type=str,
            default='admin@hospital.local',
            help='Email for superuser (default: admin@hospital.local)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Fixing All Login Issues ===\n'))
        
        # Step 1: Verify database connection
        self.stdout.write('[1/6] Verifying database connection...')
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            self.stdout.write(self.style.SUCCESS('    ✅ Database connection OK'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    ❌ Database connection failed: {e}'))
            return
        
        # Step 2: Check and fix users
        self.stdout.write('\n[2/6] Checking and fixing users...')
        total_users = User.objects.count()
        inactive_users = User.objects.filter(is_active=False)
        inactive_count = inactive_users.count()
        
        self.stdout.write(f'    Total users: {total_users}')
        self.stdout.write(f'    Inactive users: {inactive_count}')
        
        if inactive_count > 0:
            activated = inactive_users.update(is_active=True)
            self.stdout.write(self.style.SUCCESS(f'    ✅ Activated {activated} inactive user(s)'))
        else:
            self.stdout.write('    ✅ All users are active')
        
        # Step 3: Unlock all login attempts
        self.stdout.write('\n[3/6] Unlocking all login attempts...')
        locked_attempts = LoginAttempt.objects.filter(
            Q(is_locked=True) | 
            Q(manually_blocked=True) | 
            Q(locked_until__isnull=False)
        )
        locked_count = locked_attempts.count()
        self.stdout.write(f'    Locked/blocked attempts: {locked_count}')
        
        if locked_count > 0:
            unlocked = 0
            for attempt in locked_attempts:
                attempt.unblock(note='Bulk unlock from fix_all_logins command')
                unlocked += 1
            self.stdout.write(self.style.SUCCESS(f'    ✅ Unlocked {unlocked} login attempt(s)'))
        else:
            self.stdout.write('    ✅ No locked login attempts')
        
        # Step 4: Reset all failed attempt counters
        self.stdout.write('\n[4/6] Resetting failed login attempt counters...')
        failed_attempts = LoginAttempt.objects.filter(failed_attempts__gt=0)
        failed_count = failed_attempts.count()
        self.stdout.write(f'    Login attempts with failures: {failed_count}')
        
        if failed_count > 0:
            reset = failed_attempts.update(failed_attempts=0)
            self.stdout.write(self.style.SUCCESS(f'    ✅ Reset {reset} failed attempt counter(s)'))
        else:
            self.stdout.write('    ✅ No failed login attempts to reset')
        
        # Step 5: Check for superuser
        self.stdout.write('\n[5/6] Checking for superuser...')
        superuser_count = User.objects.filter(is_superuser=True).count()
        self.stdout.write(f'    Superusers: {superuser_count}')
        
        if superuser_count == 0:
            if options['create_superuser']:
                try:
                    username = options['superuser_username']
                    password = options['superuser_password']
                    email = options['superuser_email']
                    
                    # Check if user already exists
                    if User.objects.filter(username=username).exists():
                        self.stdout.write(self.style.WARNING(f'    ⚠️  User "{username}" already exists. Updating to superuser...'))
                        user = User.objects.get(username=username)
                        user.is_superuser = True
                        user.is_staff = True
                        user.is_active = True
                        user.set_password(password)
                        user.email = email
                        user.save()
                        self.stdout.write(self.style.SUCCESS(f'    ✅ Updated user "{username}" to superuser'))
                    else:
                        User.objects.create_superuser(
                            username=username,
                            email=email,
                            password=password
                        )
                        self.stdout.write(self.style.SUCCESS(f'    ✅ Created superuser "{username}"'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'    ❌ Failed to create superuser: {e}'))
            else:
                self.stdout.write(self.style.WARNING('    ⚠️  No superuser found. Use --create-superuser to create one.'))
        else:
            self.stdout.write('    ✅ Superuser exists')
        
        # Step 6: Verify database tables
        self.stdout.write('\n[6/6] Verifying database tables...')
        required_tables = [
            'auth_user',
            'hospital_loginattempt',
            'django_session',
        ]
        
        missing_tables = []
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            for table in required_tables:
                if table not in existing_tables:
                    missing_tables.append(table)
                else:
                    self.stdout.write(f'    ✅ Table "{table}" exists')
        
        if missing_tables:
            self.stdout.write(self.style.WARNING(f'    ⚠️  Missing tables: {", ".join(missing_tables)}'))
            self.stdout.write('    Run migrations: python manage.py migrate')
        else:
            self.stdout.write('    ✅ All required tables exist')
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n=== Login Issues Fixed ==='))
        self.stdout.write(f'✅ Activated users: {inactive_count}')
        self.stdout.write(f'✅ Unlocked attempts: {locked_count}')
        self.stdout.write(f'✅ Reset counters: {failed_count}')
        self.stdout.write(f'✅ Superusers: {superuser_count}')
        self.stdout.write('\n✅ All login issues have been fixed!\n')






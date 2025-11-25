"""
Management command to fix common server errors and misbehaviors
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.core.cache import cache
from django.db import connection
from django.conf import settings
import logging
import sys

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix common server errors and misbehaviors'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only check for errors, do not fix',
        )

    def handle(self, *args, **options):
        check_only = options.get('check_only', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('FIXING SERVER ERRORS'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        errors_found = []
        fixes_applied = []
        
        # 1. Check database connection
        self.stdout.write('\n[1] Checking database connection...')
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                self.stdout.write(self.style.SUCCESS('  ✓ Database connection OK'))
        except Exception as e:
            error_msg = f'  ✗ Database connection error: {e}'
            self.stdout.write(self.style.ERROR(error_msg))
            errors_found.append(error_msg)
            if not check_only:
                self.stdout.write(self.style.WARNING('  → Try: python manage.py migrate'))
        
        # 2. Check cache connection
        self.stdout.write('\n[2] Checking cache connection...')
        try:
            cache.set('test_key', 'test_value', 1)
            test_val = cache.get('test_key')
            if test_val == 'test_value':
                self.stdout.write(self.style.SUCCESS('  ✓ Cache connection OK'))
            else:
                raise Exception('Cache test failed')
        except Exception as e:
            error_msg = f'  ✗ Cache connection error: {e}'
            self.stdout.write(self.style.ERROR(error_msg))
            errors_found.append(error_msg)
            if not check_only:
                try:
                    cache.clear()
                    self.stdout.write(self.style.SUCCESS('  → Cleared cache'))
                    fixes_applied.append('Cleared cache')
                except:
                    pass
        
        # 3. Check for pending migrations
        self.stdout.write('\n[3] Checking for pending migrations...')
        try:
            from django.core.management import call_command
            from io import StringIO
            output = StringIO()
            call_command('showmigrations', '--plan', stdout=output, verbosity=0)
            output_str = output.getvalue()
            if '[ ]' in output_str:
                pending = output_str.count('[ ]')
                error_msg = f'  ⚠ {pending} pending migration(s) found'
                self.stdout.write(self.style.WARNING(error_msg))
                errors_found.append(error_msg)
                if not check_only:
                    self.stdout.write(self.style.SUCCESS('  → Run: python manage.py migrate'))
            else:
                self.stdout.write(self.style.SUCCESS('  ✓ No pending migrations'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠ Could not check migrations: {e}'))
        
        # 4. Clear all caches
        if not check_only:
            self.stdout.write('\n[4] Clearing all caches...')
            try:
                cache.clear()
                # Clear Redis if available
                try:
                    import redis
                    if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
                        redis_client = redis.from_url(settings.REDIS_URL)
                        redis_client.flushdb()
                except:
                    pass
                self.stdout.write(self.style.SUCCESS('  ✓ All caches cleared'))
                fixes_applied.append('Cleared all caches')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠ Cache clear warning: {e}'))
        
        # 5. Check static files
        self.stdout.write('\n[5] Checking static files...')
        try:
            from django.contrib.staticfiles.finders import get_finders
            finders = list(get_finders())
            if finders:
                self.stdout.write(self.style.SUCCESS('  ✓ Static files finders OK'))
            else:
                self.stdout.write(self.style.WARNING('  ⚠ No static files finders configured'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠ Static files check warning: {e}'))
        
        # 6. Validate settings
        self.stdout.write('\n[6] Validating settings...')
        try:
            # Check critical settings
            if not hasattr(settings, 'SECRET_KEY') or not settings.SECRET_KEY:
                error_msg = '  ✗ SECRET_KEY not set'
                self.stdout.write(self.style.ERROR(error_msg))
                errors_found.append(error_msg)
            else:
                self.stdout.write(self.style.SUCCESS('  ✓ SECRET_KEY OK'))
            
            if not hasattr(settings, 'DATABASES') or 'default' not in settings.DATABASES:
                error_msg = '  ✗ Database configuration missing'
                self.stdout.write(self.style.ERROR(error_msg))
                errors_found.append(error_msg)
            else:
                self.stdout.write(self.style.SUCCESS('  ✓ Database configuration OK'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠ Settings validation warning: {e}'))
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        if errors_found:
            self.stdout.write(self.style.ERROR(f'Found {len(errors_found)} issue(s):'))
            for error in errors_found:
                self.stdout.write(self.style.ERROR(f'  - {error}'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ No critical errors found!'))
        
        if fixes_applied:
            self.stdout.write(self.style.SUCCESS(f'\nApplied {len(fixes_applied)} fix(es):'))
            for fix in fixes_applied:
                self.stdout.write(self.style.SUCCESS(f'  - {fix}'))
        
        self.stdout.write('=' * 60)
        
        if errors_found and not check_only:
            self.stdout.write('\nRecommended actions:')
            self.stdout.write('  1. Run: python manage.py migrate')
            self.stdout.write('  2. Run: python manage.py clear_all_caches')
            self.stdout.write('  3. Restart the server')
        
        return 0 if not errors_found else 1





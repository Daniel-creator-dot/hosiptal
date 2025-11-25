"""
Management command to clear all caches (Django, Redis, static files)
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache, caches
from django.core.management import call_command
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clear all caches (Django cache, Redis, static files)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--redis-only',
            action='store_true',
            help='Only clear Redis cache',
        )
        parser.add_argument(
            '--django-only',
            action='store_true',
            help='Only clear Django cache',
        )
        parser.add_argument(
            '--static-only',
            action='store_true',
            help='Only clear static files',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('CLEARING ALL CACHES'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        redis_only = options.get('redis_only', False)
        django_only = options.get('django_only', False)
        static_only = options.get('static_only', False)
        
        success_count = 0
        total_operations = 0
        
        # Clear Django cache
        if not redis_only and not static_only:
            total_operations += 1
            try:
                cache.clear()
                self.stdout.write(self.style.SUCCESS('✓ Django default cache cleared'))
                success_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error clearing Django cache: {e}'))
            
            # Clear session cache
            try:
                if hasattr(settings, 'CACHES') and 'sessions' in settings.CACHES:
                    session_cache = caches['sessions']
                    session_cache.clear()
                    self.stdout.write(self.style.SUCCESS('✓ Session cache cleared'))
                    success_count += 1
                    total_operations += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Session cache clear skipped: {e}'))
        
        # Clear Redis directly
        if not django_only and not static_only:
            total_operations += 1
            try:
                import redis
                if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
                    redis_client = redis.from_url(settings.REDIS_URL)
                    redis_client.flushdb()
                    self.stdout.write(self.style.SUCCESS('✓ Redis cache cleared'))
                    success_count += 1
                else:
                    self.stdout.write(self.style.WARNING('  Redis URL not configured, skipping'))
            except ImportError:
                self.stdout.write(self.style.WARNING('  Redis library not available, skipping'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Redis clear skipped: {e}'))
        
        # Clear static files
        if not django_only and not redis_only:
            total_operations += 1
            try:
                call_command('collectstatic', '--noinput', '--clear', verbosity=0)
                self.stdout.write(self.style.SUCCESS('✓ Static files cleared'))
                success_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error clearing static files: {e}'))
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        if success_count == total_operations:
            self.stdout.write(self.style.SUCCESS(f'✓ All caches cleared successfully! ({success_count}/{total_operations})'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠ Some operations completed with warnings ({success_count}/{total_operations})'))
        self.stdout.write(self.style.SUCCESS('=' * 60))





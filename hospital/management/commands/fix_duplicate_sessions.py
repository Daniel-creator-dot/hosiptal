"""
Management command to fix duplicate active sessions
Closes duplicate sessions, keeping only the most recent one per user
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Max
from hospital.models import UserSession
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix duplicate active sessions by closing duplicates and keeping only the most recent session per user'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.WARNING('Checking for duplicate active sessions...'))
        
        # Find users with multiple active sessions
        duplicates = UserSession.objects.filter(
            is_active=True,
            logout_time__isnull=True
        ).values('user_id').annotate(
            count=Count('id'),
            latest_login=Max('login_time')
        ).filter(count__gt=1)
        
        if not duplicates.exists():
            self.stdout.write(self.style.SUCCESS('✅ No duplicate sessions found!'))
            return
        
        total_duplicates = duplicates.count()
        self.stdout.write(self.style.WARNING(f'Found {total_duplicates} user(s) with multiple active sessions'))
        
        fixed_count = 0
        closed_count = 0
        
        for dup in duplicates:
            user_id = dup['user_id']
            count = dup['count']
            latest_login = dup['latest_login']
            
            # Get all active sessions for this user
            user_sessions = list(UserSession.objects.filter(
                user_id=user_id,
                is_active=True,
                logout_time__isnull=True
            ).order_by('-login_time'))
            
            # Keep the most recent session, close the rest
            sessions_to_close = user_sessions[1:] if len(user_sessions) > 1 else []  # All except the first (most recent)
            
            self.stdout.write(f'\nUser ID {user_id}: {count} active sessions')
            self.stdout.write(f'  Keeping: Session from {user_sessions[0].login_time} (most recent)')
            
            for session in sessions_to_close:
                self.stdout.write(f'  Closing: Session {session.session_key} from {session.login_time}')
                
                if not dry_run:
                    session.is_active = False
                    session.logout_time = timezone.now()
                    session.save(update_fields=['is_active', 'logout_time', 'modified'])
                    closed_count += 1
            
            fixed_count += 1
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY RUN] Would fix {fixed_count} user(s) and close {closed_count} duplicate session(s)'))
            self.stdout.write(self.style.WARNING('Run without --dry-run to apply changes'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Fixed {fixed_count} user(s)'))
            self.stdout.write(self.style.SUCCESS(f'✅ Closed {closed_count} duplicate session(s)'))
            
            # Verify fix
            remaining_duplicates = UserSession.objects.filter(
                is_active=True,
                logout_time__isnull=True
            ).values('user_id').annotate(count=Count('id')).filter(count__gt=1).count()
            
            if remaining_duplicates == 0:
                self.stdout.write(self.style.SUCCESS('✅ All duplicates resolved!'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️  {remaining_duplicates} user(s) still have duplicates'))











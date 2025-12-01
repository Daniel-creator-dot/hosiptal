"""
Django Management Command to Check and Fix All Usernames (Staff and Non-Staff)
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from hospital.models import Staff
import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Check and fix all usernames (staff and non-staff users)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--fix-all',
            action='store_true',
            help='Apply all fixes',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        fix_all = options['fix_all']
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('ALL USERNAME CHECK AND FIX'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
        
        # Get all users
        all_users = User.objects.all()
        total_count = all_users.count()
        
        self.stdout.write(f'Total users to check: {total_count}')
        self.stdout.write('')
        
        # Statistics
        stats = {
            'empty_username': [],
            'duplicate_username': [],
            'invalid_username': [],
            'too_long': [],
        }
        
        # Check for issues
        self.stdout.write('[1/3] Checking for issues...')
        
        usernames = []
        for user in all_users:
            username = user.username
            
            # Check for empty username
            if not username or username.strip() == '':
                stats['empty_username'].append(user)
                continue
            
            usernames.append(username)
            
            # Check for invalid format
            # Django allows: alphanumeric, @, +, -, ., _
            if not re.match(r'^[\w.@+-]+$', username):
                stats['invalid_username'].append(user)
            
            # Check for too long (Django max is 150)
            if len(username) > 150:
                stats['too_long'].append(user)
        
        # Check for duplicates
        username_counts = Counter(usernames)
        for username, count in username_counts.items():
            if count > 1:
                duplicate_users = User.objects.filter(username=username)
                stats['duplicate_username'].extend(duplicate_users)
        
        # Print statistics
        self.stdout.write(f'  Empty usernames: {len(stats["empty_username"])}')
        self.stdout.write(f'  Duplicate usernames: {len(stats["duplicate_username"])}')
        self.stdout.write(f'  Invalid username formats: {len(stats["invalid_username"])}')
        self.stdout.write(f'  Usernames too long (>150 chars): {len(stats["too_long"])}')
        self.stdout.write('')
        
        # Show examples
        if stats['empty_username']:
            self.stdout.write('  Examples of empty usernames:')
            for user in stats['empty_username'][:5]:
                self.stdout.write(f'    - User ID {user.id}: Email={user.email}')
        
        if stats['duplicate_username']:
            self.stdout.write('  Examples of duplicate usernames:')
            seen = set()
            for user in stats['duplicate_username'][:10]:
                if user.username not in seen:
                    seen.add(user.username)
                    duplicates = User.objects.filter(username=user.username)
                    self.stdout.write(f'    - "{user.username}": {duplicates.count()} users')
        
        if stats['invalid_username']:
            self.stdout.write('  Examples of invalid usernames:')
            for user in stats['invalid_username'][:5]:
                self.stdout.write(f'    - User ID {user.id}: "{user.username}"')
        
        self.stdout.write('')
        
        # Fix issues
        fixed_count = 0
        
        if fix_all and stats['empty_username']:
            self.stdout.write('[2/3] Fixing empty usernames...')
            for user in stats['empty_username']:
                try:
                    new_username = self.generate_username(user)
                    if not dry_run:
                        with transaction.atomic():
                            user.username = new_username
                            user.save(update_fields=['username'])
                            fixed_count += 1
                            self.stdout.write(f'  ✅ Fixed empty username: User {user.id} -> {new_username}')
                    else:
                        self.stdout.write(f'  [DRY RUN] Would fix empty username: User {user.id} -> {new_username}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Error fixing user {user.id}: {e}'))
            self.stdout.write('')
        
        if fix_all and stats['duplicate_username']:
            self.stdout.write('[3/3] Fixing duplicate usernames...')
            # Group by username
            username_groups = {}
            for user in stats['duplicate_username']:
                username = user.username
                if username not in username_groups:
                    username_groups[username] = []
                username_groups[username].append(user)
            
            for username, user_list in username_groups.items():
                # Keep first one, fix others
                for idx, user in enumerate(user_list[1:], 1):
                    try:
                        new_username = self.generate_unique_username(user, exclude=username)
                        if not dry_run:
                            with transaction.atomic():
                                user.username = new_username
                                user.save(update_fields=['username'])
                                fixed_count += 1
                                self.stdout.write(f'  ✅ Fixed duplicate: User {user.id} ({user.email}) -> {new_username}')
                        else:
                            self.stdout.write(f'  [DRY RUN] Would fix duplicate: User {user.id} -> {new_username}')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ❌ Error fixing duplicate for user {user.id}: {e}'))
            self.stdout.write('')
        
        if fix_all and stats['invalid_username']:
            self.stdout.write('[4/3] Fixing invalid username formats...')
            for user in stats['invalid_username']:
                try:
                    new_username = self.generate_username(user)
                    if not dry_run:
                        with transaction.atomic():
                            user.username = new_username
                            user.save(update_fields=['username'])
                            fixed_count += 1
                            self.stdout.write(f'  ✅ Fixed invalid username: User {user.id} -> {new_username}')
                    else:
                        self.stdout.write(f'  [DRY RUN] Would fix invalid username: User {user.id} -> {new_username}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Error fixing invalid username for user {user.id}: {e}'))
            self.stdout.write('')
        
        if fix_all and stats['too_long']:
            self.stdout.write('[5/3] Fixing usernames that are too long...')
            for user in stats['too_long']:
                try:
                    new_username = user.username[:150]  # Truncate to 150 chars
                    # Ensure it's still unique
                    new_username = self.generate_unique_username(user, base_username=new_username)
                    if not dry_run:
                        with transaction.atomic():
                            user.username = new_username
                            user.save(update_fields=['username'])
                            fixed_count += 1
                            self.stdout.write(f'  ✅ Fixed long username: User {user.id} -> {new_username}')
                    else:
                        self.stdout.write(f'  [DRY RUN] Would fix long username: User {user.id} -> {new_username}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Error fixing long username for user {user.id}: {e}'))
            self.stdout.write('')
        
        # Summary
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        self.stdout.write(f'Total users checked: {total_count}')
        self.stdout.write(f'Issues found: {len(stats["empty_username"]) + len(stats["duplicate_username"]) + len(stats["invalid_username"]) + len(stats["too_long"])}')
        self.stdout.write(f'Issues fixed: {fixed_count}')
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were made. Run without --dry-run to apply fixes.'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Username check and fix complete!'))
        
        self.stdout.write('')
    
    def generate_username(self, user):
        """Generate a username from user information"""
        # Try email first (before @)
        if user.email:
            email_username = user.email.split('@')[0]
            # Clean email username
            email_username = re.sub(r'[^a-z0-9._+-]', '', email_username.lower())
            if email_username and len(email_username) <= 150:
                return email_username[:30]
        
        # Try first_name.last_name
        first_name = (user.first_name or '').lower().strip()
        last_name = (user.last_name or '').lower().strip()
        
        # Clean names
        first_name = re.sub(r'[^a-z0-9]', '', first_name)
        last_name = re.sub(r'[^a-z0-9]', '', last_name)
        
        if first_name and last_name:
            username = f"{first_name}.{last_name}"[:30]
        elif first_name:
            username = first_name[:30]
        elif last_name:
            username = last_name[:30]
        else:
            username = f"user{user.id}"[:30]
        
        return username
    
    def generate_unique_username(self, user, base_username=None, exclude=None):
        """Generate a unique username"""
        if not base_username:
            base_username = self.generate_username(user)
        
        username = base_username
        counter = 1
        
        while User.objects.filter(username=username).exclude(id=user.id).exists():
            if exclude and username == exclude:
                break
            username = f"{base_username}{counter}"[:30]
            counter += 1
            if counter > 1000:  # Safety limit
                username = f"user{user.id}{counter}"[:30]
                break
        
        return username






"""
Django Management Command to Check and Fix All Staff Usernames
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from hospital.models import Staff
import re
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = 'Check and fix all staff usernames'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--fix-missing',
            action='store_true',
            help='Create users for staff without user accounts',
        )
        parser.add_argument(
            '--fix-duplicates',
            action='store_true',
            help='Fix duplicate usernames',
        )
        parser.add_argument(
            '--fix-invalid',
            action='store_true',
            help='Fix invalid username formats',
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
        self.stdout.write(self.style.SUCCESS('STAFF USERNAME CHECK AND FIX'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
        
        # Get all staff
        all_staff = Staff.objects.filter(is_deleted=False).select_related('user')
        total_count = all_staff.count()
        
        self.stdout.write(f'Total staff to check: {total_count}')
        self.stdout.write('')
        
        # Statistics
        stats = {
            'missing_user': [],
            'empty_username': [],
            'duplicate_username': [],
            'invalid_username': [],
            'no_staff_linked': [],
        }
        
        # Check for issues
        self.stdout.write('[1/4] Checking for issues...')
        
        for staff in all_staff:
            # Check for missing user
            if not staff.user:
                stats['missing_user'].append(staff)
                continue
            
            # Check for empty username
            if not staff.user.username or staff.user.username.strip() == '':
                stats['empty_username'].append(staff)
            
            # Check for invalid username format
            username = staff.user.username
            if username:
                # Username should be alphanumeric, underscore, or hyphen, max 150 chars
                if not re.match(r'^[\w.@+-]+$', username) or len(username) > 150:
                    stats['invalid_username'].append(staff)
        
        # Check for duplicate usernames
        username_counts = {}
        for staff in all_staff:
            if staff.user and staff.user.username:
                username = staff.user.username
                if username not in username_counts:
                    username_counts[username] = []
                username_counts[username].append(staff)
        
        for username, staff_list in username_counts.items():
            if len(staff_list) > 1:
                stats['duplicate_username'].extend(staff_list)
        
        # Check for users without staff profiles
        all_users = User.objects.all()
        for user in all_users:
            if not hasattr(user, 'staff') and user.is_staff:
                stats['no_staff_linked'].append(user)
        
        # Print statistics
        self.stdout.write(f'  Missing user accounts: {len(stats["missing_user"])}')
        self.stdout.write(f'  Empty usernames: {len(stats["empty_username"])}')
        self.stdout.write(f'  Duplicate usernames: {len(stats["duplicate_username"])}')
        self.stdout.write(f'  Invalid username formats: {len(stats["invalid_username"])}')
        self.stdout.write(f'  Users without staff profiles: {len(stats["no_staff_linked"])}')
        self.stdout.write('')
        
        # Fix issues
        fixed_count = 0
        
        if (fix_all or options['fix_missing']) and stats['missing_user']:
            self.stdout.write('[2/4] Fixing missing user accounts...')
            for staff in stats['missing_user']:
                try:
                    # Generate username from staff name
                    username = self.generate_username(staff)
                    
                    if not dry_run:
                        with transaction.atomic():
                            user = User.objects.create_user(
                                username=username,
                                email=staff.personal_email or f'{username}@hospital.local',
                                first_name=staff.first_name or '',
                                last_name=staff.last_name or '',
                                is_staff=True,
                                is_active=True,
                            )
                            staff.user = user
                            staff.save(update_fields=['user'])
                            fixed_count += 1
                            self.stdout.write(f'  ✅ Created user for {staff.full_name}: {username}')
                    else:
                        self.stdout.write(f'  [DRY RUN] Would create user for {staff.full_name}: {username}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Error creating user for {staff.full_name}: {e}'))
            self.stdout.write('')
        
        if (fix_all or options['fix_duplicates']) and stats['duplicate_username']:
            self.stdout.write('[3/4] Fixing duplicate usernames...')
            # Group by username
            username_groups = {}
            for staff in stats['duplicate_username']:
                username = staff.user.username
                if username not in username_groups:
                    username_groups[username] = []
                username_groups[username].append(staff)
            
            for username, staff_list in username_groups.items():
                # Keep first one, fix others
                for idx, staff in enumerate(staff_list[1:], 1):
                    try:
                        new_username = self.generate_unique_username(staff, exclude=username)
                        if not dry_run:
                            with transaction.atomic():
                                staff.user.username = new_username
                                staff.user.save(update_fields=['username'])
                                fixed_count += 1
                                self.stdout.write(f'  ✅ Fixed duplicate: {staff.full_name} -> {new_username}')
                        else:
                            self.stdout.write(f'  [DRY RUN] Would fix duplicate: {staff.full_name} -> {new_username}')
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ❌ Error fixing duplicate for {staff.full_name}: {e}'))
            self.stdout.write('')
        
        if (fix_all or options['fix_invalid']) and stats['invalid_username']:
            self.stdout.write('[4/4] Fixing invalid username formats...')
            for staff in stats['invalid_username']:
                try:
                    new_username = self.generate_username(staff)
                    if not dry_run:
                        with transaction.atomic():
                            staff.user.username = new_username
                            staff.user.save(update_fields=['username'])
                            fixed_count += 1
                            self.stdout.write(f'  ✅ Fixed invalid username: {staff.full_name} -> {new_username}')
                    else:
                        self.stdout.write(f'  [DRY RUN] Would fix invalid username: {staff.full_name} -> {new_username}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Error fixing invalid username for {staff.full_name}: {e}'))
            self.stdout.write('')
        
        # Fix empty usernames
        if stats['empty_username']:
            self.stdout.write('[5/4] Fixing empty usernames...')
            for staff in stats['empty_username']:
                try:
                    new_username = self.generate_username(staff)
                    if not dry_run:
                        with transaction.atomic():
                            staff.user.username = new_username
                            staff.user.save(update_fields=['username'])
                            fixed_count += 1
                            self.stdout.write(f'  ✅ Fixed empty username: {staff.full_name} -> {new_username}')
                    else:
                        self.stdout.write(f'  [DRY RUN] Would fix empty username: {staff.full_name} -> {new_username}')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ❌ Error fixing empty username for {staff.full_name}: {e}'))
            self.stdout.write('')
        
        # Summary
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        self.stdout.write(f'Total staff checked: {total_count}')
        self.stdout.write(f'Issues found: {len(stats["missing_user"]) + len(stats["empty_username"]) + len(stats["duplicate_username"]) + len(stats["invalid_username"])}')
        self.stdout.write(f'Issues fixed: {fixed_count}')
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes were made. Run without --dry-run to apply fixes.'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ Staff username check and fix complete!'))
        
        self.stdout.write('')
    
    def generate_username(self, staff):
        """Generate a username from staff information"""
        # Staff model uses user.first_name and user.last_name
        if staff.user:
            first_name = (staff.user.first_name or '').lower().strip()
            last_name = (staff.user.last_name or '').strip()
        else:
            first_name = ''
            last_name = ''
        
        # Clean names (remove special characters, keep only alphanumeric)
        first_name = re.sub(r'[^a-z0-9]', '', first_name)
        last_name = re.sub(r'[^a-z0-9]', '', last_name.lower())
        
        if first_name and last_name:
            username = f"{first_name}.{last_name}"[:30]
        elif first_name:
            username = first_name[:30]
        elif last_name:
            username = last_name[:30]
        elif staff.employee_id:
            username = staff.employee_id.lower().replace('-', '')[:30]
        else:
            username = f"staff{staff.id}"[:30]
        
        # Ensure it's unique
        return self.generate_unique_username(staff, base_username=username)
    
    def generate_unique_username(self, staff, base_username=None, exclude=None):
        """Generate a unique username"""
        if not base_username:
            base_username = self.generate_username(staff)
        
        username = base_username
        counter = 1
        
        while User.objects.filter(username=username).exclude(id=staff.user.id if staff.user else None).exists():
            if exclude and username == exclude:
                break
            username = f"{base_username}{counter}"[:30]
            counter += 1
        
        return username


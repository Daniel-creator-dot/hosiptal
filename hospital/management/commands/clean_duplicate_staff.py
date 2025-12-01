"""
Django Management Command to Clean Duplicate Staff Records
Removes duplicate User records with numbered suffixes and merges them
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db import transaction
from django.contrib.auth.models import User
from hospital.models import Staff


class Command(BaseCommand):
    help = 'Clean duplicate staff records by merging numbered username variants'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
        parser.add_argument(
            '--merge',
            action='store_true',
            help='Actually merge duplicates (default is just to show them)'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        merge = options.get('merge', False)
        
        if dry_run:
            merge = False
        
        self.stdout.write(self.style.SUCCESS('=== CLEANING DUPLICATE STAFF RECORDS ===\n'))
        
        if merge:
            self.stdout.write(self.style.WARNING('MERGE MODE: Duplicates will be merged!\n'))
        elif dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: Showing what would be done\n'))
        else:
            self.stdout.write(self.style.WARNING('REPORT MODE: Just showing duplicates (use --merge to actually merge)\n'))
        
        # Find users with numbered suffixes that match base usernames
        self.find_and_merge_numbered_duplicates(merge)
    
    def find_and_merge_numbered_duplicates(self, merge=False):
        """Find users with numbered suffixes and merge them with base username"""
        self.stdout.write(self.style.WARNING('\n--- Finding Duplicate Users with Numbered Suffixes ---'))
        
        all_users = User.objects.all().order_by('username')
        user_groups = {}
        
        # Group users by base name (without number suffix)
        for user in all_users:
            base_name = self.get_base_username(user.username)
            if base_name not in user_groups:
                user_groups[base_name] = []
            user_groups[base_name].append(user)
        
        # Find groups with multiple users (potential duplicates)
        duplicate_groups = {k: v for k, v in user_groups.items() if len(v) > 1}
        
        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS('  No duplicate user groups found\n'))
            return
        
        self.stdout.write(f'  Found {len(duplicate_groups)} groups of potential duplicates:\n')
        
        total_merged = 0
        for base_name, users in duplicate_groups.items():
            # Sort by username - base name first, then numbered ones
            users_sorted = sorted(users, key=lambda u: (
                0 if u.username == base_name else 1,
                u.username
            ))
            
            primary = users_sorted[0]
            duplicates = users_sorted[1:]
            
            # Check if they have the same first/last name (likely duplicates)
            same_name = all(
                u.first_name.lower() == primary.first_name.lower() and
                u.last_name.lower() == primary.last_name.lower()
                for u in duplicates
            )
            
            if same_name and primary.first_name and primary.last_name:
                self.stdout.write(f'\n  [{len(users)} users] {primary.get_full_name()} ({base_name}):')
                self.stdout.write(f'    PRIMARY: {primary.username} (ID: {primary.id})')
                
                for dup in duplicates:
                    staff_count = Staff.objects.filter(user=dup, is_deleted=False).count()
                    self.stdout.write(
                        f'    DUPLICATE: {dup.username} (ID: {dup.id}, Staff records: {staff_count})'
                    )
                
                if merge:
                    merged = self.merge_user_duplicates(primary, duplicates)
                    total_merged += merged
                else:
                    total_merged += len(duplicates)
        
        if merge:
            self.stdout.write(self.style.SUCCESS(f'\n  Successfully merged {total_merged} duplicate user(s)'))
        else:
            self.stdout.write(f'\n  Would merge {total_merged} duplicate user(s) (use --merge to proceed)')
    
    def get_base_username(self, username):
        """Extract base username without number suffix"""
        # Remove trailing digits and optional separator
        import re
        # Match pattern like "name1", "name2", etc.
        match = re.match(r'^(.+?)(\d+)$', username)
        if match:
            return match.group(1).rstrip('.')
        return username
    
    def merge_user_duplicates(self, primary_user, duplicate_users):
        """Merge duplicate users into primary user"""
        merged_count = 0
        
        with transaction.atomic():
            for dup_user in duplicate_users:
                try:
                    # Check if duplicate has staff record
                    dup_staff = Staff.objects.filter(user=dup_user, is_deleted=False).first()
                    primary_staff = Staff.objects.filter(user=primary_user, is_deleted=False).first()
                    
                    if dup_staff and not primary_staff:
                        # Move staff record to primary user
                        dup_staff.user = primary_user
                        dup_staff.save()
                        self.stdout.write(
                            f'      Moved staff record from {dup_user.username} to {primary_user.username}'
                        )
                    elif dup_staff and primary_staff:
                        # Both have staff records - mark duplicate as deleted
                        dup_staff.is_deleted = True
                        dup_staff.save()
                        self.stdout.write(
                            f'      Marked duplicate staff record as deleted: {dup_user.username}'
                        )
                    
                    # Delete the duplicate user
                    dup_user.delete()
                    merged_count += 1
                    self.stdout.write(f'      Deleted duplicate user: {dup_user.username}')
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'      Error merging {dup_user.username}: {str(e)}')
                    )
        
        return merged_count



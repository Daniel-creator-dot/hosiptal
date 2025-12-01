"""
Django Management Command to Find and Remove Duplicate Staff Records
Identifies staff with duplicate users or employee_ids and removes duplicates
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.db import transaction
from django.contrib.auth.models import User
from hospital.models import Staff


class Command(BaseCommand):
    help = 'Find and optionally remove duplicate staff records'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Actually remove duplicates (default is just to show them)'
        )
        parser.add_argument(
            '--keep-oldest',
            action='store_true',
            default=True,
            help='Keep the oldest record when removing duplicates (default: True)'
        )
    
    def handle(self, *args, **options):
        remove = options['remove']
        keep_oldest = options['keep_oldest']
        
        self.stdout.write(self.style.SUCCESS('=== DUPLICATE STAFF FINDER ===\n'))
        
        if remove:
            self.stdout.write(self.style.WARNING('REMOVE MODE: Duplicates will be removed!\n'))
        else:
            self.stdout.write(self.style.WARNING('REPORT MODE: Just showing duplicates (use --remove to actually remove)\n'))
        
        # Find duplicates by user (OneToOneField violation)
        self.find_duplicates_by_user(remove, keep_oldest)
        
        # Find duplicates by employee_id
        self.find_duplicates_by_employee_id(remove, keep_oldest)
    
    def find_duplicates_by_user(self, remove=False, keep_oldest=True):
        """Find staff records with duplicate users"""
        self.stdout.write(self.style.WARNING('\n--- Duplicates by User (OneToOneField violation) ---'))
        
        # Find users with multiple staff records
        duplicates = Staff.objects.filter(is_deleted=False).values('user').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        total_groups = duplicates.count()
        
        if total_groups == 0:
            self.stdout.write(self.style.SUCCESS('  No duplicate users found\n'))
        else:
            self.stdout.write(f'  Found {total_groups} users with multiple staff records:\n')
            
            total_duplicates = 0
            for dup in duplicates:
                user_id = dup['user']
                count = dup['count']
                total_duplicates += (count - 1)  # Count duplicates (excluding the one to keep)
                
                try:
                    user = User.objects.get(id=user_id)
                    staff_records = Staff.objects.filter(user=user, is_deleted=False).order_by('created')
                    
                    self.stdout.write(f'\n  [{count} records] User: {user.get_full_name()} ({user.username}):')
                    for staff in staff_records:
                        self.stdout.write(
                            f'    - Staff ID: {staff.id}, Employee ID: {staff.employee_id}, '
                            f'Profession: {staff.get_profession_display()}, '
                            f'Created: {staff.created.date()}, Active: {staff.is_active}'
                        )
                    
                    if remove:
                        self.remove_duplicate_staff_by_user(staff_records, keep_oldest)
                except User.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'    User ID {user_id} not found'))
            
            if not remove:
                self.stdout.write(f'\n  Total duplicate records to remove: {total_duplicates}')
    
    def find_duplicates_by_employee_id(self, remove=False, keep_oldest=True):
        """Find staff records with duplicate employee_ids"""
        self.stdout.write(self.style.WARNING('\n--- Duplicates by Employee ID ---'))
        
        # Find employee_ids with multiple staff records
        duplicates = Staff.objects.filter(
            is_deleted=False,
            employee_id__isnull=False
        ).exclude(employee_id='').values('employee_id').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        total_groups = duplicates.count()
        
        if total_groups == 0:
            self.stdout.write(self.style.SUCCESS('  No duplicate employee IDs found\n'))
        else:
            self.stdout.write(f'  Found {total_groups} employee IDs with multiple staff records:\n')
            
            total_duplicates = 0
            for dup in duplicates:
                employee_id = dup['employee_id']
                count = dup['count']
                total_duplicates += (count - 1)  # Count duplicates (excluding the one to keep)
                
                staff_records = Staff.objects.filter(
                    employee_id=employee_id,
                    is_deleted=False
                ).order_by('created')
                
                self.stdout.write(f'\n  [{count} records] Employee ID: {employee_id}:')
                for staff in staff_records:
                    self.stdout.write(
                        f'    - Staff ID: {staff.id}, User: {staff.user.get_full_name()} ({staff.user.username}), '
                        f'Profession: {staff.get_profession_display()}, '
                        f'Created: {staff.created.date()}, Active: {staff.is_active}'
                    )
                
                if remove:
                    self.remove_duplicate_staff_by_employee_id(staff_records, keep_oldest)
            
            if not remove:
                self.stdout.write(f'\n  Total duplicate records to remove: {total_duplicates}')
    
    def remove_duplicate_staff_by_user(self, staff_records, keep_oldest=True):
        """Remove duplicate staff records for the same user"""
        if len(staff_records) <= 1:
            return
        
        # Sort by creation date
        if keep_oldest:
            staff_sorted = sorted(staff_records, key=lambda x: x.created)
        else:
            staff_sorted = sorted(staff_records, key=lambda x: x.created, reverse=True)
        
        primary = staff_sorted[0]
        duplicates = staff_sorted[1:]
        
        self.stdout.write(f'\n    KEEPING: Staff ID {primary.id} ({primary.user.get_full_name()})')
        
        with transaction.atomic():
            for dup in duplicates:
                try:
                    # Check if this duplicate has any related records that need to be handled
                    # For now, we'll just mark as deleted
                    dup.is_deleted = True
                    dup.save()
                    
                    self.stdout.write(
                        f'      Removed: Staff ID {dup.id} ({dup.user.get_full_name()}, '
                        f'Employee ID: {dup.employee_id})'
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'      Error removing Staff ID {dup.id}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'    Successfully removed {len(duplicates)} duplicate(s)'))
    
    def remove_duplicate_staff_by_employee_id(self, staff_records, keep_oldest=True):
        """Remove duplicate staff records with the same employee_id"""
        if len(staff_records) <= 1:
            return
        
        # Sort by creation date
        if keep_oldest:
            staff_sorted = sorted(staff_records, key=lambda x: x.created)
        else:
            staff_sorted = sorted(staff_records, key=lambda x: x.created, reverse=True)
        
        primary = staff_sorted[0]
        duplicates = staff_sorted[1:]
        
        self.stdout.write(f'\n    KEEPING: Staff ID {primary.id} ({primary.user.get_full_name()})')
        
        with transaction.atomic():
            for dup in duplicates:
                try:
                    # Generate a new employee_id for the duplicate
                    # This prevents conflicts while preserving the record
                    if dup.employee_id:
                        # Try to generate a unique employee_id
                        base_id = dup.employee_id
                        counter = 1
                        new_employee_id = f"{base_id}-{counter}"
                        while Staff.objects.filter(employee_id=new_employee_id, is_deleted=False).exists():
                            counter += 1
                            new_employee_id = f"{base_id}-{counter}"
                        
                        dup.employee_id = new_employee_id
                        dup.save()
                        self.stdout.write(
                            f'      Updated Employee ID: Staff ID {dup.id} ({dup.user.get_full_name()}) '
                            f'-> {new_employee_id}'
                        )
                    else:
                        # If no employee_id, just mark as deleted
                        dup.is_deleted = True
                        dup.save()
                        self.stdout.write(
                            f'      Removed: Staff ID {dup.id} ({dup.user.get_full_name()})'
                        )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'      Error processing Staff ID {dup.id}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'    Successfully processed {len(duplicates)} duplicate(s)'))



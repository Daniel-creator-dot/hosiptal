"""
Merge duplicate users identified by phone number and name
Deletes duplicate user accounts and their staff records, keeping only the most recent
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import transaction
from django.contrib.auth.models import User
from hospital.models import Staff


class Command(BaseCommand):
    help = 'Merge duplicate users by phone number and name, keeping only the most recent'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Actually delete duplicates (default: False, dry-run mode)'
        )
    
    def handle(self, *args, **options):
        force = options.get('force', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('MERGE DUPLICATE USERS BY PHONE NUMBER'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write()
        
        if not force:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: Use --force to actually delete\n'))
        
        # Find phone numbers with multiple staff records
        phone_duplicates = Staff.objects.filter(
            is_deleted=False,
            phone_number__isnull=False
        ).exclude(phone_number='').values('phone_number').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        total_groups = phone_duplicates.count()
        
        if total_groups == 0:
            self.stdout.write(self.style.SUCCESS('✅ No duplicate phone numbers found!\n'))
            return
        
        self.stdout.write(f'Found {total_groups} phone numbers with multiple staff records\n')
        
        total_to_delete = 0
        users_to_delete = []
        staff_to_delete = []
        
        for dup in phone_duplicates:
            phone = dup['phone_number']
            count = dup['count']
            
            staff_records = Staff.objects.filter(
                phone_number=phone,
                is_deleted=False
            ).select_related('user').order_by('-created')
            
            # Group by user name to identify true duplicates
            name_groups = {}
            for staff in staff_records:
                full_name = staff.user.get_full_name() or staff.user.username
                if full_name not in name_groups:
                    name_groups[full_name] = []
                name_groups[full_name].append(staff)
            
            # For each name group with multiple records, keep the most recent
            for name, staff_list in name_groups.items():
                if len(staff_list) > 1:
                    # Sort by created date, most recent first
                    staff_list_sorted = sorted(staff_list, key=lambda x: x.created, reverse=True)
                    keep_staff = staff_list_sorted[0]
                    delete_staff_list = staff_list_sorted[1:]
                    
                    self.stdout.write(
                        f'\n  Name: {name}, Phone: {phone} - {len(staff_list)} records'
                    )
                    self.stdout.write(
                        f'    Keeping: User {keep_staff.user.username} (ID: {keep_staff.user_id}), '
                        f'Staff ID: {keep_staff.id}, Employee ID: {keep_staff.employee_id}, '
                        f'Created: {keep_staff.created.date()}'
                    )
                    
                    for staff in delete_staff_list:
                        self.stdout.write(
                            f'    Deleting: User {staff.user.username} (ID: {staff.user_id}), '
                            f'Staff ID: {staff.id}, Employee ID: {staff.employee_id}, '
                            f'Created: {staff.created.date()}'
                        )
                        staff_to_delete.append(staff)
                        if staff.user not in users_to_delete:
                            users_to_delete.append(staff.user)
                        total_to_delete += 1
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(f'SUMMARY: {total_to_delete} duplicate staff records will be deleted')
        self.stdout.write(f'         {len(users_to_delete)} duplicate user accounts will be deleted')
        self.stdout.write('=' * 70)
        
        if not force:
            self.stdout.write(self.style.WARNING('\nRun with --force to actually delete these records'))
            return
        
        # Actually delete
        self.stdout.write(self.style.WARNING('\nDeleting duplicates...'))
        
        deleted_staff = 0
        deleted_users = 0
        errors = 0
        
        with transaction.atomic():
            # Delete staff records first (soft delete)
            for staff in staff_to_delete:
                try:
                    staff.is_deleted = True
                    staff.save(update_fields=['is_deleted'])
                    deleted_staff += 1
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'  Error deleting Staff ID {staff.id}: {str(e)}')
                    )
            
            # Delete user accounts (hard delete - they're duplicates)
            for user in users_to_delete:
                try:
                    # Check if user has any remaining non-deleted staff
                    remaining_staff = Staff.objects.filter(user=user, is_deleted=False).count()
                    if remaining_staff == 0:
                        user.delete()
                        deleted_users += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Skipping user {user.username} - still has {remaining_staff} active staff records'
                            )
                        )
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'  Error deleting User {user.username}: {str(e)}')
                    )
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS(f'✅ Deleted {deleted_staff} duplicate staff records'))
        self.stdout.write(self.style.SUCCESS(f'✅ Deleted {deleted_users} duplicate user accounts'))
        if errors > 0:
            self.stdout.write(self.style.ERROR(f'❌ Errors: {errors}'))
        self.stdout.write('=' * 70)



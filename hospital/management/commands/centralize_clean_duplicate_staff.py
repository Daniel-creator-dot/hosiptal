"""
Centralized Command to Clean ALL Duplicate Staff Records
Comprehensive cleanup that handles all types of duplicates
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q, OuterRef, Subquery
from django.db import transaction
from django.contrib.auth.models import User
from hospital.models import Staff


class Command(BaseCommand):
    help = 'Comprehensive cleanup of ALL duplicate staff records'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Actually delete duplicates (default: False, dry-run mode)'
        )
    
    def handle(self, *args, **options):
        force = options.get('force', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('CENTRALIZED DUPLICATE STAFF CLEANUP'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write()
        
        if not force:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: Use --force to actually delete\n'))
        
        # Method 1: Find duplicates by user (OneToOneField violation)
        self.stdout.write(self.style.WARNING('--- Checking for duplicates by User ---'))
        duplicates_by_user = self.find_duplicates_by_user()
        
        # Method 2: Find duplicates by employee_id
        self.stdout.write(self.style.WARNING('\n--- Checking for duplicates by Employee ID ---'))
        duplicates_by_employee_id = self.find_duplicates_by_employee_id()
        
        # Method 3: Find duplicates by user email/username
        self.stdout.write(self.style.WARNING('\n--- Checking for duplicates by User Email/Username ---'))
        duplicates_by_email = self.find_duplicates_by_email()
        
        total_to_delete = len(duplicates_by_user) + len(duplicates_by_employee_id) + len(duplicates_by_email)
        
        if total_to_delete == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ No duplicates found!'))
            return
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(f'SUMMARY: {total_to_delete} duplicate records found')
        self.stdout.write('=' * 70)
        
        if not force:
            self.stdout.write(self.style.WARNING('\nRun with --force to delete these duplicates'))
            return
        
        # Delete all duplicates
        self.stdout.write(self.style.WARNING('\nDeleting duplicates...'))
        deleted = 0
        
        with transaction.atomic():
            # Delete by user duplicates
            for staff in duplicates_by_user:
                try:
                    staff.is_deleted = True
                    staff.save(update_fields=['is_deleted'])
                    deleted += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error deleting Staff ID {staff.id}: {e}'))
            
            # Delete by employee_id duplicates
            for staff in duplicates_by_employee_id:
                try:
                    staff.is_deleted = True
                    staff.save(update_fields=['is_deleted'])
                    deleted += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error deleting Staff ID {staff.id}: {e}'))
            
            # Delete by email duplicates
            for staff in duplicates_by_email:
                try:
                    staff.is_deleted = True
                    staff.save(update_fields=['is_deleted'])
                    deleted += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error deleting Staff ID {staff.id}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Deleted {deleted} duplicate records'))
        
        # Verify
        remaining = self.find_duplicates_by_user() + self.find_duplicates_by_employee_id() + self.find_duplicates_by_email()
        if len(remaining) == 0:
            self.stdout.write(self.style.SUCCESS('✅ All duplicates removed!'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️  {len(remaining)} duplicates still remain'))
    
    def find_duplicates_by_user(self):
        """Find staff records with duplicate users"""
        duplicates_to_delete = []
        
        # Find users with multiple staff records
        user_counts = Staff.objects.filter(is_deleted=False).values('user').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        for item in user_counts:
            user_id = item['user']
            try:
                user = User.objects.get(id=user_id)
                staff_records = Staff.objects.filter(
                    user=user,
                    is_deleted=False
                ).order_by('-created')  # Most recent first
                
                # Keep the first (most recent), delete the rest
                keep = staff_records.first()
                to_delete = list(staff_records[1:])
                
                if to_delete:
                    self.stdout.write(
                        f'  User: {user.get_full_name()} ({user.username}) - '
                        f'Keeping: {keep.id}, Deleting: {len(to_delete)}'
                    )
                    duplicates_to_delete.extend(to_delete)
            except User.DoesNotExist:
                pass
        
        return duplicates_to_delete
    
    def find_duplicates_by_employee_id(self):
        """Find staff records with duplicate employee_ids"""
        duplicates_to_delete = []
        
        # Find employee_ids with multiple staff records
        emp_id_counts = Staff.objects.filter(
            is_deleted=False,
            employee_id__isnull=False
        ).exclude(employee_id='').values('employee_id').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        for item in emp_id_counts:
            emp_id = item['employee_id']
            staff_records = Staff.objects.filter(
                employee_id=emp_id,
                is_deleted=False
            ).order_by('-created')
            
            # Keep the first, delete the rest
            keep = staff_records.first()
            to_delete = list(staff_records[1:])
            
            if to_delete:
                self.stdout.write(
                    f'  Employee ID: {emp_id} - '
                    f'Keeping: {keep.id}, Deleting: {len(to_delete)}'
                )
                duplicates_to_delete.extend(to_delete)
        
        return duplicates_to_delete
    
    def find_duplicates_by_email(self):
        """Find staff records with duplicate user emails"""
        duplicates_to_delete = []
        
        # Find users with same email but different staff records
        from django.db.models import Count
        email_counts = Staff.objects.filter(
            is_deleted=False
        ).values('user__email').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        for item in email_counts:
            email = item['user__email']
            if not email:
                continue
            
            staff_records = Staff.objects.filter(
                user__email=email,
                is_deleted=False
            ).order_by('-created')
            
            # Keep the first, delete the rest
            keep = staff_records.first()
            to_delete = list(staff_records[1:])
            
            if to_delete:
                self.stdout.write(
                    f'  Email: {email} - '
                    f'Keeping: {keep.id}, Deleting: {len(to_delete)}'
                )
                duplicates_to_delete.extend(to_delete)
        
        return duplicates_to_delete



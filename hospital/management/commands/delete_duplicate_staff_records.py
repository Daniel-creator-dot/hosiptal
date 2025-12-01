"""
Delete ALL duplicate staff records, keeping only the most recent per user
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import transaction
from django.contrib.auth.models import User
from hospital.models import Staff


class Command(BaseCommand):
    help = 'Delete ALL duplicate staff records, keeping only the most recent per user'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Actually delete duplicates (default: False, dry-run mode)'
        )
    
    def handle(self, *args, **options):
        force = options.get('force', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('DELETE DUPLICATE STAFF RECORDS'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write()
        
        if not force:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: Use --force to actually delete\n'))
        
        # Find all users with multiple staff records
        duplicates = Staff.objects.filter(is_deleted=False).values('user').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        total_groups = duplicates.count()
        
        if total_groups == 0:
            self.stdout.write(self.style.SUCCESS('✅ No duplicate staff records found!\n'))
            return
        
        self.stdout.write(f'Found {total_groups} users with multiple staff records\n')
        
        total_to_delete = 0
        records_to_delete = []
        
        for dup in duplicates:
            user_id = dup['user']
            count = dup['count']
            total_to_delete += (count - 1)  # Keep one, delete the rest
            
            try:
                user = User.objects.get(id=user_id)
                staff_records = Staff.objects.filter(
                    user=user,
                    is_deleted=False
                ).order_by('-created')  # Most recent first
                
                # Keep the first (most recent), mark others for deletion
                keep_record = staff_records.first()
                delete_records = list(staff_records[1:])
                
                self.stdout.write(
                    f'\n  User: {user.get_full_name()} ({user.username}) - '
                    f'{count} records found'
                )
                self.stdout.write(
                    f'    Keeping: Staff ID {keep_record.id}, '
                    f'Employee ID: {keep_record.employee_id}, '
                    f'Created: {keep_record.created.date()}'
                )
                
                if delete_records:
                    self.stdout.write(f'    Deleting {len(delete_records)} duplicate(s):')
                    for staff in delete_records:
                        self.stdout.write(
                            f'      - Staff ID: {staff.id}, '
                            f'Employee ID: {staff.employee_id}, '
                            f'Created: {staff.created.date()}'
                        )
                        records_to_delete.append(staff)
                
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'    User ID {user_id} not found'))
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(f'SUMMARY: {total_to_delete} duplicate records will be deleted')
        self.stdout.write('=' * 70)
        
        if not force:
            self.stdout.write(self.style.WARNING('\nRun with --force to actually delete these records'))
            return
        
        # Actually delete the duplicates
        self.stdout.write(self.style.WARNING('\nDeleting duplicate records...'))
        
        deleted_count = 0
        error_count = 0
        
        with transaction.atomic():
            for staff in records_to_delete:
                try:
                    # Mark as deleted (soft delete)
                    staff.is_deleted = True
                    staff.save(update_fields=['is_deleted'])
                    deleted_count += 1
                    
                    if deleted_count % 5 == 0:
                        self.stdout.write(f'  Deleted {deleted_count}/{len(records_to_delete)}...')
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'  Error deleting Staff ID {staff.id}: {str(e)}')
                    )
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS(f'✅ Successfully deleted {deleted_count} duplicate records'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'❌ Errors: {error_count}'))
        self.stdout.write('=' * 70)
        
        # Verify cleanup
        remaining_duplicates = Staff.objects.filter(is_deleted=False).values('user').annotate(
            count=Count('id')
        ).filter(count__gt=1).count()
        
        if remaining_duplicates == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ All duplicates have been removed!'))
        else:
            self.stdout.write(self.style.WARNING(f'\n⚠️  {remaining_duplicates} users still have multiple staff records'))



"""
Management command to fix user name for staff members
Updates the linked User account's first_name and last_name so the name displays correctly
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from hospital.models import Staff


class Command(BaseCommand):
    help = 'Fix user name for staff member by updating the linked User account'

    def add_arguments(self, parser):
        parser.add_argument(
            '--employee-id',
            type=str,
            required=True,
            help='Employee ID of the staff member (e.g., SPE-DOC-0001)',
        )
        parser.add_argument(
            '--first-name',
            type=str,
            required=True,
            help='First name to set',
        )
        parser.add_argument(
            '--last-name',
            type=str,
            required=True,
            help='Last name to set',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email to set (optional)',
        )

    def handle(self, *args, **options):
        employee_id = options.get('employee_id')
        first_name = options.get('first_name')
        last_name = options.get('last_name')
        email = options.get('email')
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('FIXING STAFF USER NAME'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        try:
            with transaction.atomic():
                # Find staff by employee ID
                self.stdout.write(f'[1/3] Finding staff with Employee ID: {employee_id}...')
                
                staff = Staff.objects.filter(
                    employee_id=employee_id,
                    is_deleted=False
                ).select_related('user').first()
                
                if not staff:
                    self.stdout.write(self.style.ERROR(f'   ❌ Staff with Employee ID "{employee_id}" not found!'))
                    self.stdout.write(self.style.WARNING('   💡 Please check the Employee ID and try again.'))
                    return
                
                self.stdout.write(self.style.SUCCESS(f'   ✅ Found staff record'))
                
                # Get the linked user
                user = staff.user
                if not user:
                    self.stdout.write(self.style.ERROR(f'   ❌ No user account linked to this staff record!'))
                    return
                
                self.stdout.write(f'[2/3] Found linked user: {user.username}')
                
                # Update user name
                self.stdout.write(f'[3/3] Updating user name...')
                
                user.first_name = first_name
                user.last_name = last_name
                
                if email:
                    user.email = email
                elif not user.email:
                    # Set a default email if none exists
                    user.email = f'{user.username}@hospital.com'
                
                user.save()
                
                self.stdout.write(self.style.SUCCESS(f'   ✅ Updated user name'))
                
                self.stdout.write(self.style.SUCCESS('\n' + '='*70))
                self.stdout.write(self.style.SUCCESS('✅ NAME FIXED SUCCESSFULLY!'))
                self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
                
                self.stdout.write(f'Employee ID: {employee_id}')
                self.stdout.write(f'Username: {user.username}')
                self.stdout.write(f'Full Name: {user.get_full_name()}')
                self.stdout.write(f'First Name: {user.first_name}')
                self.stdout.write(f'Last Name: {user.last_name}')
                self.stdout.write(f'Email: {user.email}')
                
                self.stdout.write(self.style.SUCCESS('\n✅ The name should now display in the USER column!'))
                self.stdout.write(self.style.WARNING('💡 Refresh the staff list page to see the update.\n'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            return





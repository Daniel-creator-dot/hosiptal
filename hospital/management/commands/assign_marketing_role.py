"""
Management command to assign marketing role to a user
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction
from hospital.models import Department, Staff


class Command(BaseCommand):
    help = 'Assign marketing role to a user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username of the user')
        parser.add_argument('--password', type=str, help='Password to set for the user')
        parser.add_argument('--email', type=str, help='Email address for the user')
        parser.add_argument('--first-name', type=str, help='First name')
        parser.add_argument('--last-name', type=str, help='Last name')

    def handle(self, *args, **options):
        username = options['username']
        password = options.get('password')
        email = options.get('email')
        first_name = options.get('first_name')
        last_name = options.get('last_name')
        
        with transaction.atomic():
            # Get or create user
            try:
                user = User.objects.get(username=username)
                self.stdout.write(self.style.WARNING(f'User "{username}" already exists. Updating...'))
                created = False
            except User.DoesNotExist:
                user = User.objects.create_user(
                    username=username,
                    email=email or f'{username}@hms.local',
                    first_name=first_name or '',
                    last_name=last_name or '',
                    is_staff=True,
                    is_active=True
                )
                created = True
                self.stdout.write(self.style.SUCCESS(f'✅ Created user: {username}'))
            
            # Set password if provided
            if password:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f'✅ Password set for user: {username}'))
            
            # Update email if provided
            if email:
                user.email = email
                user.save()
            
            # Update names if provided
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            if first_name or last_name:
                user.save()
            
            # Get Marketing & Business Development group
            try:
                marketing_group = Group.objects.get(name='Marketing & Business Development')
            except Group.DoesNotExist:
                self.stdout.write(self.style.ERROR('❌ Marketing & Business Development group not found. Run create_marketing_department first.'))
                return
            
            # Add user to marketing group
            if marketing_group not in user.groups.all():
                user.groups.add(marketing_group)
                self.stdout.write(self.style.SUCCESS(f'✅ Added user to Marketing & Business Development group'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️  User already in Marketing & Business Development group'))
            
            # Get Marketing & Business Development department
            try:
                marketing_dept = Department.objects.get(name='Marketing & Business Development')
                
                # Update or create staff profile
                staff, staff_created = Staff.objects.get_or_create(
                    user=user,
                    defaults={
                        'profession': 'marketing',
                        'department': marketing_dept,
                        'is_active': True,
                    }
                )
                
                if not staff_created:
                    # Update existing staff
                    staff.profession = 'marketing'
                    staff.department = marketing_dept
                    staff.is_active = True
                    staff.save()
                    self.stdout.write(self.style.SUCCESS(f'✅ Updated staff profile'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'✅ Created staff profile'))
                    
            except Department.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'⚠️  Marketing & Business Development department not found. Staff profile not updated.'))
            
            self.stdout.write(self.style.SUCCESS(f'\n✅ User "{username}" has been assigned the marketing role!'))
            self.stdout.write(f'   Username: {user.username}')
            self.stdout.write(f'   Full Name: {user.get_full_name() or "Not set"}')
            self.stdout.write(f'   Email: {user.email}')
            self.stdout.write(f'   Groups: {", ".join([g.name for g in user.groups.all()])}')
            self.stdout.write(f'   Staff: {"Yes" if hasattr(user, "staff") else "No"}')
            if hasattr(user, 'staff') and user.staff:
                self.stdout.write(f'   Profession: {user.staff.profession}')
                self.stdout.write(f'   Department: {user.staff.department.name if user.staff.department else "None"}')











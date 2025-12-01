"""
Django Management Command to Assign HR Manager Role to a User
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from hospital.models import Staff, Department
from hospital.utils_roles import assign_user_to_role, ROLE_FEATURES


class Command(BaseCommand):
    help = 'Assign HR Manager role to a user and update their staff profile'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username of the user to assign HR Manager role'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Full name of the user (e.g., "Nana Yaa B. Asamoah")'
        )
        parser.add_argument(
            '--update-profession',
            action='store_true',
            help='Update staff profession to hr_manager'
        )
        parser.add_argument(
            '--update-department',
            action='store_true',
            help='Update staff department to HR'
        )
    
    def handle(self, *args, **options):
        username = options.get('username')
        name = options.get('name')
        update_profession = options.get('update_profession', True)
        update_department = options.get('update_department', True)
        
        if not username and not name:
            self.stdout.write(self.style.ERROR('Error: Must provide either --username or --name'))
            return
        
        # Find user
        user = None
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User with username "{username}" not found'))
                return
        else:
            # Search by name
            name_parts = name.split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])
                users = User.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name
                )
                if users.count() == 1:
                    user = users.first()
                elif users.count() > 1:
                    self.stdout.write(self.style.WARNING(f'Found {users.count()} users with name "{name}":'))
                    for u in users:
                        self.stdout.write(f'  - {u.username} ({u.email})')
                    self.stdout.write(self.style.ERROR('Please use --username to specify which user'))
                    return
                else:
                    self.stdout.write(self.style.ERROR(f'User with name "{name}" not found'))
                    return
            else:
                self.stdout.write(self.style.ERROR('Name must include first and last name'))
                return
        
        if not user:
            self.stdout.write(self.style.ERROR('User not found'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found user: {user.get_full_name()} ({user.username})'))
        
        # Get or create staff record
        staff, created = Staff.objects.get_or_create(
            user=user,
            defaults={
                'profession': 'admin',  # Default, will update below
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(self.style.WARNING(f'Created new staff record for {user.get_full_name()}'))
        else:
            self.stdout.write(f'Found existing staff record for {user.get_full_name()}')
        
        # Update profession
        if update_profession:
            old_profession = staff.profession
            # Update profession to hr_manager
            staff.profession = 'hr_manager'
            self.stdout.write(f'  Updated profession: {old_profession} → hr_manager')
            staff.save()
        
        # Update department to HR
        if update_department:
            hr_dept, dept_created = Department.objects.get_or_create(
                name='HR',
                defaults={
                    'code': 'HR',
                    'description': 'Human Resources Department',
                    'is_active': True,
                }
            )
            if dept_created:
                self.stdout.write(self.style.WARNING(f'Created HR department'))
            
            old_dept = staff.department.name if staff.department else 'None'
            staff.department = hr_dept
            staff.save()
            self.stdout.write(f'  Updated department: {old_dept} → HR')
        
        # Assign HR Manager role
        try:
            assign_user_to_role(user, 'hr_manager')
            self.stdout.write(self.style.SUCCESS(f'  ✅ Assigned HR Manager role to {user.get_full_name()}'))
            self.stdout.write(f'  Dashboard URL: {ROLE_FEATURES["hr_manager"]["dashboards"][0]}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error assigning role: {str(e)}'))
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('HR Manager Assignment Complete!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write('')
        self.stdout.write(f'User: {user.get_full_name()} ({user.username})')
        self.stdout.write(f'Profession: {staff.profession}')
        self.stdout.write(f'Department: {staff.department.name if staff.department else "None"}')
        self.stdout.write(f'Role: HR Manager')
        self.stdout.write(f'Dashboard: /hms/hr/worldclass/')
        self.stdout.write('')


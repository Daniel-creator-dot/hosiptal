"""
Management command to add Dr. Kwadwo Ayisi as Medical Director
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from datetime import date, timedelta
from hospital.models import Staff, Department


class Command(BaseCommand):
    help = 'Add Dr. Kwadwo Ayisi as Medical Director with complete staff profile'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username for the user account (if already created)',
            default=None,
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing staff profile if found',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('ADDING DR. KWADWO AYISI - MEDICAL DIRECTOR'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        
        username = options.get('username')
        update_mode = options.get('update', False)
        
        # Staff information
        employee_id = 'SPE-DOC-0001'
        first_name = 'Kwadwo'
        last_name = 'Ayisi'
        full_name = f'Dr. {first_name} {last_name}'
        phone_number = '0246979797'
        age = 68
        # Calculate date of birth (approximately)
        today = date.today()
        date_of_birth = date(today.year - age, 1, 1)  # Approximate DOB
        
        try:
            with transaction.atomic():
                # Step 1: Find or create user
                self.stdout.write('[1/6] Finding or creating user account...')
                
                if username:
                    user = User.objects.filter(username=username).first()
                    if not user:
                        self.stdout.write(self.style.ERROR(f'   ❌ User with username "{username}" not found!'))
                        self.stdout.write(self.style.WARNING('   💡 Please provide the correct username or create the user first.'))
                        return
                else:
                    # Try multiple methods to find the user
                    # Method 1: Search by name
                    user = User.objects.filter(
                        first_name__icontains='kwadwo',
                        last_name__icontains='ayisi'
                    ).first()
                    
                    if not user:
                        # Method 2: Search common usernames
                        possible_usernames = [
                            'kwadwo.ayisi',
                            'kwadwoayisi',
                            'kayisi',
                            'dr.kwadwo.ayisi',
                            'spe-doc-0001',
                        ]
                        
                        for uname in possible_usernames:
                            user = User.objects.filter(username=uname).first()
                            if user:
                                break
                    
                    if not user:
                        # Method 3: List recent users without staff profiles
                        users_without_staff = User.objects.filter(
                            is_staff=True,
                            is_active=True
                        ).exclude(
                            id__in=Staff.objects.values_list('user_id', flat=True)
                        ).order_by('-date_joined')[:10]
                        
                        if users_without_staff.exists():
                            self.stdout.write(self.style.WARNING('   ⚠️  Found users without staff profiles:'))
                            for u in users_without_staff:
                                self.stdout.write(f'      - {u.username} ({u.get_full_name() or "No name"})')
                            self.stdout.write(self.style.WARNING('   💡 Please run with --username USERNAME to specify which user to use'))
                            return
                        
                        # If still not found, create new user
                        username = 'kwadwo.ayisi'
                        self.stdout.write(self.style.WARNING(f'   ⚠️  User not found. Creating new user: {username}'))
                        user = User.objects.create_user(
                            username=username,
                            email=f'{username}@hospital.com',
                            first_name=first_name,
                            last_name=last_name,
                            password='hospital123',  # Default password - should be changed
                            is_staff=True,
                            is_active=True,
                        )
                        self.stdout.write(self.style.SUCCESS(f'   ✅ Created user: {user.username}'))
                    else:
                        self.stdout.write(self.style.SUCCESS(f'   ✅ Found existing user: {user.username}'))
                
                # Update user information
                user.first_name = first_name
                user.last_name = last_name
                if not user.email:
                    user.email = f'{user.username}@hospital.com'
                user.is_staff = True
                user.is_active = True
                user.save()
                
                # Step 2: Find or create Specialist Clinic department
                self.stdout.write('[2/6] Finding Specialist Clinic department...')
                department = Department.objects.filter(
                    name__icontains='specialist'
                ).first()
                
                if not department:
                    department = Department.objects.filter(
                        name__icontains='clinic'
                    ).first()
                
                if not department:
                    # Create department if not exists
                    department = Department.objects.create(
                        name='Specialist Clinic',
                        code='SPE',
                        description='Specialist Clinic Department',
                        is_active=True,
                    )
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Created department: {department.name}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Found department: {department.name}'))
                
                # Step 3: Create or update staff profile
                self.stdout.write('[3/6] Creating/updating staff profile...')
                
                staff, created = Staff.objects.get_or_create(
                    user=user,
                    defaults={
                        'employee_id': employee_id,
                        'profession': 'doctor',
                        'department': department,
                        'phone_number': phone_number,
                        'date_of_birth': date_of_birth,
                        'specialization': 'Medical Director and Administrator',
                        'employment_status': 'active',
                        'is_active': True,
                        'is_deleted': False,
                    }
                )
                
                if not created and update_mode:
                    # Update existing staff profile
                    staff.employee_id = employee_id
                    staff.profession = 'doctor'
                    staff.department = department
                    staff.phone_number = phone_number
                    staff.date_of_birth = date_of_birth
                    staff.specialization = 'Medical Director and Administrator'
                    staff.employment_status = 'active'
                    staff.is_active = True
                    staff.is_deleted = False
                    staff.save()
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Updated staff profile'))
                elif created:
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Created staff profile'))
                else:
                    self.stdout.write(self.style.WARNING(f'   ⚠️  Staff profile already exists. Use --update to update it.'))
                    return
                
                # Step 4: Set as superuser and admin
                self.stdout.write('[4/6] Setting admin privileges...')
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(self.style.SUCCESS('   ✅ Set as superuser and staff'))
                
                # Step 5: Add to Admin group
                self.stdout.write('[5/6] Adding to Admin and Medical Director groups...')
                admin_group, _ = Group.objects.get_or_create(name='Admin')
                user.groups.add(admin_group)
                
                med_director_group, _ = Group.objects.get_or_create(name='Medical Director')
                user.groups.add(med_director_group)
                
                # Also add to Doctor group
                doctor_group, _ = Group.objects.get_or_create(name='Doctor')
                user.groups.add(doctor_group)
                
                self.stdout.write(self.style.SUCCESS('   ✅ Added to Admin, Medical Director, and Doctor groups'))
                
                # Step 6: Add procurement approval permissions (if applicable)
                self.stdout.write('[6/6] Adding procurement approval permissions...')
                try:
                    from hospital.models_procurement import ProcurementRequest
                    content_type = ContentType.objects.get_for_model(ProcurementRequest)
                    
                    admin_perm, _ = Permission.objects.get_or_create(
                        codename='can_approve_procurement_admin',
                        content_type=content_type,
                        defaults={'name': 'Can approve procurement requests (Admin)'}
                    )
                    
                    user.user_permissions.add(admin_perm)
                    self.stdout.write(self.style.SUCCESS('   ✅ Added procurement approval permissions'))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'   ⚠️  Could not add procurement permissions: {e}'))
                
                self.stdout.write(self.style.SUCCESS('\n' + '='*70))
                self.stdout.write(self.style.SUCCESS('✅ DR. KWADWO AYISI ADDED SUCCESSFULLY!'))
                self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
                
                self.stdout.write(f'Employee ID: {employee_id}')
                self.stdout.write(f'Name: {full_name}')
                self.stdout.write(f'Department: {department.name}')
                self.stdout.write(f'Profession: Doctor')
                self.stdout.write(f'Position: Medical Director and Administrator')
                self.stdout.write(f'Phone: {phone_number}')
                self.stdout.write(f'Username: {user.username}')
                self.stdout.write(f'Email: {user.email}')
                self.stdout.write(f'\n✅ Staff profile complete with all details!')
                
                if created or update_mode:
                    self.stdout.write(self.style.WARNING(f'\n⚠️  IMPORTANT: User password was set to default.'))
                    self.stdout.write(self.style.WARNING(f'   Please change the password after first login!'))
                self.stdout.write('\n')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            return


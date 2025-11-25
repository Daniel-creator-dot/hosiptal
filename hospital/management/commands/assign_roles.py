"""
Management command to assign roles to users based on their staff profession
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from hospital.models import Staff
from hospital.utils_roles import ROLE_FEATURES, assign_user_to_role, create_default_groups


class Command(BaseCommand):
    help = 'Assign roles to users based on their staff profession'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-groups',
            action='store_true',
            help='Create default role groups with permissions',
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Assign role to specific user',
        )
        parser.add_argument(
            '--role',
            type=str,
            help='Role to assign (use with --username)',
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("Role Assignment System"))
        self.stdout.write("=" * 70)
        self.stdout.write("")
        
        # Create default groups if requested
        if options['create_groups']:
            self.stdout.write("Creating default role groups...")
            create_default_groups()
            self.stdout.write(self.style.SUCCESS("✓ Default groups created!"))
            self.stdout.write("")
        
        # Assign specific user if requested
        if options['username'] and options['role']:
            try:
                user = User.objects.get(username=options['username'])
                role = options['role']
                
                if role not in ROLE_FEATURES:
                    self.stdout.write(self.style.ERROR(f"✗ Invalid role: {role}"))
                    self.stdout.write(f"Valid roles: {', '.join(ROLE_FEATURES.keys())}")
                    return
                
                assign_user_to_role(user, role)
                self.stdout.write(self.style.SUCCESS(
                    f"✓ Assigned {user.username} to role: {ROLE_FEATURES[role]['name']}"
                ))
                return
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"✗ User not found: {options['username']}"))
                return
        
        # Auto-assign roles based on staff profession
        self.stdout.write("Auto-assigning roles based on staff profession...")
        self.stdout.write("")
        
        profession_to_role = {
            'doctor': 'doctor',
            'nurse': 'nurse',
            'pharmacist': 'pharmacist',
            'lab_technician': 'lab_technician',
            'receptionist': 'receptionist',
            'cashier': 'cashier',
        }
        
        assigned_count = 0
        
        for staff in Staff.objects.filter(is_active=True, is_deleted=False):
            user = staff.user
            profession = staff.profession
            
            # Skip superusers
            if user.is_superuser:
                self.stdout.write(self.style.WARNING(
                    f"  • Skipped {user.username} (already superuser/admin)"
                ))
                continue
            
            # Map profession to role
            role = profession_to_role.get(profession)
            
            if role:
                # Assign role
                assign_user_to_role(user, role)
                assigned_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ {user.get_full_name()} ({user.username}) → {ROLE_FEATURES[role]['name']}"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"  • {user.get_full_name()} ({profession}) - No role mapping"
                ))
        
        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(f"Summary: Assigned roles to {assigned_count} users"))
        self.stdout.write("=" * 70)
        self.stdout.write("")
        self.stdout.write("Role Mappings:")
        self.stdout.write("  • Doctor → Medical Dashboard")
        self.stdout.write("  • Nurse → Triage/Nursing Dashboard")
        self.stdout.write("  • Pharmacist → Pharmacy Dashboard")
        self.stdout.write("  • Lab Technician → Laboratory Dashboard")
        self.stdout.write("  • Receptionist → Reception Dashboard")
        self.stdout.write("  • Cashier → Cashier Dashboard")
        self.stdout.write("")
        self.stdout.write("To manually assign a role:")
        self.stdout.write("  python manage.py assign_roles --username USERNAME --role ROLE")
        self.stdout.write("")
        self.stdout.write("Available roles:")
        for role_slug, role_config in ROLE_FEATURES.items():
            self.stdout.write(f"  • {role_slug} - {role_config['name']}")
























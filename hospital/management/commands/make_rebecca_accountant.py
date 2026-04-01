"""
Django management command to change Rebecca from cashier to accountant
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from hospital.models import Staff
from hospital.utils_roles import assign_user_to_role, get_user_role, get_user_dashboard_url, ROLE_FEATURES


class Command(BaseCommand):
    help = 'Change Rebecca from cashier to accountant'

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write("CHANGING REBECCA FROM CASHIER TO ACCOUNTANT")
        self.stdout.write("=" * 70)
        self.stdout.write("")
        
        # Find Rebecca by username
        username = 'rebecca.'
        try:
            user = User.objects.get(username=username)
            self.stdout.write(self.style.SUCCESS(f"✓ Found user: {user.get_full_name()} ({user.username})"))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"✗ User not found: {username}"))
            return
        
        # Get staff record
        try:
            staff = Staff.objects.get(user=user, is_deleted=False)
            old_profession = staff.profession
            self.stdout.write(self.style.SUCCESS(f"✓ Found staff record"))
            self.stdout.write(f"  Current profession: {old_profession}")
        except Staff.DoesNotExist:
            self.stdout.write(self.style.ERROR("✗ Staff record not found"))
            return
        
        # Check current role
        current_role = get_user_role(user)
        self.stdout.write(f"  Current role: {current_role}")
        self.stdout.write("")
        
        # Update profession to accountant
        self.stdout.write("Updating profession to 'accountant'...")
        staff.profession = 'accountant'
        staff.save(update_fields=['profession'])
        self.stdout.write(self.style.SUCCESS(f"✓ Updated profession: {old_profession} → accountant"))
        self.stdout.write("")
        
        # Assign accountant role
        self.stdout.write("Assigning accountant role...")
        assign_user_to_role(user, 'accountant')
        self.stdout.write(self.style.SUCCESS(f"✓ Assigned role: {ROLE_FEATURES['accountant']['name']}"))
        self.stdout.write("")
        
        # Verify changes
        user.refresh_from_db()
        staff.refresh_from_db()
        new_role = get_user_role(user)
        dashboard_url = get_user_dashboard_url(user, new_role)
        
        self.stdout.write("=" * 70)
        self.stdout.write("VERIFICATION")
        self.stdout.write("=" * 70)
        self.stdout.write(f"  Username: {user.username}")
        self.stdout.write(f"  Full Name: {user.get_full_name()}")
        self.stdout.write(f"  Staff Profession: {staff.profession}")
        self.stdout.write(f"  User Groups: {', '.join([g.name for g in user.groups.all()])}")
        self.stdout.write(f"  Detected Role: {new_role}")
        self.stdout.write(f"  Dashboard URL: {dashboard_url}")
        self.stdout.write("")
        
        if new_role == 'accountant' and dashboard_url == '/hms/accountant/comprehensive-dashboard/':
            self.stdout.write("=" * 70)
            self.stdout.write(self.style.SUCCESS("✓ SUCCESS! Rebecca is now an accountant"))
            self.stdout.write("=" * 70)
            self.stdout.write("")
            self.stdout.write("Rebecca will now:")
            self.stdout.write("  • Be redirected to the Comprehensive Accountant Dashboard on login")
            self.stdout.write("  • Have access to all accounting features")
            self.stdout.write("  • See the account dashboard at: /hms/accountant/comprehensive-dashboard/")
        else:
            self.stdout.write("=" * 70)
            self.stdout.write(self.style.WARNING("⚠ WARNING: Role assignment may not have worked correctly"))
            self.stdout.write("=" * 70)
            self.stdout.write(f"  Expected role: accountant, Got: {new_role}")
            self.stdout.write(f"  Expected dashboard: /hms/accountant/comprehensive-dashboard/, Got: {dashboard_url}")







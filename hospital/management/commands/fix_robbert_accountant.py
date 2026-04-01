"""
Django management command to fix Robbert's accountant dashboard access
Run: python manage.py fix_robbert_accountant
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from hospital.models import Staff, Department
from hospital.utils_roles import get_user_role, get_user_dashboard_url

User = get_user_model()


class Command(BaseCommand):
    help = 'Fix Robbert\'s accountant dashboard access (without making him superuser)'

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("FIXING ROBBERT'S ACCOUNTANT DASHBOARD ACCESS"))
        self.stdout.write("=" * 70)
        self.stdout.write("")
        
        # Find Robbert
        user = None
        for username in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame']:
            try:
                user = User.objects.get(username=username)
                break
            except User.DoesNotExist:
                continue
        
        if not user:
            users = User.objects.filter(username__icontains='robbert')
            if users.exists():
                user = users.first()
        
        if not user:
            self.stdout.write(self.style.ERROR("❌ User 'robbert' not found!"))
            self.stdout.write("")
            self.stdout.write("Available users with 'robbert':")
            users = User.objects.filter(username__icontains='robbert')
            for u in users:
                self.stdout.write(f"  - {u.username} ({u.email})")
            return
        
        self.stdout.write(self.style.SUCCESS(f"✅ Found user: {user.username}"))
        self.stdout.write(f"   Email: {user.email or 'No email'}")
        self.stdout.write(f"   Full Name: {user.get_full_name()}")
        self.stdout.write("")
        
        # Step 1: Ensure NOT superuser
        self.stdout.write("[1/5] Ensuring NOT superuser (accounting access only)...")
        if user.is_superuser:
            user.is_superuser = False
            user.save(update_fields=['is_superuser'])
            self.stdout.write(self.style.SUCCESS("   ✅ Removed superuser status"))
        else:
            self.stdout.write("   ✅ Already not superuser")
        self.stdout.write("")
        
        # Step 2: Ensure is_staff = True
        self.stdout.write("[2/5] Ensuring staff access...")
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=['is_staff'])
            self.stdout.write(self.style.SUCCESS("   ✅ Set as staff"))
        else:
            self.stdout.write("   ✅ Already staff")
        self.stdout.write("")
        
        # Step 3: Ensure is_active = True
        self.stdout.write("[3/5] Ensuring account is active...")
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])
            self.stdout.write(self.style.SUCCESS("   ✅ Activated account"))
        else:
            self.stdout.write("   ✅ Account already active")
        self.stdout.write("")
        
        # Step 4: Add to Accountant group
        self.stdout.write("[4/5] Adding to Accountant group...")
        accountant_group, created = Group.objects.get_or_create(name='Accountant')
        if not user.groups.filter(name='Accountant').exists():
            user.groups.add(accountant_group)
            self.stdout.write(self.style.SUCCESS("   ✅ Added to Accountant group"))
        else:
            self.stdout.write("   ✅ Already in Accountant group")
        self.stdout.write("")
        
        # Step 5: Ensure staff record has profession='accountant'
        self.stdout.write("[5/5] Setting up staff record...")
        staff, staff_created = Staff.objects.get_or_create(
            user=user,
            defaults={
                'profession': 'accountant',
                'department': Department.objects.filter(name__icontains='account').first() or Department.objects.first(),
                'is_active': True,
                'is_deleted': False,
            }
        )
        
        if not staff_created:
            staff.profession = 'accountant'
            staff.is_active = True
            staff.is_deleted = False
            staff.save(update_fields=['profession', 'is_active', 'is_deleted'])
            self.stdout.write(self.style.SUCCESS("   ✅ Updated staff record as accountant"))
        else:
            self.stdout.write(self.style.SUCCESS("   ✅ Created staff record as accountant"))
        self.stdout.write("")
        
        # Verify setup
        self.stdout.write("=" * 70)
        self.stdout.write("VERIFICATION")
        self.stdout.write("=" * 70)
        self.stdout.write("")
        
        role = get_user_role(user)
        dashboard_url = get_user_dashboard_url(user)
        groups = list(user.groups.values_list('name', flat=True))
        
        self.stdout.write(f"Username: {user.username}")
        self.stdout.write(f"Full Name: {user.get_full_name()}")
        self.stdout.write(f"Email: {user.email or 'No email'}")
        self.stdout.write("")
        self.stdout.write(f"is_staff: {user.is_staff}")
        self.stdout.write(f"is_superuser: {user.is_superuser} ❌ (Should be False)")
        self.stdout.write(f"is_active: {user.is_active}")
        self.stdout.write("")
        self.stdout.write(f"Groups: {groups}")
        self.stdout.write(f"Staff Profession: {staff.profession if staff else 'None'}")
        self.stdout.write("")
        self.stdout.write(f"Detected Role: {role}")
        self.stdout.write(f"Dashboard URL: {dashboard_url}")
        self.stdout.write("")
        
        # Check if setup is correct
        if role == 'accountant' and dashboard_url == '/hms/accountant/comprehensive-dashboard/':
            self.stdout.write(self.style.SUCCESS("✅ SUCCESS! Robbert is properly configured as Accountant!"))
            self.stdout.write("")
            self.stdout.write("Access Details:")
            self.stdout.write("  ✅ Can log in (is_staff=True, is_active=True)")
            self.stdout.write("  ✅ NOT superuser (accounting access only)")
            self.stdout.write("  ✅ In Accountant group")
            self.stdout.write("  ✅ Staff profession = 'accountant'")
            self.stdout.write("  ✅ Will redirect to: /hms/accountant/comprehensive-dashboard/")
            self.stdout.write("")
            self.stdout.write("Dashboard Access:")
            self.stdout.write("  • Main Dashboard: /hms/accountant/comprehensive-dashboard/")
            self.stdout.write("  • All accounting features under /hms/accountant/")
            self.stdout.write("  • Payment vouchers: /hms/accounting/pv/")
            self.stdout.write("  • Cheques: /hms/accounting/cheques/")
            self.stdout.write("  • Chart of Accounts: /hms/accountant/chart-of-accounts/")
        else:
            self.stdout.write(self.style.WARNING("⚠️  WARNING: Setup may not be complete"))
            self.stdout.write(f"   Expected role: 'accountant', Got: '{role}'")
            self.stdout.write(f"   Expected dashboard: '/hms/accountant/comprehensive-dashboard/', Got: '{dashboard_url}'")







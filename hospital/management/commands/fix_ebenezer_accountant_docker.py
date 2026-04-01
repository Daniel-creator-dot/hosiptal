"""
Docker Management Command: Fix Ebenezer Accountant Access
Run: docker-compose exec web python manage.py fix_ebenezer_accountant_docker
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from hospital.models import Staff, Department
from hospital.utils_roles import get_user_role, get_user_dashboard_url


class Command(BaseCommand):
    help = 'Fix Ebenezer\'s accountant role and ensure dashboard redirect works in Docker'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('FIXING EBENEZER ACCOUNTANT ACCESS (DOCKER)')
        self.stdout.write('=' * 70)
        self.stdout.write()
        
        # Find Ebenezer
        ebenezer = Staff.objects.filter(user__username='ebenezer.donkor', is_deleted=False).first()
        
        if not ebenezer:
            self.stdout.write(
                self.style.ERROR('[ERROR] Ebenezer not found!')
            )
            return
        
        user = ebenezer.user
        self.stdout.write(
            self.style.SUCCESS(f'[OK] Found Ebenezer: {user.get_full_name()} ({user.username})')
        )
        self.stdout.write()
        
        # 1. Ensure in Accountant group
        self.stdout.write('[1/5] Ensuring Accountant group membership...')
        accountant_group, created = Group.objects.get_or_create(name='Accountant')
        if created:
            self.stdout.write(self.style.SUCCESS('  [OK] Created Accountant group'))
        
        if accountant_group not in user.groups.all():
            user.groups.add(accountant_group)
            self.stdout.write(self.style.SUCCESS('  [OK] Added to Accountant group'))
        else:
            self.stdout.write('  [INFO] Already in Accountant group')
        self.stdout.write()
        
        # 2. Ensure profession is accountant
        self.stdout.write('[2/5] Checking profession...')
        if ebenezer.profession != 'accountant':
            ebenezer.profession = 'accountant'
            ebenezer.save()
            self.stdout.write(self.style.SUCCESS(f'  [OK] Updated profession to: accountant'))
        else:
            self.stdout.write(f'  [INFO] Profession already: accountant')
        self.stdout.write()
        
        # 3. Ensure department is Finance
        self.stdout.write('[3/5] Checking department...')
        finance_dept = Department.objects.filter(name__icontains='finance').first()
        if finance_dept and ebenezer.department != finance_dept:
            ebenezer.department = finance_dept
            ebenezer.save()
            self.stdout.write(self.style.SUCCESS(f'  [OK] Updated department to: {finance_dept.name}'))
        elif ebenezer.department:
            self.stdout.write(f'  [INFO] Department: {ebenezer.department.name}')
        self.stdout.write()
        
        # 4. Verify role detection
        self.stdout.write('[4/5] Verifying role detection...')
        role = get_user_role(user)
        dashboard_url = get_user_dashboard_url(user, role)
        self.stdout.write(f'  [OK] Detected role: {role}')
        self.stdout.write(f'  [OK] Dashboard URL: {dashboard_url}')
        
        if role == 'accountant' and dashboard_url == '/hms/accountant/comprehensive-dashboard/':
            self.stdout.write(self.style.SUCCESS('  [OK] Role detection working correctly!'))
        else:
            self.stdout.write(
                self.style.WARNING(f'  [WARNING] Role is {role}, expected accountant')
            )
        self.stdout.write()
        
        # 5. Ensure user is active and staff
        self.stdout.write('[5/5] Checking user flags...')
        updated = False
        if not user.is_active:
            user.is_active = True
            updated = True
        if not user.is_staff:
            user.is_staff = True
            updated = True
        if updated:
            user.save()
            self.stdout.write(self.style.SUCCESS('  [OK] Updated user flags'))
        else:
            self.stdout.write('  [INFO] User flags already correct')
        self.stdout.write()
        
        # Summary
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('FIX COMPLETE!'))
        self.stdout.write('=' * 70)
        self.stdout.write()
        self.stdout.write('Ebenezer Configuration:')
        self.stdout.write(f'  Username: {user.username}')
        self.stdout.write(f'  Department: {ebenezer.department.name if ebenezer.department else "None"}')
        self.stdout.write(f'  Profession: {ebenezer.profession}')
        self.stdout.write(f'  Role: {role}')
        self.stdout.write(f'  Groups: {", ".join([g.name for g in user.groups.all()])}')
        self.stdout.write(f'  Dashboard URL: {dashboard_url}')
        self.stdout.write(f'  is_active: {user.is_active}')
        self.stdout.write(f'  is_staff: {user.is_staff}')
        self.stdout.write()
        
        if role == 'accountant' and dashboard_url == '/hms/accountant/comprehensive-dashboard/':
            self.stdout.write(
                self.style.SUCCESS('[OK] Configuration is correct!')
            )
            self.stdout.write()
            self.stdout.write('Next Steps:')
            self.stdout.write('  1. Have Ebenezer log out completely')
            self.stdout.write('  2. Clear browser cache (Ctrl + F5)')
            self.stdout.write('  3. Log back in')
            self.stdout.write('  4. He will be automatically redirected to:')
            self.stdout.write('     /hms/accountant/comprehensive-dashboard/')
        else:
            self.stdout.write(
                self.style.WARNING('[WARNING] Configuration may need adjustment')
            )
        self.stdout.write()




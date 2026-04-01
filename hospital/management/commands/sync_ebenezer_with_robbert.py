"""
Management command to sync Ebenezer with Robbert's department and dashboard
Run: python manage.py sync_ebenezer_with_robbert
Or in Docker: docker-compose exec web python manage.py sync_ebenezer_with_robbert
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from hospital.models import Staff, Department

User = get_user_model()


class Command(BaseCommand):
    help = 'Sync Ebenezer to use the same department and dashboard as Robbert (Account/Finance are one department)'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('SYNCING EBENEZER WITH ROBBERT')
        self.stdout.write('=' * 70)
        self.stdout.write()
        
        # 1. Find Robbert
        self.stdout.write('[1/5] Finding Robbert...')
        robbert = None
        for username in ['robbert.kwamegbologah', 'robbert', 'robbert.kwame']:
            try:
                user = User.objects.filter(username__icontains=username).first()
                if user:
                    robbert = Staff.objects.filter(user=user, is_deleted=False).first()
                    if robbert:
                        break
            except:
                continue
        
        if not robbert:
            robbert = Staff.objects.filter(
                user__first_name__icontains='Robbert',
                is_deleted=False
            ).first()
        
        if not robbert:
            self.stdout.write(
                self.style.ERROR('[ERROR] Robbert not found!')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Found Robbert: {robbert.user.get_full_name()} ({robbert.user.username})'
            )
        )
        self.stdout.write(
            f'[OK] Robbert\'s Department: {robbert.department.name if robbert.department else "None"}'
        )
        self.stdout.write(
            f'[OK] Robbert\'s Profession: {robbert.profession}'
        )
        self.stdout.write()
        
        # 2. Find Ebenezer
        self.stdout.write('[2/5] Finding Ebenezer...')
        ebenezer = None
        for username in ['ebenezer.donkor', 'ebenezer', 'ebenezer.moses']:
            try:
                user = User.objects.filter(username__icontains=username).first()
                if user:
                    ebenezer = Staff.objects.filter(user=user, is_deleted=False).first()
                    if ebenezer:
                        break
            except:
                continue
        
        if not ebenezer:
            ebenezer = Staff.objects.filter(
                user__first_name__icontains='Ebenezer',
                is_deleted=False
            ).first()
        
        if not ebenezer:
            self.stdout.write(
                self.style.ERROR('[ERROR] Ebenezer not found!')
            )
            self.stdout.write('Searching all users with "ebenezer" in name...')
            users = User.objects.filter(
                username__icontains='ebenezer'
            ) | User.objects.filter(
                first_name__icontains='ebenezer'
            ) | User.objects.filter(
                last_name__icontains='ebenezer'
            )
            for u in users[:5]:
                self.stdout.write(f'  - {u.username} ({u.get_full_name()})')
            return
        
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Found Ebenezer: {ebenezer.user.get_full_name()} ({ebenezer.user.username})'
            )
        )
        self.stdout.write(
            f'[OK] Current Department: {ebenezer.department.name if ebenezer.department else "None"}'
        )
        self.stdout.write(
            f'[OK] Current Profession: {ebenezer.profession}'
        )
        self.stdout.write()
        
        # 3. Update Ebenezer's department to match Robbert
        self.stdout.write('[3/5] Updating Ebenezer\'s department to match Robbert...')
        if robbert.department:
            ebenezer.department = robbert.department
            ebenezer.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'[OK] Updated Ebenezer\'s department to: {robbert.department.name}'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING('[WARNING] Robbert has no department assigned!')
            )
        self.stdout.write()
        
        # 4. Update Ebenezer's profession to match Robbert
        self.stdout.write('[4/5] Updating Ebenezer\'s profession...')
        if robbert.profession:
            ebenezer.profession = robbert.profession
            ebenezer.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'[OK] Updated Ebenezer\'s profession to: {robbert.profession}'
                )
            )
        self.stdout.write()
        
        # 5. Ensure both are in Accountant group
        self.stdout.write('[5/5] Ensuring both are in Accountant group...')
        accountant_group, created = Group.objects.get_or_create(name='Accountant')
        if created:
            self.stdout.write(self.style.SUCCESS('[OK] Created Accountant group'))
        
        # Add Robbert to Accountant group if not already
        if accountant_group not in robbert.user.groups.all():
            robbert.user.groups.add(accountant_group)
            self.stdout.write(self.style.SUCCESS('[OK] Added Robbert to Accountant group'))
        else:
            self.stdout.write('[INFO] Robbert already in Accountant group')
        
        # Add Ebenezer to Accountant group if not already
        if accountant_group not in ebenezer.user.groups.all():
            ebenezer.user.groups.add(accountant_group)
            self.stdout.write(self.style.SUCCESS('[OK] Added Ebenezer to Accountant group'))
        else:
            self.stdout.write('[INFO] Ebenezer already in Accountant group')
        self.stdout.write()
        
        # Summary
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('SYNC COMPLETE!'))
        self.stdout.write('=' * 70)
        self.stdout.write()
        self.stdout.write('ROBBERT:')
        self.stdout.write(f'  Username: {robbert.user.username}')
        self.stdout.write(f'  Department: {robbert.department.name if robbert.department else "None"}')
        self.stdout.write(f'  Profession: {robbert.profession}')
        self.stdout.write(f'  Dashboard: /hms/accountant/comprehensive-dashboard/')
        self.stdout.write()
        self.stdout.write('EBENEZER:')
        self.stdout.write(f'  Username: {ebenezer.user.username}')
        self.stdout.write(f'  Department: {ebenezer.department.name if ebenezer.department else "None"}')
        self.stdout.write(f'  Profession: {ebenezer.profession}')
        self.stdout.write(f'  Dashboard: /hms/accountant/comprehensive-dashboard/')
        self.stdout.write()
        self.stdout.write(
            self.style.SUCCESS(
                '[OK] Both users are now in the same department and will use the same dashboard!'
            )
        )
        self.stdout.write()
        self.stdout.write('Both will be automatically redirected to:')
        self.stdout.write('  /hms/accountant/comprehensive-dashboard/')
        self.stdout.write()




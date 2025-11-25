"""
Management command to verify accountant user permissions
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from hospital.utils_roles import get_user_role
from hospital.models_accounting_advanced import ProfitLossReport


class Command(BaseCommand):
    help = 'Verify accountant user permissions for admin access'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Check specific username',
        )

    def handle(self, *args, **options):
        if options['username']:
            try:
                user = User.objects.get(username=options['username'])
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User {options["username"]} not found')
                )
                return
        else:
            # Get first accountant user
            users = User.objects.filter(is_active=True)
            user = None
            for u in users:
                if get_user_role(u) == 'accountant':
                    user = u
                    break
            
            if not user:
                self.stdout.write(self.style.ERROR('No accountant user found'))
                return
        
        self.stdout.write(f'\nChecking permissions for: {user.username}')
        self.stdout.write(f'is_staff: {user.is_staff}')
        self.stdout.write(f'is_superuser: {user.is_superuser}')
        self.stdout.write(f'is_active: {user.is_active}')
        
        # Check ProfitLossReport permissions
        ct = ContentType.objects.get_for_model(ProfitLossReport)
        required_perms = ['add_profitlossreport', 'change_profitlossreport', 'view_profitlossreport', 'delete_profitlossreport']
        
        self.stdout.write(f'\nProfitLossReport Permissions:')
        for perm_codename in required_perms:
            has_perm = user.has_perm(f'hospital.{perm_codename}')
            self.stdout.write(f'  {perm_codename}: {has_perm}')
        
        # Check all user permissions
        user_perms = user.user_permissions.all()
        self.stdout.write(f'\nTotal user permissions: {user_perms.count()}')
        
        # Check group permissions
        group_perms = Permission.objects.filter(group__user=user)
        self.stdout.write(f'Total group permissions: {group_perms.count()}')
        
        # Check if user can access admin
        can_access_admin = user.is_staff and user.is_active
        self.stdout.write(f'\nCan access admin: {can_access_admin}')


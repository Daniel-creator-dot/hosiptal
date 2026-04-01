"""
Management command to remove admin access from benjamin
Run: python manage.py remove_benjamin_admin_access
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


class Command(BaseCommand):
    help = 'Remove admin access (is_superuser and is_staff) from benjamin'

    def handle(self, *args, **options):
        # Find benjamin - try multiple username variations
        user = None
        for username in ['benjamin.armah', 'benjamin', 'benjamin.armah']:
            try:
                user = User.objects.get(username=username)
                break
            except User.DoesNotExist:
                continue
        
        # If not found, search by first name or last name
        if not user:
            users = User.objects.filter(
                username__icontains='benjamin'
            ) | User.objects.filter(
                first_name__icontains='benjamin'
            ) | User.objects.filter(
                last_name__icontains='benjamin'
            )
            if users.exists():
                user = users.first()
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Found user by name search: {user.username}'
                    )
                )
        
        if not user:
            self.stdout.write(
                self.style.ERROR('❌ User "benjamin" not found!')
            )
            self.stdout.write('   Searched for: benjamin.armah, benjamin')
            self.stdout.write('   Please check the username and try again.')
            return
        
        self.stdout.write(f'✅ Found user: {user.username}')
        self.stdout.write(f'   Full name: {user.get_full_name() or "N/A"}')
        self.stdout.write(f'   Email: {user.email or "N/A"}')
        self.stdout.write()
        
        # Show current status
        self.stdout.write('📋 Current Status:')
        self.stdout.write(f'   - is_superuser: {user.is_superuser}')
        self.stdout.write(f'   - is_staff: {user.is_staff}')
        self.stdout.write(f'   - is_active: {user.is_active}')
        
        # Get current groups
        current_groups = user.groups.all()
        if current_groups.exists():
            self.stdout.write(f'   - Groups: {", ".join([g.name for g in current_groups])}')
        else:
            self.stdout.write('   - Groups: None')
        self.stdout.write()
        
        # Remove admin access
        changes_made = []
        
        if user.is_superuser:
            user.is_superuser = False
            changes_made.append('is_superuser = False')
        
        if user.is_staff:
            user.is_staff = False
            changes_made.append('is_staff = False')
        
        # Remove from admin-related groups
        admin_groups = Group.objects.filter(
            name__in=['Admin', 'Administrator', 'admin', 'administrator']
        )
        removed_groups = []
        for group in admin_groups:
            if user.groups.filter(id=group.id).exists():
                user.groups.remove(group)
                removed_groups.append(group.name)
        
        if removed_groups:
            changes_made.append(f'Removed from groups: {", ".join(removed_groups)}')
        
        # Save changes
        if changes_made:
            user.save()
            self.stdout.write(
                self.style.SUCCESS('✅ Admin access removed!')
            )
            self.stdout.write()
            self.stdout.write('📋 Changes made:')
            for change in changes_made:
                self.stdout.write(f'   - {change}')
            self.stdout.write()
            self.stdout.write('📋 New Status:')
            self.stdout.write(f'   - is_superuser: {user.is_superuser}')
            self.stdout.write(f'   - is_staff: {user.is_staff}')
            self.stdout.write(f'   - is_active: {user.is_active}')
            
            # Show remaining groups
            remaining_groups = user.groups.all()
            if remaining_groups.exists():
                self.stdout.write(f'   - Groups: {", ".join([g.name for g in remaining_groups])}')
            else:
                self.stdout.write('   - Groups: None')
            self.stdout.write()
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  IMPORTANT: Benjamin must log out and log back in for changes to take effect!'
                )
            )
            self.stdout.write()
            self.stdout.write(
                self.style.SUCCESS(
                    'Benjamin will no longer have access to:'
                )
            )
            self.stdout.write('   - Django admin panel (/admin/)')
            self.stdout.write('   - Admin dashboard (/hms/admin-dashboard/)')
            self.stdout.write('   - Other admin-only features')
        else:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  No changes needed - benjamin does not have admin access.'
                )
            )
            self.stdout.write('   is_superuser and is_staff are already False.')

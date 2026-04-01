"""
Management command to make Robbert a superuser to fix account change access
Run: python manage.py make_robbert_superuser
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Make Robbert a superuser to fix all forbidden errors (account, cashbook, insurance receivable, etc.)'

    def handle(self, *args, **options):
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
            self.stdout.write(
                self.style.ERROR('❌ User "robbert" not found!')
            )
            return
        
        self.stdout.write(f'✅ Found user: {user.username}')
        
        # Make superuser
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Robbert is now a superuser!')
        )
        self.stdout.write(f'   - is_superuser: {user.is_superuser}')
        self.stdout.write(f'   - is_staff: {user.is_staff}')
        self.stdout.write(f'   - is_active: {user.is_active}')
        self.stdout.write()
        self.stdout.write(
            self.style.WARNING(
                '⚠️  IMPORTANT: Robbert must log out and log back in for changes to take effect!'
            )
        )
        self.stdout.write()
        self.stdout.write(
            self.style.SUCCESS(
                'He should now be able to change accounts and access all admin features without forbidden errors!'
            )
        )
        
        # Also grant all accounting permissions explicitly
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        
        accounting_models = [
            'account', 'cashbook', 'insurancereceivable', 'paymentvoucher', 'pettycashtransaction',
            'advancedjournalentry', 'revenue', 'expense', 'accountspayable',
            'bankaccount', 'transaction', 'paymentreceipt', 'journalentry',
        ]
        
        perms_granted = 0
        for model_name in accounting_models:
            try:
                content_type = ContentType.objects.get(
                    app_label='hospital',
                    model=model_name.lower()
                )
                permissions = Permission.objects.filter(content_type=content_type)
                user.user_permissions.add(*permissions)
                perms_granted += permissions.count()
            except ContentType.DoesNotExist:
                continue
        
        if perms_granted > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Also granted {perms_granted} explicit accounting permissions'
                )
            )


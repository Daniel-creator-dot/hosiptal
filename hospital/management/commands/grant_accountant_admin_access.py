"""
Management command to grant admin panel access to accountant users
Sets is_staff=True and grants all accounting model permissions
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from hospital.utils_roles import get_user_role


class Command(BaseCommand):
    help = 'Grant admin panel access (is_staff=True) and model permissions to all accountant users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Grant access to specific username',
        )
        parser.add_argument(
            '--all-accountants',
            action='store_true',
            help='Grant access to all users with accountant role',
        )

    def grant_accounting_permissions(self, user):
        """Grant all accounting-related model permissions to user"""
        # Get all accounting-related content types
        accounting_models = [
            'account', 'costcenter', 'transaction', 'paymentreceipt',
            'advancedjournalentry', 'advancedjournalentryline', 'advancedgeneralledger',
            'paymentvoucher', 'receiptvoucher', 'cheque',
            'revenue', 'revenuecategory', 'expense', 'expensecategory',
            'advancedaccountsreceivable', 'accountspayable',
            'bankaccount', 'banktransaction', 'budget', 'budgetline',
            'cashbook', 'bankreconciliation', 'bankreconciliationitem',
            'insurancereceivable', 'procurementpurchase',
            'accountingpayroll', 'accountingpayrollentry', 'doctorcommission',
            'incomegroup', 'profitlossreport',
            'registrationfee', 'cashsale', 'accountingcorporateaccount',
            'withholdingreceivable', 'deposit', 'initialrevaluation',
            'accountcategory', 'fiscalyear', 'accountingperiod', 'journal',
            'pettycashtransaction',  # Petty cash transactions
            'insurancereceivableentry',  # Insurance Receivable Entry (PrimeCare)
            'insurancepaymentreceived',  # Insurance Payment Received (PrimeCare)
            'undepositedfunds',  # Undeposited Funds (PrimeCare)
        ]
        
        permissions_granted = 0
        for model_name in accounting_models:
            try:
                content_type = ContentType.objects.get(
                    app_label='hospital',
                    model=model_name
                )
                # Grant all permissions (add, change, delete, view) for this model
                permissions = Permission.objects.filter(content_type=content_type)
                for perm in permissions:
                    user.user_permissions.add(perm)
                    permissions_granted += 1
            except ContentType.DoesNotExist:
                # Model might not exist or have different name, skip
                continue
        
        return permissions_granted

    def handle(self, *args, **options):
        if options['username']:
            try:
                user = User.objects.get(username=options['username'])
                user.is_staff = True
                user.save()
                perms = self.grant_accounting_permissions(user)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Granted admin access to {user.username} '
                        f'({perms} permissions granted)'
                    )
                )
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User {options["username"]} not found')
                )
        
        elif options['all_accountants']:
            # Get all users and check their role
            users = User.objects.filter(is_active=True)
            count = 0
            total_perms = 0
            for user in users:
                role = get_user_role(user)
                if role in ('accountant', 'senior_account_officer'):
                    user.is_staff = True
                    user.save()
                    perms = self.grant_accounting_permissions(user)
                    count += 1
                    total_perms += perms
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Granted admin access to {user.username} ({role}) '
                            f'({perms} permissions granted)'
                        )
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Granted admin access to {count} accountant/senior account officer users '
                    f'({total_perms} total permissions granted)'
                )
            )
        
        else:
            self.stdout.write(
                self.style.WARNING(
                    'Please specify --username <username> or --all-accountants'
                )
            )
            self.stdout.write('Example: python manage.py grant_accountant_admin_access --all-accountants')


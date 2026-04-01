"""
Middleware to grant finance/account users access to Django admin without being asked to log in again.
Sets is_staff=True and grants accounting model permissions so they can use Insurance Receivable etc.
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission


# Groups and roles that are allowed admin access (must match admin.py logic)
FINANCE_ACCOUNT_GROUPS = {
    'accountant', 'finance', 'senior_account_officer',
    'account_officer', 'account_personnel',
}
FINANCE_ACCOUNT_ROLES = (
    'accountant', 'senior_account_officer', 'account_officer', 'account_personnel',
)

# Accounting models finance/account users can access in admin (same as grant_accountant_admin_access)
ACCOUNTING_MODELS = [
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
    'pettycashtransaction',
    'insurancereceivableentry', 'insurancepaymentreceived', 'undepositedfunds',
]


def _user_is_finance_or_account(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    # By group name
    for g in user.groups.values_list('name', flat=True):
        if not g:
            continue
        normalized = g.lower().replace(' ', '_').replace('&', '_')
        if normalized in FINANCE_ACCOUNT_GROUPS:
            return True
        # Also match group names containing "account" or "finance"
        if 'account' in normalized or 'finance' in normalized:
            return True
    # By role from get_user_role (groups + Staff profession)
    try:
        from hospital.utils_roles import get_user_role
        if get_user_role(user) in FINANCE_ACCOUNT_ROLES:
            return True
    except Exception:
        pass
    # By Staff profession: any profession containing "account" or "finance"
    try:
        from hospital.models import Staff
        staff = Staff.objects.filter(user=user, is_deleted=False).first()
        if staff and staff.profession:
            p = (staff.profession or '').lower()
            if 'account' in p or 'finance' in p:
                return True
    except Exception:
        pass
    # Explicit usernames that should have finance/account admin access
    if user.username and user.username.lower() in ('finance', 'accountant', 'ebenezer.donkor'):
        return True
    return False


def _grant_accounting_permissions(user):
    """Grant add/change/delete/view for accounting models so they can use admin."""
    try:
        for model_name in ACCOUNTING_MODELS:
            ct = ContentType.objects.filter(app_label='hospital', model=model_name).first()
            if not ct:
                continue
            for perm in Permission.objects.filter(content_type=ct):
                user.user_permissions.add(perm)
    except Exception:
        pass


class FinanceAccountAdminAccessMiddleware:
    """
    Ensure finance/account users have is_staff=True and accounting permissions
    so they can access /admin/ (Insurance Receivable, etc.) without being
    redirected to the login page or getting 403.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and _user_is_finance_or_account(user):
            just_granted_staff = False
            if not getattr(user, 'is_staff', False):
                try:
                    User = get_user_model()
                    User.objects.filter(pk=user.pk).update(is_staff=True)
                    user.is_staff = True
                    just_granted_staff = True
                except Exception:
                    pass
            # Grant accounting permissions: when we just set is_staff, or first time hitting admin this session
            if just_granted_staff or (
                request.path.startswith('/admin/') and
                not request.session.get('finance_admin_perms_granted')
            ):
                _grant_accounting_permissions(user)
                if request.path.startswith('/admin/'):
                    request.session['finance_admin_perms_granted'] = True
        return self.get_response(request)

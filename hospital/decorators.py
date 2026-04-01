"""
Reusable decorators and mixins for enforcing role-based access.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse, NoReverseMatch

from .utils_roles import (
    get_user_role,
    get_role_display_info,
    is_pharmacy_user,
    user_can_remove_invoice_from_bill,
    user_can_waive,
)

ACCESS_DENIED_TEMPLATE = 'hospital/access_denied.html'


def block_pharmacy_from_invoice_and_payment(view_func):
    """
    Decorator to block pharmacy staff from invoice and payment views.
    Pharmacy should not view invoices or process payments; that is for cashier/accountant.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        if is_pharmacy_user(request.user):
            messages.error(
                request,
                "Access denied. Pharmacy staff cannot access invoices or payments. Please use the cashier for billing and payment."
            )
            try:
                return redirect('hospital:pharmacy_dashboard')
            except NoReverseMatch:
                return redirect('hospital:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped

# Accounting-related URL patterns that accountants are allowed to access
ACCOUNTING_ALLOWED_PATTERNS = [
    '/hms/accounting',
    '/hms/accountant',  # All accountant features
    '/hms/invoice',
    '/hms/payment',
    '/hms/cashier',
    '/hms/revenue',
    '/hms/accounts',
    '/hms/budget',
    '/hms/procurement/accounts',
    '/hms/accounts-approval',
    '/hms/financial',
    '/hms/receipt',
    '/hms/reports/financial',
    '/hms/payroll',
    '/hms/hr/payroll',
    '/hms/locum',
    '/hms/logout',
    '/hms/login',
    '/hms/dashboard',  # Will redirect to accountant dashboard
    '/accounting/petty-cash',  # Petty cash management
    '/accounting/pv',  # Payment vouchers
    '/admin/',  # Allow Django admin for account management and other necessary features
]


def block_accountant_from_non_accounting(view_func):
    """
    Decorator to block accountants from accessing non-accounting features.
    Accountants should only access accounting, cashier, and related financial features.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        
        user_role = get_user_role(request.user)
        
        # Only block accountants, allow admins and others
        if user_role == 'accountant' and not request.user.is_superuser:
            # Check if the current path is accounting-related
            current_path = request.path.lower()
            
            # Allow accounting-related URLs
            is_accounting_url = any(
                pattern in current_path 
                for pattern in ACCOUNTING_ALLOWED_PATTERNS
            )
            
            if not is_accounting_url:
                messages.error(
                    request, 
                    "Access denied. Accountants can only access accounting, cashier, and financial features."
                )
                return redirect('hospital:accountant_dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped


def role_required(*allowed_roles, redirect_to=None, raise_exception=False, message=None):
    """
    Decorator to restrict a view to one or more HMS roles.

    Usage:
        @login_required
        @role_required('pharmacist', 'admin')
        def pharmacy_dashboard(request):
            ...
    """
    normalized_roles = {role.lower() for role in allowed_roles if role}

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            user_role = get_user_role(request.user)

            # Admins implicitly allowed unless explicitly blocked
            if normalized_roles and user_role not in normalized_roles and user_role != 'admin':
                required_display = ', '.join(role.replace('_', ' ').title() for role in normalized_roles) or 'authorized staff'
                denial_message = message or f"Access denied. {required_display} role required."

                context = {
                    'message': denial_message,
                    'required_roles': normalized_roles,
                    'user_role': user_role,
                    'role_display': get_role_display_info(request.user),
                    'dashboard_url': '/hms/',  # Direct path to avoid URL resolution errors
                    'login_url': '/hms/login/',
                }

                if raise_exception:
                    raise PermissionDenied(denial_message)

                if redirect_to:
                    try:
                        destination = reverse(redirect_to)
                    except NoReverseMatch:
                        destination = redirect_to
                    messages.error(request, denial_message)
                    return redirect(destination)

                try:
                    return render(request, ACCESS_DENIED_TEMPLATE, context, status=403)
                except Exception as e:
                    # Fallback if template rendering fails
                    from django.http import HttpResponse
                    return HttpResponse(
                        f'<html><body><h1>403 - Access Denied</h1>'
                        f'<p>{denial_message}</p>'
                        f'<p><a href="/hms/">Go to Dashboard</a></p>'
                        f'</body></html>',
                        status=403
                    )

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def invoice_from_bill_remover_required(view_func):
    """
    Enforce the same rule as the Total Bill "Remove" buttons (Accountant / Admin / Administrator
    groups). Uses group membership, not get_user_role(), so staff with multiple groups
    (e.g. Procurement + Accountant) are not blocked after seeing the button.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not user_can_remove_invoice_from_bill(request.user):
            denial_message = (
                'Access denied. Only Accountant, Admin, or Administrator group members can remove '
                'an invoice from the bill. Waiving prescribe sales or lines is restricted to administrators.'
            )
            messages.error(request, denial_message)
            context = {
                'message': denial_message,
                'required_roles': {'accountant', 'admin', 'administrator'},
                'user_role': get_user_role(request.user),
                'role_display': get_role_display_info(request.user),
                'dashboard_url': '/hms/',
                'login_url': '/hms/login/',
            }
            try:
                return render(request, ACCESS_DENIED_TEMPLATE, context, status=403)
            except Exception:
                raise PermissionDenied(denial_message)
        return view_func(request, *args, **kwargs)

    return _wrapped


def waiver_permission_required(view_func):
    """
    Same rule as can_waive in templates: user_can_waive() (Admin/Admin group or resolved admin role).
    Must match utils_roles.user_can_waive — do not use role_required('admin') alone, because
    get_user_role() can return accountant when the user is in both Accountant and Admin groups.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not user_can_waive(request.user):
            denial_message = (
                'Access denied. Only administrators (Admin or Administrator group) can waive charges.'
            )
            messages.error(request, denial_message)
            context = {
                'message': denial_message,
                'required_roles': {'admin', 'administrator'},
                'user_role': get_user_role(request.user),
                'role_display': get_role_display_info(request.user),
                'dashboard_url': '/hms/',
                'login_url': '/hms/login/',
            }
            try:
                return render(request, ACCESS_DENIED_TEMPLATE, context, status=403)
            except Exception:
                raise PermissionDenied(denial_message)
        return view_func(request, *args, **kwargs)

    return _wrapped


class RoleRequiredMixin:
    """
    Class-based view mixin enforcing HMS role membership.

    Example:
        class PharmacyView(RoleRequiredMixin, TemplateView):
            allowed_roles = ('pharmacist',)
            template_name = '...'
    """

    allowed_roles = ()
    redirect_url = None
    raise_exception = False
    permission_denied_message = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        checker = role_required(
            *self.get_allowed_roles(),
            redirect_to=self.redirect_url,
            raise_exception=self.raise_exception,
            message=self.get_permission_denied_message(),
        )
        wrapped_dispatch = checker(lambda req, *a, **kw: super(RoleRequiredMixin, self).dispatch(req, *a, **kw))
        return wrapped_dispatch(request, *args, **kwargs)

    def get_allowed_roles(self):
        return tuple(self.allowed_roles)

    def get_permission_denied_message(self):
        return self.permission_denied_message


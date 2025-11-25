"""
Reusable decorators and mixins for enforcing role-based access.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse, NoReverseMatch

from .utils_roles import get_user_role, get_role_display_info

ACCESS_DENIED_TEMPLATE = 'hospital/access_denied.html'

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
    '/hms/admin',  # Admin panel
    '/hms/logout',
    '/hms/login',
    '/hms/dashboard',  # Will redirect to accountant dashboard
    '/admin',  # Django admin
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

                return render(request, ACCESS_DENIED_TEMPLATE, context, status=403)

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


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


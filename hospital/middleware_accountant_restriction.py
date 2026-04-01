"""
Middleware to restrict accountants to only accounting-related features.
Accountants should only access accounting, cashier, invoices, payments, and related financial features.
"""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from .utils_roles import get_user_role

# URL patterns that accountants are allowed to access
ACCOUNTING_ALLOWED_PATTERNS = [
    '/hms/accounting',
    '/hms/accountant',  # All accountant features
    '/hms/invoice',
    '/hms/payment',
    '/hms/cashier',
    '/hms/revenue',
    '/hms/accounts',
    '/hms/budget',  # Budget vs Actual reports - accountants need access for financial analysis
    '/hms/procurement/accounts',  # Accounts approval for procurement
    '/hms/accounts-approval',  # Accounts approval
    '/hms/financial',  # Financial reports
    '/hms/receipt',  # Receipt verification (accounting-related)
    '/hms/reports/financial',  # Financial reports
    '/hms/payroll',  # Payroll access for accountants (special case)
    '/hms/hr/payroll',  # HR payroll access
    '/hms/locum',  # Locum doctor payment management
    '/hms/staff',  # Staff portal - accountants are staff members and need access to their own portal
    '/hms/staff/portal',  # Staff portal dashboard
    '/hms/staff/leave',  # Staff leave requests and history
    '/hms/staff/activities',  # Staff activities calendar
    '/hms/staff/notifications',  # Staff notifications
    '/hms/staff/dashboard',  # Staff dashboard
    '/hms/staff/my-schedule',  # Staff schedule view
    '/hms/performance-reviews',  # Performance reviews
    '/hms/logout',
    '/hms/login',
    '/hms/static',
    '/hms/media',
    '/accounting/petty-cash',  # Petty cash management
    '/accounting/pv',  # Payment vouchers
    '/api/notifications',  # Allow notifications API
    '/api/hospital/invoice',  # Invoice API
    '/api/hospital/payment',  # Payment API
    '/hms/notifications/mark-all-read',  # Allow notification actions
    '/hms/notifications/clear-all',  # Clear all notifications
    '/hms/notifications/',  # Allow notifications list
    '/admin/',  # Allow Django admin for account management and other necessary features
]


class AccountantRestrictionMiddleware:
    """
    Middleware to restrict accountants from accessing non-accounting features.
    Only allows accountants to access accounting, cashier, and financial-related URLs.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only check authenticated users
        if request.user.is_authenticated:
            user_role = get_user_role(request.user)
            
            # Only restrict accountants (not admins)
            if user_role == 'accountant' and not request.user.is_superuser:
                current_path = request.path.lower()
                
                # Skip static/media files and API endpoints (check them separately)
                if current_path.startswith('/static/') or current_path.startswith('/media/'):
                    response = self.get_response(request)
                    return response
                
                # Allow API endpoints that are accounting-related
                if current_path.startswith('/api/'):
                    is_accounting_api = any(
                        pattern in current_path 
                        for pattern in ['invoice', 'payment', 'accounting', 'cashier', 'revenue', 'receipt', 'payroll', 'locum']
                    )
                    if not is_accounting_api:
                        messages.error(
                            request, 
                            "Access denied. Accountants can only access accounting, cashier, and financial features."
                        )
                        return redirect('hospital:accountant_dashboard')
                    response = self.get_response(request)
                    return response
                
                # Allow accountants to access admin panel for account management and other necessary features
                # Only block admin dashboard, not the admin panel itself
                if current_path.startswith('/hms/admin-dashboard'):
                    messages.error(
                        request, 
                        "Access denied. Accountants can only access accounting, cashier, and financial features."
                    )
                    return redirect('hospital:accountant_comprehensive_dashboard')
                
                # Check if the current path is accounting-related
                is_accounting_url = any(
                    pattern in current_path 
                    for pattern in ACCOUNTING_ALLOWED_PATTERNS
                )
                
                # Also allow root dashboard (will redirect to accountant dashboard)
                if current_path in ['/hms/', '/hms', '/hms/dashboard/', '/hms/dashboard']:
                    is_accounting_url = True
                
                # If not accounting-related, redirect to accountant dashboard
                if not is_accounting_url:
                    messages.error(
                        request, 
                        "Access denied. Accountants can only access accounting, cashier, and financial features."
                    )
                    return redirect('hospital:accountant_comprehensive_dashboard')
        
        response = self.get_response(request)
        return response


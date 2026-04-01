"""
Middleware to restrict HR staff to only HR-related features.
HR staff should only access HR, staff, payroll, leave, attendance, performance, and related HR features.
"""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from .utils_roles import get_user_role

# URL patterns that HR staff are allowed to access
HR_ALLOWED_PATTERNS = [
    '/hms/hr',  # All HR URLs
    '/hms/staff',  # Staff management (including staff portal)
    '/hms/payroll',  # Payroll
    '/hms/leave',  # Leave management
    '/hms/attendance',  # Attendance
    '/hms/performance',  # Performance reviews
    '/hms/training',  # Training records
    '/hms/recruitment',  # Recruitment
    '/hms/recognition',  # Staff recognition
    '/hms/wellness',  # Wellness programs
    '/hms/surveys',  # HR surveys
    '/hms/contracts',  # Employment contracts
    '/hms/certificates',  # Certificates management
    '/hms/shifts',  # Staff shifts
    '/hms/skills',  # Skills matrix
    '/hms/overtime',  # Overtime tracking
    '/hms/availability',  # Staff availability
    '/hms/activities',  # HR activities
    '/hms/logout',
    '/hms/login',
    '/hms/static',
    '/hms/media',
    '/admin/logout',
    '/api/notifications',  # Allow notifications API
    '/api/hospital/staff',  # Staff API
    '/api/hospital/payroll',  # Payroll API
    '/api/hospital/leave',  # Leave API
    '/api/hospital/attendance',  # Attendance API
    '/api/hospital/performance',  # Performance API
    '/api/expiring-items',  # Expiring contracts/certificates API
    '/hms/notifications/mark-all-read',  # Allow notification actions
    '/hms/notifications/clear-all',  # Clear all notifications
    '/hms/notifications/',  # Allow notifications list
]


class HRRestrictionMiddleware:
    """
    Middleware to restrict HR staff from accessing non-HR features.
    Only allows HR staff to access HR, staff, payroll, leave, attendance, and related HR URLs.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only check authenticated users
        if request.user.is_authenticated:
            user_role = get_user_role(request.user)
            
            # Only restrict HR managers (not admins)
            if user_role == 'hr_manager' and not request.user.is_superuser:
                current_path = request.path.lower()
                
                # Skip static/media files and API endpoints (check them separately)
                if current_path.startswith('/static/') or current_path.startswith('/media/'):
                    response = self.get_response(request)
                    return response
                
                # Allow API endpoints that are HR-related
                if current_path.startswith('/api/'):
                    is_hr_api = any(
                        pattern in current_path 
                        for pattern in ['staff', 'payroll', 'leave', 'attendance', 'performance', 'training', 'hr', 'recruitment', 'contract', 'certificate', 'expiring-items']
                    )
                    if not is_hr_api:
                        messages.error(
                            request, 
                            "Access denied. HR staff can only access HR, staff, payroll, leave, attendance, and related HR features."
                        )
                        # Redirect to HR manager dashboard
                        try:
                            return redirect('hospital:hr_manager_dashboard')
                        except:
                            return redirect('hospital:hr_worldclass_dashboard')
                    response = self.get_response(request)
                    return response
                
                # Check if the current path is HR-related
                is_hr_url = any(
                    pattern in current_path 
                    for pattern in HR_ALLOWED_PATTERNS
                )
                
                # Allow staff portal and related URLs for HR (HR needs to access staff information)
                # Only block if it's a staff-only self-service action that HR shouldn't perform
                # (Currently allowing all staff portal access for HR)
                
                # Also allow root dashboard (will redirect to HR dashboard)
                if current_path in ['/hms/', '/hms', '/hms/dashboard/', '/hms/dashboard']:
                    is_hr_url = True
                
                # If not HR-related, redirect to HR dashboard
                if not is_hr_url:
                    messages.error(
                        request, 
                        "Access denied. HR staff can only access HR, staff, payroll, leave, attendance, and related HR features."
                    )
                    # Redirect to HR manager dashboard
                    try:
                        return redirect('hospital:hr_manager_dashboard')
                    except:
                        return redirect('hospital:hr_worldclass_dashboard')
        
        response = self.get_response(request)
        return response


"""
Role-based redirect views
Automatically redirect users to their appropriate role dashboard
"""
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .views_role_dashboards import get_staff_profile


@login_required
def role_dashboard_redirect(request):
    """Redirect user to their role-specific dashboard"""
    staff = get_staff_profile(request.user)
    
    if not staff:
        # If no staff profile, redirect to main dashboard
        return redirect('hospital:dashboard')
    
    # Map profession to dashboard URL
    role_dashboards = {
        'doctor': 'hospital:doctor_dashboard',
        'nurse': 'hospital:nurse_dashboard',
        'lab_technician': 'hospital:lab_technician_dashboard',
        'pharmacist': 'hospital:pharmacist_dashboard',
        'radiologist': 'hospital:radiologist_dashboard',
        'receptionist': 'hospital:receptionist_dashboard',
        'cashier': 'hospital:cashier_dashboard_role',
        'admin': 'hospital:admin_dashboard_role',
    }
    
    dashboard_url = role_dashboards.get(staff.profession)
    
    if dashboard_url:
        return redirect(dashboard_url)
    else:
        # If profession not found, redirect to main dashboard
        return redirect('hospital:dashboard')

























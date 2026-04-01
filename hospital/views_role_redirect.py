"""
Role-based redirect views
Automatically redirect users to their appropriate role dashboard
"""
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .views_role_dashboards import get_staff_profile
from .utils_roles import get_user_role


@login_required
def role_dashboard_redirect(request):
    """Redirect user to their role-specific dashboard"""
    staff = get_staff_profile(request.user)
    
    if not staff:
        return redirect('hospital:dashboard')
    
    # Use centralized role resolution so profession aliases (e.g., lab, laboratory_scientist)
    # still land on the correct dashboard.
    resolved_role = get_user_role(request.user)

    role_dashboards = {
        'doctor': 'hospital:doctor_dashboard',
        'nurse': 'hospital:nurse_dashboard',
        'lab_technician': 'hospital:laboratory_dashboard',
        'radiologist': 'hospital:radiologist_dashboard',
        'receptionist': 'hospital:receptionist_dashboard',
        'cashier': 'hospital:cashier_dashboard',  # Main cashier dashboard (with patient/date filters)
        'admin': 'hospital:admin_dashboard',
        'accountant': 'hospital:accountant_comprehensive_dashboard',
        'hr_manager': 'hospital:hr_manager_dashboard',
        # World-class pharmacy hub (links to pending dispensing, stock, etc.)
        'pharmacist': 'hospital:pharmacy_dashboard',
        'store_manager': 'hospital:inventory_dashboard',
    }
    
    dashboard_url = role_dashboards.get(resolved_role)
    
    if dashboard_url:
        return redirect(dashboard_url)
    else:
        return redirect('hospital:dashboard')


























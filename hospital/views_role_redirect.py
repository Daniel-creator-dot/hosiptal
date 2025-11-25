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
        return redirect('hospital:dashboard')
    
    # Force pharmacists into the dispensing/payment verification workflow only
    profession = (staff.profession or '').lower()
    if profession == 'pharmacist':
        return redirect('hospital:pharmacy_pending_dispensing')
    
    role_dashboards = {
        'doctor': 'hospital:doctor_dashboard',
        'nurse': 'hospital:nurse_dashboard',
        'lab_technician': 'hospital:lab_technician_dashboard',
        'radiologist': 'hospital:radiologist_dashboard',
        'receptionist': 'hospital:receptionist_dashboard',
        'cashier': 'hospital:cashier_dashboard_role',
        'admin': 'hospital:admin_dashboard_role',
        'accountant': 'hospital:accountant_comprehensive_dashboard',
        'hr_manager': 'hospital:hr_manager_dashboard',
        'pharmacist': 'hospital:pharmacy_pending_dispensing',
        'store_manager': 'hospital:inventory_dashboard',
    }
    
    dashboard_url = role_dashboards.get(profession)
    
    if dashboard_url:
        return redirect(dashboard_url)
    else:
        return redirect('hospital:dashboard')


























"""
Data Validation Views
Interface for running data integrity checks
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from .utils_data_validation import run_data_integrity_checks
from .utils_roles import get_user_role

def is_admin(user):
    """Strict admin check (no is_staff fallback)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) == 'admin'


@login_required
@user_passes_test(is_admin)
def data_validation_view(request):
    """Run data integrity checks and display results"""
    results = run_data_integrity_checks()
    
    total_errors = sum(len(errors) for errors in results.values())
    
    context = {
        'title': 'Data Integrity Check',
        'results': results,
        'total_errors': total_errors,
    }
    
    return render(request, 'hospital/admin/data_validation.html', context)


@login_required
@user_passes_test(is_admin)
def data_validation_api(request):
    """API endpoint for data validation (AJAX)"""
    results = run_data_integrity_checks()
    total_errors = sum(len(errors) for errors in results.values())
    
    return JsonResponse({
        'results': results,
        'total_errors': total_errors,
        'status': 'error' if total_errors > 0 else 'ok'
    })







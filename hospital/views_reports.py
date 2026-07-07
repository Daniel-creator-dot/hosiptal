"""
Reports Dashboard View
Central hub for all system reports
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages


def _can_access_medical_analytics(request):
    try:
        from .admin import _primecare_admin_has_permission

        return _primecare_admin_has_permission(request)
    except Exception:
        return False


@login_required
def reports_dashboard(request):
    """
    Main reports dashboard - hub for all available reports
    """
    # Define all available reports organized by category
    report_categories = {
        'Financial Reports': [
            {
                'title': 'Financial Report',
                'url': 'hospital:financial_report',
                'icon': 'currency-dollar',
                'description': 'Comprehensive financial overview and analysis'
            },
            {
                'title': 'Daily Report',
                'url': 'hospital:daily_report',
                'icon': 'calendar-day',
                'description': 'Daily operations and revenue summary'
            },
        ],
        'Patient Reports': [
            {
                'title': 'Patient Statistics',
                'url': 'hospital:patient_statistics_report',
                'icon': 'people',
                'description': 'Patient demographics and statistics'
            },
            {
                'title': 'Admission Report',
                'url': 'hospital:admission_report',
                'icon': 'hospital',
                'description': 'Admission trends and analysis'
            },
        ],
        'Operational Reports': [
            {
                'title': 'Encounter Report',
                'url': 'hospital:encounter_report',
                'icon': 'clipboard-pulse',
                'description': 'Patient encounter statistics and trends'
            },
            {
                'title': 'Department Performance',
                'url': 'hospital:department_performance_report',
                'icon': 'graph-up',
                'description': 'Department performance metrics'
            },
            {
                'title': 'Bed Utilization',
                'url': 'hospital:bed_utilization_report',
                'icon': 'bed',
                'description': 'Bed occupancy and utilization analysis'
            },
        ],
        'HR Reports': [
            {
                'title': 'HR Reports Dashboard',
                'url': 'hospital:hr_reports_dashboard',
                'icon': 'people-fill',
                'description': 'Staff, leave, attendance, and payroll reports'
            },
        ],
        'Front Desk Reports': [
            {
                'title': 'Front Desk Reports',
                'url': 'hospital:frontdesk_reports_dashboard',
                'icon': 'person-workspace',
                'description': 'Registration and appointment reports'
            },
        ],
        'Accounting Reports': [
            {
                'title': 'Accounting Reports Hub',
                'url': 'hospital:accounting_reports_hub',
                'icon': 'calculator',
                'description': 'Financial statements and accounting reports'
            },
            {
                'title': 'Profit & Loss Statement',
                'url': 'hospital:profit_loss_statement',
                'icon': 'graph-up-arrow',
                'description': 'P&L statement and financial performance'
            },
        ],
    }

    if _can_access_medical_analytics(request):
        report_categories['Clinical & population analytics'] = [
            {
                'title': 'Medical analytics',
                'url': 'hospital:admin_medical_analytics_report',
                'icon': 'clipboard2-pulse',
                'description': 'Diagnosis frequency, repeat visits, by corporate company, prevention themes',
            },
        ]
    
    context = {
        'title': 'Reports Dashboard',
        'report_categories': report_categories,
    }
    
    return render(request, 'hospital/reports_dashboard.html', context)












"""
Accountant payroll URLs — included from hms.urls BEFORE hospital.urls so
/hms/accountant/payroll/<uuid>/ resolves even when an older hospital.urls
on a server omits these routes.

Reverse as: accountant_payroll_list, accountant_payroll_detail, etc. (no hospital: prefix).
"""
from django.urls import path

from . import views_accountant_comprehensive

urlpatterns = [
    path('accountant/payroll/new/', views_accountant_comprehensive.accountant_payroll_create, name='accountant_payroll_create'),
    path('accountant/payroll/import/', views_accountant_comprehensive.accountant_payroll_import, name='accountant_payroll_import'),
    path('accountant/payroll/template.xlsx', views_accountant_comprehensive.accountant_payroll_template_download, name='accountant_payroll_template'),
    path(
        'accountant/payroll/export-runs.xlsx',
        views_accountant_comprehensive.accountant_payroll_export_runs,
        name='accountant_payroll_export_runs',
    ),
    path(
        'accountant/payroll/<uuid:pk>/export-lines.xlsx',
        views_accountant_comprehensive.accountant_payroll_export_lines,
        name='accountant_payroll_export_lines',
    ),
    path(
        'accountant/payroll/<uuid:pk>/deduction-rates/',
        views_accountant_comprehensive.accountant_payroll_deduction_rates,
        name='accountant_payroll_deduction_rates',
    ),
    path(
        'accountant/payroll/<uuid:pk>/submit-approval/',
        views_accountant_comprehensive.accountant_payroll_submit_approval,
        name='accountant_payroll_submit_approval',
    ),
    path(
        'accountant/payroll/<uuid:pk>/withdraw-submission/',
        views_accountant_comprehensive.accountant_payroll_withdraw_submission,
        name='accountant_payroll_withdraw_submission',
    ),
    path(
        'accountant/payroll/<uuid:pk>/approve/',
        views_accountant_comprehensive.accountant_payroll_approve,
        name='accountant_payroll_approve',
    ),
    path(
        'accountant/payroll/<uuid:pk>/reject/',
        views_accountant_comprehensive.accountant_payroll_reject,
        name='accountant_payroll_reject',
    ),
    path('accountant/payroll/<uuid:pk>/', views_accountant_comprehensive.accountant_payroll_detail, name='accountant_payroll_detail'),
    path('accountant/payroll/', views_accountant_comprehensive.payroll_list, name='accountant_payroll_list'),
]

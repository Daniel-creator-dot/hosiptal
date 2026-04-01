"""
URL configuration for hms project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from . import views

# Screening routes in root URLconf so /hms/screening/ works even if hospital.urls is outdated on server
from hospital import views_screening
from hospital import views as hospital_views
from hospital import views_centralized_cashier
from hospital import views_waiver_audit
from hospital import views_billing_claims

urlpatterns = [
    # Favicon - must be early to catch browser requests
    path('favicon.ico', views.favicon, name='favicon'),
    re_path(r'^favicon\.ico$', views.favicon, name='favicon_alt'),
    
    path('', views.home, name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # login/logout/password-change
    # Pre-employment / Pre-admission screening (registered here so server always has these routes)
    path('hms/screening/', views_screening.screening_dashboard, name='screening_dashboard'),
    path('hms/screening/templates/', views_screening.screening_templates_list, name='screening_templates_list'),
    path('hms/screening/templates/<uuid:encounter_id>/', views_screening.screening_templates_list, name='screening_templates_for_encounter'),
    path('hms/screening/apply/<uuid:encounter_id>/<uuid:template_id>/', views_screening.apply_screening_template, name='apply_screening_template'),
    path('hms/screening/report/<uuid:encounter_id>/', views_screening.screening_report_form, name='screening_report_form'),
    path('hms/screening/report/<uuid:encounter_id>/print/', views_screening.screening_report_print, name='screening_report_print'),
    path('hms/invoices/patient/<uuid:patient_id>/combined/', hospital_views.invoice_combined_patient, name='invoice_combined_patient'),
    # Waiver audit: registered here so /hms/accountant/billing/waiver-audit/ works if hospital.urls on server lags deploy
    path(
        'hms/accountant/billing/waiver-audit/',
        views_waiver_audit.waiver_audit_view,
        name='waiver_audit',
    ),
    # Receivable entry detail (HMS): explicit route so {% url 'receivable_entry_detail' %} works if hospital.urls on server lags deploy
    path(
        'hms/accountant/billing/receivable-entry/<uuid:entry_id>/',
        views_billing_claims.receivable_entry_detail,
        name='receivable_entry_detail',
    ),
    # Corporate bill pack export: before hospital.urls so reverse works if hospital.urls lags deploy
    path('hms/', include('hospital.urls_corporate_bill_pack_export')),
    # Invoice-group billing: match waiver_audit pattern — explicit route before include() so this URL always resolves.
    path(
        'hms/accountant/billing/bills/by-invoice-group/',
        views_billing_claims.bills_by_invoice_group2_cover_page,
    ),
    # Revenue/payment analysis: explicit route before hospital.urls so /hms/accountant/billing/... always resolves
    path(
        'hms/accountant/billing/revenue-payment-analysis/',
        views_billing_claims.revenue_payment_analysis,
    ),
    # Medical bills statement report: explicit route so /hms/accountant/billing/medical-bills/report/ always resolves
    path(
        'hms/accountant/billing/medical-bills/report/',
        views_billing_claims.medical_bills_statement_report,
    ),
    # Accountant payroll (RMC import): before hospital.urls so detail UUID path always resolves
    # even if a deployed hospital.urls is missing these routes. Reverse: accountant_payroll_* (no namespace).
    path('hms/', include('hospital.urls_accountant_payroll')),
    # Backward-compatible global reverse name used by older deployed template variants.
    path(
        'hms/cashier/central/patient/<uuid:patient_id>/deposit/<uuid:deposit_id>/usage/',
        views_centralized_cashier.cashier_patient_deposit_usage_json,
        name='cashier_patient_deposit_usage_json',
    ),
    path('hms/', include('hospital.urls')),  # Frontend hospital management views
    path('hms/telemedicine/', include('hospital.urls_telemedicine')),  # Telemedicine URLs
    
    # Redirect legacy URLs to /hms/ prefix
    re_path(r'^patients/(?P<pk>[0-9a-f-]+)/$', RedirectView.as_view(url='/hms/patients/%(pk)s/', permanent=True)),
    re_path(r'^patients/$', RedirectView.as_view(url='/hms/patients/', permanent=True)),
    # Catch broken URLs with /None - redirect to correct patient detail
    re_path(r'^hms/patients/(?P<pk>[0-9a-f-]+)/None/?$', RedirectView.as_view(url='/hms/patients/%(pk)s/', permanent=False)),
    # Redirect legacy account URLs to /hms/ prefix
    re_path(r'^accounting/$', RedirectView.as_view(url='/hms/accounting/', permanent=True)),
    re_path(r'^accounting/(?P<path>.*)$', RedirectView.as_view(url='/hms/accounting/%(path)s', permanent=True)),
    re_path(r'^accounts/$', RedirectView.as_view(url='/hms/accounts/', permanent=True)),
    re_path(r'^accountant/(?P<path>.*)$', RedirectView.as_view(url='/hms/accountant/%(path)s', permanent=True)),
    # Catch broken account URLs with /None or /INVALID
    re_path(r'^hms/accounting/(?P<path>.*)/None/?$', RedirectView.as_view(url='/hms/accounting/', permanent=False)),
    re_path(r'^hms/accounting/(?P<path>.*)/INVALID/?$', RedirectView.as_view(url='/hms/accounting/', permanent=False)),
    re_path(r'^hms/accounts/(?P<path>.*)/None/?$', RedirectView.as_view(url='/hms/accounts/', permanent=False)),
    re_path(r'^hms/accounts/(?P<path>.*)/INVALID/?$', RedirectView.as_view(url='/hms/accounts/', permanent=False)),
    re_path(r'^hms/accountant/(?P<path>.*)/None/?$', RedirectView.as_view(url='/hms/accountant/comprehensive-dashboard/', permanent=False)),
    re_path(r'^hms/accountant/(?P<path>.*)/INVALID/?$', RedirectView.as_view(url='/hms/accountant/comprehensive-dashboard/', permanent=False)),
    
    path('api/', include('rest_framework.urls')),
    path('api/hospital/', include('hospital.api_urls')),  # REST API
    # path('api/auth/', include('rest_framework_simplejwt.urls')),  # Temporarily disabled
    path('api/allauth/', include('allauth.urls')),
    path('health/', include('health_check.urls')),
    path('prometheus/', include('django_prometheus.urls')),
]

# Add debug toolbar URLs in development - DISABLED for performance
if False and settings.DEBUG:  # Disabled for performance
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
        path('silk/', include('silk.urls', namespace='silk')),
    ]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

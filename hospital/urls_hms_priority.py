"""
Routes registered from hms.urls BEFORE hospital.urls so they resolve even when
hospital.urls on a deployed server lags behind templates.

Reverse as: hospital:receivables_hub, hospital:admin_cashier_quick_services, etc.
"""
from django.urls import path
from django.views.generic import RedirectView

from . import views_accountant_receivables
from . import views_admin_cashier_services
from . import views_accounting
from . import views_accounting_advanced
from . import views_billing_claims
from . import views_centralized_cashier
from . import views_frontdesk_diagnostics
from . import views_frontdesk_pricing
from . import views_insurance_management
from . import views_medical_records
from . import views_accounting_management
from . import views_management_reports
from . import views_department_billed_revenue
from . import views_revenue_monitoring
from . import views_screening
from . import views_telemedicine
from . import views

urlpatterns = [
    # Corporate & insurance receivables hub
    path('accountant/receivables/', views_accountant_receivables.receivables_hub, name='receivables_hub'),
    path('accountant/receivables/analytics/', views_accountant_receivables.receivables_analytics, name='receivables_analytics'),
    path(
        'accountant/receivables/remittance/',
        views_accountant_receivables.receivable_record_remittance,
        name='receivable_record_remittance',
    ),
    path(
        'accountant/receivables/payer/<uuid:payer_id>/month/<str:month_key>/',
        views_accountant_receivables.receivable_company_month_detail,
        name='receivable_company_month_detail',
    ),
    path(
        'accountant/receivables/entry/<uuid:entry_id>/',
        views_accountant_receivables.receivable_entry_detail,
        name='accountant_receivable_entry_detail',
    ),
    path(
        'accountant/receivables/entry/<uuid:entry_id>/api/',
        views_accountant_receivables.receivable_entry_api,
        name='receivable_entry_api',
    ),
    # Admin cashier quick services (price book)
    path(
        'admin/cashier-quick-services/',
        views_admin_cashier_services.admin_cashier_quick_services_list,
        name='admin_cashier_quick_services',
    ),
    path(
        'admin/cashier-quick-services/add/',
        views_admin_cashier_services.admin_cashier_quick_service_add,
        name='admin_cashier_quick_service_add',
    ),
    path(
        'admin/cashier-quick-services/<int:pk>/edit/',
        views_admin_cashier_services.admin_cashier_quick_service_edit,
        name='admin_cashier_quick_service_edit',
    ),
    # Cashier: non-patient charge + line discount (templates reference these names)
    path(
        'cashier/non-patient-charge/',
        views_centralized_cashier.cashier_non_patient_charge,
        name='cashier_non_patient_charge',
    ),
    path(
        'invoices/line/update-discount/',
        views.update_invoice_line_discount,
        name='update_invoice_line_discount',
    ),
    # Patient document file streaming (admission review, lab, imaging templates)
    path(
        'medical-records/documents/<uuid:document_id>/file/',
        views_medical_records.patient_document_file,
        name='patient_document_file',
    ),
    # Bank payment vouchers (comprehensive dashboard + bank account pages)
    path('accountant/bank-payments/', views_accounting_management.bank_payment_list, name='bank_payment_list'),
    path('accountant/bank-payments/create/', views_accounting_management.bank_payment_create, name='bank_payment_create'),
    path('accountant/bank-payments/<uuid:entry_id>/', views_accounting_management.bank_payment_detail, name='bank_payment_detail'),
    path('accountant/bank-payments/<uuid:entry_id>/post/', views_accounting_management.bank_payment_post, name='bank_payment_post'),
    path('accountant/bank-payments/<uuid:entry_id>/void/', views_accounting_management.bank_payment_void, name='bank_payment_void'),
    # Management reports hub (comprehensive dashboard + accounting reports hub)
    path('accountant/management-reports/', views_management_reports.management_reports_hub, name='management_reports_hub'),
    path(
        'accountant/management-reports/service-revenue/',
        views_management_reports.management_service_revenue_report,
        name='management_service_revenue_report',
    ),
    path(
        'accountant/department-billed-revenue/',
        views_department_billed_revenue.department_billed_revenue_report,
        name='department_billed_revenue_report',
    ),
    # Revenue streams exports (management reports hub + streams dashboard)
    path(
        'accounting/revenue-streams/export/excel/',
        views_revenue_monitoring.revenue_streams_dashboard_export_excel,
        name='revenue_streams_dashboard_export_excel',
    ),
    path(
        'accounting/revenue-streams/print/',
        views_revenue_monitoring.revenue_streams_dashboard_print,
        name='revenue_streams_dashboard_print',
    ),
    path(
        'accounting/revenue-streams/service-details/',
        views_revenue_monitoring.revenue_streams_service_details,
        name='revenue_streams_service_details',
    ),
    path(
        'accounting/stream-reports/export/excel/',
        views_revenue_monitoring.accounting_stream_reports_export_excel,
        name='accounting_stream_reports_export_excel',
    ),
    # Bills list print/export (lost in crash — restored here so templates resolve)
    path(
        'accountant/billing/bills/export/excel/',
        views_billing_claims.bills_list_export_excel,
        name='bills_list_export_excel',
    ),
    path(
        'accountant/billing/bills/print/',
        views_billing_claims.bills_list_print,
        name='bills_list_print',
    ),
    # Cashier total-bill discount (admin/accountant)
    path(
        'cashier/central/patient/<uuid:patient_id>/apply-total-discount/',
        views_centralized_cashier.cashier_apply_total_bill_discount,
        name='cashier_apply_total_bill_discount',
    ),
    # Drug formulary insurance exclusion POST + soft delete
    path('drugs/<uuid:pk>/insurance-settings/', views.drug_insurance_settings, name='drug_insurance_settings'),
    path('drugs/<uuid:pk>/delete/', views.drug_delete, name='drug_delete'),
    # Front desk diagnostics & charge lookup
    path(
        'frontdesk/diagnostics/',
        views_frontdesk_diagnostics.frontdesk_diagnostics_dashboard,
        name='frontdesk_diagnostics_dashboard',
    ),
    path(
        'frontdesk/service-charges/',
        views_frontdesk_pricing.frontdesk_service_charges,
        name='frontdesk_service_charges',
    ),
    # Trial balance closing stock sync (template uses sync_closing_stock)
    path(
        'accounting/sync-closing-stock/',
        views_accounting_advanced.sync_closing_stock_to_gl,
        name='sync_closing_stock',
    ),
    # Legacy AR report name used by accounts_receivable.html
    path('accounting/ar/', views_accounting.accounts_receivable, name='accounts_receivable'),
    # Medical records (templates use these names)
    path(
        'medical-records/search/',
        views_medical_records.patient_records_search,
        name='patient_records_search',
    ),
    path(
        'medical-records/patient/<uuid:pk>/complete/',
        views_medical_records.patient_complete_record,
        name='patient_complete_record',
    ),
    # Patient insurance enrollment detail (global search)
    path(
        'insurance/enrollment/<uuid:pk>/',
        views_insurance_management.patient_insurance_detail,
        name='insurance_detail',
    ),
    # Screening apply (hospital: namespace — templates reference hospital:apply_screening_template)
    path(
        'screening/apply/<uuid:encounter_id>/<uuid:template_id>/',
        views_screening.apply_screening_template,
        name='apply_screening_template',
    ),
    # Telemedicine shortcuts (worldclass dashboard uses hospital: names)
    path(
        'telemedicine/schedule/',
        views_telemedicine.schedule_consultation,
        name='telemedicine_schedule',
    ),
    path(
        'telemedicine/settings/',
        RedirectView.as_view(pattern_name='hospital:hospital_settings', permanent=False),
        name='telemedicine_settings',
    ),
    path(
        'telemedicine/start/',
        RedirectView.as_view(pattern_name='telemedicine:schedule_consultation', permanent=False),
        name='start_consultation',
    ),
]

"""
URL configuration for hospital app frontend.
"""
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.shortcuts import redirect
from . import views
from . import views_advanced
from . import views_workflow
from . import views_cashier
from . import views_accounting
from . import views_hr
from . import views_hr_reports
from . import views_hr_shifts_department
from . import views_reports
from . import views_procurement, views_procurement_enhanced
from . import views_procurement_approval
from . import views_store_transfer_enhanced
from . import views_procurement_receiving_enhanced
from . import views_inventory_stores_manager, views_inventory_duplicates
from . import views_hod_scheduling
from . import views_hod_shift_monitoring
from . import views_revenue_monitoring
from . import views_reminders
from . import views_sms
from . import views_departments
from . import views_radiology
from . import views_lab_export
from . import views_imaging_reports
from . import views_consultation
from . import views_receipt_verification
from . import views_lab_payment_verification
from . import views_lab_management
from . import views_lab_reagent_procurement
from . import views_order_management
from . import views_screening
from . import views_medical_history_comprehensive
from . import views_consultation_history
from . import views_admission_review
from . import views_blood_bank
from . import views_login_tracking
from . import views_medical_records
from . import views_insurance
from . import views_insurance_management
from . import views_flexible_pricing
from . import views_theatre
from . import views_contracts
from . import views_hr_worldclass
from . import views_hr_advanced
from . import views_hr_calendar
from . import views_hr_activities
from . import views_hr_manager
from . import views_locum_doctors
from . import views_role_specific
from . import views_admin_medical_analytics
from . import views_telemedicine_enhanced
from . import views_staff_dashboard
from . import views_specialists
from . import views_role_dashboards
from . import views_role_redirect
from . import views_telemedicine
from . import views_legacy_patients  # Legacy patient utilities (needed for admin tools)
from . import views_pricing
from . import views_marketing
from . import views_staff_portal
from . import views_medical_chit
from . import views_triage
from . import views_admission
from . import views_ambulance
from . import views_appointments
from . import views_appointments_advanced
from . import views_appointment_confirmation
from . import views_frontdesk_reports
from . import views_frontdesk_visit
from . import views_payment_verification
from . import views_unified_payments
from . import views_centralized_cashier
from . import views_service_pricing
from . import views_lab_results_enforced
from . import views_pharmacy_dispensing_enforced
from . import views_pharmacy_walkin
from . import views_pharmacy_label_print
from . import views_pharmacy_tally
from . import views_pharmacy_flowboard
from . import views_pharmacy_patients
from . import views_nurse_flowboard
from . import views_doctor_flowboard
from . import views_autocomplete
from . import views_consulting_rooms
from . import views_nurse_assignment

# Import drug accountability views - always import, views handle missing models
# Create dummy view function first to ensure it's always available
def _dummy_accountability_view(request, *args, **kwargs):
    """Dummy view that redirects if accountability system is not available"""
    from django.shortcuts import redirect
    from django.contrib import messages
    messages.warning(request, 'Drug accountability system is not available. Please run migrations: python manage.py migrate hospital 1058_add_drug_accountability_system')
    return redirect('hospital:pharmacy_dashboard')

# Import deletion history views
try:
    from . import views_deletion_history
    DELETION_HISTORY_AVAILABLE = True
except Exception as e:
    views_deletion_history = None
    DELETION_HISTORY_AVAILABLE = False
    # Create dummy views
    def _dummy_deletion_view(request, *args, **kwargs):
        from django.shortcuts import redirect
        from django.contrib import messages
        messages.warning(request, 'Deletion history system is not available.')
        return redirect('hospital:dashboard')
    views_deletion_history = type('Module', (), {
        'deletion_history_dashboard': _dummy_deletion_view,
        'deletion_history_export': _dummy_deletion_view,
    })()

# Try to import the real views module
try:
    from . import views_drug_accountability
    # Verify the module has the required functions
    if not hasattr(views_drug_accountability, 'drug_returns_list'):
        raise AttributeError('views_drug_accountability missing required functions')
    DRUG_ACCOUNTABILITY_AVAILABLE = getattr(views_drug_accountability, 'ACCOUNTABILITY_AVAILABLE', True)
except (ImportError, AttributeError, Exception) as e:
    # If import fails for any reason, create a dummy module with all required functions
    # This ensures URLs are always registered even if the module can't be imported
    import sys
    from types import ModuleType
    views_drug_accountability = ModuleType('views_drug_accountability')
    DRUG_ACCOUNTABILITY_AVAILABLE = False
    # Add all required dummy functions
    views_drug_accountability.inventory_accountability_dashboard = _dummy_accountability_view
    views_drug_accountability.drug_returns_list = _dummy_accountability_view
    views_drug_accountability.drug_return_create = _dummy_accountability_view
    views_drug_accountability.patient_search_api = _dummy_accountability_view
    views_drug_accountability.drug_search_api = _dummy_accountability_view
    views_drug_accountability.drug_return_detail = _dummy_accountability_view
    views_drug_accountability.drug_return_approve = _dummy_accountability_view
    views_drug_accountability.drug_return_reject = _dummy_accountability_view
    views_drug_accountability.drug_return_process = _dummy_accountability_view
    views_drug_accountability.drug_return_bulk_approve = _dummy_accountability_view
    views_drug_accountability.inventory_history = _dummy_accountability_view
    views_drug_accountability.inventory_item_history = _dummy_accountability_view
    views_drug_accountability.drug_administration_history = _dummy_accountability_view
from . import views_notifications
from .views_auth import HMSLoginView, change_password
from . import views_prescription
from . import views_prescription_enhanced
from . import views_drug_guide
from . import views_prescription_assistant
from . import views_patient_export
from . import views_backup
from . import views_accounting_advanced
from . import views_management_reports
from . import views_department_billed_revenue
from . import views_accountant_comprehensive, views_billing_claims
from . import views_accounting_management
from . import views_doctor_performance
from . import views_strategic_objectives_api
from . import views_senior_account_officer
from . import views_patient_deposits
from . import views_budget
from . import views_session_management
from . import views_system_health
from . import views_it_operations
from . import views_pv_cheque
from . import views_petty_cash
from . import views_audit_logs
from . import views_waiver_audit
from . import views_chat
from . import views_user_chat
from . import views_backup_management
from . import views_data_validation
from . import views_performance
from . import views_staff_portal
from . import views_medical_chit
from . import views_queue, views_queue_frontdesk
from . import views_user_management
app_name = 'hospital'

urlpatterns = [
    
    # Frontend views - Role-based routing
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', HMSLoginView.as_view(), name='login'),
    path('logout/', views.end_session, name='logout'),
    path('account/change-password/', change_password, name='change_password'),
    
    # Role-Specific Dashboards
    path('accountant-dashboard/', views_role_specific.accountant_dashboard, name='accountant_dashboard'),
    path('admin-dashboard/', views_role_specific.admin_dashboard, name='admin_dashboard'),
    path(
        'medical-analytics/',
        views_admin_medical_analytics.admin_medical_analytics_report,
        name='admin_medical_analytics_report',
    ),
    path('medical-dashboard/', views_role_specific.medical_dashboard, name='medical_dashboard'),
    path('reception-dashboard/', views_role_specific.reception_dashboard, name='reception_dashboard'),
    
    # Admin Session Management
    path('admin/sessions/', views_session_management.active_sessions_view, name='active_sessions'),
    path('admin/sessions/unlock-all/', views_session_management.unlock_all_accounts, name='unlock_all_accounts'),
    path('admin/users/<int:user_id>/logout/', views_session_management.force_logout_user, name='force_logout_user'),
    path('admin/users/<int:user_id>/block/', views_session_management.block_user, name='block_user'),
    path('admin/users/<int:user_id>/unblock/', views_session_management.unblock_user, name='unblock_user'),
    path('admin/sessions/<str:session_key>/logout/', views_session_management.force_logout_session, name='force_logout_session'),
    path('admin/sessions/logout-all/', views_session_management.force_logout_all, name='force_logout_all'),
    
    # System Health Monitoring
    path('admin/system-health/', views_system_health.system_health_dashboard, name='system_health'),
    path('system-health/', views_system_health.system_health_dashboard, name='system_health_short'),  # Alias for convenience
    path('admin/system-health/api/', views_system_health.system_health_api, name='system_health_api'),
    path('system-health/api/', views_system_health.system_health_api, name='system_health_api_short'),  # Alias for convenience
    
    # IT Operations Center
    path('admin/it-operations/', views_it_operations.it_operations_dashboard, name='it_operations_dashboard'),
    path('admin/it-operations/api/', views_it_operations.it_operations_api, name='it_operations_api'),
    path('it/dashboard/', views_it_operations.it_operations_dashboard, name='it_dashboard'),  # Alias for convenience
    
    # User Management
    path('admin/users/', views_user_management.user_management_view, name='user_management'),
    
    # User Management (IT Operations)
    path('admin/users/create/', views_it_operations.create_user, name='create_user'),
    path('admin/users/<int:user_id>/reset-password/', views_it_operations.reset_user_password, name='reset_user_password'),
    path('admin/users/<int:user_id>/password-form/', views_it_operations.get_user_password_form, name='get_user_password_form'),
    
    # Staff Management (IT Operations)
    path('admin/staff/', views_it_operations.staff_list_for_it, name='staff_list_it'),
    path('admin/staff/<uuid:staff_id>/reset-password/', views_it_operations.reset_staff_password, name='reset_staff_password'),
    path('admin/staff/<uuid:staff_id>/password-form/', views_it_operations.get_staff_password_form, name='get_staff_password_form'),
    path('admin/staff/<uuid:staff_id>/revoke-sessions/', views_it_operations.revoke_staff_sessions, name='revoke_staff_sessions'),
    
    # Audit Logs
    path('admin/audit-logs/', views_audit_logs.audit_logs_view, name='audit_logs'),
    path('audit-logs/', views_audit_logs.audit_logs_view, name='audit_logs_short'),  # Alias for convenience
    path('admin/activity-logs/', views_audit_logs.activity_logs_view, name='activity_logs'),
    path('activity-logs/', views_audit_logs.activity_logs_view, name='activity_logs_short'),  # Alias for convenience
    path('admin/activity-logs/<uuid:pk>/', views_audit_logs.activity_log_detail_view, name='activity_log_detail'),
    
    # Admin Chat Channel
    path('admin/chat/', views_chat.chat_dashboard, name='chat_dashboard'),
    path('admin/chat/api/<uuid:channel_id>/', views_chat.chat_api, name='chat_api'),
    path('admin/chat/api/', views_chat.chat_api, name='chat_api_default'),
    path('admin/chat/notifications/', views_chat.chat_notifications_api, name='chat_notifications_api'),
    path('chat/', views_chat.chat_dashboard, name='chat_dashboard_short'),  # Alias
    
    # User-to-User Direct Chat (WhatsApp-like)
    path('chat/users/', views_user_chat.user_chat_dashboard, name='user_chat_dashboard'),
    path('chat/direct/<int:user_id>/', views_user_chat.direct_chat_api, name='direct_chat_api'),
    path('chat/direct/', views_user_chat.direct_chat_api, name='direct_chat_api_default'),
    path('chat/online-users/', views_user_chat.online_users_api, name='online_users_api'),
    path('chat/users-by-department/', views_user_chat.users_by_department_api, name='users_by_department_api'),
    path('chat/notifications/', views_user_chat.chat_notifications_api, name='user_chat_notifications_api'),
    path('admin/chat/all-conversations/', views_user_chat.admin_all_conversations, name='admin_all_conversations'),
    
    # Backup Management
    path('admin/backups/', views_backup_management.backup_list_view, name='backup_list'),
    path('admin/backups/create/', views_backup_management.create_backup_view, name='create_backup'),
    path('admin/backups/download/<str:filename>/', views_backup_management.download_backup_view, name='download_backup'),
    
    # Data Validation
    path('admin/data-validation/', views_data_validation.data_validation_view, name='data_validation'),
    path('admin/data-validation/api/', views_data_validation.data_validation_api, name='data_validation_api'),
    
    # Performance Monitoring
    path('admin/performance/', views_performance.performance_dashboard, name='performance_dashboard'),
    path('admin/performance/api/', views_performance.performance_api, name='performance_api'),
    
    # Strategic Objectives API (Real-time)
    path('admin/strategic-objectives/api/', views_strategic_objectives_api.strategic_objectives_api, name='strategic_objectives_api'),

    # Admin cashier quick services — canonical routes in urls_hms_priority (included from hms.urls first).
    
    # Notifications
    path('notifications/', views_notifications.notifications_list, name='notifications_list'),
    path('notifications/<uuid:notification_id>/read/', views_notifications.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views_notifications.mark_all_read, name='mark_all_read'),
    path('notifications/clear-all/', views_notifications.clear_all_notifications, name='clear_all_notifications'),
    path('api/notifications/', views_notifications.notifications_api, name='notifications_api'),
    
    # Staff Portal
    path('staff/', RedirectView.as_view(url='dashboard/', permanent=False), name='staff_redirect'),
    path('staff/portal/', views_staff_portal.staff_portal, name='staff_portal'),
    path('staff/my-profile/', views_staff_portal.my_profile, name='my_profile'),
    path('staff/leave/request/', views_staff_portal.staff_leave_request, name='staff_leave_request'),
    path('staff/leave/history/', views_staff_portal.staff_leave_history, name='staff_leave_history'),
    path('staff/activities/', views_staff_portal.staff_activities, name='staff_activities'),
    path('staff/notifications/', views_staff_portal.staff_notifications, name='staff_notifications'),
    path('staff/notifications/<uuid:notification_id>/read/', views_staff_portal.mark_notification_read_staff, name='mark_notification_read_staff'),
    path('staff/notifications/mark-all-read/', views_staff_portal.mark_all_notifications_read_staff, name='mark_all_notifications_read_staff'),
    
    # Staff Medical Chits
    path('staff/medical-chit/apply/', views_medical_chit.staff_medical_chit_apply, name='staff_medical_chit_apply'),
    path('staff/medical-chit/history/', views_medical_chit.staff_medical_chit_history, name='staff_medical_chit_history'),
    path('staff/medical-chit/<uuid:chit_id>/', views_medical_chit.staff_medical_chit_detail, name='staff_medical_chit_detail'),
    path('staff/medical-chit/<uuid:chit_id>/print/', views_medical_chit.staff_medical_chit_print, name='staff_medical_chit_print'),
    
    path('stats/', views.api_stats, name='api_stats'),
    path('api/dashboard-stats/', views.api_stats, name='api_dashboard_stats'),
    
    # Patient views
    path('patients/', views.patient_list, name='patient_list'),
    path('patients/new/', views.patient_create, name='patient_create'),
    path('patient-registration/', views.patient_create, name='patient_registration'),
    # Handle invalid patient IDs gracefully
    path('patients/INVALID/', lambda request: redirect('hospital:patient_list'), name='patient_invalid_redirect'),
    # Catch-all for broken URLs with None - redirect to correct patient detail
    re_path(r'^patients/(?P<pk>[0-9a-f-]+)/None/?$', lambda request, pk: redirect('hospital:patient_detail', pk=pk), name='patient_none_redirect'),
    path('patients/<uuid:patient_id>/outstanding/', views.patient_outstanding_api, name='patient_outstanding_api'),
    path('patients/<uuid:pk>/', views.patient_detail, name='patient_detail'),
    path('patients/<uuid:pk>/edit/', views.patient_edit, name='patient_edit'),
    path('patients/<uuid:patient_pk>/quick-visit/', views.patient_quick_visit_create, name='patient_quick_visit_create'),
    path('frontdesk/visit/create/<uuid:patient_id>/', views_frontdesk_visit.frontdesk_visit_create, name='frontdesk_visit_create'),
    path('frontdesk/visit/<uuid:encounter_id>/update-payer/', views_frontdesk_visit.frontdesk_visit_update_payer, name='frontdesk_visit_update_payer'),
    path('frontdesk/visit/<uuid:encounter_id>/pricing-preview/', views_frontdesk_visit.frontdesk_visit_pricing_preview, name='frontdesk_visit_pricing_preview'),
    path('patients/<uuid:patient_pk>/qr-card/', views.patient_qr_card, name='patient_qr_card'),
    path('patient-checkin/qr/', views.patient_qr_checkin, name='patient_qr_checkin'),
    path('patient-checkin/qr/scan/', views.patient_qr_checkin_api, name='patient_qr_checkin_api'),
    path('patient-checkin/qr/verify/', views.patient_qr_verify, name='patient_qr_verify'),
    # Backward compatibility for legacy patient URLs (previous deployments bookmarked /patients/legacy/<id>/)
    path('patients/legacy/', views_legacy_patients.legacy_patient_list, name='legacy_patient_list_legacy_url'),
    path('patients/legacy/<int:pid>/', views_legacy_patients.legacy_patient_detail, name='legacy_patient_detail_legacy_url'),
    path('patients/legacy/<int:pid>/migrate/', views_legacy_patients.migrate_legacy_patient, name='legacy_patient_migrate_legacy_url'),
    path('consultations/', lambda request: redirect('/hms/my-consultations/'), name='consultations_redirect'),
    
    # Patient export
    path('patients/export/csv/', views_patient_export.export_patients_csv, name='export_patients_csv'),
    path('patients/export/excel/', views_patient_export.export_patients_excel, name='export_patients_excel'),
    path('patients/export/pdf/', views_patient_export.export_patients_pdf, name='export_patients_pdf'),
    
    # Encounter views
    path('encounters/', views.encounter_list, name='encounter_list'),
    path('encounters/new/', views.encounter_create, name='encounter_create'),
    path('encounters/<uuid:pk>/', views.encounter_detail, name='encounter_detail'),
    path('encounters/<uuid:pk>/flow-ajax/', views.encounter_flow_ajax, name='encounter_flow_ajax'),
    path('encounters/<uuid:encounter_id>/surgery-control/', views.surgery_control, name='surgery_control'),
    
    # Admission views
    path('admissions/', views_admission.admission_list_enhanced, name='admission_list'),
    path('admissions/list/', views_admission.admission_list_enhanced, name='admission_list_enhanced'),  # Alias for backward compatibility
    path('admissions/old/', views.admission_list, name='admission_list_old'),
    path('admissions/create/', views_admission.admission_create_enhanced, name='admission_create'),
    path('admissions/<uuid:pk>/', views_admission.admission_detail, name='admission_detail'),
    path('admissions/<uuid:admission_id>/transfer/', views_admission.admission_transfer, name='hms_admission_transfer'),
    path('admissions/<uuid:admission_id>/discharge/', views_admission.discharge_patient, name='discharge_patient'),
    
    # Invoice views
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/patient/<uuid:patient_id>/combined/', views.invoice_combined_patient, name='invoice_combined_patient'),
    path('invoices/line/update-quantity/', views.update_invoice_line_quantity, name='update_invoice_line_quantity'),
    path('invoices/line/update-discount/', views.update_invoice_line_discount, name='update_invoice_line_discount'),
    path('invoices/<uuid:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<uuid:pk>/print/', views.invoice_print, name='invoice_print'),
    path('payments/', views_cashier.cashier_receipts_list, name='payments_redirect'),
    
    # Bed Management (World-Class)
    path('beds/', views_admission.bed_management_worldclass, name='bed_availability'),
    path('beds/management/', views_admission.bed_management_worldclass, name='bed_management_worldclass'),
    path('api/bed/<uuid:bed_id>/details/', views_admission.bed_details_api, name='bed_details_api'),
    path('api/admission/patient-search/', views_admission.api_admission_patient_search, name='api_admission_patient_search'),
    
    # Reports Dashboard
    path('reports/', views_reports.reports_dashboard, name='reports_dashboard'),
    
    # Marketing Strategy & Corporate Growth
    path('marketing/', views_marketing.marketing_dashboard, name='marketing_dashboard'),
    path('marketing/objectives/', views_marketing.marketing_objectives_list, name='marketing_objectives_list'),
    path('marketing/objectives/create/', views_marketing.create_marketing_objective, name='create_marketing_objective'),
    path('marketing/objectives/<uuid:objective_id>/', views_marketing.marketing_objective_detail, name='marketing_objective_detail'),
    path('marketing/objectives/<uuid:objective_id>/tasks/create/', views_marketing.create_marketing_task, name='create_marketing_task'),
    path('marketing/tasks/create/', views_marketing.create_task_standalone, name='create_task_standalone'),
    path('marketing/tasks/<uuid:task_id>/update-status/', views_marketing.update_task_status, name='update_task_status'),
    path('marketing/tasks/', views_marketing.marketing_tasks_list, name='marketing_tasks_list'),
    path('marketing/campaigns/', views_marketing.marketing_campaigns_list, name='marketing_campaigns_list'),
    path('marketing/partnerships/', views_marketing.corporate_partnerships_list, name='corporate_partnerships_list'),
    path('marketing/metrics/', views_marketing.marketing_metrics_dashboard, name='marketing_metrics_dashboard'),
    path('marketing/api/metrics/', views_marketing.marketing_metrics_api, name='marketing_metrics_api'),
    
    # Call Reports
    path('marketing/call-reports/', views_marketing.call_reports_list, name='call_reports_list'),
    path('marketing/call-reports/create/', views_marketing.create_call_report, name='create_call_report'),
    path('marketing/call-reports/<uuid:report_id>/', views_marketing.call_report_detail, name='call_report_detail'),
    path('marketing/call-reports/<uuid:report_id>/edit/', views_marketing.edit_call_report, name='edit_call_report'),
    path('marketing/call-reports/<uuid:report_id>/delete/', views_marketing.delete_call_report, name='delete_call_report'),
    
    # Reports
    path('reports/daily/', views.daily_report, name='daily_report'),
    path('reports/financial/', views.financial_report_view, name='financial_report'),
    path('reports/financial/export/excel/', views.financial_report_export_excel, name='financial_report_export_excel'),
    path('reports/financial/export/pdf/', views.financial_report_export_pdf, name='financial_report_export_pdf'),
    path('reports/patients/', views.patient_statistics_report_view, name='patient_statistics_report'),
    path('reports/encounters/', views.encounter_report_view, name='encounter_report'),
    path('reports/admissions/', views.admission_report_view, name='admission_report'),
    path('reports/departments/', views.department_performance_report_view, name='department_performance_report'),
    path('reports/beds/', views.bed_utilization_report_view, name='bed_utilization_report'),
    
    # Export views
    path('export/patients/csv/', views.export_patients_csv, name='export_patients_csv'),
    path('export/invoices/csv/', views.export_invoices_csv, name='export_invoices_csv'),
    path('export/encounters/csv/', views.export_encounters_csv, name='export_encounters_csv'),
    
    # Department Dashboards
    path('pharmacy/', views_departments.pharmacy_dashboard, name='pharmacy_dashboard'),
    path('pharmacy-dashboard/', views_departments.pharmacy_dashboard, name='pharmacy_dashboard_alt'),  # Alias for compatibility
    path('pharmacy/my-sales/', views_departments.pharmacy_my_sales, name='pharmacy_my_sales'),
    path('pharmacy/stock/', views_departments.pharmacy_stock_list, name='pharmacy_stock_list'),
    path('pharmacy/stock/print/', views_departments.pharmacy_stock_print, name='pharmacy_stock_print'),
    path('pharmacy/stock/export/pdf/', views_departments.pharmacy_stock_pdf, name='pharmacy_stock_pdf'),
    path('pharmacy/stock/export/excel/', views_departments.pharmacy_stock_excel, name='pharmacy_stock_excel'),
    path('pharmacy/stock/add/', views_departments.pharmacy_stock_add, name='pharmacy_stock_add'),
    path('pharmacy/stock/<uuid:pk>/edit/', views_departments.pharmacy_stock_edit, name='pharmacy_stock_edit'),
    path('pharmacy/stock/utilization/', views_departments.pharmacy_stock_utilization, name='pharmacy_stock_utilization'),
    path(
        'pharmacy/stock/utilization/export/pdf/',
        views_departments.pharmacy_stock_utilization_pdf,
        name='pharmacy_stock_utilization_pdf',
    ),
    path(
        'pharmacy/stock/utilization/export/excel/',
        views_departments.pharmacy_stock_utilization_excel,
        name='pharmacy_stock_utilization_excel',
    ),
    path('pharmacy/stock/loss-log/', views_departments.pharmacy_stock_loss_log, name='pharmacy_stock_loss_log'),
    path(
        'pharmacy/stock/<uuid:pk>/record-loss/',
        views_departments.pharmacy_stock_loss_record,
        name='pharmacy_stock_loss_record',
    ),
    path('pharmacy/requests/', views_procurement.procurement_requests_list, name='pharmacy_requests_list'),
    path('pharmacy/requests/new/', views_procurement.procurement_request_create, name='pharmacy_request_create'),
    path('pharmacy/add-consumables/', views_departments.pharmacy_add_consumables, name='pharmacy_add_consumables'),
    path('pharmacy/prescribe/', views_departments.pharmacy_prescribe, name='pharmacy_prescribe'),
    path('pharmacy/inventory-tally/', views_pharmacy_tally.pharmacy_inventory_tally, name='pharmacy_inventory_tally'),
    path('pharmacy/tally-export/', views_pharmacy_tally.pharmacy_tally_export, name='pharmacy_tally_export'),
    path('pharmacy/flowboard/', views_pharmacy_flowboard.pharmacy_flowboard, name='pharmacy_flowboard'),
    path('pharmacy/patients/', views_pharmacy_patients.pharmacy_patients_list, name='pharmacy_patients_list'),
    path('api/pharmacy/patient-search/', views_pharmacy_walkin.api_patient_search, name='api_pharmacy_patient_search'),
    path('api/pharmacy/order/<uuid:order_id>/prescriptions/', views_departments.get_pharmacy_order_prescriptions, name='get_pharmacy_order_prescriptions'),
    path('api/pharmacy/order/<uuid:order_id>/payment-status/', views_departments.check_pharmacy_order_payment_status, name='check_pharmacy_order_payment_status'),
    path('api/pharmacy/order/<uuid:order_id>/send-to-cashier/', views_departments.send_pharmacy_order_to_cashier, name='send_pharmacy_order_to_cashier'),
    path('api/pharmacy/order/<uuid:order_id>/dispense/', views_departments.dispense_pharmacy_order, name='dispense_pharmacy_order'),
    path(
        'api/pharmacy/served/prescription/<uuid:prescription_id>/',
        views_departments.pharmacy_served_prescription_detail,
        name='pharmacy_served_prescription_detail',
    ),
    path(
        'api/pharmacy/served/order/<uuid:order_id>/',
        views_departments.pharmacy_served_order_detail,
        name='pharmacy_served_order_detail',
    ),
    path('api/pharmacy/queue-pulse/', views_departments.pharmacy_queue_pulse, name='pharmacy_queue_pulse'),
    
    # 🔒 Pharmacy Dispensing - Payment Enforced (NEW)
    path('pharmacy/pending-dispensing/', views_pharmacy_dispensing_enforced.pharmacy_pending_dispensing, name='pharmacy_pending_dispensing'),
    path('pharmacy/dispense/<uuid:prescription_id>/', views_pharmacy_dispensing_enforced.pharmacy_dispense_enforced, name='pharmacy_dispense_enforced'),
    path('pharmacy/dispense/<uuid:prescription_id>/send-to-payer/', views_pharmacy_dispensing_enforced.send_prescription_to_payer, name='send_prescription_to_payer'),
    path('pharmacy/prescription/<uuid:sale_id>/send-to-insurance/', views_pharmacy_dispensing_enforced.send_prescribe_sale_to_insurance, name='send_prescribe_sale_to_insurance'),
    
    # Pharmacy Label Printing (Brother QL-820NWB)
    path('pharmacy/label/<uuid:prescription_id>/', views_pharmacy_label_print.pharmacy_label_print, name='pharmacy_label_print'),
    path('pharmacy/prescription-label/<uuid:sale_id>/', views_pharmacy_label_print.pharmacy_walkin_label_print, name='pharmacy_walkin_label_print'),
    path('pharmacy/batch-labels/', views_pharmacy_label_print.pharmacy_batch_label_print, name='pharmacy_batch_label_print'),
    path('api/pharmacy/payment-check/<uuid:prescription_id>/', views_pharmacy_dispensing_enforced.check_pharmacy_payment_required, name='check_pharmacy_payment_required'),
    
    # 💊 Pharmacy Prescription (Direct OTC Sales)
    path('pharmacy/prescription/', views_pharmacy_walkin.pharmacy_walkin_sales_list, name='pharmacy_walkin_sales_list'),
    path('pharmacy/prescription/new/', views_pharmacy_walkin.pharmacy_walkin_sale_create, name='pharmacy_walkin_sale_create'),
    path('pharmacy/prescription/<uuid:sale_id>/', views_pharmacy_walkin.pharmacy_walkin_sale_detail, name='pharmacy_walkin_sale_detail'),
    path('pharmacy/prescription/<uuid:sale_id>/dispense/', views_pharmacy_walkin.pharmacy_walkin_dispense, name='pharmacy_walkin_dispense'),
    path('pharmacy/prescription/<uuid:sale_id>/payment/', views_pharmacy_walkin.pharmacy_walkin_record_payment, name='pharmacy_walkin_record_payment'),
    path('api/pharmacy/search-drugs/', views_pharmacy_walkin.api_search_drugs, name='api_search_drugs'),
    path('api/pharmacy/consumables-search/', views_departments.api_pharmacy_consumables_search, name='api_pharmacy_consumables_search'),
    path('api/pharmacy/search-patients/', views_pharmacy_walkin.api_patient_search, name='api_patient_search'),
    
    # Autocomplete APIs
    path('api/autocomplete/patients/', views_autocomplete.api_autocomplete_patients, name='api_autocomplete_patients'),
    path('api/autocomplete/items/', views_autocomplete.api_autocomplete_items, name='api_autocomplete_items'),
    path('api/autocomplete/drugs/', views_autocomplete.api_autocomplete_drugs, name='api_autocomplete_drugs'),
    path('api/autocomplete/lab-tests/', views_autocomplete.api_autocomplete_lab_tests, name='api_autocomplete_lab_tests'),
    path('api/autocomplete/imaging/', views_autocomplete.api_autocomplete_imaging_studies, name='api_autocomplete_imaging_studies'),
    path('api/autocomplete/consumables/', views_autocomplete.api_autocomplete_consumables, name='api_autocomplete_consumables'),
    
    # 🔒 Drug Accountability & Returns System
    # NOTE: These URLs are ALWAYS registered, even if views_drug_accountability import fails
    # If import fails, dummy views are used that redirect to pharmacy dashboard
    path('drug-accountability/dashboard/', views_drug_accountability.inventory_accountability_dashboard, name='inventory_accountability_dashboard'),
    path('drug-returns/', views_drug_accountability.drug_returns_list, name='drug_returns_list'),
    path('drug-returns/create/', views_drug_accountability.drug_return_create, name='drug_return_create'),
    path('drug-returns/patient-search/', views_drug_accountability.patient_search_api, name='drug_return_patient_search'),
    path('drug-returns/drug-search/', views_drug_accountability.drug_search_api, name='drug_return_drug_search'),
    path('drug-returns/<uuid:return_id>/', views_drug_accountability.drug_return_detail, name='drug_return_detail'),
    path('drug-returns/<uuid:return_id>/approve/', views_drug_accountability.drug_return_approve, name='drug_return_approve'),
    path('drug-returns/<uuid:return_id>/reject/', views_drug_accountability.drug_return_reject, name='drug_return_reject'),
    path('drug-returns/<uuid:return_id>/process/', views_drug_accountability.drug_return_process, name='drug_return_process'),
    path('drug-returns/bulk-approve/', views_drug_accountability.drug_return_bulk_approve, name='drug_return_bulk_approve'),
    path('inventory/history/', views_drug_accountability.inventory_history, name='inventory_history'),
    path('inventory/history/item/<uuid:item_id>/', views_drug_accountability.inventory_item_history, name='inventory_item_history'),
    path('drug-administration/history/', views_drug_accountability.drug_administration_history, name='drug_administration_history'),
    
    # 🔍 Deletion History System (Medical Director & Admin Access)
    path('deletion-history/', views_deletion_history.deletion_history_dashboard, name='deletion_history_dashboard'),
    path('deletion-history/export/', views_deletion_history.deletion_history_export, name='deletion_history_export'),
    
    # Enhanced Prescription APIs - Outstanding Category-Based Drug Selection
    path('api/prescription/drugs/search/', views_prescription_enhanced.api_search_drugs_by_category, name='api_search_drugs_by_category'),
    path('api/prescription/drugs/categories/', views_prescription_enhanced.api_get_drug_categories, name='api_get_drug_categories'),
    path('api/prescription/drugs/category/<str:category_code>/', views_prescription_enhanced.api_get_drugs_by_category, name='api_get_drugs_by_category'),
    
    path('laboratory/', views_departments.laboratory_dashboard, name='laboratory_dashboard'),
    path('laboratory/report/', views_lab_export.laboratory_financial_report, name='laboratory_financial_report'),
    path('laboratory/report/export/excel/', views_lab_export.export_laboratory_financial_excel, name='export_laboratory_financial_excel'),
    path('laboratory/report/export/pdf/', views_lab_export.export_laboratory_financial_pdf, name='export_laboratory_financial_pdf'),
    path('laboratory/remove-overdue-lab/', views_departments.laboratory_remove_overdue_lab, name='laboratory_remove_overdue_lab'),
    path('laboratory/results/', views_departments.lab_results_list, name='lab_results_list'),
    path('lab-results/', views_departments.lab_results_list, name='lab_results_list_legacy'),
    path('laboratory/results/export/excel/', views_lab_export.export_lab_results_excel, name='export_lab_results_excel'),
    path('imaging/study/<uuid:study_id>/print/', views_imaging_reports.print_imaging_report, name='print_imaging_report'),
    path('lab-orders/', views_departments.laboratory_dashboard, name='lab_orders_list_legacy'),
    path('laboratory/result/<uuid:result_id>/edit/', views_departments.edit_lab_result, name='edit_lab_result'),
    path('laboratory/result/<uuid:result_id>/tabular/', views.tabular_lab_report, name='tabular_lab_report'),
    
    # Lab Management: Equipment, Reagents, Quality Control
    path('lab/equipment/', views_lab_management.lab_equipment_dashboard, name='lab_equipment_dashboard'),
    path('lab/equipment/add/', views_lab_management.lab_equipment_add, name='lab_equipment_add'),
    path('lab/equipment/<uuid:equipment_id>/', views_lab_management.equipment_detail, name='equipment_detail'),
    path('lab/reagents/', views_lab_management.lab_reagent_dashboard, name='lab_reagent_dashboard'),
    path('lab/reagents/<uuid:reagent_id>/', views_lab_management.reagent_detail, name='reagent_detail'),
    path('lab/reagents/transaction/', views_lab_management.record_reagent_transaction, name='record_reagent_transaction'),
    path('lab/reagents/add-via-procurement/', views_lab_reagent_procurement.add_reagent_via_procurement, name='add_reagent_via_procurement'),
    path('lab/reagents/<uuid:reagent_id>/sync-inventory/', views_lab_reagent_procurement.sync_reagent_from_inventory, name='sync_reagent_from_inventory'),
    path('lab/quality-control/', views_lab_management.quality_control_dashboard, name='quality_control_dashboard'),
    path('lab/quality-control/create/', views_lab_management.create_qc_test, name='create_qc_test'),
    path('lab/quality-control/<uuid:qc_test_id>/', views_lab_management.qc_test_detail, name='qc_test_detail'),
    path('lab/alerts/<uuid:alert_id>/resolve/', views_lab_management.resolve_alert, name='resolve_alert'),
    
    # Enhanced Order Management (proper separation of lab, imaging, medication)
    path('orders/create/<uuid:encounter_id>/', views_order_management.create_order, name='create_order_enhanced'),
    path('orders/<uuid:order_id>/', views_order_management.order_detail, name='order_detail_enhanced'),

    # Pre-employment & Pre-admission screening (templates → lab + imaging → report)
    path('screening/', views_screening.screening_dashboard, name='screening_dashboard'),
    path('screening/templates/', views_screening.screening_templates_list, name='screening_templates_list'),
    path('screening/templates/<uuid:encounter_id>/', views_screening.screening_templates_list, name='screening_templates_for_encounter'),
    path('screening/apply/<uuid:encounter_id>/<uuid:template_id>/', views_screening.apply_screening_template, name='apply_screening_template'),
    path('screening/report/<uuid:encounter_id>/', views_screening.screening_report_form, name='screening_report_form'),
    path('screening/report/<uuid:encounter_id>/print/', views_screening.screening_report_print, name='screening_report_print'),
    
    # 🔒 Lab Results - Payment Enforced (NEW)
    path('laboratory/pending-release/', views_lab_results_enforced.lab_results_pending_release, name='lab_results_pending_release'),
    path('laboratory/release/<uuid:lab_result_id>/', views_lab_results_enforced.lab_result_release_enforced, name='lab_result_release_enforced'),
    path('api/lab/payment-check/<uuid:lab_result_id>/', views_lab_results_enforced.check_lab_payment_required, name='check_lab_payment_required'),
    path('imaging/', views_departments.imaging_dashboard, name='imaging_dashboard'),
    
    # Radiology-specific views
    path('imaging/pending/', views_radiology.radiologist_pending_orders, name='radiologist_pending_orders'),
    path('imaging/my-studies/', views_radiology.radiologist_my_studies, name='radiologist_my_studies'),
    path('imaging/report-queue/', views_radiology.radiologist_report_queue, name='radiologist_report_queue'),
    path('imaging/completed/', views_radiology.radiologist_completed_studies, name='radiologist_completed_studies'),
    
    # Teleradiology & Equipment Management
    path('imaging/teleradiology/', views_departments.imaging_teleradiology, name='imaging_teleradiology'),
    path('imaging/equipment/', views_departments.imaging_equipment_management, name='imaging_equipment'),
    
    path('imaging/study/<uuid:study_id>/', views_departments.imaging_study_detail, name='imaging_study_detail'),
    path('imaging/study/<uuid:study_id>/upload/', views_departments.upload_imaging_image, name='upload_imaging_image'),
    path('imaging/upload-multiple/', views_departments.upload_multiple_imaging_images, name='upload_multiple_imaging_images'),
    path('imaging/create-study/', views_departments.create_imaging_study, name='create_imaging_study'),
    path('imaging/add-order/', views_departments.imaging_add_order, name='imaging_add_order'),
    path('imaging/catalog/', views_departments.imaging_catalog_list, name='imaging_catalog_list'),
    path('imaging/study/<uuid:study_id>/edit-report/', views_departments.edit_imaging_report, name='edit_imaging_report'),
    path('imaging/study/<uuid:study_id>/verify-report/', views_departments.verify_imaging_report, name='verify_imaging_report'),
    path('api/imaging-study/<uuid:study_id>/images/', views_departments.get_imaging_study_images, name='get_imaging_study_images'),
    
    # Imaging API Endpoints (for dashboard JavaScript)
    path('api/imaging/export-queue/', views_departments.export_imaging_queue, name='export_imaging_queue'),
    path('api/imaging/order/<uuid:order_id>/start/', views_departments.start_imaging_order, name='start_imaging_order'),
    path('api/imaging/study/<uuid:study_id>/images/', views_departments.get_imaging_study_images, name='api_imaging_study_images'),
    path('api/imaging/study/<uuid:study_id>/', views_departments.get_imaging_study_api, name='api_imaging_study_detail'),
    path('api/imaging/study/<uuid:study_id>/ai-analysis/', views_departments.imaging_ai_analysis, name='api_imaging_ai_analysis'),
    path('api/imaging/study/<uuid:study_id>/report/', views_departments.save_imaging_report_api, name='api_imaging_save_report'),
    path('api/imaging/study/<uuid:study_id>/finalize/', views_departments.finalize_imaging_report_api, name='api_imaging_finalize'),
    path('api/imaging/study/<uuid:study_id>/verify/', views_departments.verify_imaging_report_api, name='api_imaging_verify'),
    
    # World-Class Payment Verification System
    path('verification/', views_receipt_verification.verification_dashboard, name='verification_dashboard'),
    path('verification/search/', views_receipt_verification.search_receipt, name='search_receipt'),
    path('verification/receipt/<uuid:receipt_id>/', views_receipt_verification.receipt_detail, name='receipt_detail'),
    path('verification/verify/<uuid:receipt_id>/', views_receipt_verification.verify_receipt, name='verify_receipt'),
    path('verification/scanner/', views_receipt_verification.scan_qr_code, name='scan_qr_code'),
    path('verification/verify-qr/', views_receipt_verification.verify_qr_code, name='verify_qr_code'),
    path('verification/analytics/', views_receipt_verification.analytics_dashboard, name='verification_analytics'),
    
    # Real-time AJAX endpoints
    path('api/order/<uuid:order_id>/update-status/', views_departments.update_order_status, name='update_order_status'),
    path('api/lab-result/<uuid:result_id>/update-status/', views_departments.update_lab_result_status, name='update_lab_result_status'),
    path('api/dashboard-stats/', views_departments.dashboard_stats, name='dashboard_stats'),
    
    # Consultation & Prescribing
    path('consultation/<uuid:encounter_id>/', views_consultation.consultation_view, name='consultation_view'),
    path('consultation/<uuid:encounter_id>/pricing/', views_consultation.consultation_pricing_api, name='consultation_pricing_api'),
    path('consultation/<uuid:encounter_id>/vitals/', views_consultation.consultation_latest_vitals_api, name='consultation_latest_vitals_api'),
    path('consultation/patient/<uuid:patient_id>/start/', views_consultation.quick_consultation, name='quick_consultation'),
    
    # Prescription Management
    path('prescription/<uuid:prescription_id>/delete/', views_prescription.delete_prescription, name='delete_prescription'),
    
    # Consultation History & Records
    path('patient/<uuid:patient_id>/consultation-history/', views_consultation_history.patient_consultation_history, name='patient_consultation_history'),
    path('encounter/<uuid:encounter_id>/full-record/', views_consultation_history.encounter_full_record, name='encounter_full_record'),
    path('my-consultations/', views_consultation_history.my_consultations, name='my_consultations'),
    
    # Admission Review & Shift Handover
    path('admitted-patients/', views_admission_review.admitted_patients_list, name='admitted_patients_list'),
    path('admission-review/<uuid:encounter_id>/', views_admission_review.admission_review, name='admission_review'),
    path('shift-handover-report/', views_admission_review.shift_handover_report, name='shift_handover_report'),
    
    # Blood Bank & Transfusion Management
    path('blood-bank/', views_blood_bank.blood_bank_dashboard, name='blood_bank_dashboard'),
    path('blood-bank/inventory/', views_blood_bank.blood_inventory_list, name='blood_inventory_list'),
    path('blood-bank/donors/', views_blood_bank.donors_list, name='donors_list'),
    path('blood-bank/donors/register/', views_blood_bank.donor_registration, name='donor_registration'),
    path('blood-bank/donor/<uuid:donor_id>/', views_blood_bank.donor_detail, name='donor_detail'),
    path('blood-bank/donor/<uuid:donor_id>/donate/', views_blood_bank.record_donation, name='record_donation'),
    path('blood-bank/donation/<uuid:donation_id>/', views_blood_bank.donation_detail, name='donation_detail'),
    path('blood-bank/transfusion-requests/', views_blood_bank.transfusion_requests_list, name='transfusion_requests_list'),
    path('blood-bank/transfusion-request/create/', views_blood_bank.transfusion_request_create, name='transfusion_request_create'),
    path('blood-bank/transfusion-request/create/patient/<uuid:patient_id>/', views_blood_bank.transfusion_request_create, name='transfusion_request_create_patient'),
    path('blood-bank/transfusion-request/create/encounter/<uuid:encounter_id>/', views_blood_bank.transfusion_request_create, name='transfusion_request_create_encounter'),
    path('blood-bank/transfusion-request/<uuid:request_id>/', views_blood_bank.transfusion_request_detail, name='transfusion_request_detail'),
    
    # Login Location Tracking & Security
    path('my-login-history/', views_login_tracking.my_login_history, name='my_login_history'),
    path('login-activity/', views_login_tracking.all_login_activity, name='all_login_activity'),
    path('security-alerts/', views_login_tracking.security_alerts_dashboard, name='security_alerts_dashboard'),
    path('login-map/', views_login_tracking.login_map_view, name='login_map_view'),
    
    # Insurance & Claims
    path('insurance/', views_insurance.insurance_list, name='insurance_list'),
    path('insurance/claims/', views_insurance.insurance_claims_dashboard, name='insurance_claims_dashboard'),
    path('claims/', views_insurance.claims_list, name='claims_list'),
    path('claims/create/invoice/<uuid:invoice_id>/', views_insurance.create_claim_from_invoice, name='create_claim_from_invoice'),
    path('claims/<uuid:pk>/', views_insurance.claim_detail, name='claim_detail'),
    path('claims/<uuid:pk>/submit/', views_insurance.submit_claim, name='submit_claim'),
    path('claims/<uuid:pk>/payment/', views_insurance.process_claim_payment, name='process_claim_payment'),
    path('insurance/claim-items/', views_insurance.insurance_claim_items_list, name='insurance_claim_items_list'),
    path('insurance/claim-items/<uuid:pk>/', views_insurance.insurance_claim_item_detail, name='insurance_claim_item_detail'),
    path('insurance/monthly-claims/', views_insurance.monthly_claims_list, name='monthly_claims_list'),
    path('insurance/monthly-claims/<uuid:pk>/', views_insurance.monthly_claim_detail, name='monthly_claim_detail'),
    path('insurance/monthly-claims/generate/', views_insurance.generate_monthly_claims, name='generate_monthly_claims'),
    path('insurance/monthly-claims/<uuid:pk>/submit/', views_insurance.submit_monthly_claim, name='submit_monthly_claim'),
    path('patients/<uuid:patient_id>/insurance-claims/', views_insurance.patient_insurance_claims, name='patient_insurance_claims'),
    
    # Insurance Management (World-Class)
    path('insurance/management/', views_insurance_management.insurance_management_dashboard, name='insurance_management_dashboard'),
    path('insurance/companies/', views_insurance_management.insurance_company_list, name='insurance_company_list'),
    path('insurance/companies/new/', views_insurance_management.insurance_company_create, name='insurance_company_create'),
    path('insurance/companies/<uuid:pk>/', views_insurance_management.insurance_company_detail, name='insurance_company_detail'),
    path('insurance/companies/<uuid:company_pk>/plans/new/', views_insurance_management.insurance_plan_create, name='insurance_plan_create'),
    path('insurance/patients/<uuid:patient_pk>/enroll/', views_insurance_management.patient_insurance_enroll, name='patient_insurance_enroll'),
    
    # Insurance API Endpoints
    path('api/insurance/companies/<uuid:company_pk>/plans/', views_insurance_management.get_insurance_plans_api, name='get_insurance_plans_api'),
    path('api/insurance/verify/patient/<uuid:patient_pk>/', views_insurance_management.verify_patient_insurance_api, name='verify_patient_insurance_api'),
    path('api/insurance/calculate-coverage/', views_insurance_management.calculate_insurance_coverage_api, name='calculate_insurance_coverage_api'),
    
    # Flexible Pricing Management (World-Class)
    path('pricing/', views_flexible_pricing.pricing_dashboard, name='pricing_dashboard'),
    path('pricing/categories/', views_flexible_pricing.pricing_category_list, name='pricing_category_list'),
    path('pricing/categories/new/', views_flexible_pricing.pricing_category_create, name='pricing_category_create'),
    path('pricing/categories/<uuid:pk>/', views_flexible_pricing.pricing_category_detail, name='pricing_category_detail'),
    path('pricing/matrix/', views_flexible_pricing.service_price_matrix, name='service_price_matrix'),
    path('pricing/bulk-input/', views_flexible_pricing.bulk_price_input, name='bulk_price_input'),
    path('pricing/export/<uuid:category_pk>/csv/', views_flexible_pricing.export_prices_csv, name='export_prices_csv'),
    
    # Pricing API Endpoints
    path('api/pricing/create/', views_flexible_pricing.service_price_create_api, name='service_price_create_api'),
    path('api/pricing/get/', views_flexible_pricing.get_service_price_api, name='get_service_price_api'),
    
    # Theatre/Surgery Management
    path('theatre/', views_theatre.theatre_dashboard, name='theatre_dashboard'),
    path('theatre/schedule/new/', views_theatre.theatre_schedule_create, name='theatre_schedule_create'),
    path('api/patient/<uuid:patient_id>/encounters/', views_theatre.get_patient_encounters_api, name='get_patient_encounters_api'),
    
    # Contracts & Certificates Management
    path('contracts/', views_contracts.contracts_dashboard, name='contracts_dashboard'),
    path('contracts/list/', views_contracts.contract_list, name='contract_list'),
    path('contracts/new/', views_contracts.contract_create, name='contract_create'),
    path('contracts/<uuid:pk>/', views_contracts.contract_detail, name='contract_detail'),
    path('certificates/list/', views_contracts.certificate_list, name='certificate_list'),
    path('certificates/new/', views_contracts.certificate_create, name='certificate_create'),
    path('certificates/<uuid:pk>/', views_contracts.certificate_detail, name='certificate_detail'),
    path('api/expiring-items/', views_contracts.get_expiring_items_api, name='get_expiring_items_api'),
    
    # HR Manager Dashboard
    path('hr/manager-dashboard/', views_hr_manager.hr_manager_dashboard, name='hr_manager_dashboard'),
    
    # World-Class HR Management
    path('hr/service-desk/', views_hr_worldclass.hr_services_dashboard, name='hr_services_dashboard'),
    path('hr/worldclass/', views_hr_worldclass.hr_worldclass_dashboard, name='hr_worldclass_dashboard'),
    path('hr/leave-calendar/', views_hr_worldclass.leave_calendar, name='leave_calendar'),
    path('hr/shift-calendar/', views_hr_worldclass.shift_calendar, name='shift_calendar'),
    path('hr/attendance-calendar/', views_hr_worldclass.attendance_calendar, name='attendance_calendar'),
    
    # Advanced HR Features
    path('hr/skills-matrix/', views_hr_advanced.staff_skills_matrix, name='staff_skills_matrix'),
    path('hr/overtime-tracking/', views_hr_advanced.overtime_tracking, name='overtime_tracking'),
    path('hr/staff-availability/', views_hr_advanced.staff_availability_dashboard, name='staff_availability_dashboard'),
    
    # HR Activity Calendar & Events
    path('hr/activities/', views_hr_calendar.activity_calendar, name='activity_calendar'),
    path('hr/activities/<uuid:pk>/', views_hr_calendar.activity_detail, name='activity_detail'),
    
    # HR Activity Management (Create/Edit/Delete)
    path('hr/activities/list/', views_hr_activities.activity_list, name='activity_list'),
    path('hr/activities/create/', views_hr_activities.activity_create, name='activity_create'),
    path('hr/activities/manage/<uuid:pk>/', views_hr_activities.activity_detail, name='activity_detail_manage'),
    path('hr/activities/manage/<uuid:pk>/edit/', views_hr_activities.activity_edit, name='activity_edit'),
    path('hr/activities/manage/<uuid:pk>/delete/', views_hr_activities.activity_delete, name='activity_delete'),
    path('hr/activities/manage/<uuid:pk>/rsvp/', views_hr_activities.activity_rsvp, name='activity_rsvp'),
    path('hr/recognition-board/', views_hr_calendar.staff_recognition_board, name='recognition_board'),
    path('hr/recruitment/', views_hr_calendar.recruitment_pipeline, name='recruitment_pipeline'),
    path('hr/wellness/', views_hr_calendar.wellness_dashboard, name='wellness_dashboard'),
    path('hr/surveys/', views_hr_calendar.survey_dashboard, name='survey_dashboard'),
    
    # Legacy URL redirects (for cached links)
    path('lab/', lambda request: redirect('/hms/laboratory/'), name='lab_redirect'),
    path('lab-dashboard/', views_role_dashboards.lab_technician_dashboard, name='lab_dashboard_legacy'),
    path('dashboard/lab/', views_role_dashboards.lab_team_summary_dashboard, name='lab_technician_dashboard'),
    
    # 🔒 Lab Payment Verification System
    path('lab/payment-verification/', views_lab_payment_verification.lab_payment_verification_dashboard, name='lab_payment_verification_dashboard'),
    path('lab/cashier-ticket/<uuid:lab_result_id>/', views_lab_payment_verification.lab_cashier_ticket, name='lab_cashier_ticket'),
    path('lab/verify-payment/<uuid:lab_result_id>/', views_lab_payment_verification.lab_verify_payment_by_receipt, name='lab_verify_payment'),
    path('lab/release-result/<uuid:lab_result_id>/', views_lab_payment_verification.lab_release_result, name='lab_release_result'),
    path('lab/api/search-receipt/', views_lab_payment_verification.lab_search_receipt_api, name='lab_search_receipt_api'),
    
    # Telemedicine Module
    path('telemedicine/', views_telemedicine.telemedicine_dashboard, name='telemedicine_dashboard'),
    path('telemedicine/schedule/', views_telemedicine.schedule_consultation, name='schedule_consultation'),
    path('telemedicine/consultation/<uuid:consultation_id>/room/', views_telemedicine.consultation_room, name='consultation_room'),
    path('telemedicine/chat/', views_telemedicine.chat_interface, name='chat_interface'),
    path('telemedicine/consultation/<uuid:consultation_id>/messages/', views_telemedicine.chat_messages, name='chat_messages'),
    
    # Enhanced Telemedicine - World-Class Features
    path('telemedicine/command-center/', views_telemedicine_enhanced.telemedicine_worldclass_dashboard, name='telemedicine_command_center'),
    path('telemedicine/virtual-waiting-room/', views_telemedicine_enhanced.virtual_waiting_room_display, name='virtual_waiting_room'),
    path('telemedicine/ai-symptom-checker/', views_telemedicine_enhanced.ai_symptom_checker_interface, name='ai_symptom_checker'),
    path('telemedicine/analytics/', views_telemedicine_enhanced.consultation_analytics_dashboard, name='consultation_analytics'),
    path('telemedicine/patient-checkin/', views_telemedicine_enhanced.patient_self_checkin, name='patient_self_checkin'),
    
    # Staff Dashboard (Leave Countdown & Activities)
    path('staff/dashboard/', views_staff_dashboard.staff_dashboard, name='staff_dashboard'),
    path('staff/activities/', views_staff_dashboard.staff_activities_calendar, name='staff_activities_calendar'),
    path('staff/alert/<int:alert_id>/acknowledge/', views_staff_dashboard.acknowledge_leave_alert, name='acknowledge_leave_alert'),
    path('staff/leave-counter/api/', views_staff_dashboard.staff_leave_counter_api, name='staff_leave_counter_api'),
    
    # Advanced feature views
    path('queues/', views_advanced.queue_display, name='queue_display'),
    path('queues/doctor-console/', views_queue.doctor_queue_console, name='doctor_queue_console'),
    path('queues/api/call-next/', views_queue.queue_call_next, name='queue_call_next'),
    path('queues/api/<uuid:queue_id>/call/', views_queue.queue_call_specific, name='queue_call_specific'),
    path('queues/api/<uuid:queue_id>/start/', views_queue.queue_start_entry, name='queue_start_entry'),
    path('queues/api/<uuid:queue_id>/complete/', views_queue.queue_complete_entry, name='queue_complete_entry'),
    path('queues/api/<uuid:queue_id>/no-show/', views_queue.queue_mark_no_show, name='queue_mark_no_show'),
    path('queues/api/feed/', views_queue.queue_status_feed, name='queue_status_feed'),
    path('queues/<uuid:queue_id>/<str:action>/', views_advanced.queue_action, name='queue_action'),
    path('queues/call-next/', views_advanced.queue_call_next, name='queue_call_next_legacy'),  # Legacy endpoint, kept for backward compatibility
    path('api/queues/data/', views_advanced.queue_data_api, name='queue_data_api'),
    path('triage/', views_advanced.triage_queue, name='triage_queue'),
    
    # Consulting Rooms & Doctor Room Assignment
    path('consulting-rooms/', views_consulting_rooms.consulting_rooms_dashboard, name='consulting_rooms_dashboard'),
    path('doctor/room-selection/', views_consulting_rooms.doctor_room_selection, name='doctor_room_selection'),
    path('doctor/appointment-calendar/', views_consulting_rooms.doctor_appointment_calendar, name='doctor_appointment_calendar'),
    path('api/doctor/assign-room/', views_consulting_rooms.assign_doctor_to_room, name='assign_doctor_to_room'),
    path('api/doctor/end-room-assignment/', views_consulting_rooms.end_room_assignment, name='end_room_assignment'),
    # Front Desk Queue Management
    path('frontdesk/queue/create/', views_queue_frontdesk.frontdesk_queue_create, name='frontdesk_queue_create'),
    path('api/doctor/<int:doctor_id>/current-room/', views_queue_frontdesk.get_doctor_current_room_api, name='get_doctor_current_room_api'),
    
    # Enhanced Triage System
    path('triage/dashboard/', views_triage.triage_dashboard_enhanced, name='triage_dashboard'),  # Ambulance System Dashboard
    path('triage/dashboard/enhanced/', views_triage.triage_dashboard_enhanced, name='triage_dashboard_enhanced'),  # Alias
    path('triage/reports/', views_triage.triage_reports, name='triage_reports'),
    path('triage/move/<uuid:encounter_id>/', views_triage.move_patient_to_department, name='move_patient_to_department'),
    path('triage/complete/<uuid:encounter_id>/<str:current_stage>/', views_triage.complete_and_move, name='complete_and_move'),
    
    # Ambulance System
    path('ambulance/dispatch/create/', views_ambulance.create_ambulance_dispatch, name='ambulance_dispatch_create'),
    path('ambulance/dispatch/create/patient/<uuid:patient_id>/', views_ambulance.create_ambulance_dispatch, name='ambulance_dispatch_create_patient'),
    path('ambulance/dispatch/<uuid:dispatch_id>/complete/', views_ambulance.complete_ambulance_dispatch, name='ambulance_dispatch_complete'),
    path('ambulance/request/encounter/<uuid:encounter_id>/', views_ambulance.patient_request_ambulance, name='ambulance_request_transfer'),
    path('ambulance/dashboard/', views_ambulance.ambulance_dashboard, name='ambulance_dashboard'),
    
    # Medical Records System
    path('medical-records/patient/<uuid:patient_id>/', views_medical_records.comprehensive_medical_record, name='comprehensive_medical_record'),
    path('medical-records/encounter/<uuid:encounter_id>/', views_medical_records.encounter_documentation, name='encounter_documentation'),
    path('medical-records/timeline/<uuid:patient_id>/', views_medical_records.patient_timeline, name='patient_timeline'),
    path(
        'medical-records/documents/<uuid:document_id>/file/',
        views_medical_records.patient_document_file,
        name='patient_document_file',
    ),
    path('theatre/', views_advanced.theatre_schedule, name='theatre_schedule'),
    path('mar/', views_advanced.mar_admin, name='mar_admin'),
    path('kpi-dashboard/', views_advanced.kpi_dashboard, name='kpi_dashboard'),
    path('provider-calendar/<uuid:provider_id>/', views_advanced.provider_calendar, name='provider_calendar'),
    path('provider-calendar/', views_advanced.provider_calendar, name='provider_calendar_my'),
    path('handovers/', views_advanced.handover_sheet_list, name='handover_sheet_list'),
    path('equipment/', views_advanced.equipment_list, name='equipment_list'),
    path('consumables/', views_advanced.consumables_list, name='consumables_list'),
    path('incidents/', views_advanced.incident_list_view, name='incident_list'),
    
    # Create forms
    path('queues/new/', views_advanced.queue_create, name='queue_create'),
    path('triage/new/', views_advanced.triage_create, name='triage_create'),
    path('appointments/new/', views_advanced.appointment_create, name='appointment_create'),
    
    # Front Desk Appointment Management
    path('frontdesk/appointments/', views_appointments.frontdesk_appointment_dashboard, name='frontdesk_appointment_dashboard'),
    path('frontdesk/appointments/create/', views_appointments.frontdesk_appointment_create, name='frontdesk_appointment_create'),
    path('frontdesk/appointments/list/', views_appointments.frontdesk_appointment_list, name='frontdesk_appointment_list'),
    path('frontdesk/appointments/<uuid:pk>/', views_appointments.frontdesk_appointment_detail, name='frontdesk_appointment_detail'),
    path('frontdesk/appointments/<uuid:pk>/edit/', views_appointments.frontdesk_appointment_edit, name='frontdesk_appointment_edit'),
    path('frontdesk/appointments/<uuid:pk>/send-feedback-sms/', views_appointments.frontdesk_send_feedback_sms, name='frontdesk_send_feedback_sms'),
    path('frontdesk/appointments/send-feedback-sms-manual/', views_appointments.frontdesk_send_feedback_sms_manual, name='frontdesk_send_feedback_sms_manual'),
    
    # Front Desk Reports
    path('frontdesk/reports/', views_frontdesk_reports.frontdesk_reports_dashboard, name='frontdesk_reports_dashboard'),
    path('frontdesk/reports/generate/', views_frontdesk_reports.frontdesk_report_generate, name='frontdesk_report_generate'),
    
    # Legacy shortcut
    path('appointments/', views_appointments.frontdesk_appointment_dashboard, name='appointments_redirect'),
    
    # State-of-the-Art Appointment System
    path('appointments/calendar/', views_appointments_advanced.appointment_calendar_view, name='appointment_calendar_view'),
    path('appointments/smart-booking/', views_appointments_advanced.smart_appointment_booking, name='smart_appointment_booking'),
    path('appointments/analytics/', views_appointments_advanced.appointment_analytics_dashboard, name='appointment_analytics'),
    path('appointments/waiting-list/', views_appointments_advanced.waiting_list_dashboard, name='waiting_list_dashboard'),
    path('appointments/waiting-list/add/', views_appointments_advanced.add_to_waiting_list, name='add_to_waiting_list'),
    path('api/appointments/check-availability/', views_appointments_advanced.check_availability_api, name='check_availability_api'),
    
    # Patient Appointment Confirmation (Public - No Login Required)
    path('appointments/confirm/<uuid:appointment_id>/<str:token>/', views_appointment_confirmation.appointment_confirmation_page, name='appointment_confirmation_page'),
    path('api/appointments/confirm/<uuid:appointment_id>/<str:token>/', views_appointment_confirmation.confirm_appointment, name='confirm_appointment_api'),
    path('api/appointments/cancel/<uuid:appointment_id>/<str:token>/', views_appointment_confirmation.cancel_appointment_patient, name='cancel_appointment_patient'),
    
    # Payment Verification System (World-Class Receipt Verification)
    path('payment/verification/', views_payment_verification.payment_verification_dashboard, name='payment_verification_dashboard'),
    path('payment/lab-results/release/', views_payment_verification.lab_result_release_workflow, name='lab_result_release_workflow'),
    path('payment/pharmacy/dispensing/', views_payment_verification.pharmacy_dispensing_workflow, name='pharmacy_dispensing_workflow'),
    path('payment/verify/lab/<uuid:lab_result_id>/', views_payment_verification.verify_payment_for_lab_result, name='verify_payment_for_lab_result'),
    path('payment/verify/pharmacy/<uuid:prescription_id>/', views_payment_verification.verify_payment_for_pharmacy, name='verify_payment_for_pharmacy'),
    path('payment/pharmacy/<uuid:prescription_id>/bill-to-insurance-corporate/', views_payment_verification.bill_prescription_to_insurance_corporate, name='bill_prescription_to_insurance_corporate'),
    path('api/payment/scan-qr/', views_payment_verification.scan_receipt_qr_api, name='scan_receipt_qr_api'),
    path('payment/receipt/<uuid:receipt_id>/print-qr/', views_payment_verification.print_receipt_with_qr, name='print_receipt_with_qr'),
    
    # 🏆 Unified Payment System with Auto QR Receipts (All Services)
    path('payment/process/lab/<uuid:lab_result_id>/', views_unified_payments.lab_payment_process, name='lab_payment_process'),
    path('payment/process/pharmacy/<uuid:prescription_id>/', views_unified_payments.pharmacy_payment_process, name='pharmacy_payment_process'),
    path('payment/process/imaging/<uuid:imaging_study_id>/', views_unified_payments.imaging_payment_process, name='imaging_payment_process'),
    path('payment/process/consultation/<uuid:encounter_id>/', views_unified_payments.consultation_payment_process, name='consultation_payment_process'),
    
    # Receipt Management (View, Print, Verify)
    path('receipt/<uuid:receipt_id>/', views_unified_payments.receipt_detail, name='receipt_detail'),
    path('receipt/<uuid:receipt_id>/print/', views_unified_payments.receipt_print, name='receipt_print'),
    path('receipt/<uuid:receipt_id>/pos/', views_unified_payments.receipt_pos_print, name='receipt_pos_print'),
    path('receipt/<uuid:receipt_id>/pos/print-preview/', views_unified_payments.receipt_pos_print_preview, name='receipt_pos_print_preview'),
    path('receipt/verify/qr/', views_unified_payments.receipt_verify_qr, name='receipt_verify_qr'),
    path('receipt/verify/number/', views_unified_payments.receipt_verify_number, name='receipt_verify_number'),
    
    # Receipt API Endpoints (for QR scanning)
    path('api/receipt/verify/qr/', views_unified_payments.api_verify_receipt_qr, name='api_verify_receipt_qr'),
    path('api/receipt/<str:receipt_number>/', views_unified_payments.api_receipt_details, name='api_receipt_details'),
    
    # Global search
    path('search/', views.global_search, name='global_search'),
    
    # Patient Workflow
    # Patient Flow - World Class
    path('flow/dashboard/', views_workflow.flow_dashboard, name='flow_dashboard'),
    path('flow/<uuid:encounter_id>/', views_workflow.patient_flow, name='patient_flow'),
    path('flow/stage/<uuid:stage_id>/start/', views_workflow.start_flow_stage, name='start_flow_stage'),
    path('flow/stage/<uuid:stage_id>/complete/', views_workflow.complete_flow_stage, name='complete_flow_stage'),
    path('flow/<uuid:encounter_id>/vitals/', views_workflow.record_vitals, name='record_vitals'),
    path('flow/<uuid:encounter_id>/bill/', views_workflow.create_bill, name='create_bill'),
    # Legacy convenience route for vitals dashboard
    path('vitals/', views_workflow.flow_dashboard, name='vitals_dashboard_legacy'),
    
    # Cashier Module (Original)
    path('cashier/', views_cashier.cashier_dashboard, name='cashier_dashboard'),
    path('cashier/dashboard/', views_cashier.cashier_dashboard, name='cashier_dashboard_legacy'),
    
    # 💰 Centralized Cashier System (All payments through here)
    path('cashier/central/', views_centralized_cashier.centralized_cashier_dashboard, name='centralized_cashier_dashboard'),
    path('cashier/central/all-pending/', views_centralized_cashier.cashier_all_pending_bills, name='cashier_all_pending_bills'),
    path('cashier/central/patient-bills/', views_centralized_cashier.cashier_patient_bills, name='cashier_patient_bills'),
    path('cashier/central/patient/<uuid:patient_id>/total-bill/', views_centralized_cashier.cashier_patient_total_bill, name='cashier_patient_total_bill'),
    path(
        'cashier/central/patient/<uuid:patient_id>/deposit/<uuid:deposit_id>/usage/',
        views_centralized_cashier.cashier_patient_deposit_usage_json,
        name='cashier_patient_deposit_usage_json',
    ),
    path('cashier/central/patient/<uuid:patient_id>/apply-deposit/', views_centralized_cashier.cashier_apply_deposit_to_bill, name='cashier_apply_deposit_to_bill'),
    path('cashier/central/patient/<uuid:patient_id>/refund-credit/', views_centralized_cashier.cashier_refund_credit, name='cashier_refund_credit'),
    path('cashier/central/api/search-billable-items/', views_centralized_cashier.cashier_search_billable_items, name='cashier_search_billable_items'),
    path('cashier/central/patient/<uuid:patient_id>/add-services-to-invoice/', views_centralized_cashier.cashier_add_services_to_invoice, name='cashier_add_services_to_invoice'),
    path('cashier/central/patient/<uuid:patient_id>/add-services/', views_centralized_cashier.cashier_add_services_select, name='cashier_add_services_select'),
    path('cashier/central/add-manual-payment/', views_centralized_cashier.cashier_add_manual_payment, name='cashier_add_manual_payment'),
    path('cashier/non-patient-charge/', views_centralized_cashier.cashier_non_patient_charge, name='cashier_non_patient_charge'),
    path('cashier/central/patients/', views_centralized_cashier.cashier_patient_list, name='cashier_patient_list'),
    path('cashier/central/create-billing/', views_centralized_cashier.cashier_create_billing, name='cashier_create_billing'),
    path('cashier/central/process/<str:service_type>/<uuid:service_id>/', views_centralized_cashier.cashier_process_service_payment, name='cashier_process_service_payment'),
    path('cashier/central/process-pharmacy-encounter/<uuid:encounter_id>/', views_centralized_cashier.cashier_process_pharmacy_encounter, name='cashier_process_pharmacy_encounter'),
    path('cashier/central/process-combined/<uuid:patient_id>/', views_centralized_cashier.cashier_process_patient_combined_payment, name='cashier_process_patient_combined_payment'),
    path('cashier/central/combined-bill/<uuid:receipt_id>/print/', views_centralized_cashier.cashier_combined_bill_print, name='cashier_combined_bill_print'),
    path('cashier/revenue-report/', views_centralized_cashier.cashier_revenue_report, name='cashier_revenue_report'),
    
    # 💰 Service Pricing Management (Lab, Pharmacy, etc.)
    path('pricing/', views_service_pricing.pricing_dashboard, name='pricing_dashboard'),
    path('pricing/lab/', views_service_pricing.lab_pricing_list, name='lab_pricing_list'),
    path('pricing/lab/<uuid:lab_id>/update/', views_service_pricing.lab_pricing_update, name='lab_pricing_update'),
    path('pricing/drug/', views_service_pricing.drug_pricing_list, name='drug_pricing_list'),
    path('pricing/drug/<uuid:drug_id>/update/', views_service_pricing.drug_pricing_update, name='drug_pricing_update'),
    path('pricing/bulk-update/', views_service_pricing.bulk_price_update, name='bulk_price_update'),
    path('api/pricing/<str:service_type>/<uuid:service_id>/', views_service_pricing.get_service_price_api, name='get_service_price_api'),
    path('cashier/payments/process/<uuid:payment_request_id>/', views_cashier.process_payment, name='process_payment_request'),
    path('cashier/payments/process-bill/<uuid:bill_id>/', views_cashier.process_payment, name='process_payment_bill'),
    path('cashier/payments/process-invoice/<uuid:invoice_id>/', views_cashier.process_payment, name='process_payment_invoice'),
    path('cashier/receipts/', views_cashier.cashier_receipts_list, name='cashier_receipts_list'),
    path('cashier/receipt/<uuid:receipt_id>/', views_cashier.payment_receipt, name='payment_receipt'),
    path('cashier/session/create/', views_cashier.create_session, name='create_session'),
    path('cashier/session/<uuid:session_id>/update-notes/', views_cashier.update_session_notes, name='update_session_notes'),
    path('cashier/session/<uuid:session_id>/close/', views_cashier.close_session, name='close_session'),
    path('cashier/session/<uuid:session_id>/print/', views_cashier.cashier_session_print, name='cashier_session_print'),
    path('cashier/session/', views_cashier.cashier_session_detail, name='cashier_session_detail'),
    path('cashier-sessions/', views_cashier.cashier_sessions_list, name='cashier_sessions_list'),
    path('cashier/<int:cashier_id>/history/', views_cashier.cashier_history, name='cashier_history'),
    path('cashier/bills/', views_cashier.cashier_bills, name='cashier_bills'),
    path('cashier/invoices/', views_cashier.cashier_invoices, name='cashier_invoices'),
    path('cashier/invoices/<uuid:pk>/', views_cashier.cashier_invoice_detail, name='cashier_invoice_detail'),
    path('cashier/invoices/waive-line/', views_cashier.waive_invoice_line, name='waive_invoice_line'),
    path('cashier/invoices/remove-from-bill/', views_cashier.remove_invoice_from_bill, name='remove_invoice_from_bill'),
    path('cashier/waive-prescribe-sale/', views_cashier.waive_prescribe_sale, name='waive_prescribe_sale'),
    path('cashier/waive-prescribe-sale-line/', views_cashier.waive_prescribe_sale_line, name='waive_prescribe_sale_line'),
    path('cashier/debt/', views_cashier.customer_debt, name='customer_debt'),
    path('cashier/patient/<uuid:patient_id>/invoices/', views_cashier.patient_invoices, name='cashier_patient_invoices'),
    path('cashier/patient/<uuid:patient_id>/invoices/print/', views_cashier.patient_invoices_print, name='cashier_patient_invoices_print'),
    
    # Accounting Module (OLD - commented out, using advanced accounting instead)
    # path('accounting/', views_accounting.accounting_dashboard, name='accounting_dashboard'),
    path('accounts/', views_accounting.chart_of_accounts, name='chart_of_accounts'),
    # Handle invalid account IDs gracefully
    path('accounts/INVALID/', lambda request: redirect('hospital:chart_of_accounts'), name='account_invalid_redirect'),
    re_path(r'^accounts/(?P<account_id>[0-9]+)/None/?$', lambda request, account_id: redirect('hospital:chart_of_accounts'), name='account_none_redirect'),
    # OLD URLs - kept for backward compatibility but not actively used
    # path('accounting/ar/', views_accounting.accounts_receivable, name='accounts_receivable_old'),
    # path('accounting/ledger/', views_accounting.general_ledger, name='general_ledger_old'),
    # path('accounting/trial-balance/', views_accounting.trial_balance, name='trial_balance'),  # OLD - Using advanced version
    # path('accounting/financial-statement/', views_accounting.financial_statement, name='financial_statement_old'),
    # Handle invalid accounting URLs
    path('accounting/INVALID/', lambda request: redirect('hospital:accounting_dashboard'), name='accounting_invalid_redirect'),
    re_path(r'^accounting/(?P<report_type>[a-z-]+)/INVALID/?$', lambda request, report_type: redirect('hospital:accounting_dashboard'), name='accounting_report_invalid_redirect'),
    
    # HOD Scheduling & Timetable Management
    path('hod/scheduling/', views_hod_scheduling.hod_scheduling_dashboard, name='hod_scheduling_dashboard'),
    path('hod/timetable/create/', views_hod_scheduling.hod_create_timetable_simple, name='hod_create_timetable'),
    path('hod/shift/create/', views_hod_scheduling.hod_create_shift, name='hod_create_shift'),
    path('hod/shifts/bulk-assign/', views_hod_scheduling.hod_bulk_assign_shifts, name='hod_bulk_assign_shifts'),
    path('hod/roster/upload/', views_hod_scheduling.hod_upload_roster, name='hod_upload_roster'),
    path('hod/scheduling/events/', views_hod_scheduling.hod_schedule_events, name='hod_schedule_events'),
    path('staff/my-schedule/', views_hod_scheduling.staff_dashboard_with_schedule, name='staff_schedule_dashboard'),
    
    # HOD Shift Monitoring & Attendance Tracking
    path('hod/shift-monitoring/', views_hod_shift_monitoring.hod_shift_monitoring_dashboard, name='hod_shift_monitoring_dashboard'),
    path('hod/shift-attendance-report/', views_hod_shift_monitoring.hod_shift_attendance_report, name='hod_shift_attendance_report'),
    path('hod/shift/create-enhanced/', views_hod_shift_monitoring.hod_create_shift_enhanced, name='hod_create_shift_enhanced'),
    path('hod/shortages-alert/', views_hod_shift_monitoring.hod_shortages_alert, name='hod_shortages_alert'),
    
    # HR Module
    path('hr/', views_hr.hr_dashboard, name='hr_dashboard'),
    path('hr/staff/', views_hr.staff_list, name='staff_list'),
    path('hr/staff/new/', views_hr.staff_create, name='staff_create'),
    path('hr/staff/<uuid:pk>/', views_hr.staff_detail, name='staff_detail'),
    path('hr/staff/<uuid:pk>/edit/', views_hr.staff_edit, name='staff_edit'),
    path('hr/staff/<uuid:staff_id>/contract/', views_hr.staff_contract_create, name='staff_contract_create'),
    path('hr/staff/<uuid:staff_id>/document/', views_hr.staff_document_upload, name='staff_document_upload'),
    path('hr/staff/<uuid:staff_id>/review/', views_hr.performance_review_create, name='performance_review_create'),
    path('hr/staff/<uuid:staff_id>/training/', views_hr.training_record_create, name='training_record_create'),
    # Payroll redirect (for easier access)
    path('payroll/', lambda request: redirect('hospital:payroll_list'), name='payroll_redirect'),
    path('hr/payroll/', views_hr.payroll_list, name='payroll_list'),
    path('hr/payroll/<uuid:pk>/', views_hr.payroll_detail, name='payroll_detail'),
    path('hr/payroll/process/<uuid:period_id>/', views_hr.process_payroll, name='process_payroll'),
    
    # Payroll Settings
    path('hr/payroll/settings/', views_hr.payroll_settings, name='payroll_settings'),
    path('hr/payroll/settings/config/', views_hr.payroll_config_create, name='payroll_config_create'),
    path('hr/payroll/settings/config/<uuid:pk>/edit/', views_hr.payroll_config_edit, name='payroll_config_edit'),
    path('hr/payroll/settings/allowances/', views_hr.allowance_type_list, name='allowance_type_list'),
    path('hr/payroll/settings/allowances/new/', views_hr.allowance_type_create, name='allowance_type_create'),
    path('hr/payroll/settings/allowances/<uuid:pk>/edit/', views_hr.allowance_type_edit, name='allowance_type_edit'),
    path('hr/payroll/settings/deductions/', views_hr.deduction_type_list, name='deduction_type_list'),
    path('hr/payroll/settings/deductions/new/', views_hr.deduction_type_create, name='deduction_type_create'),
    path('hr/payroll/settings/deductions/<uuid:pk>/edit/', views_hr.deduction_type_edit, name='deduction_type_edit'),
    path('hr/payroll/settings/tax-brackets/', views_hr.tax_bracket_list, name='tax_bracket_list'),
    path('hr/payroll/settings/tax-brackets/new/', views_hr.tax_bracket_create, name='tax_bracket_create'),
    path('hr/payroll/settings/tax-brackets/<uuid:pk>/edit/', views_hr.tax_bracket_edit, name='tax_bracket_edit'),
    path('hr/shifts/', views_hr.staff_shift_list, name='staff_shift_list'),
    path('hr/shifts/new/', views_hr.staff_shift_create, name='staff_shift_create'),
    
    # HR/Admin Department-Wise Shift Management
    path('hr/shifts/by-department/', views_hr_shifts_department.hr_shifts_by_department, name='hr_shifts_by_department'),
    path('hr/shifts/department/<uuid:dept_id>/', views_hr_shifts_department.hr_department_shifts_detail, name='hr_department_shifts_detail'),
    path('hr/shifts/department/<uuid:dept_id>/calendar/', views_hr_shifts_department.hr_department_shifts_calendar, name='hr_department_shifts_calendar'),
    path('hr/leaves/', views_hr.leave_request_list, name='leave_request_list'),
    path('hr/leaves/new/', views_hr.leave_request_create, name='leave_request_create'),
    path('hr/leaves/<uuid:pk>/approve/', views_hr.leave_request_approve, name='leave_request_approve'),
    
    # HR Reports Module
    path('hr/reports/', views_hr_reports.hr_reports_dashboard, name='hr_reports_dashboard'),
    path('hr/reports/staff/', views_hr_reports.staff_list_report, name='staff_list_report'),
    path('hr/reports/leave/', views_hr_reports.leave_report, name='leave_report'),
    path('hr/reports/attendance/', views_hr_reports.attendance_report, name='attendance_report'),
    path('hr/attendance/login-sessions/', views_hr_reports.login_attendance_dashboard, name='login_attendance_dashboard'),
    path('hr/live-sessions/', views_hr_reports.live_session_monitor, name='live_session_monitor'),
    path('hr/reports/payroll/', views_hr_reports.payroll_report, name='payroll_report'),
    path('hr/reports/training/', views_hr_reports.training_report, name='training_report'),
    path('hr/reports/performance/', views_hr_reports.performance_report, name='performance_report'),
    
    # Procurement Module
    path('procurement/', views_procurement.procurement_dashboard, name='procurement_dashboard'),
    path('procurement/stores/', views_procurement.stores_list, name='stores_list'),
    path('procurement/stores/<uuid:pk>/', views_procurement.store_detail, name='store_detail'),
    path('procurement/requests/', views_procurement.procurement_requests_list, name='procurement_requests_list'),
    path('procurement/requests/<uuid:pk>/', views_procurement.procurement_request_detail, name='procurement_request_detail'),
    
    # Pharmacy to Procurement Requests
    path('pharmacy/procurement-requests/', views_procurement_enhanced.pharmacy_procurement_requests_worldclass, name='pharmacy_procurement_requests'),
    path('pharmacy/request/create/', views_procurement.pharmacy_request_create, name='pharmacy_request_create'),
    path('procurement/request/<uuid:pk>/submit/', views_procurement.submit_procurement_request, name='submit_procurement_request'),
    path('procurement/request/<uuid:pk>/approve/', views_procurement.approve_procurement_request, name='approve_procurement_request'),
    path('procurement/request/<uuid:pk>/receive/', views_procurement.mark_request_received, name='mark_request_received'),
    
    # World-Class Procurement Workflow (Multi-Tier Approval)
    path('procurement/approvals/', views_procurement_enhanced.procurement_approval_dashboard, name='procurement_approval_dashboard'),
    path('procurement/request/<uuid:pk>/admin-review/', views_procurement_enhanced.procurement_admin_review, name='procurement_admin_review'),
    path('procurement/request/<uuid:pk>/finance-review/', views_procurement_enhanced.finance_review_request, name='finance_review_request'),
    path('procurement/request/<uuid:pk>/release/', views_procurement_enhanced.release_to_pharmacy, name='release_to_pharmacy'),
    path('procurement/workflow/', views_procurement_enhanced.procurement_workflow_dashboard, name='procurement_workflow_dashboard'),
    
    path('procurement/transfers/', views_procurement.store_transfers_list, name='store_transfers_list'),
    path('procurement/transfers/<uuid:pk>/', views_procurement.store_transfer_detail, name='store_transfer_detail'),
    # Enhanced Transfer System
    path('procurement/transfers/dashboard/', views_store_transfer_enhanced.transfer_dashboard, name='transfer_dashboard'),
    path('procurement/transfers/create-modern/', views_store_transfer_enhanced.create_transfer_modern, name='create_transfer_modern'),
    path('procurement/transfers/<uuid:pk>/approve/', views_store_transfer_enhanced.approve_transfer, name='approve_transfer'),
    path('procurement/transfers/<uuid:pk>/complete/', views_store_transfer_enhanced.complete_transfer, name='complete_transfer'),
    path('procurement/transfers/<uuid:pk>/detail-enhanced/', views_store_transfer_enhanced.transfer_detail_enhanced, name='transfer_detail_enhanced'),
    path('procurement/api/store-items/', views_store_transfer_enhanced.api_get_store_items, name='api_get_store_items'),
    path('procurement/api/item-details/', views_store_transfer_enhanced.api_get_item_details, name='api_get_item_details'),
    path('procurement/api/categories/', views_store_transfer_enhanced.api_get_categories, name='api_get_categories'),
    # Enhanced Receiving System
    path('procurement/receiving/dashboard/', views_procurement_receiving_enhanced.procurement_receiving_dashboard, name='procurement_receiving_dashboard'),
    path('procurement/receiving/<uuid:pk>/modern/', views_procurement_receiving_enhanced.receive_procurement_modern, name='receive_procurement_modern'),
    path('procurement/reports/low-stock/', views_procurement.low_stock_report, name='low_stock_report'),
    path('procurement/suppliers/', views_procurement.suppliers_list, name='suppliers_list'),
    path('procurement/suppliers/new/', views_procurement.supplier_create, name='supplier_create'),
    path('procurement/suppliers/<uuid:pk>/edit/', views_procurement.supplier_edit, name='supplier_edit'),
    path('procurement/inventory/', views_procurement.inventory_management, name='inventory_management'),
    path('procurement/stores/new/', views_procurement.store_create, name='store_create'),
    path('procurement/stores/<uuid:pk>/edit/', views_procurement.store_edit, name='store_edit'),
    path('procurement/inventory-items/new/', views_procurement.inventory_item_create, name='inventory_item_create'),
    path('procurement/inventory-items/<uuid:pk>/edit/', views_procurement.inventory_item_edit, name='inventory_item_edit'),
    path('procurement/inventory-items/<uuid:pk>/delete/', views_procurement.inventory_item_delete, name='inventory_item_delete'),
    path('procurement/inventory/duplicates/', views_inventory_duplicates.inventory_duplicates_view, name='inventory_duplicates'),
    path('procurement/inventory/merge-duplicates/', views_inventory_duplicates.merge_duplicates, name='merge_duplicates'),
    path('procurement/requests/new/', views_procurement.procurement_request_create, name='procurement_request_create'),
    path('procurement/requests/<uuid:pk>/edit/', views_procurement.procurement_request_edit, name='procurement_request_edit'),
    path('procurement/transfers/new/', views_procurement.store_transfer_create, name='store_transfer_create'),
    
    # Procurement Approval Workflow (NEW - World-Class P2P)
    path('procurement/approval/dashboard/', views_procurement_approval.procurement_dashboard, name='procurement_approval_dashboard'),
    path('procurement/approval/create/', views_procurement_approval.create_procurement_request, name='create_procurement_request'),
    path('procurement/approval/<uuid:pr_id>/submit/', views_procurement_approval.submit_procurement_request, name='submit_procurement_request'),
    path('procurement/approval/<uuid:pr_id>/detail/', views_procurement_approval.procurement_detail, name='procurement_approval_detail'),
    path('procurement/approval/list/', views_procurement_approval.procurement_list, name='procurement_approval_list'),
    
    # Admin Approval
    path('procurement/admin/pending/', views_procurement_approval.admin_approval_list, name='admin_approval_list'),
    path('procurement/admin/<uuid:pr_id>/approve/', views_procurement_approval.approve_admin, name='approve_admin'),
    path('procurement/admin/<uuid:pr_id>/reject/', views_procurement_approval.reject_admin, name='reject_admin'),
    
    # Accounts Approval (Creates Accounting Entries!)
    path('procurement/accounts/pending/', views_procurement_approval.accounts_approval_list, name='accounts_approval_list'),
    path('procurement/accounts/post-to-ledger/', views_procurement_approval.procurement_post_to_ledger_list, name='procurement_post_to_ledger_list'),
    path('procurement/accounts/<uuid:pr_id>/post-to-ledger/', views_procurement_approval.procurement_post_to_ledger, name='procurement_post_to_ledger'),
    path('procurement/accounts/<uuid:pr_id>/approve/', views_procurement_approval.approve_accounts, name='approve_accounts'),
    path('procurement/accounts/<uuid:pr_id>/reject/', views_procurement_approval.reject_accounts, name='reject_accounts'),
    
    # API
    path('procurement/api/stats/', views_procurement_approval.procurement_stats_api, name='procurement_stats_api'),
    
    # ==================== WORLD-CLASS INVENTORY MANAGEMENT SYSTEM ====================
    # State-of-the-art supply chain management with complete accountability
    # Include inventory URLs with explicit namespace for proper nested namespace resolution
    path('inventory/', include(('hospital.urls_inventory', 'inventory'))),
    
    # Inventory & Stores Manager Dashboard
    path('inventory-stores/dashboard/', views_inventory_stores_manager.inventory_stores_manager_dashboard, name='inventory_stores_manager_dashboard'),
    
    # Birthday Reminders & SMS
    path('reminders/birthdays/', views_reminders.birthday_reminders, name='birthday_reminders'),
    path('reminders/sms/', views_reminders.sms_notifications, name='sms_notifications'),
    path('api/sms/birthday/', views_reminders.send_birthday_sms_api, name='send_birthday_sms_api'),
    path('sms/send/', views_sms.send_sms, name='send_sms'),
    path('sms/lab-result/<uuid:lab_result_id>/', views_sms.send_lab_result_sms, name='send_lab_result_sms'),
    path('sms/bulk/dashboard/', views_sms.bulk_sms_dashboard, name='bulk_sms_dashboard'),
    path('sms/bulk/', views_sms.send_bulk_sms, name='send_bulk_sms'),
    
    # Specialist Views
    path('specialists/', views_specialists.specialist_dashboard, name='specialist_dashboard'),
    path('specialists/patient-select/', views_specialists.specialist_patient_select, name='specialist_patient_select'),
    path('specialists/my-dashboard/', views_specialists.specialist_personal_dashboard, name='specialist_personal_dashboard'),
    path('specialists/dentist/dashboard/', views_specialists.dentist_dashboard, name='dentist_dashboard'),
    path('specialists/dental/patient/<uuid:patient_id>/', views_specialists.dental_consultation, name='dental_consultation'),
    path('specialists/dental/encounter/<uuid:encounter_id>/', views_specialists.dental_consultation, name='dental_consultation_encounter'),
    path('specialists/cardiology/patient/<uuid:patient_id>/', views_specialists.cardiology_consultation, name='cardiology_consultation'),
    path('specialists/cardiology/encounter/<uuid:encounter_id>/', views_specialists.cardiology_consultation, name='cardiology_consultation_encounter'),
    path('specialists/ophthalmology/patient/<uuid:patient_id>/', views_specialists.ophthalmology_consultation, name='ophthalmology_consultation'),
    path('specialists/ophthalmology/encounter/<uuid:encounter_id>/', views_specialists.ophthalmology_consultation, name='ophthalmology_consultation_encounter'),
    path('specialists/psychiatric/dashboard/', views_specialists.psychiatric_dashboard, name='psychiatric_dashboard'),
    path('specialists/psychiatric/dasboard/', views_specialists.psychiatric_dashboard, name='psychiatric_dashboard_typo'),  # Redirect for typo
    path('specialists/psychiatric/patient/<uuid:patient_id>/', views_specialists.psychiatric_consultation, name='psychiatric_consultation'),
    path('specialists/psychiatric/encounter/<uuid:encounter_id>/', views_specialists.psychiatric_consultation, name='psychiatric_consultation_encounter'),
    path('specialists/gynecology/dashboard/', views_specialists.gynecology_dashboard, name='gynecology_dashboard'),
    path('specialists/gynecology/dasboard/', views_specialists.gynecology_dashboard, name='gynecology_dashboard_typo'),  # Redirect for typo
    path('specialists/gynecology/patient/<uuid:patient_id>/', views_specialists.gynecology_consultation, name='gynecology_consultation'),
    path('specialists/gynecology/encounter/<uuid:encounter_id>/', views_specialists.gynecology_consultation, name='gynecology_consultation_encounter'),
    
    
    # Specialist API endpoints
    path('api/tooth-condition/save/', views_specialists.save_tooth_condition, name='save_tooth_condition'),
    path('api/dental-procedure/save/', views_specialists.save_dental_procedure, name='save_dental_procedure'),
    path('api/specialists/by-specialty/', views_specialists.get_specialists_by_specialty, name='get_specialists_by_specialty'),
    path('api/specialists/all/', views_specialists.get_all_specialists, name='get_all_specialists'),
    
    # Referral views
    path('referrals/', views_specialists.referral_list, name='referral_list'),
    path('referrals/<uuid:referral_id>/', views_specialists.referral_detail, name='referral_detail'),
    path('referrals/create/encounter/<uuid:encounter_id>/', views_specialists.create_referral, name='create_referral'),
    
    # API endpoints for AJAX
    path('api/kpi-stats/', views_advanced.api_kpi_stats, name='api_kpi_stats'),
    path('api/mar/<uuid:mar_id>/administer/', views_advanced.mar_administer, name='mar_administer'),
    
    # Role-specific dashboards
    path('dashboard/role/', views_role_redirect.role_dashboard_redirect, name='role_dashboard_redirect'),
    path('dashboard/doctor/', views_role_dashboards.doctor_dashboard, name='doctor_dashboard'),
    path('dashboard/doctor/order-lab-tests/', views_role_dashboards.doctor_order_lab_tests, name='doctor_order_lab_tests'),
    path('dashboard/nurse/', views_role_dashboards.nurse_dashboard, name='nurse_dashboard'),
    path('nurse/flowboard/', views_nurse_flowboard.nurse_patient_flowboard, name='nurse_patient_flowboard'),
    path('doctor/flowboard/', views_doctor_flowboard.doctor_patient_flowboard, name='doctor_patient_flowboard'),
    
    # Nurse assignment views
    path('nurse/assign-patients/', views_nurse_assignment.nurse_patient_assignment, name='nurse_patient_assignment'),
    path('nurse/assign-patient/<uuid:encounter_id>/', views_nurse_assignment.assign_patient_to_doctor, name='assign_patient_to_doctor'),
    path('nurse/view-assignments/', views_nurse_assignment.view_patient_assignments, name='view_patient_assignments'),
    path('dashboard/midwife/', views_role_dashboards.midwife_dashboard, name='midwife_dashboard'),
    
    # Midwife-specific URLs
    path('midwife/records/', views_role_dashboards.midwife_records, name='midwife_records'),
    path('midwife/antenatal/', views_role_dashboards.antenatal_care, name='antenatal_care'),
    path('midwife/antenatal-items/', views_pharmacy_walkin.antenatal_items_billing, name='antenatal_items_billing'),
    path('midwife/postnatal/', views_role_dashboards.postnatal_care, name='postnatal_care'),
    path('midwife/delivery/', views_role_dashboards.midwife_records, name='midwife_delivery'),  # Delivery records use same view as records
    
    path('dashboard/lab/', views_role_dashboards.lab_technician_dashboard, name='lab_technician_dashboard'),
    path('dashboard/pharmacy/', views_role_dashboards.pharmacist_dashboard, name='pharmacist_dashboard'),
    path('dashboard/radiology/', views_role_dashboards.radiologist_dashboard, name='radiologist_dashboard'),
    path('dashboard/reception/', views_role_dashboards.receptionist_dashboard, name='receptionist_dashboard'),
    path('dashboard/cashier-role/', views_role_dashboards.cashier_dashboard_role, name='cashier_dashboard_role'),
    
    # Legacy Patient Management (needed for migration dashboard + admin links)
    path('legacy-patients/', views_legacy_patients.legacy_patient_list, name='legacy_patient_list'),
    path('legacy-patients/<int:pid>/', views_legacy_patients.legacy_patient_detail, name='legacy_patient_detail'),
    path('legacy-patients/<int:pid>/migrate/', views_legacy_patients.migrate_legacy_patient, name='migrate_legacy_patient'),
    path('migration/dashboard/', views_legacy_patients.migration_dashboard, name='migration_dashboard'),
    path('migration/bulk-migrate/', views_legacy_patients.bulk_migrate_patients, name='bulk_migrate_patients'),
    
    # Pricing Management
    path('pricing/', views_pricing.pricing_dashboard, name='pricing_dashboard'),
    path('pricing/services/', views_pricing.service_list, name='service_list'),
    path('pricing/services/create/', views_pricing.service_create, name='service_create'),
    path('pricing/services/<uuid:pk>/edit/', views_pricing.service_edit, name='service_edit'),
    path('pricing/payer/', views_pricing.payer_pricing, name='payer_pricing'),
    path('pricing/payer/<uuid:payer_id>/service/<str:service_code>/update/', views_pricing.update_payer_price, name='update_payer_price'),
    path('pricing/specialist/', views_pricing.specialist_services, name='specialist_services'),
    path('pricing/specialist/create/', views_pricing.create_specialist_service, name='create_specialist_service'),
    path('pricing/bulk-update/', views_pricing.bulk_price_update, name='bulk_price_update'),
    
    # Staff Self-Service Portal (aliases for older template URL names)
    path('staff/profile/', RedirectView.as_view(pattern_name='hospital:my_profile', permanent=False), name='staff_profile'),
    path('staff/leave/<uuid:pk>/', RedirectView.as_view(pattern_name='hospital:staff_leave_history', permanent=False), name='staff_leave_detail'),
    path('staff/leave/<uuid:pk>/submit/', RedirectView.as_view(pattern_name='hospital:staff_leave_history', permanent=False), name='staff_leave_submit'),
    path('staff/leave/<uuid:pk>/cancel/', RedirectView.as_view(pattern_name='hospital:staff_leave_history', permanent=False), name='staff_leave_cancel'),
    path('staff/training/', RedirectView.as_view(pattern_name='hospital:staff_portal', permanent=False), name='staff_training_history'),
    path('performance-reviews/', views_staff_portal.staff_performance_reviews, name='staff_performance_reviews'),
    
    # Manager/Admin Leave Approval
    path('hr/leave/approvals/', views_hr.leave_approval_list, name='leave_approval_list'),
    path('hr/leave/<uuid:pk>/approve/', views_hr.leave_approve, name='leave_approve'),
    path('hr/leave/<uuid:pk>/print/', views_hr.leave_print, name='leave_print'),
    path('hr/leave/<uuid:pk>/reject/', views_hr.leave_reject, name='leave_reject'),
    path('hr/leave/create-for-staff/', views_hr.create_leave_for_staff, name='create_leave_for_staff'),
    
    # HR Medical Chit Management
    path('hr/medical-chits/', views_medical_chit.hr_medical_chit_list, name='hr_medical_chit_list'),
    path('hr/medical-chits/<uuid:chit_id>/approve/', views_medical_chit.hr_medical_chit_approve, name='hr_medical_chit_approve'),
    path('hr/medical-chits/<uuid:chit_id>/reject/', views_medical_chit.hr_medical_chit_reject, name='hr_medical_chit_reject'),
    
    # Medical Staff - View Approved Chits
    path('medical/chits/approved/', views_medical_chit.medical_chit_view_approved, name='medical_chit_view_approved'),
    
    # Front Desk - Medical Chit Lookup and Visit Creation
    path('frontdesk/medical-chit/lookup/', views_medical_chit.frontdesk_medical_chit_lookup, name='frontdesk_medical_chit_lookup'),
    path('frontdesk/medical-chit/<uuid:chit_id>/create-visit/', views_medical_chit.frontdesk_medical_chit_create_visit, name='frontdesk_medical_chit_create_visit'),
    
    # Lab Report Printing & Hospital Settings
    path('laboratory/result/<uuid:result_id>/print/', views.print_lab_report, name='print_lab_report'),
    path('laboratory/result/<uuid:result_id>/pdf/', views.download_lab_report_pdf, name='download_lab_report_pdf'),
    path(
        'laboratory/result/<uuid:result_id>/attachment/',
        views.lab_result_attachment_file,
        name='lab_result_attachment_file',
    ),
    path('settings/', views.hospital_settings_view, name='hospital_settings'),
    
    # 💾 Database Backup Management
    path('backups/', views_backup.backup_dashboard, name='backup_dashboard'),
    path('backups/create/', views_backup.create_backup, name='create_backup'),
    path('backups/auto-now/', views_backup.auto_backup_now, name='auto_backup_now'),
    path('backups/download/<str:filename>/', views_backup.download_backup, name='download_backup'),
    path('backups/download-all/', views_backup.download_all_backups, name='download_all_backups'),
    path('backups/delete/<str:filename>/', views_backup.delete_backup, name='delete_backup'),
    path('backups/delete-old/', views_backup.delete_old_backups, name='delete_old_backups'),
    path('backups/info/<str:filename>/', views_backup.backup_info, name='backup_info'),
    
    # 📊 Advanced Accounting & Financial Reports
    path('accounting/', views_accounting_advanced.accounting_dashboard, name='accounting_dashboard'),
    path('accounting-dashboard/', lambda request: redirect('hospital:accountant_comprehensive_dashboard'), name='accounting_dashboard_legacy'),
    path('accounting/reports/', views_accounting_advanced.accounting_reports_hub, name='accounting_reports_hub'),
    path('accounting/profit-loss/', views_accounting_advanced.profit_loss_statement, name='profit_loss_statement'),
    path('accounting/balance-sheet/', views_accounting_advanced.balance_sheet, name='balance_sheet'),
    path('accounting/trial-balance/', views_accounting_advanced.trial_balance, name='trial_balance'),
    path('accounting/cash-flow/', views_accounting_advanced.cash_flow_statement, name='cash_flow_statement'),
    path('accounting/general-ledger/', views_accounting_advanced.general_ledger_report, name='general_ledger_report'),
    path('accounting/ar-aging/', views_accounting_advanced.accounts_receivable_aging, name='ar_aging_report'),
    path('accounting/corporate-receivables/', views_accounting_advanced.corporate_receivables, name='corporate_receivables'),
    path('accounting/ar-test/', views_accounting_advanced.ar_aging_test, name='ar_aging_test'),  # DEBUG test
    path('accounting/ap-report/', views_accounting_advanced.accounts_payable_report, name='ap_report'),
    path('accounting/ap/<uuid:ap_id>/record-payment/', views_accounting_advanced.record_ap_payment, name='record_ap_payment'),
    path('accounting/budget-variance/', views_accounting_advanced.budget_variance_report, name='budget_variance_report'),
    path('accounting/revenue-report/', views_accounting_advanced.revenue_report, name='revenue_report'),
    path('accounting/expense-report/', views_accounting_advanced.expense_report, name='expense_report'),
    path('accounting/payment-vouchers/', views_accounting_advanced.payment_voucher_list, name='payment_voucher_list'),
    path('accounting/vouchers/mark-paid/', views_accounting_advanced.mark_voucher_paid, name='mark_voucher_paid'),
    path('accounting/vouchers/export-excel/', views_accounting_advanced.export_vouchers_excel, name='export_vouchers_excel'),
    path('accounting/vouchers/export-pdf/', views_accounting_advanced.export_vouchers_pdf, name='export_vouchers_pdf'),
    
    # Payment Voucher and Cheque Management
    path('accounting/pv/setup-accounts/', views_pv_cheque.pv_account_setup, name='pv_account_setup'),
    path('accounting/pv/', views_pv_cheque.pv_list, name='pv_list'),
    path('accounting/pv/create/', views_pv_cheque.pv_create, name='pv_create'),
    path('accounting/pv/<uuid:voucher_id>/', views_pv_cheque.pv_detail, name='pv_detail'),
    path('accounting/pv/<uuid:voucher_id>/approve/', views_pv_cheque.pv_approve, name='pv_approve'),
    path('accounting/pv/<int:voucher_id>/mark-paid/', views_pv_cheque.pv_mark_paid, name='pv_mark_paid'),
    
    # Petty Cash Management
    path('accounting/petty-cash/', views_petty_cash.petty_cash_list, name='petty_cash_list'),
    path('accounting/petty-cash/create/', views_petty_cash.petty_cash_create, name='petty_cash_create'),
    path('accounting/petty-cash/<uuid:transaction_id>/', views_petty_cash.petty_cash_detail, name='petty_cash_detail'),
    path('accounting/petty-cash/<uuid:transaction_id>/submit/', views_petty_cash.petty_cash_submit, name='petty_cash_submit'),
    path('accounting/petty-cash/<uuid:transaction_id>/approve/', views_petty_cash.petty_cash_approve, name='petty_cash_approve'),
    path('accounting/petty-cash/<uuid:transaction_id>/reject/', views_petty_cash.petty_cash_reject, name='petty_cash_reject'),
    path('accounting/petty-cash/<uuid:transaction_id>/mark-paid/', views_petty_cash.petty_cash_mark_paid, name='petty_cash_mark_paid'),
    path('accounting/petty-cash/approvals/', views_petty_cash.petty_cash_approval_list, name='petty_cash_approval_list'),
    path('accounting/cheques/', views_pv_cheque.cheque_list, name='cheque_list'),
    path('accounting/cheques/create/', views_pv_cheque.cheque_create, name='cheque_create'),
    path('accounting/cheques/<uuid:cheque_id>/', views_pv_cheque.cheque_detail, name='cheque_detail'),
    path('accounting/cheques/<uuid:cheque_id>/clear/', views_pv_cheque.cheque_clear, name='cheque_clear'),
    path('accounting/cheques/<uuid:cheque_id>/bounce/', views_pv_cheque.cheque_bounce, name='cheque_bounce'),
    path('accounting/cheques/<uuid:cheque_id>/void/', views_pv_cheque.cheque_void, name='cheque_void'),
    path('accounting/cheques/<uuid:cheque_id>/print/', views_pv_cheque.cheque_print, name='cheque_print'),
    # Handle invalid cheque URLs
    path('accounting/cheques/INVALID/', lambda request: redirect('hospital:cheque_list'), name='cheque_invalid_redirect'),
    re_path(r'^accounting/cheques/(?P<cheque_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/None/?$', lambda request, cheque_id: redirect('hospital:cheque_list'), name='cheque_none_redirect'),
    # Handle invalid PV URLs
    path('accounting/pv/INVALID/', lambda request: redirect('hospital:pv_list'), name='pv_invalid_redirect'),
    re_path(r'^accounting/pv/(?P<voucher_id>[0-9]+)/None/?$', lambda request, voucher_id: redirect('hospital:pv_list'), name='pv_none_redirect'),
    path('accounting/receipt-vouchers/', views_accounting_advanced.receipt_voucher_list, name='receipt_voucher_list'),
    path('accounting/api/stats/', views_accounting_advanced.accounting_api_stats, name='accounting_api_stats'),
    
    # ==================== SENIOR ACCOUNT OFFICER FEATURES ====================
    # Senior Account Officer Dashboard
    path('senior-account-officer/dashboard/', views_senior_account_officer.senior_account_officer_dashboard, name='senior_account_officer_dashboard'),
    path('senior-account-officer/account-staff/', views_senior_account_officer.account_staff_list, name='account_staff_list'),
    path('senior-account-officer/account-staff/<uuid:pk>/', views_senior_account_officer.account_staff_detail, name='account_staff_detail'),
    
    # ==================== PATIENT DEPOSIT SYSTEM ====================
    # Patient Deposits
    path('patient-deposits/', views_patient_deposits.patient_deposit_list, name='patient_deposit_list'),
    path('patient-deposits/record/', views_patient_deposits.record_patient_deposit, name='record_patient_deposit'),
    path('patient-deposits/record/<uuid:patient_id>/', views_patient_deposits.record_patient_deposit, name='record_patient_deposit'),
    path('patient-deposits/<uuid:deposit_id>/', views_patient_deposits.patient_deposit_detail, name='patient_deposit_detail'),
    path('patient-deposits/<uuid:deposit_id>/print/', views_patient_deposits.patient_deposit_print, name='patient_deposit_print'),
    path('patient-deposits/<uuid:deposit_id>/apply/', views_patient_deposits.apply_deposit_manually, name='apply_deposit_manually'),
    path('patient-deposits/<uuid:deposit_id>/refund/', views_patient_deposits.refund_deposit, name='refund_deposit'),
    path('patients/<uuid:patient_id>/deposits/', views_patient_deposits.patient_deposit_history, name='patient_deposit_history'),
    
    # ==================== COMPREHENSIVE ACCOUNTANT FEATURES ====================
    # Comprehensive Accountant Dashboard
    path('accountant/comprehensive-dashboard/', views_accountant_comprehensive.accountant_comprehensive_dashboard, name='accountant_comprehensive_dashboard'),
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
    path('accountant/stock-management-monitoring/', views_accountant_comprehensive.stock_management_monitoring, name='stock_management_monitoring'),
    path('accountant/supplier-accounts/', views_accountant_comprehensive.supplier_accounts_list, name='supplier_accounts_list'),
    path(
        'accountant/supplier-accounts/<uuid:supplier_id>/',
        views_accountant_comprehensive.supplier_account_detail,
        name='supplier_account_detail',
    ),
    
    # Accounting Management Views (HMS Interface for Admin Features)
    # Accounts Receivable
    path('accountant/ar/', views_accounting_management.ar_list, name='ar_list'),
    path('accountant/ar/create/', views_accounting_management.ar_create, name='ar_create'),
    path('accountant/ar/<uuid:ar_id>/', views_accounting_management.ar_detail, name='ar_detail'),
    path('accountant/ar/<uuid:ar_id>/edit/', views_accounting_management.ar_edit, name='ar_edit'),
    
    # Accounts Payable
    path('accountant/ap/', views_accounting_management.ap_list, name='ap_list'),
    path('accountant/ap/create/', views_accounting_management.ap_create, name='ap_create'),
    path('accountant/ap/<uuid:ap_id>/', views_accounting_management.ap_detail, name='ap_detail'),
    path('accountant/ap/<uuid:ap_id>/edit/', views_accounting_management.ap_edit, name='ap_edit'),
    
    # Journal Entries
    path('accountant/journal-entries/', views_accounting_management.journal_entry_list, name='journal_entry_list'),
    path('accountant/journal-entries/create/', views_accounting_management.journal_entry_create, name='journal_entry_create'),
    path('accountant/journal-entries/<uuid:entry_id>/', views_accounting_management.journal_entry_detail, name='journal_entry_detail'),
    path('accountant/journal-entries/<uuid:entry_id>/edit/', views_accounting_management.journal_entry_edit, name='journal_entry_edit'),
    path('accountant/journal-entries/<uuid:entry_id>/post/', views_accounting_management.journal_entry_post, name='journal_entry_post'),
    
    # Revenue
    path('accountant/revenue/', views_accounting_management.revenue_list, name='revenue_list'),
    path('accountant/revenue/create/', views_accounting_management.revenue_create, name='revenue_create'),
    path('accountant/revenue/<uuid:revenue_id>/', views_accounting_management.revenue_detail, name='revenue_detail'),
    path('accountant/revenue/<uuid:revenue_id>/edit/', views_accounting_management.revenue_edit, name='revenue_edit'),
    
    # Expense
    path('accountant/expense/', views_accounting_management.expense_list, name='expense_list'),
    path('accountant/expense/create/', views_accounting_management.expense_create, name='expense_create'),
    path('accountant/expense/<uuid:expense_id>/', views_accounting_management.expense_detail, name='expense_detail'),
    path('accountant/expense/<uuid:expense_id>/edit/', views_accounting_management.expense_edit, name='expense_edit'),
    
    # Receipt Voucher
    path('accountant/receipt-vouchers/', views_accounting_management.receipt_voucher_list, name='receipt_voucher_list'),
    path('accountant/receipt-vouchers/create/', views_accounting_management.receipt_voucher_create, name='receipt_voucher_create'),
    path('accountant/receipt-vouchers/<uuid:voucher_id>/', views_accounting_management.receipt_voucher_detail, name='receipt_voucher_detail'),
    path('accountant/receipt-vouchers/<uuid:voucher_id>/edit/', views_accounting_management.receipt_voucher_edit, name='receipt_voucher_edit'),
    path('accountant/receipt-vouchers/<uuid:voucher_id>/issue/', views_accounting_management.receipt_voucher_issue, name='receipt_voucher_issue'),
    
    # Deposit
    path('accountant/deposits/', views_accounting_management.deposit_list, name='deposit_list'),
    path('accountant/deposits/create/', views_accounting_management.deposit_create, name='deposit_create'),
    path('accountant/deposits/<uuid:deposit_id>/', views_accounting_management.deposit_detail, name='deposit_detail'),
    path('accountant/deposits/<uuid:deposit_id>/edit/', views_accounting_management.deposit_edit, name='deposit_edit'),
    
    # Initial Revaluation
    path('accountant/revaluations/', views_accounting_management.initial_revaluation_list, name='initial_revaluation_list'),
    path('accountant/revaluations/create/', views_accounting_management.initial_revaluation_create, name='initial_revaluation_create'),
    path('accountant/revaluations/<uuid:revaluation_id>/', views_accounting_management.initial_revaluation_detail, name='initial_revaluation_detail'),
    path('accountant/revaluations/<uuid:revaluation_id>/edit/', views_accounting_management.initial_revaluation_edit, name='initial_revaluation_edit'),
    
    # Withholding Receivable
    path('accountant/withholding-receivables/', views_accounting_management.withholding_receivable_list, name='withholding_receivable_list'),
    path('accountant/withholding-receivables/create/', views_accounting_management.withholding_receivable_create, name='withholding_receivable_create'),
    path('accountant/withholding-receivables/<uuid:receivable_id>/', views_accounting_management.withholding_receivable_detail, name='withholding_receivable_detail'),
    path('accountant/withholding-receivables/<uuid:receivable_id>/edit/', views_accounting_management.withholding_receivable_edit, name='withholding_receivable_edit'),
    
    # Bank Account
    path('accountant/bank-accounts/', views_accounting_management.bank_account_list, name='bank_account_list'),
    path('accountant/bank-accounts/create/', views_accounting_management.bank_account_create, name='bank_account_create'),
    path('accountant/bank-accounts/<uuid:bank_id>/', views_accounting_management.bank_account_detail, name='bank_account_detail'),
    path('accountant/bank-accounts/<uuid:bank_id>/edit/', views_accounting_management.bank_account_edit, name='bank_account_edit'),
    
    # Bank Transaction
    path('accountant/bank-transactions/', views_accounting_management.bank_transaction_list, name='bank_transaction_list'),
    path('accountant/bank-transactions/create/', views_accounting_management.bank_transaction_create, name='bank_transaction_create'),
    path('accountant/bank-transactions/<uuid:transaction_id>/', views_accounting_management.bank_transaction_detail, name='bank_transaction_detail'),
    path('accountant/bank-transactions/<uuid:transaction_id>/edit/', views_accounting_management.bank_transaction_edit, name='bank_transaction_edit'),

    # Bank payment vouchers (Bank ↔ Expense entries)
    path('accountant/bank-payments/', views_accounting_management.bank_payment_list, name='bank_payment_list'),
    path('accountant/bank-payments/create/', views_accounting_management.bank_payment_create, name='bank_payment_create'),
    path('accountant/bank-payments/<uuid:entry_id>/', views_accounting_management.bank_payment_detail, name='bank_payment_detail'),
    path('accountant/bank-payments/<uuid:entry_id>/post/', views_accounting_management.bank_payment_post, name='bank_payment_post'),
    path('accountant/bank-payments/<uuid:entry_id>/void/', views_accounting_management.bank_payment_void, name='bank_payment_void'),
    # Handle invalid accountant URLs
    path('accountant/INVALID/', lambda request: redirect('hospital:accountant_comprehensive_dashboard'), name='accountant_invalid_redirect'),
    re_path(r'^accountant/(?P<feature>[a-z-]+)/INVALID/?$', lambda request, feature: redirect('hospital:accountant_comprehensive_dashboard'), name='accountant_feature_invalid_redirect'),
    re_path(r'^accountant/(?P<feature>[a-z-]+)/(?P<id>[0-9a-f-]+)/None/?$', lambda request, feature, id: redirect('hospital:accountant_comprehensive_dashboard'), name='accountant_feature_none_redirect'),
    
    # Cashbook
    path('accountant/cashbook/', views_accountant_comprehensive.cashbook_list, name='cashbook_list'),
    path('accountant/cashbook/<uuid:entry_id>/', views_accountant_comprehensive.cashbook_detail, name='cashbook_detail'),
    path('accountant/cashbook/<uuid:entry_id>/classify/', views_accountant_comprehensive.cashbook_classify, name='cashbook_classify'),
    path('accountant/cashbook/bulk-classify/', views_accountant_comprehensive.cashbook_bulk_classify, name='cashbook_bulk_classify'),
    
    # Bank Reconciliation
    path('accountant/finance-sensitive/confirm-password/', views_accountant_comprehensive.finance_sensitive_confirm_password, name='finance_sensitive_confirm_password'),
    path('accountant/bank-reconciliation/', views_accountant_comprehensive.bank_reconciliation_list, name='bank_reconciliation_list'),
    path('accountant/bank-reconciliation/create/', views_accountant_comprehensive.bank_reconciliation_create, name='bank_reconciliation_create'),
    path('accountant/bank-reconciliation/<uuid:recon_id>/', views_accountant_comprehensive.bank_reconciliation_detail, name='bank_reconciliation_detail'),
    path('accountant/bank-reconciliation/<uuid:recon_id>/edit/', views_accountant_comprehensive.bank_reconciliation_edit, name='bank_reconciliation_edit'),
    
    # Insurance Receivable
    path('accountant/insurance-receivable/', views_accountant_comprehensive.insurance_receivable_list, name='insurance_receivable_list'),
    path('accountant/insurance-receivable/create/', views_accountant_comprehensive.insurance_receivable_create, name='insurance_receivable_create'),
    path('accountant/insurance-receivable/<uuid:receivable_id>/edit/', views_accountant_comprehensive.insurance_receivable_edit, name='insurance_receivable_edit'),

    # Receivables hub routes live in hospital.urls_hms_priority (included first from hms.urls).
    
    # Procurement Purchases
    path('accountant/procurement-purchases/', views_accountant_comprehensive.procurement_purchase_list, name='procurement_purchase_list'),
    path('accountant/procurement-expenses-report/', views_accountant_comprehensive.procurement_expenses_report, name='procurement_expenses_report'),
    
    # Accountant payroll routes live in hospital.urls_accountant_payroll (included first from hms.urls).
    path('accountant/doctor-commissions/', views_accountant_comprehensive.doctor_commission_list, name='doctor_commission_list'),
    
    # Doctor Performance Tracking (Finance)
    path('accountant/doctor-performance/', views_doctor_performance.doctor_performance_dashboard, name='doctor_performance_dashboard'),
    path('accountant/doctor-performance/<uuid:staff_id>/', views_doctor_performance.doctor_performance_detail, name='doctor_performance_detail'),
    path('accountant/doctor-performance/api/', views_doctor_performance.doctor_performance_api, name='doctor_performance_api'),
    
    # Profit & Loss Reports
    path('accountant/profit-loss/', views_accountant_comprehensive.profit_loss_list, name='profit_loss_list'),
    path('accountant/profit-loss/create/', views_accountant_comprehensive.profit_loss_create, name='profit_loss_create'),
    path('accountant/profit-loss/<uuid:report_id>/edit/', views_accountant_comprehensive.profit_loss_edit, name='profit_loss_edit'),
    path('accountant/detailed-financial-report/', views_accountant_comprehensive.detailed_financial_report, name='detailed_financial_report'),
    
    # Registration Fees
    path('accountant/registration-fees/', views_accountant_comprehensive.registration_fee_list, name='registration_fee_list'),
    
    # Cash Sales
    path('accountant/cash-sales/', views_accountant_comprehensive.cash_sale_list, name='cash_sale_list'),
    
    # Corporate Accounts
    path('accountant/corporate-accounts/', views_accountant_comprehensive.corporate_account_list, name='corporate_account_list'),
    
    # Deposits
    path('accountant/deposits/', views_accountant_comprehensive.deposit_list, name='deposit_list'),
    
    # Initial Revaluations
    path('accountant/revaluations/', views_accountant_comprehensive.initial_revaluation_list, name='initial_revaluation_list'),
    
    # Chart of Accounts (Accountant)
    path('accountant/chart-of-accounts/', views_accountant_comprehensive.chart_of_accounts, name='accountant_chart_of_accounts'),
    path('accountant/account/create/', views_accountant_comprehensive.account_create, name='accountant_account_create'),
    path('accountant/account/<uuid:account_id>/', views_accountant_comprehensive.account_detail, name='accountant_account_detail'),
    path('accountant/account/<uuid:account_id>/edit/', views_accountant_comprehensive.account_edit, name='accountant_account_edit'),
    path('accountant/sync-accounts/', views_accountant_comprehensive.sync_accounts, name='sync_accounts'),
    
    # ==================== BILLING & CLAIMS ====================
    # Claims Bills Hub
    path('accountant/billing/claims-hub/', views_billing_claims.claims_bills_hub, name='claims_bills_hub'),
    path('accountant/billing/waiver-audit/', views_waiver_audit.waiver_audit_view, name='waiver_audit'),
    
    # Bills Management
    path('accountant/billing/bills/', views_billing_claims.bills_list, name='bills_list'),
    path('accountant/billing/bills/by-invoice/', views_billing_claims.bills_by_normal_invoice, name='bills_by_normal_invoice'),
    path('accountant/billing/bills/by-invoice-group/', views_billing_claims.bills_by_invoice_group2_cover_page, name='bills_by_invoice_group2_cover_page'),
    path('accountant/billing/bills/summary/', views_billing_claims.bill_summary, name='bill_summary'),
    path('accountant/billing/bills/total/', views_billing_claims.bill_total, name='bill_total'),
    
    # Company/Corporate Bills
    path('accountant/billing/company-bills/', views_billing_claims.company_bill_list, name='company_bill_list'),
    path('accountant/billing/company-bills/<uuid:statement_id>/cover-page/', views_billing_claims.company_bill_with_cover_page, name='company_bill_with_cover_page'),
    path('accountant/billing/company-bills/<uuid:statement_id>/offer/', views_billing_claims.company_bill_with_offer, name='company_bill_with_offer'),
    path('accountant/billing/corporate-bills/', views_billing_claims.corporate_bill_list, name='corporate_bill_list'),
    path('accountant/billing/corporate-bills/payer/<uuid:payer_id>/', views_billing_claims.corporate_bill_detail_by_payer, name='corporate_bill_detail_by_payer'),
    path(
        'accountant/billing/receivable-entry/<uuid:entry_id>/',
        views_billing_claims.receivable_entry_detail,
        name='receivable_entry_detail',
    ),
    path('accountant/billing/corporate-bills/<uuid:statement_id>/subscriber/', views_billing_claims.corporate_bill_with_subscriber, name='corporate_bill_with_subscriber'),
    
    # Insurance Bills
    path('accountant/billing/insurance-bills/', views_billing_claims.insurance_bill_list, name='insurance_bill_list'),
    
    # Medical Bills Statement
    path('accountant/billing/medical-bills/processing/', views_billing_claims.medical_bills_statement_processing, name='medical_bills_statement_processing'),
    path('accountant/billing/medical-bills/report/', views_billing_claims.medical_bills_statement_report, name='medical_bills_statement_report'),
    
    # Staff Dependency Bills
    path('accountant/billing/staff-dep-bills/', views_billing_claims.staff_dep_bill_list, name='staff_dep_bill_list'),
    
    # Revenue/Payment Analysis
    path('accountant/billing/revenue-payment-analysis/', views_billing_claims.revenue_payment_analysis, name='revenue_payment_analysis'),
    
    # Sales Details & Summary
    path('accountant/billing/sales-details-claims/', views_billing_claims.sales_details_claims, name='sales_details_claims'),
    path('accountant/billing/sales-summary-by-company/', views_billing_claims.sales_summary_by_company, name='sales_summary_by_company'),
    
    # Revenue Stream Monitoring
    path('accounting/revenue-streams/', views_revenue_monitoring.revenue_streams_dashboard, name='revenue_streams_dashboard'),
    path('accounting/revenue-by-department/', views_revenue_monitoring.revenue_by_department_report, name='revenue_by_department'),
    path('accounting/api/revenue-streams/', views_revenue_monitoring.revenue_streams_api, name='revenue_streams_api'),
    # Export/print routes registered in urls_hms_priority (prepended to this urlconf).
    
    # Locum Doctor Payment Management (Accountants)
    path('locum/doctors/', views_locum_doctors.locum_doctors_dashboard, name='locum_doctors_dashboard'),
    path('locum/doctors/services/', views_locum_doctors.locum_doctor_services_list, name='locum_doctor_services_list'),
    path('locum/doctors/services/new/', views_locum_doctors.locum_doctor_service_create, name='locum_doctor_service_create'),
    path('locum/doctors/services/<uuid:service_id>/', views_locum_doctors.locum_doctor_service_detail, name='locum_doctor_service_detail'),
    path('locum/doctors/services/<uuid:service_id>/edit/', views_locum_doctors.locum_doctor_service_edit, name='locum_doctor_service_edit'),
    path('locum/doctors/services/doctor/<uuid:doctor_id>/', views_locum_doctors.locum_doctor_services_list, name='locum_doctor_services_by_doctor'),
    path('locum/doctors/doctor/<uuid:doctor_id>/create-batch/', views_locum_doctors.locum_doctor_payment_batch, name='locum_doctor_payment_batch'),
    path('locum/doctors/batch/<uuid:batch_id>/', views_locum_doctors.locum_doctor_payment_batch_detail, name='locum_doctor_payment_batch_detail'),
    
    # Department Budgeting System
    path('budget/', views_budget.budget_dashboard, name='budget_dashboard'),
    path('budget/period/create/', views_budget.create_budget_period, name='create_budget_period'),
    path('budget/period/<uuid:period_id>/allocate/', views_budget.allocate_department_budgets, name='allocate_department_budgets'),
    path('budget/department/<uuid:budget_id>/', views_budget.department_budget_detail, name='department_budget_detail'),
    path('budget/my-department/', views_budget.my_department_budget, name='my_department_budget'),
    path('budget/reports/vs-actual/', views_budget.budget_vs_actual_report, name='budget_vs_actual_report'),
    
    # 📬 Multi-Channel Notification Management
    path('notifications/preferences/<uuid:patient_id>/', views_notifications.notification_preferences, name='notification_preferences'),
    path('notifications/history/<uuid:patient_id>/', views_notifications.notification_history, name='notification_history'),
    path('notifications/test/<uuid:patient_id>/', views_notifications.test_notification, name='test_notification'),
    path('notifications/bulk-settings/', views_notifications.notification_settings_bulk, name='notification_settings_bulk'),
    
    # 💊 Drug Formulary Management
    path('drugs/', views.drug_formulary_list, name='drug_formulary_list'),
    path('drugs/print/', views.drug_formulary_print, name='drug_formulary_print'),
    path('drugs/export/pdf/', views.drug_formulary_pdf, name='drug_formulary_pdf'),
    path('drugs/export/excel/', views.drug_formulary_excel, name='drug_formulary_excel'),
    path('drugs/new/', views.drug_create, name='drug_create'),
    path('drugs/<uuid:pk>/', views.drug_detail, name='drug_detail'),
    path('drugs/<uuid:pk>/audit-trail/', views.drug_audit_trail, name='drug_audit_trail'),
    path('drugs/<uuid:pk>/edit/', views.drug_edit, name='drug_edit'),
    path('drug-classification-guide/', views_drug_guide.drug_classification_guide, name='drug_classification_guide'),
    path('drugs/category/<str:category_code>/', views_drug_guide.drugs_by_category, name='drugs_by_category'),
    path('api/drugs/category/<str:category_code>/', views_drug_guide.api_drugs_by_category, name='api_drugs_by_category'),
    path('api/drug/<uuid:drug_id>/', views_drug_guide.api_drug_detail, name='api_drug_detail'),
    path('api/encounters/search-active/', views_drug_guide.api_search_active_encounters, name='api_search_active_encounters'),
    # Prescription Assistant (Top-Up): Drug classification + AI chat → prescription
    path('prescription-assistant/', views_prescription_assistant.prescription_assistant_view, name='prescription_assistant'),
    path('api/prescription-assistant/chat/', views_prescription_assistant.api_prescription_assistant_chat, name='api_prescription_assistant_chat'),
    path('api/prescription-assistant/dosing/<str:category_code>/', views_prescription_assistant.api_prescription_assistant_dosing, name='api_prescription_assistant_dosing'),
    path('api/prescription-assistant/check-interactions/', views_prescription_assistant.api_prescription_assistant_check_interactions, name='api_prescription_assistant_check_interactions'),
    
    # 🧪 Lab Tests Catalog Management
    path('lab-tests/', views.lab_tests_catalog, name='lab_tests_catalog'),
    path('lab-tests/new/', views.lab_test_create, name='lab_test_create'),
    path('lab-tests/<uuid:pk>/', views.lab_test_detail, name='lab_test_detail'),
    path('lab-tests/<uuid:pk>/edit/', views.lab_test_edit, name='lab_test_edit'),
    path('lab-tests/<uuid:pk>/delete/', views.lab_test_delete, name='lab_test_delete'),
    
    # 📋 Comprehensive Medical History System
    path('patient/<uuid:patient_id>/medical-history/', views_medical_history_comprehensive.patient_medical_history_comprehensive, name='patient_medical_history'),
    path('patient/<uuid:patient_id>/medical-timeline/', views_medical_history_comprehensive.patient_medical_timeline, name='patient_medical_timeline'),
    
    # 🏥 Departments Management
    path('departments/', views.departments_list, name='departments_list'),
    path('departments/new/', views.department_create, name='department_create'),
    path('departments/<uuid:pk>/', views.department_detail, name='department_detail'),
    path('departments/<uuid:pk>/edit/', views.department_edit, name='department_edit'),
    
    # 🛏️ Wards Management
    path('wards/', views.wards_list, name='wards_list'),
    path('wards/new/', views.ward_create, name='ward_create'),
    path('wards/<uuid:pk>/', views.ward_detail, name='ward_detail'),
    path('wards/<uuid:pk>/edit/', views.ward_edit, name='ward_edit'),
    
    # 📋 Medical Records Management
    path('medical-records/', views.medical_records_list, name='medical_records_list'),
    path('medical-records/new/', views.medical_record_create, name='medical_record_create'),
    path('medical-records/<uuid:pk>/', views.medical_record_detail, name='medical_record_detail'),
    
    # 📝 Orders Management
    path('orders/', views.orders_list, name='orders_list'),
    path('orders/new/', views.order_create, name='order_create'),
    path('orders/<uuid:pk>/', views.order_detail, name='order_detail'),
]

# Receivables hub, admin cashier catalogue, etc. — prepended so they share one
# `hospital:` namespace with the rest of this urlconf (avoids duplicate-namespace reverse bugs).
from .urls_hms_priority import urlpatterns as _hms_priority_urlpatterns

urlpatterns = _hms_priority_urlpatterns + urlpatterns


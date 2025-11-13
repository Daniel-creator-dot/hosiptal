"""
URL configuration for hospital app frontend.
"""
from django.urls import path, include
from django.shortcuts import redirect
from . import views
from . import views_advanced
from . import views_workflow
from . import views_cashier
from . import views_accounting
from . import views_hr
from . import views_hr_reports
from . import views_procurement, views_procurement_enhanced
from . import views_procurement_approval
from . import views_hod_scheduling
from . import views_revenue_monitoring
from . import views_reminders
from . import views_sms
from . import views_departments
from . import views_consultation
from . import views_receipt_verification
from . import views_lab_payment_verification
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
from . import views_role_specific
from . import views_telemedicine_enhanced
from . import views_staff_dashboard
from . import views_specialists
from . import views_role_dashboards
from . import views_role_redirect
from . import views_telemedicine
# from . import views_legacy_patients  # DISABLED: Legacy patients removed for performance
from . import views_pricing
from . import views_staff_portal
from . import views_triage
from . import views_admission
from . import views_ambulance
from . import views_appointments
from . import views_appointments_advanced
from . import views_appointment_confirmation
from . import views_payment_verification
from . import views_unified_payments
from . import views_centralized_cashier
from . import views_service_pricing
from . import views_lab_results_enforced
from . import views_pharmacy_dispensing_enforced
# from . import views_pharmacy_walkin  # Temporarily disabled
from . import views_notifications
from . import views_biometric
from . import views_biometric_rebuilt
from . import views_patient_export
from . import views_backup
from . import views_accounting_advanced
from . import views_budget
app_name = 'hospital'

urlpatterns = [
    # Biometric Authentication System (Original)
    path('biometric/', include('hospital.urls_biometric', namespace='biometric')),
    
    # World-Class Biometric System (Rebuilt)
    path('bio/login/', views_biometric_rebuilt.biometric_login_page, name='biometric_login_page_rebuilt'),
    path('bio/authenticate/', views_biometric_rebuilt.authenticate_biometric, name='authenticate_biometric_rebuilt'),
    path('bio/enrollment/', views_biometric_rebuilt.enrollment_hub, name='biometric_enrollment_rebuilt'),
    path('bio/enroll/', views_biometric_rebuilt.enroll_biometric, name='enroll_biometric_rebuilt'),
    path('bio/my-profile/', views_biometric_rebuilt.my_biometric_profile, name='biometric_my_profile'),
    path('bio/delete/<uuid:biometric_id>/', views_biometric_rebuilt.delete_biometric, name='delete_biometric'),
    path('bio/detect-devices/', views_biometric_rebuilt.detect_devices, name='detect_biometric_devices'),
    
    # Frontend views - Role-based routing
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Role-Specific Dashboards
    path('accountant-dashboard/', views_role_specific.accountant_dashboard, name='accountant_dashboard'),
    path('admin-dashboard/', views_role_specific.admin_dashboard, name='admin_dashboard'),
    path('medical-dashboard/', views_role_specific.medical_dashboard, name='medical_dashboard'),
    path('reception-dashboard/', views_role_specific.reception_dashboard, name='reception_dashboard'),
    path('stats/', views.api_stats, name='api_stats'),
    path('api/dashboard-stats/', views.api_stats, name='api_dashboard_stats'),
    
    # Patient views
    path('patients/', views.patient_list, name='patient_list'),
    path('patients/new/', views.patient_create, name='patient_create'),
    path('patients/<uuid:pk>/', views.patient_detail, name='patient_detail'),
    path('patients/<uuid:pk>/edit/', views.patient_edit, name='patient_edit'),
    path('patients/<uuid:patient_pk>/quick-visit/', views.patient_quick_visit_create, name='patient_quick_visit_create'),
    
    # Patient export
    path('patients/export/csv/', views_patient_export.export_patients_csv, name='export_patients_csv'),
    path('patients/export/excel/', views_patient_export.export_patients_excel, name='export_patients_excel'),
    path('patients/export/pdf/', views_patient_export.export_patients_pdf, name='export_patients_pdf'),
    
    # Encounter views
    path('encounters/', views.encounter_list, name='encounter_list'),
    path('encounters/new/', views.encounter_create, name='encounter_create'),
    path('encounters/<uuid:pk>/', views.encounter_detail, name='encounter_detail'),
    path('encounters/<uuid:encounter_id>/surgery-control/', views.surgery_control, name='surgery_control'),
    
    # Admission views
    path('admissions/', views_admission.admission_list_enhanced, name='admission_list'),
    path('admissions/list/', views_admission.admission_list_enhanced, name='admission_list_enhanced'),  # Alias for backward compatibility
    path('admissions/old/', views.admission_list, name='admission_list_old'),
    path('admissions/create/', views_admission.admission_create_enhanced, name='admission_create'),
    path('admissions/<uuid:pk>/', views_admission.admission_detail, name='admission_detail'),
    path('admissions/<uuid:admission_id>/discharge/', views_admission.discharge_patient, name='discharge_patient'),
    
    # Invoice views
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/<uuid:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<uuid:pk>/print/', views.invoice_print, name='invoice_print'),
    
    # Bed Management (World-Class)
    path('beds/', views_admission.bed_management_worldclass, name='bed_availability'),
    path('beds/management/', views_admission.bed_management_worldclass, name='bed_management_worldclass'),
    path('api/bed/<uuid:bed_id>/details/', views_admission.bed_details_api, name='bed_details_api'),
    
    # Reports
    path('reports/daily/', views.daily_report, name='daily_report'),
    path('reports/financial/', views.financial_report_view, name='financial_report'),
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
    path('pharmacy/stock/', views_departments.pharmacy_stock_list, name='pharmacy_stock_list'),
    path('pharmacy/requests/', views_procurement.procurement_requests_list, name='pharmacy_requests_list'),
    path('pharmacy/requests/new/', views_procurement.procurement_request_create, name='pharmacy_request_create'),
    path('api/pharmacy/order/<uuid:order_id>/prescriptions/', views_departments.get_pharmacy_order_prescriptions, name='get_pharmacy_order_prescriptions'),
    path('api/pharmacy/order/<uuid:order_id>/payment-status/', views_departments.check_pharmacy_order_payment_status, name='check_pharmacy_order_payment_status'),
    path('api/pharmacy/order/<uuid:order_id>/dispense/', views_departments.dispense_pharmacy_order, name='dispense_pharmacy_order'),
    
    # 🔒 Pharmacy Dispensing - Payment Enforced (NEW)
    path('pharmacy/pending-dispensing/', views_pharmacy_dispensing_enforced.pharmacy_pending_dispensing, name='pharmacy_pending_dispensing'),
    path('pharmacy/dispense/<uuid:prescription_id>/', views_pharmacy_dispensing_enforced.pharmacy_dispense_enforced, name='pharmacy_dispense_enforced'),
    path('api/pharmacy/payment-check/<uuid:prescription_id>/', views_pharmacy_dispensing_enforced.check_pharmacy_payment_required, name='check_pharmacy_payment_required'),
    
    # 💊 Walk-in Pharmacy Sales (Direct OTC Sales) - TEMPORARILY DISABLED
    # Uncomment after running migrations for walk-in pharmacy models
    # path('pharmacy/walkin-sales/', views_pharmacy_walkin.pharmacy_walkin_sales_list, name='pharmacy_walkin_sales_list'),
    # path('pharmacy/walkin-sales/new/', views_pharmacy_walkin.pharmacy_walkin_sale_create, name='pharmacy_walkin_sale_create'),
    # path('pharmacy/walkin-sales/<uuid:sale_id>/', views_pharmacy_walkin.pharmacy_walkin_sale_detail, name='pharmacy_walkin_sale_detail'),
    # path('pharmacy/walkin-sales/<uuid:sale_id>/dispense/', views_pharmacy_walkin.pharmacy_walkin_dispense, name='pharmacy_walkin_dispense'),
    # path('pharmacy/walkin-sales/<uuid:sale_id>/payment/', views_pharmacy_walkin.pharmacy_walkin_record_payment, name='pharmacy_walkin_record_payment'),
    # path('api/pharmacy/search-drugs/', views_pharmacy_walkin.api_search_drugs, name='api_search_drugs'),
    # path('api/pharmacy/search-patients/', views_pharmacy_walkin.api_patient_search, name='api_patient_search'),
    
    path('laboratory/', views_departments.laboratory_dashboard, name='laboratory_dashboard'),
    path('laboratory/results/', views_departments.lab_results_list, name='lab_results_list'),
    path('laboratory/result/<uuid:result_id>/edit/', views_departments.edit_lab_result, name='edit_lab_result'),
    path('laboratory/result/<uuid:result_id>/tabular/', views.tabular_lab_report, name='tabular_lab_report'),
    
    # 🔒 Lab Results - Payment Enforced (NEW)
    path('laboratory/pending-release/', views_lab_results_enforced.lab_results_pending_release, name='lab_results_pending_release'),
    path('laboratory/release/<uuid:lab_result_id>/', views_lab_results_enforced.lab_result_release_enforced, name='lab_result_release_enforced'),
    path('api/lab/payment-check/<uuid:lab_result_id>/', views_lab_results_enforced.check_lab_payment_required, name='check_lab_payment_required'),
    path('imaging/', views_departments.imaging_dashboard, name='imaging_dashboard'),
    path('imaging/study/<uuid:study_id>/', views_departments.imaging_study_detail, name='imaging_study_detail'),
    path('imaging/study/<uuid:study_id>/upload/', views_departments.upload_imaging_image, name='upload_imaging_image'),
    path('imaging/upload-multiple/', views_departments.upload_multiple_imaging_images, name='upload_multiple_imaging_images'),
    path('imaging/create-study/', views_departments.create_imaging_study, name='create_imaging_study'),
    path('imaging/study/<uuid:study_id>/edit-report/', views_departments.edit_imaging_report, name='edit_imaging_report'),
    path('imaging/study/<uuid:study_id>/verify-report/', views_departments.verify_imaging_report, name='verify_imaging_report'),
    path('api/imaging-study/<uuid:study_id>/images/', views_departments.get_imaging_study_images, name='get_imaging_study_images'),
    
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
    path('consultation/patient/<uuid:patient_id>/start/', views_consultation.quick_consultation, name='quick_consultation'),
    
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
    
    # World-Class HR Management
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
    path('hr/activities/<uuid:activity_id>/', views_hr_calendar.activity_detail, name='activity_detail'),
    path('hr/recognition-board/', views_hr_calendar.staff_recognition_board, name='recognition_board'),
    path('hr/recruitment/', views_hr_calendar.recruitment_pipeline, name='recruitment_pipeline'),
    path('hr/wellness/', views_hr_calendar.wellness_dashboard, name='wellness_dashboard'),
    path('hr/surveys/', views_hr_calendar.survey_dashboard, name='survey_dashboard'),
    
    # Legacy URL redirects (for cached links)
    path('lab/', lambda request: redirect('/hms/laboratory/'), name='lab_redirect'),
    
    # 🔒 Lab Payment Verification System
    path('lab/payment-verification/', views_lab_payment_verification.lab_payment_verification_dashboard, name='lab_payment_verification_dashboard'),
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
    path('queues/<uuid:queue_id>/<str:action>/', views_advanced.queue_action, name='queue_action'),
    path('queues/call-next/', views_advanced.queue_call_next, name='queue_call_next'),
    path('api/queues/data/', views_advanced.queue_data_api, name='queue_data_api'),
    path('triage/', views_advanced.triage_queue, name='triage_queue'),
    
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
    
    # Cashier Module (Original)
    path('cashier/', views_cashier.cashier_dashboard, name='cashier_dashboard'),
    
    # 💰 Centralized Cashier System (All payments through here)
    path('cashier/central/', views_centralized_cashier.centralized_cashier_dashboard, name='centralized_cashier_dashboard'),
    path('cashier/central/all-pending/', views_centralized_cashier.cashier_all_pending_bills, name='cashier_all_pending_bills'),
    path('cashier/central/patient-bills/', views_centralized_cashier.cashier_patient_bills, name='cashier_patient_bills'),
    path('cashier/central/process/<str:service_type>/<uuid:service_id>/', views_centralized_cashier.cashier_process_service_payment, name='cashier_process_service_payment'),
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
    path('cashier/receipt/<uuid:receipt_id>/', views_cashier.payment_receipt, name='payment_receipt'),
    path('cashier/session/<uuid:session_id>/close/', views_cashier.close_session, name='close_session'),
    path('cashier/bills/', views_cashier.cashier_bills, name='cashier_bills'),
    path('cashier/invoices/', views_cashier.cashier_invoices, name='cashier_invoices'),
    path('cashier/invoices/<uuid:pk>/', views_cashier.cashier_invoice_detail, name='cashier_invoice_detail'),
    path('cashier/debt/', views_cashier.customer_debt, name='customer_debt'),
    path('cashier/patient/<uuid:patient_id>/invoices/', views_cashier.patient_invoices, name='cashier_patient_invoices'),
    
    # Accounting Module (OLD - commented out, using advanced accounting instead)
    # path('accounting/', views_accounting.accounting_dashboard, name='accounting_dashboard'),
    path('accounting/ar/', views_accounting.accounts_receivable, name='accounts_receivable_old'),
    path('accounting/ledger/', views_accounting.general_ledger, name='general_ledger_old'),
    # path('accounting/trial-balance/', views_accounting.trial_balance, name='trial_balance'),  # OLD - Using advanced version
    path('accounting/financial-statement/', views_accounting.financial_statement, name='financial_statement_old'),
    
    # HOD Scheduling & Timetable Management
    path('hod/scheduling/', views_hod_scheduling.hod_scheduling_dashboard, name='hod_scheduling_dashboard'),
    path('hod/timetable/create/', views_hod_scheduling.hod_create_timetable_simple, name='hod_create_timetable'),
    path('hod/shift/create/', views_hod_scheduling.hod_create_shift, name='hod_create_shift'),
    path('hod/shifts/bulk-assign/', views_hod_scheduling.hod_bulk_assign_shifts, name='hod_bulk_assign_shifts'),
    path('hod/roster/upload/', views_hod_scheduling.hod_upload_roster, name='hod_upload_roster'),
    path('staff/my-schedule/', views_hod_scheduling.staff_dashboard_with_schedule, name='staff_schedule_dashboard'),
    
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
    path('hr/leaves/', views_hr.leave_request_list, name='leave_request_list'),
    path('hr/leaves/new/', views_hr.leave_request_create, name='leave_request_create'),
    path('hr/leaves/<uuid:pk>/approve/', views_hr.leave_request_approve, name='leave_request_approve'),
    
    # HR Reports Module
    path('hr/reports/', views_hr_reports.hr_reports_dashboard, name='hr_reports_dashboard'),
    path('hr/reports/staff/', views_hr_reports.staff_list_report, name='staff_list_report'),
    path('hr/reports/leave/', views_hr_reports.leave_report, name='leave_report'),
    path('hr/reports/attendance/', views_hr_reports.attendance_report, name='attendance_report'),
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
    path('procurement/reports/low-stock/', views_procurement.low_stock_report, name='low_stock_report'),
    path('procurement/suppliers/', views_procurement.suppliers_list, name='suppliers_list'),
    path('procurement/suppliers/new/', views_procurement.supplier_create, name='supplier_create'),
    path('procurement/suppliers/<uuid:pk>/edit/', views_procurement.supplier_edit, name='supplier_edit'),
    path('procurement/inventory/', views_procurement.inventory_management, name='inventory_management'),
    path('procurement/stores/new/', views_procurement.store_create, name='store_create'),
    path('procurement/stores/<uuid:pk>/edit/', views_procurement.store_edit, name='store_edit'),
    path('procurement/inventory-items/new/', views_procurement.inventory_item_create, name='inventory_item_create'),
    path('procurement/inventory-items/<uuid:pk>/edit/', views_procurement.inventory_item_edit, name='inventory_item_edit'),
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
    path('procurement/accounts/<uuid:pr_id>/approve/', views_procurement_approval.approve_accounts, name='approve_accounts'),
    path('procurement/accounts/<uuid:pr_id>/reject/', views_procurement_approval.reject_accounts, name='reject_accounts'),
    
    # API
    path('procurement/api/stats/', views_procurement_approval.procurement_stats_api, name='procurement_stats_api'),
    
    # ==================== WORLD-CLASS INVENTORY MANAGEMENT SYSTEM ====================
    # State-of-the-art supply chain management with complete accountability
    path('inventory/', include('hospital.urls_inventory')),
    
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
    path('specialists/dentist/dashboard/', views_specialists.dentist_dashboard, name='dentist_dashboard'),
    path('specialists/dental/patient/<uuid:patient_id>/', views_specialists.dental_consultation, name='dental_consultation'),
    path('specialists/dental/encounter/<uuid:encounter_id>/', views_specialists.dental_consultation, name='dental_consultation_encounter'),
    path('specialists/cardiology/patient/<uuid:patient_id>/', views_specialists.cardiology_consultation, name='cardiology_consultation'),
    path('specialists/cardiology/encounter/<uuid:encounter_id>/', views_specialists.cardiology_consultation, name='cardiology_consultation_encounter'),
    path('specialists/ophthalmology/patient/<uuid:patient_id>/', views_specialists.ophthalmology_consultation, name='ophthalmology_consultation'),
    path('specialists/ophthalmology/encounter/<uuid:encounter_id>/', views_specialists.ophthalmology_consultation, name='ophthalmology_consultation_encounter'),
    
    
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
    path('dashboard/nurse/', views_role_dashboards.nurse_dashboard, name='nurse_dashboard'),
    path('dashboard/lab/', views_role_dashboards.lab_technician_dashboard, name='lab_technician_dashboard'),
    path('dashboard/pharmacy/', views_role_dashboards.pharmacist_dashboard, name='pharmacist_dashboard'),
    path('dashboard/radiology/', views_role_dashboards.radiologist_dashboard, name='radiologist_dashboard'),
    path('dashboard/reception/', views_role_dashboards.receptionist_dashboard, name='receptionist_dashboard'),
    path('dashboard/cashier-role/', views_role_dashboards.cashier_dashboard_role, name='cashier_dashboard_role'),
    path('dashboard/admin/', views_role_dashboards.admin_dashboard_role, name='admin_dashboard_role'),
    
    # Legacy Patient Management - DISABLED FOR PERFORMANCE
    # path('legacy-patients/', views_legacy_patients.legacy_patient_list, name='legacy_patient_list'),
    # path('legacy-patients/<int:pid>/', views_legacy_patients.legacy_patient_detail, name='legacy_patient_detail'),
    # path('legacy-patients/<int:pid>/migrate/', views_legacy_patients.migrate_legacy_patient, name='migrate_legacy_patient'),
    # path('migration/dashboard/', views_legacy_patients.migration_dashboard, name='migration_dashboard'),
    # path('migration/bulk-migrate/', views_legacy_patients.bulk_migrate_patients, name='bulk_migrate_patients'),
    
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
    
    # Staff Self-Service Portal
    path('staff/portal/', views_staff_portal.staff_dashboard, name='staff_portal_dashboard'),
    path('staff/profile/', views_staff_portal.staff_profile, name='staff_profile'),
    
    # Staff Leave Management (Self-Service)
    path('staff/leave/', views_staff_portal.staff_leave_list, name='staff_leave_list'),
    path('staff/leave/create/', views_staff_portal.staff_leave_request_create, name='staff_leave_request_create'),
    path('staff/leave/<uuid:pk>/', views_staff_portal.staff_leave_detail, name='staff_leave_detail'),
    path('staff/leave/<uuid:pk>/submit/', views_staff_portal.staff_leave_submit, name='staff_leave_submit'),
    path('staff/leave/<uuid:pk>/cancel/', views_staff_portal.staff_leave_cancel, name='staff_leave_cancel'),
    
    # Staff Training & Performance (Self-Service)
    path('staff/training/', views_staff_portal.staff_training_history, name='staff_training_history'),
    path('staff/performance/', views_staff_portal.staff_performance_reviews, name='staff_performance_reviews'),
    
    # Manager/Admin Leave Approval
    path('hr/leave/approvals/', views_hr.leave_approval_list, name='leave_approval_list'),
    path('hr/leave/<uuid:pk>/approve/', views_hr.leave_approve, name='leave_approve'),
    path('hr/leave/<uuid:pk>/reject/', views_hr.leave_reject, name='leave_reject'),
    path('hr/leave/create-for-staff/', views_hr.create_leave_for_staff, name='create_leave_for_staff'),
    
    # Lab Report Printing & Hospital Settings
    path('laboratory/result/<uuid:result_id>/print/', views.print_lab_report, name='print_lab_report'),
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
    path('accounting/profit-loss/', views_accounting_advanced.profit_loss_statement, name='profit_loss_statement'),
    path('accounting/balance-sheet/', views_accounting_advanced.balance_sheet, name='balance_sheet'),
    path('accounting/trial-balance/', views_accounting_advanced.trial_balance, name='trial_balance'),
    path('accounting/cash-flow/', views_accounting_advanced.cash_flow_statement, name='cash_flow_statement'),
    path('accounting/general-ledger/', views_accounting_advanced.general_ledger_report, name='general_ledger_report'),
    path('accounting/ar-aging/', views_accounting_advanced.accounts_receivable_aging, name='ar_aging_report'),
    path('accounting/ar-test/', views_accounting_advanced.ar_aging_test, name='ar_aging_test'),  # DEBUG test
    path('accounting/ap-report/', views_accounting_advanced.accounts_payable_report, name='ap_report'),
    path('accounting/budget-variance/', views_accounting_advanced.budget_variance_report, name='budget_variance_report'),
    path('accounting/revenue-report/', views_accounting_advanced.revenue_report, name='revenue_report'),
    path('accounting/expense-report/', views_accounting_advanced.expense_report, name='expense_report'),
    path('accounting/payment-vouchers/', views_accounting_advanced.payment_voucher_list, name='payment_voucher_list'),
    path('accounting/vouchers/mark-paid/', views_accounting_advanced.mark_voucher_paid, name='mark_voucher_paid'),
    path('accounting/vouchers/export-excel/', views_accounting_advanced.export_vouchers_excel, name='export_vouchers_excel'),
    path('accounting/vouchers/export-pdf/', views_accounting_advanced.export_vouchers_pdf, name='export_vouchers_pdf'),
    path('accounting/receipt-vouchers/', views_accounting_advanced.receipt_voucher_list, name='receipt_voucher_list'),
    path('accounting/api/stats/', views_accounting_advanced.accounting_api_stats, name='accounting_api_stats'),
    
    # Revenue Stream Monitoring
    path('accounting/revenue-streams/', views_revenue_monitoring.revenue_streams_dashboard, name='revenue_streams_dashboard'),
    path('accounting/revenue-by-department/', views_revenue_monitoring.revenue_by_department_report, name='revenue_by_department'),
    path('accounting/api/revenue-streams/', views_revenue_monitoring.revenue_streams_api, name='revenue_streams_api'),
    
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
    path('drugs/new/', views.drug_create, name='drug_create'),
    path('drugs/<uuid:pk>/', views.drug_detail, name='drug_detail'),
    path('drugs/<uuid:pk>/edit/', views.drug_edit, name='drug_edit'),
    
    # 🧪 Lab Tests Catalog Management
    path('lab-tests/', views.lab_tests_catalog, name='lab_tests_catalog'),
    path('lab-tests/new/', views.lab_test_create, name='lab_test_create'),
    path('lab-tests/<uuid:pk>/', views.lab_test_detail, name='lab_test_detail'),
    path('lab-tests/<uuid:pk>/edit/', views.lab_test_edit, name='lab_test_edit'),
    
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


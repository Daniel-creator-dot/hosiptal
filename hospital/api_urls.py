"""
REST API URL configuration for hospital app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import (
    PatientViewSet, EncounterViewSet, VitalSignViewSet,
    DepartmentViewSet, StaffViewSet, WardViewSet, BedViewSet,
    AdmissionViewSet, OrderViewSet, LabTestViewSet, LabResultViewSet,
    DrugViewSet, PharmacyStockViewSet, PrescriptionViewSet,
    PayerViewSet, ServiceCodeViewSet, PriceBookViewSet,
    InvoiceViewSet, InvoiceLineViewSet,
    AppointmentViewSet, MedicalRecordViewSet, NotificationViewSet
)

# Create a router and register our viewsets for REST API
router = DefaultRouter()
router.register(r'patients', PatientViewSet, basename='patient')
router.register(r'encounters', EncounterViewSet, basename='encounter')
router.register(r'vitals', VitalSignViewSet, basename='vitalsign')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'staff', StaffViewSet, basename='staff')
router.register(r'wards', WardViewSet, basename='ward')
router.register(r'beds', BedViewSet, basename='bed')
router.register(r'admissions', AdmissionViewSet, basename='admission')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'lab-tests', LabTestViewSet, basename='labtest')
router.register(r'lab-results', LabResultViewSet, basename='labresult')
router.register(r'drugs', DrugViewSet, basename='drug')
router.register(r'pharmacy-stock', PharmacyStockViewSet, basename='pharmacystock')
router.register(r'prescriptions', PrescriptionViewSet, basename='prescription')
router.register(r'payers', PayerViewSet, basename='payer')
router.register(r'service-codes', ServiceCodeViewSet, basename='servicecode')
router.register(r'price-books', PriceBookViewSet, basename='pricebook')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'invoice-lines', InvoiceLineViewSet, basename='invoiceline')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'medical-records', MedicalRecordViewSet, basename='medicalrecord')
router.register(r'notifications', NotificationViewSet, basename='notification')

# Register advanced viewsets
try:
    from .viewsets_advanced import (
        ClinicalNoteViewSet, CarePlanViewSet, ProblemListViewSet,
        ProviderScheduleViewSet, QueueViewSet, TriageViewSet,
        ImagingStudyViewSet, TheatreScheduleViewSet, SurgicalChecklistViewSet,
        AnaesthesiaRecordViewSet, MedicationAdministrationRecordViewSet,
        HandoverSheetViewSet, FallRiskAssessmentViewSet,
        PressureUlcerRiskAssessmentViewSet, CrashCartCheckViewSet, MaintenanceLogViewSet,
        IncidentLogViewSet, MedicalEquipmentViewSet, MaintenanceLogViewSet,
        ConsumablesInventoryViewSet, DutyRosterViewSet, LeaveRequestViewSet,
        AttendanceViewSet, InsurancePreAuthorizationViewSet,
        ClaimsBatchViewSet, ChargeCaptureViewSet, LabTestPanelViewSet,
        SampleCollectionViewSet, SMSLogViewSet
    )
    
    # Clinical
    router.register(r'clinical-notes', ClinicalNoteViewSet, basename='clinicalnote')
    router.register(r'care-plans', CarePlanViewSet, basename='careplan')
    router.register(r'problem-list', ProblemListViewSet, basename='problemlist')
    
    # Scheduling
    router.register(r'provider-schedules', ProviderScheduleViewSet, basename='providerschedule')
    router.register(r'queues', QueueViewSet, basename='queue')
    router.register(r'triage', TriageViewSet, basename='triage')
    
    # Imaging
    router.register(r'imaging-studies', ImagingStudyViewSet, basename='imagingstudy')
    
    # Theatre
    router.register(r'theatre-schedules', TheatreScheduleViewSet, basename='theatreschedule')
    router.register(r'surgical-checklists', SurgicalChecklistViewSet, basename='surgicalchecklist')
    router.register(r'anaesthesia-records', AnaesthesiaRecordViewSet, basename='anaesthesiarecord')
    
    # Nursing
    router.register(r'mar', MedicationAdministrationRecordViewSet, basename='medicationadministrationrecord')
    router.register(r'handover-sheets', HandoverSheetViewSet, basename='handoversheet')
    
    # ER
    router.register(r'incidents', IncidentLogViewSet, basename='incidentlog')
    router.register(r'crash-cart-checks', CrashCartCheckViewSet, basename='crashcartcheck')
    
    # Risk Assessments
    router.register(r'fall-risk-assessments', FallRiskAssessmentViewSet, basename='fallriskassessment')
    router.register(r'pressure-ulcer-assessments', PressureUlcerRiskAssessmentViewSet, basename='pressureulcerriskassessment')
    
    # Materials
    router.register(r'medical-equipment', MedicalEquipmentViewSet, basename='medicalequipment')
    router.register(r'maintenance-logs', MaintenanceLogViewSet, basename='maintenancelog')
    router.register(r'consumables', ConsumablesInventoryViewSet, basename='consumablesinventory')
    
    # HR
    router.register(r'duty-rosters', DutyRosterViewSet, basename='dutyroster')
    router.register(r'leave-requests', LeaveRequestViewSet, basename='leaverequest')
    router.register(r'attendance', AttendanceViewSet, basename='attendance')
    
    # Enhanced Billing
    router.register(r'pre-authorizations', InsurancePreAuthorizationViewSet, basename='insurancepreauthorization')
    router.register(r'claims-batches', ClaimsBatchViewSet, basename='claimsbatch')
    router.register(r'charge-capture', ChargeCaptureViewSet, basename='chargecapture')
    
    # Lab
    router.register(r'lab-panels', LabTestPanelViewSet, basename='labtestpanel')
    router.register(r'samples', SampleCollectionViewSet, basename='samplecollection')
    
    # SMS
    router.register(r'sms-logs', SMSLogViewSet, basename='smslog')
except ImportError:
    pass

# Auto-save endpoints
from .views_autosave import AutoSaveView, sync_check_view, bulk_auto_save_view
# Dashboard live updates
from .views_dashboard_updates import dashboard_updates_view

urlpatterns = [
    path('', include(router.urls)),
    # Auto-save endpoints
    path('auto-save/', AutoSaveView.as_view(), name='api_autosave'),
    path('sync-check/', sync_check_view, name='api_sync_check'),
    path('bulk-auto-save/', bulk_auto_save_view, name='api_bulk_autosave'),
    # Dashboard live updates
    path('dashboard-updates/', dashboard_updates_view, name='api_dashboard_updates'),
]


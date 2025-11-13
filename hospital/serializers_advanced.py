"""
Serializers for advanced HMS models
"""
from rest_framework import serializers
from .models_advanced import (
    ClinicalNote, CarePlan, ProblemList, ProviderSchedule, Queue, Triage,
    ImagingStudy, TheatreSchedule, SurgicalChecklist, AnaesthesiaRecord,
    MedicationAdministrationRecord, HandoverSheet, FallRiskAssessment,
    PressureUlcerRiskAssessment, CrashCartCheck, IncidentLog,
    MedicalEquipment, MaintenanceLog, ConsumablesInventory,
    DutyRoster, LeaveRequest, Attendance,
    InsurancePreAuthorization, ClaimsBatch, ChargeCapture,
    LabTestPanel, SampleCollection, SMSLog
)
from .models import Patient, Encounter, Staff, Department, Order


class ClinicalNoteSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='encounter.patient.full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = ClinicalNote
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class CarePlanSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = CarePlan
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class ProblemListSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    
    class Meta:
        model = ProblemList
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class ProviderScheduleSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider.user.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = ProviderSchedule
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class QueueSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='encounter.patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='encounter.patient.mrn', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Queue
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'checked_in_at']


class TriageSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='encounter.patient.full_name', read_only=True)
    triaged_by_name = serializers.CharField(source='triaged_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = Triage
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'triage_time']


class ImagingStudySerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.mrn', read_only=True)
    
    class Meta:
        model = ImagingStudy
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class TheatreScheduleSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    surgeon_name = serializers.CharField(source='surgeon.user.get_full_name', read_only=True)
    
    class Meta:
        model = TheatreSchedule
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class SurgicalChecklistSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='theatre_schedule.patient.full_name', read_only=True)
    completed_by_name = serializers.CharField(source='completed_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = SurgicalChecklist
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class AnaesthesiaRecordSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='theatre_schedule.patient.full_name', read_only=True)
    anaesthetist_name = serializers.CharField(source='anaesthetist.user.get_full_name', read_only=True)
    
    class Meta:
        model = AnaesthesiaRecord
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class MedicationAdministrationRecordSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    administered_by_name = serializers.CharField(source='administered_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = MedicationAdministrationRecord
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class HandoverSheetSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.user.get_full_name', read_only=True)
    ward_name = serializers.CharField(source='ward.name', read_only=True)
    
    class Meta:
        model = HandoverSheet
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class FallRiskAssessmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    assessed_by_name = serializers.CharField(source='assessed_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = FallRiskAssessment
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'assessment_date']


class PressureUlcerRiskAssessmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    assessed_by_name = serializers.CharField(source='assessed_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = PressureUlcerRiskAssessment
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'assessment_date']


class CrashCartCheckSerializer(serializers.ModelSerializer):
    checked_by_name = serializers.CharField(source='checked_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = CrashCartCheck
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'check_date']


class IncidentLogSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    reported_by_name = serializers.CharField(source='reported_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = IncidentLog
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'incident_date']


class MedicalEquipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalEquipment
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class MaintenanceLogSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    technician_name = serializers.CharField(source='technician.user.get_full_name', read_only=True)
    
    class Meta:
        model = MaintenanceLog
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class ConsumablesInventorySerializer(serializers.ModelSerializer):
    is_low_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = ConsumablesInventory
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class DutyRosterSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.user.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = DutyRoster
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class LeaveRequestSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.user.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class AttendanceSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.user.get_full_name', read_only=True)
    
    class Meta:
        model = Attendance
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class InsurancePreAuthorizationSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    payer_name = serializers.CharField(source='payer.name', read_only=True)
    
    class Meta:
        model = InsurancePreAuthorization
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'requested_date']


class ClaimsBatchSerializer(serializers.ModelSerializer):
    payer_name = serializers.CharField(source='payer.name', read_only=True)
    
    class Meta:
        model = ClaimsBatch
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class ChargeCaptureSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='encounter.patient.full_name', read_only=True)
    service_name = serializers.CharField(source='service_code.description', read_only=True)
    charged_by_name = serializers.CharField(source='charged_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = ChargeCapture
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class LabTestPanelSerializer(serializers.ModelSerializer):
    test_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = LabTestPanel
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class SampleCollectionSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.mrn', read_only=True)
    collected_by_name = serializers.CharField(source='collected_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = SampleCollection
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class SMSLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SMSLog
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'sent_at', 'provider_response']


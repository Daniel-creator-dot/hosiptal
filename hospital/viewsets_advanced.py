"""
Advanced REST API ViewSets for Hospital Management System.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters as rest_filters
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, Avg
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


# ==================== CLINICAL VIEWSETS ====================

class ClinicalNoteViewSet(viewsets.ModelViewSet):
    """ViewSet for Clinical Notes"""
    queryset = ClinicalNote.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['note_type', 'encounter', 'created_by']
    search_fields = ['notes', 'subjective', 'objective', 'assessment', 'plan']
    ordering_fields = ['created']
    ordering = ['-created']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'encounter__patient',
            'encounter__provider',
            'encounter__location',
            'created_by__user',
            'created_by__department',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import ClinicalNoteSerializer
        return ClinicalNoteSerializer


class CarePlanViewSet(viewsets.ModelViewSet):
    """ViewSet for Care Plans"""
    queryset = CarePlan.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['status', 'patient']
    search_fields = ['diagnosis', 'goals', 'interventions']
    ordering_fields = ['created', 'start_date']
    ordering = ['-created']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'patient',
            'encounter',
            'created_by__user',
            'created_by__department',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import CarePlanSerializer
        return CarePlanSerializer


class ProblemListViewSet(viewsets.ModelViewSet):
    """ViewSet for Problem List"""
    queryset = ProblemList.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['status', 'patient']
    search_fields = ['problem', 'icd10_code', 'description']
    ordering_fields = ['created']
    ordering = ['-created']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'patient',
            'encounter',
            'created_by__user',
            'created_by__department',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import ProblemListSerializer
        return ProblemListSerializer


# ==================== SCHEDULING VIEWSETS ====================

class ProviderScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for Provider Schedules"""
    queryset = ProviderSchedule.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['provider', 'department', 'date', 'is_available']
    ordering_fields = ['date', 'start_time']
    ordering = ['date', 'start_time']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'provider__user',
            'provider__department',
            'department',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import ProviderScheduleSerializer
        return ProviderScheduleSerializer


class QueueViewSet(viewsets.ModelViewSet):
    """ViewSet for Queue Management"""
    queryset = Queue.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['department', 'location', 'status', 'priority']
    ordering_fields = ['queue_number', 'checked_in_at']
    ordering = ['priority', 'queue_number']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'encounter__patient',
            'department',
        )
    
    @action(detail=False, methods=['get'])
    def current_queue(self, request):
        """Get current queue for a department"""
        department_id = request.query_params.get('department')
        location = request.query_params.get('location')
        status = request.query_params.get('status')
        
        queryset = self.filter_queryset(self.get_queryset())

        # Default behavior: only show active queue items unless status is explicitly requested.
        if not status:
            queryset = queryset.exclude(status__in=['completed', 'skipped'])
        
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        if location:
            queryset = queryset.filter(location=location)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def call(self, request, pk=None):
        """Call next patient in queue"""
        queue_item = self.get_object()
        queue_item.status = 'in_progress'
        queue_item.called_at = timezone.now()
        queue_item.save()
        serializer = self.get_serializer(queue_item)
        return Response(serializer.data)
    
    def get_serializer_class(self):
        from .serializers_advanced import QueueSerializer
        return QueueSerializer


class TriageViewSet(viewsets.ModelViewSet):
    """ViewSet for Triage"""
    queryset = Triage.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['triage_level', 'encounter']
    ordering_fields = ['triage_time']
    ordering = ['-triage_time']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'encounter__patient',
            'triaged_by__user',
            'triaged_by__department',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import TriageSerializer
        return TriageSerializer


# ==================== IMAGING VIEWSETS ====================

class ImagingStudyViewSet(viewsets.ModelViewSet):
    """ViewSet for Imaging Studies"""
    queryset = ImagingStudy.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['modality', 'status', 'priority', 'patient']
    search_fields = ['dicom_uid', 'pacs_id', 'body_part']
    ordering_fields = ['scheduled_at', 'performed_at']
    ordering = ['-scheduled_at']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'patient',
            'encounter',
            'order',
            'technician__user',
            'assigned_radiologist__user',
            'report_dictated_by__user',
            'report_verified_by__user',
        )
    
    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        """Add report to imaging study"""
        study = self.get_object()
        study.report_text = request.data.get('report_text', '')
        study.findings = request.data.get('findings', '')
        study.impression = request.data.get('impression', '')
        study.report_dictated_by_id = request.user.id if hasattr(request.user, 'staff_profile') else None
        study.status = 'reported'
        study.save()
        serializer = self.get_serializer(study)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify imaging report"""
        study = self.get_object()
        study.report_verified_by_id = request.user.id if hasattr(request.user, 'staff_profile') else None
        study.report_verified_at = timezone.now()
        study.status = 'completed'
        study.save()
        serializer = self.get_serializer(study)
        return Response(serializer.data)
    
    def get_serializer_class(self):
        from .serializers_advanced import ImagingStudySerializer
        return ImagingStudySerializer


# ==================== THEATRE VIEWSETS ====================

class TheatreScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for Theatre Schedules"""
    queryset = TheatreSchedule.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['theatre_name', 'status', 'surgeon']
    ordering_fields = ['scheduled_start']
    ordering = ['scheduled_start']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'patient',
            'encounter',
            'surgeon__user',
            'anaesthetist__user',
            'scrub_nurse__user',
        )
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start theatre procedure"""
        schedule = self.get_object()
        schedule.status = 'in_progress'
        schedule.actual_start = timezone.now()
        schedule.save()
        serializer = self.get_serializer(schedule)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete theatre procedure"""
        schedule = self.get_object()
        schedule.status = 'completed'
        schedule.actual_end = timezone.now()
        schedule.save()
        serializer = self.get_serializer(schedule)
        return Response(serializer.data)
    
    def get_serializer_class(self):
        from .serializers_advanced import TheatreScheduleSerializer
        return TheatreScheduleSerializer


class SurgicalChecklistViewSet(viewsets.ModelViewSet):
    """ViewSet for Surgical Checklists"""
    queryset = SurgicalChecklist.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().select_related(
            'theatre_schedule__patient',
            'theatre_schedule__encounter',
            'completed_by__user',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import SurgicalChecklistSerializer
        return SurgicalChecklistSerializer


class AnaesthesiaRecordViewSet(viewsets.ModelViewSet):
    """ViewSet for Anaesthesia Records"""
    queryset = AnaesthesiaRecord.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['theatre_schedule', 'anaesthetist']
    ordering_fields = ['created']
    ordering = ['-created']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'theatre_schedule__patient',
            'anaesthetist__user',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import AnaesthesiaRecordSerializer
        return AnaesthesiaRecordSerializer


# ==================== NURSING VIEWSETS ====================

class MedicationAdministrationRecordViewSet(viewsets.ModelViewSet):
    """ViewSet for MAR"""
    queryset = MedicationAdministrationRecord.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['patient', 'encounter', 'status', 'prescription']
    ordering_fields = ['scheduled_time']
    ordering = ['scheduled_time']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'patient',
            'prescription',
            'encounter',
            'administered_by__user',
        )
    
    @action(detail=True, methods=['post'])
    def administer(self, request, pk=None):
        """Record medication administration"""
        mar = self.get_object()
        mar.status = 'given'
        mar.administered_time = timezone.now()
        mar.administered_by_id = request.user.id if hasattr(request.user, 'staff_profile') else None
        mar.dose_given = request.data.get('dose_given', '')
        mar.route = request.data.get('route', '')
        mar.site = request.data.get('site', '')
        mar.notes = request.data.get('notes', '')
        mar.save()
        serializer = self.get_serializer(mar)
        return Response(serializer.data)
    
    def get_serializer_class(self):
        from .serializers_advanced import MedicationAdministrationRecordSerializer
        return MedicationAdministrationRecordSerializer


class HandoverSheetViewSet(viewsets.ModelViewSet):
    """ViewSet for Handover Sheets"""
    queryset = HandoverSheet.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['ward', 'shift_type', 'date']
    ordering_fields = ['date', 'shift_start']
    ordering = ['-date', '-shift_start']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'ward',
            'created_by__user',
            'created_by__department',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import HandoverSheetSerializer
        return HandoverSheetSerializer


# ==================== ER VIEWSETS ====================

class IncidentLogViewSet(viewsets.ModelViewSet):
    """ViewSet for Incident Logs"""
    queryset = IncidentLog.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['incident_type', 'severity', 'status']
    ordering_fields = ['incident_date']
    ordering = ['-incident_date']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'patient',
            'reported_by__user',
            'staff__user',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import IncidentLogSerializer
        return IncidentLogSerializer


class CrashCartCheckViewSet(viewsets.ModelViewSet):
    """ViewSet for Crash Cart Checks"""
    queryset = CrashCartCheck.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['location', 'status']
    ordering_fields = ['check_date']
    ordering = ['-check_date']

    def get_queryset(self):
        return super().get_queryset().select_related('checked_by__user')
    
    def get_serializer_class(self):
        from .serializers_advanced import CrashCartCheckSerializer
        return CrashCartCheckSerializer


# ==================== MATERIALS & ASSETS VIEWSETS ====================

class MedicalEquipmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Medical Equipment"""
    queryset = MedicalEquipment.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['equipment_type', 'status', 'location']
    search_fields = ['equipment_code', 'name', 'serial_number']
    ordering_fields = ['name']
    ordering = ['name']
    
    @action(detail=False, methods=['get'])
    def maintenance_due(self, request):
        """Get equipment due for maintenance"""
        from datetime import date
        equipment = self.get_queryset().filter(
            next_maintenance_due__lte=date.today(),
            status__in=['available', 'in_use']
        )
        serializer = self.get_serializer(equipment, many=True)
        return Response(serializer.data)
    
    def get_serializer_class(self):
        from .serializers_advanced import MedicalEquipmentSerializer
        return MedicalEquipmentSerializer


class ConsumablesInventoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Consumables Inventory"""
    queryset = ConsumablesInventory.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['category', 'location']
    search_fields = ['item_code', 'item_name']
    ordering_fields = ['item_name']
    ordering = ['item_name']
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get items with low stock"""
        from django.db.models import F
        items = self.get_queryset().filter(
            quantity_on_hand__lte=F('reorder_level')
        )
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)
    
    def get_serializer_class(self):
        from .serializers_advanced import ConsumablesInventorySerializer
        return ConsumablesInventorySerializer


class MaintenanceLogViewSet(viewsets.ModelViewSet):
    """ViewSet for Maintenance Logs"""
    queryset = MaintenanceLog.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['equipment', 'maintenance_type']
    ordering_fields = ['service_date']
    ordering = ['-service_date']

    def get_queryset(self):
        return super().get_queryset().select_related('equipment', 'technician__user')
    
    def get_serializer_class(self):
        from .serializers_advanced import MaintenanceLogSerializer
        return MaintenanceLogSerializer


# ==================== HR VIEWSETS ====================

class DutyRosterViewSet(viewsets.ModelViewSet):
    """ViewSet for Duty Rosters"""
    queryset = DutyRoster.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['staff', 'department', 'shift_type', 'shift_date']
    ordering_fields = ['shift_date', 'start_time']
    ordering = ['shift_date', 'start_time']

    def get_queryset(self):
        return super().get_queryset().select_related('staff__user', 'department')
    
    def get_serializer_class(self):
        from .serializers_advanced import DutyRosterSerializer
        return DutyRosterSerializer


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for Leave Requests"""
    queryset = LeaveRequest.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['staff', 'leave_type', 'status']
    ordering_fields = ['created', 'start_date']
    ordering = ['-created']

    def get_queryset(self):
        return super().get_queryset().select_related('staff__user', 'approved_by__user')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve leave request"""
        leave = self.get_object()
        leave.status = 'approved'
        leave.approved_by_id = request.user.id if hasattr(request.user, 'staff_profile') else None
        leave.approved_at = timezone.now()
        leave.save()
        serializer = self.get_serializer(leave)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject leave request"""
        leave = self.get_object()
        leave.status = 'rejected'
        leave.approved_by_id = request.user.id if hasattr(request.user, 'staff_profile') else None
        leave.approved_at = timezone.now()
        leave.save()
        serializer = self.get_serializer(leave)
        return Response(serializer.data)
    
    def get_serializer_class(self):
        from .serializers_advanced import LeaveRequestSerializer
        return LeaveRequestSerializer


# ==================== ENHANCED BILLING VIEWSETS ====================

class InsurancePreAuthorizationViewSet(viewsets.ModelViewSet):
    """ViewSet for Insurance Pre-Authorizations"""
    queryset = InsurancePreAuthorization.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['payer', 'status', 'patient']
    ordering_fields = ['requested_date']
    ordering = ['-requested_date']

    def get_queryset(self):
        return super().get_queryset().select_related('patient', 'payer', 'encounter')
    
    def get_serializer_class(self):
        from .serializers_advanced import InsurancePreAuthorizationSerializer
        return InsurancePreAuthorizationSerializer


class ClaimsBatchViewSet(viewsets.ModelViewSet):
    """ViewSet for Claims Batches"""
    queryset = ClaimsBatch.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['payer', 'status']
    ordering_fields = ['created', 'submission_date']
    ordering = ['-created']

    def get_queryset(self):
        return super().get_queryset().select_related('payer')
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit claims batch"""
        batch = self.get_object()
        batch.status = 'submitted'
        batch.submission_date = timezone.now()
        batch.save()
        serializer = self.get_serializer(batch)
        return Response(serializer.data)
    
    def get_serializer_class(self):
        from .serializers_advanced import ClaimsBatchSerializer
        return ClaimsBatchSerializer


class ChargeCaptureViewSet(viewsets.ModelViewSet):
    """ViewSet for Charge Capture"""
    queryset = ChargeCapture.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['encounter', 'service_code']
    ordering_fields = ['charge_date']
    ordering = ['-charge_date']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'encounter__patient',
            'service_code',
            'charged_by__user',
            'invoice_line',
        )
    
    def get_serializer_class(self):
        from .serializers_advanced import ChargeCaptureSerializer
        return ChargeCaptureSerializer


# ==================== LAB ENHANCEMENTS ====================

class LabTestPanelViewSet(viewsets.ModelViewSet):
    """ViewSet for Lab Test Panels"""
    queryset = LabTestPanel.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter]
    search_fields = ['panel_code', 'panel_name']

    def get_queryset(self):
        return super().get_queryset().prefetch_related('tests')
    
    def get_serializer_class(self):
        from .serializers_advanced import LabTestPanelSerializer
        return LabTestPanelSerializer


class SampleCollectionViewSet(viewsets.ModelViewSet):
    """ViewSet for Sample Collection"""
    queryset = SampleCollection.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['patient', 'sample_type', 'status']
    search_fields = ['sample_id']
    ordering_fields = ['collection_time', 'created']
    ordering = ['-created']

    def get_queryset(self):
        return super().get_queryset().select_related(
            'patient',
            'order',
            'collected_by__user',
        )
    
    @action(detail=True, methods=['post'])
    def collect(self, request, pk=None):
        """Mark sample as collected"""
        sample = self.get_object()
        sample.status = 'collected'
        sample.collection_time = timezone.now()
        sample.collected_by_id = request.user.id if hasattr(request.user, 'staff_profile') else None
        sample.save()
        serializer = self.get_serializer(sample)
        return Response(serializer.data)
    
    def get_serializer_class(self):
        from .serializers_advanced import SampleCollectionSerializer
        return SampleCollectionSerializer


# ==================== SMS ====================

class SMSLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for SMS Logs (read-only)"""
    queryset = SMSLog.objects.filter(is_deleted=False)
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['status', 'message_type']
    ordering_fields = ['created', 'sent_at']
    ordering = ['-created']
    
    def get_serializer_class(self):
        from .serializers_advanced import SMSLogSerializer
        return SMSLogSerializer


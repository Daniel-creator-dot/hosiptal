"""
REST API ViewSets for Hospital Management System.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters as rest_filters
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .models import (
    Patient, Encounter, VitalSign, Department, Staff, Ward, Bed, Admission,
    Order, LabTest, LabResult, Drug, PharmacyStock, Prescription,
    Payer, ServiceCode, PriceBook, Invoice, InvoiceLine,
    Appointment, MedicalRecord, Notification
)
from .serializers import (
    PatientSerializer, EncounterSerializer, VitalSignSerializer,
    DepartmentSerializer, StaffSerializer, WardSerializer, BedSerializer,
    AdmissionSerializer, OrderSerializer, LabTestSerializer, LabResultSerializer,
    DrugSerializer, PharmacyStockSerializer, PrescriptionSerializer,
    PayerSerializer, ServiceCodeSerializer, PriceBookSerializer,
    InvoiceSerializer, InvoiceLineSerializer,
    AppointmentSerializer, MedicalRecordSerializer, NotificationSerializer
)


# ==================== PATIENT & EMR VIEWSETS ====================

class PatientViewSet(viewsets.ModelViewSet):
    """ViewSet for Patient management"""
    queryset = Patient.objects.filter(is_deleted=False)
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['gender', 'blood_type', 'is_deleted']
    search_fields = ['first_name', 'last_name', 'mrn', 'national_id', 'phone_number', 'email']
    ordering_fields = ['created', 'last_name', 'first_name']
    ordering = ['-created']
    
    @action(detail=True, methods=['get'])
    def encounters(self, request, pk=None):
        """Get all encounters for a patient"""
        patient = self.get_object()
        encounters = Encounter.objects.filter(patient=patient, is_deleted=False)
        serializer = EncounterSerializer(encounters, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        """Get all invoices for a patient"""
        patient = self.get_object()
        invoices = Invoice.objects.filter(patient=patient, is_deleted=False)
        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data)


class EncounterViewSet(viewsets.ModelViewSet):
    """ViewSet for Encounter management"""
    queryset = Encounter.objects.filter(is_deleted=False)
    serializer_class = EncounterSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['encounter_type', 'status', 'patient', 'provider', 'location']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn', 'chief_complaint']
    ordering_fields = ['started_at', 'created']
    ordering = ['-started_at']
    
    @action(detail=True, methods=['get', 'post'])
    def vitals(self, request, pk=None):
        """Get or create vital signs for an encounter"""
        encounter = self.get_object()
        if request.method == 'GET':
            vitals = VitalSign.objects.filter(encounter=encounter, is_deleted=False)
            serializer = VitalSignSerializer(vitals, many=True)
            return Response(serializer.data)
        elif request.method == 'POST':
            data = request.data.copy()
            data['encounter'] = encounter.id
            serializer = VitalSignSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'])
    def complete(self, request, pk=None):
        """Mark encounter as completed"""
        encounter = self.get_object()
        encounter.status = 'completed'
        from django.utils import timezone
        encounter.ended_at = timezone.now()
        encounter.save()
        serializer = self.get_serializer(encounter)
        return Response(serializer.data)


class VitalSignViewSet(viewsets.ModelViewSet):
    """ViewSet for VitalSign management"""
    queryset = VitalSign.objects.filter(is_deleted=False)
    serializer_class = VitalSignSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['encounter', 'recorded_by']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name']
    ordering_fields = ['recorded_at', 'created']
    ordering = ['-recorded_at']


# ==================== STAFF & HR VIEWSETS ====================

class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Department management"""
    queryset = Department.objects.filter(is_deleted=False)
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name']
    ordering = ['name']


class StaffViewSet(viewsets.ModelViewSet):
    """ViewSet for Staff management"""
    serializer_class = StaffSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['profession', 'department', 'is_active']
    search_fields = ['user__first_name', 'user__last_name', 'employee_id']
    ordering_fields = ['user__last_name', 'user__first_name']
    ordering = ['user__last_name']
    
    def get_queryset(self):
        """Get queryset with duplicate prevention - only most recent staff record per user"""
        from hospital.utils_roles import get_deduplicated_staff_queryset
        return get_deduplicated_staff_queryset(base_filter={'is_active': True})


# ==================== FACILITY & BEDS VIEWSETS ====================

class WardViewSet(viewsets.ModelViewSet):
    """ViewSet for Ward management"""
    queryset = Ward.objects.filter(is_deleted=False)
    serializer_class = WardSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['ward_type', 'department', 'is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name']
    ordering = ['name']
    
    @action(detail=True, methods=['get'])
    def beds(self, request, pk=None):
        """Get all beds in a ward"""
        ward = self.get_object()
        beds = Bed.objects.filter(ward=ward, is_deleted=False)
        serializer = BedSerializer(beds, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def available_beds(self, request, pk=None):
        """Get available beds in a ward"""
        ward = self.get_object()
        beds = Bed.objects.filter(ward=ward, status='available', is_deleted=False, is_active=True)
        serializer = BedSerializer(beds, many=True)
        return Response(serializer.data)


class BedViewSet(viewsets.ModelViewSet):
    """ViewSet for Bed management"""
    queryset = Bed.objects.filter(is_deleted=False)
    serializer_class = BedSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['ward', 'bed_type', 'status', 'is_active']
    search_fields = ['bed_number', 'ward__name']
    ordering_fields = ['bed_number']
    ordering = ['ward', 'bed_number']


class AdmissionViewSet(viewsets.ModelViewSet):
    """ViewSet for Admission management"""
    queryset = Admission.objects.filter(is_deleted=False)
    serializer_class = AdmissionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['status', 'ward', 'bed', 'admitting_doctor']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name']
    ordering_fields = ['admit_date', 'created']
    ordering = ['-admit_date']
    
    @action(detail=True, methods=['patch'])
    def discharge(self, request, pk=None):
        """Discharge a patient"""
        admission = self.get_object()
        admission.status = 'discharged'
        from django.utils import timezone
        admission.discharge_date = timezone.now()
        if admission.bed:
            admission.bed.status = 'available'
            admission.bed.save()
        admission.save()
        serializer = self.get_serializer(admission)
        return Response(serializer.data)


# ==================== ORDERS & LAB VIEWSETS ====================

class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for Order management"""
    queryset = Order.objects.filter(is_deleted=False)
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['order_type', 'status', 'priority', 'encounter', 'requested_by']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name', 'notes']
    ordering_fields = ['requested_at', 'created']
    ordering = ['-requested_at']


class LabTestViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for LabTest (read-only catalog)"""
    queryset = LabTest.objects.filter(is_active=True, is_deleted=False)
    serializer_class = LabTestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['specimen_type', 'is_active']
    search_fields = ['code', 'name']
    ordering_fields = ['name']
    ordering = ['name']


class LabResultViewSet(viewsets.ModelViewSet):
    """ViewSet for LabResult management"""
    queryset = LabResult.objects.filter(is_deleted=False)
    serializer_class = LabResultSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['order', 'test', 'status', 'is_abnormal', 'verified_by']
    search_fields = ['order__encounter__patient__first_name', 'order__encounter__patient__last_name', 'test__name']
    ordering_fields = ['created', 'verified_at']
    ordering = ['-created']
    
    @action(detail=True, methods=['patch'])
    def verify(self, request, pk=None):
        """Verify a lab result"""
        result = self.get_object()
        result.status = 'completed'
        result.verified_by = request.user.staff if hasattr(request.user, 'staff_profile') else None
        from django.utils import timezone
        result.verified_at = timezone.now()
        result.save()
        serializer = self.get_serializer(result)
        return Response(serializer.data)


# ==================== PHARMACY VIEWSETS ====================

class DrugViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Drug (read-only formulary)"""
    queryset = Drug.objects.filter(is_active=True, is_deleted=False)
    serializer_class = DrugSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['form', 'is_controlled', 'is_active']
    search_fields = ['name', 'generic_name', 'atc_code']
    ordering_fields = ['name']
    ordering = ['name']


class PharmacyStockViewSet(viewsets.ModelViewSet):
    """ViewSet for PharmacyStock management"""
    queryset = PharmacyStock.objects.filter(is_deleted=False)
    serializer_class = PharmacyStockSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['drug', 'location']
    search_fields = ['drug__name', 'batch_number']
    ordering_fields = ['drug__name', 'expiry_date']
    ordering = ['drug__name', 'expiry_date']
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get items below reorder level"""
        from django.db.models import F
        low_stock = self.queryset.filter(
            quantity_on_hand__lte=F('reorder_level')
        )
        serializer = self.get_serializer(low_stock, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get items expiring within 30 days"""
        from django.utils import timezone
        from datetime import timedelta
        expiring_date = timezone.now().date() + timedelta(days=30)
        expiring = self.queryset.filter(expiry_date__lte=expiring_date)
        serializer = self.get_serializer(expiring, many=True)
        return Response(serializer.data)


class PrescriptionViewSet(viewsets.ModelViewSet):
    """ViewSet for Prescription management"""
    queryset = Prescription.objects.filter(is_deleted=False)
    serializer_class = PrescriptionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['order', 'drug', 'prescribed_by']
    search_fields = ['order__encounter__patient__first_name', 'order__encounter__patient__last_name', 'drug__name']
    ordering_fields = ['created']
    ordering = ['-created']


# ==================== BILLING VIEWSETS ====================

class PayerViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Payer (read-only catalog)"""
    queryset = Payer.objects.filter(is_active=True, is_deleted=False)
    serializer_class = PayerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['payer_type', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']


class ServiceCodeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for ServiceCode (read-only catalog)"""
    queryset = ServiceCode.objects.filter(is_active=True, is_deleted=False)
    serializer_class = ServiceCodeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['code', 'description']
    ordering_fields = ['code']
    ordering = ['code']


class PriceBookViewSet(viewsets.ModelViewSet):
    """ViewSet for PriceBook management"""
    queryset = PriceBook.objects.filter(is_active=True, is_deleted=False)
    serializer_class = PriceBookSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['payer', 'service_code', 'is_active']
    search_fields = ['payer__name', 'service_code__code', 'service_code__description']
    ordering_fields = ['payer', 'service_code']
    ordering = ['payer', 'service_code']


class InvoiceViewSet(viewsets.ModelViewSet):
    """ViewSet for Invoice management"""
    queryset = Invoice.objects.filter(is_deleted=False)
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['patient', 'payer', 'status', 'encounter']
    search_fields = ['invoice_number', 'patient__first_name', 'patient__last_name', 'patient__mrn']
    ordering_fields = ['issued_at', 'created']
    ordering = ['-issued_at']
    
    @action(detail=True, methods=['get', 'post'])
    def lines(self, request, pk=None):
        """Get or create invoice lines"""
        invoice = self.get_object()
        if request.method == 'GET':
            lines = InvoiceLine.objects.filter(invoice=invoice, is_deleted=False)
            serializer = InvoiceLineSerializer(lines, many=True)
            return Response(serializer.data)
        elif request.method == 'POST':
            data = request.data.copy()
            data['invoice'] = invoice.id
            serializer = InvoiceLineSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                # Recalculate invoice totals
                invoice.refresh_from_db()
                invoice.total_amount = sum(line.line_total for line in invoice.lines.all())
                invoice.balance = invoice.total_amount
                invoice.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'])
    def issue(self, request, pk=None):
        """Issue an invoice"""
        invoice = self.get_object()
        invoice.status = 'issued'
        invoice.save()
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)


class InvoiceLineViewSet(viewsets.ModelViewSet):
    """ViewSet for InvoiceLine management"""
    queryset = InvoiceLine.objects.filter(is_deleted=False)
    serializer_class = InvoiceLineSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['invoice', 'service_code']
    ordering_fields = ['created']
    ordering = ['invoice', 'created']


# ==================== NEW FEATURES VIEWSETS ====================

class AppointmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Appointment management"""
    queryset = Appointment.objects.filter(is_deleted=False)
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['status', 'department', 'provider', 'patient']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn', 'reason']
    ordering_fields = ['appointment_date', 'created']
    ordering = ['appointment_date']
    
    @action(detail=True, methods=['patch'])
    def confirm(self, request, pk=None):
        """Confirm an appointment"""
        appointment = self.get_object()
        appointment.status = 'confirmed'
        appointment.save()
        serializer = self.get_serializer(appointment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def cancel(self, request, pk=None):
        """Cancel an appointment"""
        appointment = self.get_object()
        appointment.status = 'cancelled'
        appointment.save()
        serializer = self.get_serializer(appointment)
        return Response(serializer.data)


class MedicalRecordViewSet(viewsets.ModelViewSet):
    """ViewSet for MedicalRecord management"""
    queryset = MedicalRecord.objects.filter(is_deleted=False)
    serializer_class = MedicalRecordSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['patient', 'encounter', 'record_type', 'created_by']
    search_fields = ['title', 'content', 'patient__first_name', 'patient__last_name']
    ordering_fields = ['created']
    ordering = ['-created']


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for Notification management"""
    queryset = Notification.objects.filter(is_deleted=False)
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['recipient', 'notification_type', 'is_read']
    ordering_fields = ['created']
    ordering = ['-created']
    
    def get_queryset(self):
        """Filter notifications for current user"""
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(recipient=self.request.user)
        return queryset
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications"""
        notifications = self.queryset.filter(recipient=request.user, is_read=False)
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['patch'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        notification.mark_as_read()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        count = self.queryset.filter(recipient=request.user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'marked_read': count})


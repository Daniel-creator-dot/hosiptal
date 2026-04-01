"""
REST API ViewSets for Hospital Management System.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters as rest_filters
from django.utils import timezone
from datetime import timedelta
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
    """ViewSet for Patient management with duplicate prevention"""
    queryset = Patient.objects.filter(is_deleted=False)
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.SearchFilter, rest_filters.OrderingFilter]
    filterset_fields = ['gender', 'blood_type', 'is_deleted']
    search_fields = ['first_name', 'last_name', 'mrn', 'national_id', 'phone_number', 'email']
    ordering_fields = ['created', 'last_name', 'first_name']
    ordering = ['-created']

    def get_queryset(self):
        return super().get_queryset().select_related('primary_insurance')
    
    def create(self, request, *args, **kwargs):
        """Override create to use transaction and prevent duplicates"""
        from django.db import transaction
        from rest_framework.exceptions import ValidationError
        
        # CRITICAL: Check for auto-save requests - ignore them
        is_auto_save = (
            request.data.get('auto_save') == 'true' or
            request.META.get('HTTP_X_AUTO_SAVE') == 'true'
        )
        
        if is_auto_save:
            return Response({
                'status': 'ignored',
                'message': 'Patient registration cannot be auto-saved'
            }, status=status.HTTP_200_OK)

        # Soft idempotency guard: return the recent match instead of creating again
        first_name = (request.data.get('first_name') or '').strip()
        last_name = (request.data.get('last_name') or '').strip()
        phone_number = (request.data.get('phone_number') or '').strip()
        email = (request.data.get('email') or '').strip()
        national_id = (request.data.get('national_id') or '').strip()
        date_of_birth = request.data.get('date_of_birth')

        normalized_phone = self._normalize_phone(phone_number)
        recent_cutoff = timezone.now() - timedelta(minutes=10)

        # Check by name/phone (+ optional DOB) within recent window
        if first_name and last_name and normalized_phone:
            candidates = Patient.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                is_deleted=False,
                modified__gte=recent_cutoff
            )
            if date_of_birth and date_of_birth != '2000-01-01':
                candidates = candidates.filter(date_of_birth=date_of_birth)

            for candidate in candidates:
                if self._normalize_phone(candidate.phone_number) == normalized_phone:
                    serializer = self.get_serializer(candidate)
                    data = serializer.data
                    data['duplicate'] = True
                    return Response(data, status=status.HTTP_200_OK)

        # Guard by name + DOB even when phone is missing
        if first_name and last_name and date_of_birth and date_of_birth != '2000-01-01':
            existing_dob = Patient.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                date_of_birth=date_of_birth,
                is_deleted=False,
                modified__gte=recent_cutoff
            ).order_by('-modified').first()
            if existing_dob:
                serializer = self.get_serializer(existing_dob)
                data = serializer.data
                data['duplicate'] = True
                return Response(data, status=status.HTTP_200_OK)

        # Also guard by unique identifiers recently created
        if email:
            existing_email = Patient.objects.filter(
                email__iexact=email,
                is_deleted=False,
                modified__gte=recent_cutoff
            ).first()
            if existing_email:
                serializer = self.get_serializer(existing_email)
                data = serializer.data
                data['duplicate'] = True
                return Response(data, status=status.HTTP_200_OK)

        if national_id:
            existing_nid = Patient.objects.filter(
                national_id=national_id,
                is_deleted=False,
                modified__gte=recent_cutoff
            ).first()
            if existing_nid:
                serializer = self.get_serializer(existing_nid)
                data = serializer.data
                data['duplicate'] = True
                return Response(data, status=status.HTTP_200_OK)
        
        # Use transaction to prevent race conditions
        try:
            with transaction.atomic():
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                
                # Additional duplicate check inside transaction
                instance = serializer.save()
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            # Return a single string for 'error' so clients never see [object Object]
            detail = getattr(e, 'detail', None)
            if detail is None:
                error_msg = str(e) if e.args else 'Validation failed'
            elif isinstance(detail, dict):
                parts = []
                for k, v in detail.items():
                    if isinstance(v, (list, tuple)):
                        parts.extend(f"{k}: {x}" for x in v)
                    else:
                        parts.append(f"{k}: {v}")
                error_msg = '; '.join(parts) if parts else 'Validation failed'
            elif isinstance(detail, (list, tuple)):
                error_msg = '; '.join(str(x) for x in detail) if detail else 'Validation failed'
            else:
                error_msg = str(detail)
            return Response({
                'error': error_msg,
                'detail': detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Catch any other errors - always return string error for client display
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating patient via API: {e}", exc_info=True)
            err_str = str(e) if e else 'Unknown error'
            return Response({
                'error': err_str,
                'detail': err_str
            }, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _normalize_phone(phone):
        """Normalize phone number to comparable format"""
        if not phone:
            return ''
        phone = str(phone).strip()
        phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if phone.startswith('0') and len(phone) == 10:
            phone = '233' + phone[1:]
        elif phone.startswith('+'):
            phone = phone[1:]
        return phone
    
    @action(detail=True, methods=['get'])
    def encounters(self, request, pk=None):
        """Get all encounters for a patient"""
        patient = self.get_object()
        encounters = Encounter.objects.filter(
            patient=patient, is_deleted=False
        ).select_related('patient', 'provider', 'provider__user', 'location').prefetch_related('vitals')
        serializer = EncounterSerializer(encounters, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        """Get all invoices for a patient"""
        patient = self.get_object()
        invoices = Invoice.objects.filter(
            patient=patient, is_deleted=False
        ).select_related('patient', 'payer').prefetch_related('lines')
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

    def get_queryset(self):
        return super().get_queryset().select_related(
            'patient', 'provider', 'provider__user', 'location'
        ).prefetch_related('vitals')
    
    def create(self, request, *args, **kwargs):
        """Prevent duplicate encounters from rapid double submissions"""
        from django.db import transaction
        data = request.data
        patient_id = data.get('patient')
        provider_id = data.get('provider')
        encounter_type = data.get('encounter_type')
        chief_complaint = (data.get('chief_complaint') or '').strip().lower()

        # Look for a very recent matching encounter
        recent_cutoff = timezone.now() - timedelta(minutes=5)
        existing = Encounter.objects.filter(
            patient_id=patient_id,
            encounter_type=encounter_type,
            provider_id=provider_id,
            status='active',
            started_at__gte=recent_cutoff
        ).order_by('-created').first()

        if existing:
            existing_cc = (existing.chief_complaint or '').strip().lower()
            if not chief_complaint or existing_cc == chief_complaint:
                serializer = self.get_serializer(existing)
                data = serializer.data
                data['duplicate'] = True
                return Response(data, status=status.HTTP_200_OK)

        with transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
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

    def get_queryset(self):
        return super().get_queryset().select_related(
            'encounter', 'encounter__patient', 'recorded_by', 'recorded_by__user'
        )


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

    def get_queryset(self):
        return super().get_queryset().select_related(
            'encounter', 'encounter__patient', 'ward', 'bed',
            'admitting_doctor', 'admitting_doctor__user'
        )
    
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

    def get_queryset(self):
        return super().get_queryset().select_related(
            'encounter', 'encounter__patient', 'requested_by', 'requested_by__user'
        )


class LabTestViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for LabTest (read-only catalog)"""
    queryset = LabTest.objects.filter(
        is_active=True, 
        is_deleted=False,
        name__isnull=False
    ).exclude(
        name__iexact=''
    ).exclude(
        name__icontains='INVALID'
    )
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

    def get_queryset(self):
        return super().get_queryset().select_related(
            'order', 'order__encounter', 'order__encounter__patient',
            'test', 'verified_by', 'verified_by__user'
        )
    
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
    queryset = Drug.objects.filter(
        is_active=True, 
        is_deleted=False,
        name__isnull=False
    ).exclude(
        name__iexact=''
    ).exclude(
        name__icontains='INVALID'
    )
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

    def get_queryset(self):
        return super().get_queryset().select_related(
            'order', 'order__encounter', 'order__encounter__patient',
            'drug', 'prescribed_by', 'prescribed_by__user'
        )


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

    def get_queryset(self):
        return super().get_queryset().select_related('patient', 'payer').prefetch_related('lines')
    
    @action(detail=True, methods=['get', 'post'])
    def lines(self, request, pk=None):
        """Get or create invoice lines"""
        invoice = self.get_object()
        if request.method == 'GET':
            lines = InvoiceLine.objects.filter(
                invoice=invoice, is_deleted=False, waived_at__isnull=True
            ).select_related('service_code')
            serializer = InvoiceLineSerializer(lines, many=True)
            return Response(serializer.data)
        elif request.method == 'POST':
            data = request.data.copy()
            data['invoice'] = invoice.id
            serializer = InvoiceLineSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                invoice.refresh_from_db()
                invoice.update_totals()
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

    def get_queryset(self):
        return super().get_queryset().select_related(
            'patient', 'provider', 'provider__user', 'department'
        )
    
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


"""
REST API Serializers for Hospital Management System.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Patient, Encounter, VitalSign, Department, Staff, Ward, Bed, Admission,
    Order, LabTest, LabResult, Drug, PharmacyStock, Prescription,
    Payer, ServiceCode, PriceBook, Invoice, InvoiceLine,
    Appointment, MedicalRecord, Notification
)


# ==================== USER & STAFF SERIALIZERS ====================

class UserSerializer(serializers.ModelSerializer):
    """User serializer"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active']
        read_only_fields = ['id']


class DepartmentSerializer(serializers.ModelSerializer):
    """Department serializer"""
    head_of_department_name = serializers.CharField(source='head_of_department', read_only=True)
    
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class StaffSerializer(serializers.ModelSerializer):
    """Staff serializer"""
    user = UserSerializer()
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Staff
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']
    
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create(**user_data)
        staff = Staff.objects.create(user=user, **validated_data)
        return staff
    
    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', None)
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ==================== PATIENT & EMR SERIALIZERS ====================

class PatientSerializer(serializers.ModelSerializer):
    """Patient serializer with duplicate prevention"""
    age = serializers.ReadOnlyField()
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = Patient
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']
    
    def validate(self, attrs):
        """Validate patient data and check for duplicates"""
        from .models import Patient
        
        first_name = attrs.get('first_name', '').strip()
        last_name = attrs.get('last_name', '').strip()
        phone_number = attrs.get('phone_number', '').strip()
        email = attrs.get('email', '').strip()
        national_id = attrs.get('national_id', '').strip()
        date_of_birth = attrs.get('date_of_birth')
        
        # Normalize phone
        def normalize_phone(phone):
            if not phone:
                return ''
            phone = str(phone).strip()
            phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if phone.startswith('0') and len(phone) == 10:
                phone = '233' + phone[1:]
            elif phone.startswith('+'):
                phone = phone[1:]
            return phone
        
        normalized_phone = normalize_phone(phone_number)
        
        # Get instance (if updating)
        instance = self.instance
        patient_id = instance.pk if instance else None
        
        # Check for duplicates
        if first_name and last_name and normalized_phone:
            if date_of_birth and date_of_birth != '2000-01-01':
                existing = Patient.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                    date_of_birth=date_of_birth,
                    is_deleted=False
                ).exclude(pk=patient_id).first()
            else:
                existing = Patient.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name,
                    is_deleted=False
                ).exclude(pk=patient_id).first()
            
            if existing and normalize_phone(existing.phone_number) == normalized_phone:
                raise serializers.ValidationError(
                    f"Duplicate patient detected! A patient with the same name ({first_name} {last_name}) "
                    f"and phone number ({phone_number}) already exists. MRN: {existing.mrn}"
                )

        # Fallback: guard by name + date_of_birth even if phone is missing
        if first_name and last_name and date_of_birth and date_of_birth != '2000-01-01':
            existing = Patient.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name,
                date_of_birth=date_of_birth,
                is_deleted=False
            ).exclude(pk=patient_id).first()
            if existing:
                raise serializers.ValidationError(
                    f"Duplicate patient detected! A patient named {first_name} {last_name} "
                    f"with the same date of birth already exists. MRN: {existing.mrn}"
                )
        
        if email:
            existing = Patient.objects.filter(
                email__iexact=email,
                is_deleted=False
            ).exclude(pk=patient_id).first()
            if existing:
                raise serializers.ValidationError(
                    f"Duplicate patient detected! A patient with email {email} already exists. MRN: {existing.mrn}"
                )
        
        if national_id:
            existing = Patient.objects.filter(
                national_id=national_id,
                is_deleted=False
            ).exclude(pk=patient_id).first()
            if existing:
                raise serializers.ValidationError(
                    f"Duplicate patient detected! A patient with National ID {national_id} already exists. MRN: {existing.mrn}"
                )
        
        return attrs


class VitalSignSerializer(serializers.ModelSerializer):
    """Vital signs serializer"""
    encounter_patient = serializers.CharField(source='encounter.patient.full_name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = VitalSign
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class EncounterSerializer(serializers.ModelSerializer):
    """Encounter serializer"""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.mrn', read_only=True)
    provider_name = serializers.CharField(source='provider.user.get_full_name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    vitals = VitalSignSerializer(many=True, read_only=True)
    
    class Meta:
        model = Encounter
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'started_at']


# ==================== FACILITY & BEDS SERIALIZERS ====================

class WardSerializer(serializers.ModelSerializer):
    """Ward serializer"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Ward
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class BedSerializer(serializers.ModelSerializer):
    """Bed serializer"""
    ward_name = serializers.CharField(source='ward.name', read_only=True)
    
    class Meta:
        model = Bed
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class AdmissionSerializer(serializers.ModelSerializer):
    """Admission serializer"""
    patient_name = serializers.CharField(source='encounter.patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='encounter.patient.mrn', read_only=True)
    ward_name = serializers.CharField(source='ward.name', read_only=True)
    bed_number = serializers.CharField(source='bed.bed_number', read_only=True)
    admitting_doctor_name = serializers.CharField(source='admitting_doctor.user.get_full_name', read_only=True)
    
    class Meta:
        model = Admission
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'admit_date']


# ==================== ORDERS & LAB SERIALIZERS ====================

class OrderSerializer(serializers.ModelSerializer):
    """Order serializer"""
    patient_name = serializers.CharField(source='encounter.patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='encounter.patient.mrn', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'requested_at']


class LabTestSerializer(serializers.ModelSerializer):
    """Lab test serializer"""
    class Meta:
        model = LabTest
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class LabResultSerializer(serializers.ModelSerializer):
    """Lab result serializer"""
    patient_name = serializers.CharField(source='order.encounter.patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='order.encounter.patient.mrn', read_only=True)
    test_name = serializers.CharField(source='test.name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = LabResult
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


# ==================== PHARMACY SERIALIZERS ====================

class DrugSerializer(serializers.ModelSerializer):
    """Drug serializer"""
    class Meta:
        model = Drug
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class PharmacyStockSerializer(serializers.ModelSerializer):
    """Pharmacy stock serializer"""
    drug_name = serializers.CharField(source='drug.name', read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = PharmacyStock
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']
    
    def get_is_expired(self, obj):
        from django.utils import timezone
        return obj.expiry_date < timezone.now().date() if obj.expiry_date else False


class PrescriptionSerializer(serializers.ModelSerializer):
    """Prescription serializer"""
    patient_name = serializers.CharField(source='order.encounter.patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='order.encounter.patient.mrn', read_only=True)
    drug_name = serializers.CharField(source='drug.name', read_only=True)
    prescribed_by_name = serializers.CharField(source='prescribed_by.user.get_full_name', read_only=True)
    
    class Meta:
        model = Prescription
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


# ==================== BILLING SERIALIZERS ====================

class PayerSerializer(serializers.ModelSerializer):
    """Payer serializer"""
    class Meta:
        model = Payer
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class ServiceCodeSerializer(serializers.ModelSerializer):
    """Service code serializer"""
    class Meta:
        model = ServiceCode
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class PriceBookSerializer(serializers.ModelSerializer):
    """Price book serializer"""
    payer_name = serializers.CharField(source='payer.name', read_only=True)
    service_code_code = serializers.CharField(source='service_code.code', read_only=True)
    service_description = serializers.CharField(source='service_code.description', read_only=True)
    
    class Meta:
        model = PriceBook
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class InvoiceLineSerializer(serializers.ModelSerializer):
    """Invoice line serializer"""
    service_code_code = serializers.CharField(source='service_code.code', read_only=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Match UI/print: show resolved catalog pricing when DB fields are stale zeros
        du = instance.display_unit_price
        dl = instance.display_line_total
        data['unit_price'] = str(du)
        data['line_total'] = str(dl)
        return data

    class Meta:
        model = InvoiceLine
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']


class InvoiceSerializer(serializers.ModelSerializer):
    """Invoice serializer"""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.mrn', read_only=True)
    payer_name = serializers.CharField(source='payer.name', read_only=True)
    lines = serializers.SerializerMethodField()

    def get_lines(self, obj):
        """Exclude waived lines from API response"""
        return InvoiceLineSerializer(obj.billable_lines, many=True).data

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'issued_at']


# ==================== NEW FEATURES SERIALIZERS ====================

class AppointmentSerializer(serializers.ModelSerializer):
    """Appointment serializer"""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.mrn', read_only=True)
    provider_name = serializers.CharField(source='provider.user.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    is_past_due = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']
    
    def get_is_past_due(self, obj):
        return obj.is_past_due()


class MedicalRecordSerializer(serializers.ModelSerializer):
    """Medical record serializer"""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_mrn = serializers.CharField(source='patient.mrn', read_only=True)
    encounter_type = serializers.CharField(source='encounter.get_encounter_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.user.get_full_name', read_only=True)
    document_url = serializers.SerializerMethodField()
    
    class Meta:
        model = MedicalRecord
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified']
    
    def get_document_url(self, obj):
        if obj.document:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.document.url)
        return None


class NotificationSerializer(serializers.ModelSerializer):
    """Notification serializer"""
    recipient_name = serializers.CharField(source='recipient.username', read_only=True)
    
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['id', 'created', 'modified', 'read_at']


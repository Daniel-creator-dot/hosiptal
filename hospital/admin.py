"""
Admin configuration for Hospital Management System with enhanced UI.
"""
from django.contrib import admin
from django import forms

# Import settings admin
from .admin_settings import *
#Import queue admin
from .admin_queue import *
# Import enterprise billing admin
from .admin_enterprise_billing import *
# Import insurance companies admin
from .admin_insurance_companies import *
from .admin_hr_enhanced import *
from .admin_hr_activities import *
# Import flexible pricing admin
from .admin_flexible_pricing import *
# Import contracts admin
from .admin_contracts import *
# Import telemedicine admin
from .admin_telemedicine import *
# Import legacy patients admin
from .admin_legacy_patients import *
# Import advanced accounting admin
from .admin_accounting_advanced import *
# Import patient deposits admin
from .admin_patient_deposits import *

# HOD Management
from .admin_hod_simple import *

# Auto-Attendance System
from .admin_auto_attendance import *

# Revenue Stream Tracking
from .admin_revenue_streams import *

# Department Budgeting System
from .admin_department_budgeting import *

# Locum Doctor Management
from .admin_locum_doctors import *

# Audit Logging
from .admin_audit import *

# Lab Management
from .admin_lab_management import *

# Pre-employment / Pre-admission screening
try:
    from .admin_screening import *
except ImportError:
    pass

# Consulting Rooms Management
try:
    from .admin_consulting_rooms import *
except ImportError:
    pass

from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.template.response import TemplateResponse
from django.urls import path
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from .services.auto_billing_service import AutoBillingService
from .models_payment_verification import PharmacyDispensing
from .models import (
    Patient, Encounter, VitalSign, Department, Staff, Ward, Bed, Admission,
    Order, LabTest, LabResult, Drug, PharmacyStock, Prescription,
    Payer, ServiceCode, PriceBook, Invoice, InvoiceLine,
    Appointment, MedicalRecord, Notification, PatientQRCode
)
from .models_advanced import (
    ClinicalNote, CarePlan, ProblemList, ProviderSchedule, Queue, Triage,
    ImagingStudy, ImagingCatalog, ProcedureCatalog, TheatreSchedule, SurgicalChecklist, AnaesthesiaRecord,
    MedicationAdministrationRecord, HandoverSheet, FallRiskAssessment,
    PressureUlcerRiskAssessment, CrashCartCheck, IncidentLog,
    MedicalEquipment, MaintenanceLog, ConsumablesInventory,
    DutyRoster, LeaveRequest, Attendance,
    InsurancePreAuthorization, ClaimsBatch, ChargeCapture,
    LabTestPanel, SampleCollection, SMSLog
)
from .admin_actions import (
    export_as_csv, mark_invoices_paid, mark_invoices_issued,
    complete_encounters, discharge_admissions
)


# ==================== INLINE ADMIN CLASSES ====================

class VitalSignInline(admin.TabularInline):
    model = VitalSign
    extra = 0
    readonly_fields = ['recorded_at']
    fields = ['recorded_at', 'systolic_bp', 'diastolic_bp', 'pulse', 'temperature', 'spo2']


class OrderInline(admin.TabularInline):
    model = Order
    extra = 0
    readonly_fields = ['requested_at']
    fields = ['order_type', 'status', 'priority', 'requested_by', 'requested_at']


class AdmissionInline(admin.StackedInline):
    model = Admission
    extra = 0
    readonly_fields = ['admit_date']
    can_delete = False


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1
    fields = ['service_code', 'description', 'quantity', 'unit_price', 'tax_amount', 'discount_amount', 'line_total']
    readonly_fields = ['line_total']


# ==================== MAIN ADMIN CLASSES ====================

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['mrn_display', 'full_name', 'age_badge', 'gender', 'phone_number', 'financial_summary', 'created']
    list_filter = ['gender', 'blood_type', 'created']
    search_fields = ['first_name', 'last_name', 'mrn', 'national_id', 'phone_number']
    ordering = ['last_name', 'first_name']
    readonly_fields = ['created', 'modified', 'mrn']
    actions = [export_as_csv]
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('mrn', 'national_id', 'first_name', 'last_name', 'middle_name', 
                      'date_of_birth', 'gender', 'blood_type'),
            'classes': ('wide',)
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'email', 'address'),
        }),
        ('Emergency Contact', {
            'fields': ('next_of_kin_name', 'next_of_kin_phone', 'next_of_kin_relationship'),
        }),
        ('Medical Information', {
            'fields': ('allergies', 'chronic_conditions', 'medications'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created', 'modified', 'is_deleted'),
            'classes': ('collapse',)
        }),
    )
    
    def mrn_display(self, obj):
        return format_html('<strong style="color: #667eea;">{}</strong>', obj.mrn)
    mrn_display.short_description = 'MRN'
    
    def age_badge(self, obj):
        age = obj.age
        color = 'success' if age < 65 else 'warning' if age < 80 else 'danger'
        return format_html('<span class="badge badge-{}">{}</span>', color, f'{age} yrs')
    age_badge.short_description = 'Age'
    
    def financial_summary(self, obj):
        total = obj.get_total_invoice_amount()
        balance = obj.get_outstanding_balance()
        if balance > 0:
            balance_str = f"{float(balance):.2f}"
            total_str = f"{float(total):.2f}"
            return format_html(
                '<span style="color: #f56565;">Outstanding: GHS {}</span><br><small>Total: GHS {}</small>',
                balance_str, total_str
            )
        total_str = f"{float(total):.2f}"
        return format_html('<span style="color: #48bb78;">Total: GHS {}</span>', total_str)
    financial_summary.short_description = 'Financial Summary'
    
    def save_model(self, request, obj, form, change):
        """Override save to check for duplicates in admin interface"""
        from django.db import IntegrityError
        from django.contrib import messages
        
        # Check for duplicates before saving (model.save() will also check, but this gives better error message)
        if not change:  # Only for new patients
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
            
            normalized_phone = normalize_phone(obj.phone_number)
            
            # Check for duplicates
            if obj.first_name and obj.last_name and normalized_phone:
                if obj.date_of_birth and obj.date_of_birth != '2000-01-01':
                    existing = Patient.objects.filter(
                        first_name__iexact=obj.first_name,
                        last_name__iexact=obj.last_name,
                        date_of_birth=obj.date_of_birth,
                        is_deleted=False
                    ).exclude(pk=obj.pk).first()
                else:
                    existing = Patient.objects.filter(
                        first_name__iexact=obj.first_name,
                        last_name__iexact=obj.last_name,
                        is_deleted=False
                    ).exclude(pk=obj.pk).first()
                
                if existing and normalize_phone(existing.phone_number) == normalized_phone:
                    messages.error(
                        request,
                        f'Duplicate patient detected! A patient with the same name ({obj.first_name} {obj.last_name}) '
                        f'and phone number ({obj.phone_number}) already exists. MRN: {existing.mrn}'
                    )
                    raise IntegrityError(f"Duplicate patient: {existing.mrn}")
        
        # Call parent save (which will also check duplicates in model.save())
        super().save_model(request, obj, form, change)


@admin.register(PatientQRCode)
class PatientQRCodeAdmin(admin.ModelAdmin):
    list_display = ['patient', 'mrn', 'scan_count', 'last_generated_at', 'last_scanned_at', 'is_active']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn', 'qr_token']
    list_filter = ['is_active', 'last_scanned_at']
    readonly_fields = ['qr_code_data', 'qr_code_image_preview', 'scan_count', 'last_generated_at',
                       'last_scanned_at', 'created', 'modified']
    fields = (
        'patient', 'qr_token', 'qr_code_data', 'qr_code_image', 'qr_code_image_preview',
        'scan_count', 'last_generated_at', 'last_scanned_at', 'last_scanned_by',
        'is_active', 'created', 'modified'
    )
    
    def mrn(self, obj):
        return obj.patient.mrn
    mrn.short_description = 'MRN'
    
    def qr_code_image_preview(self, obj):
        if obj.qr_code_image:
            return format_html('<img src="{}" style="width: 140px; height: 140px; object-fit: contain;" />', obj.qr_code_image.url)
        return "—"
    qr_code_image_preview.short_description = 'QR Preview'


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ['patient_link', 'encounter_type_badge', 'status_badge', 'started_at', 'provider', 'duration_display', 'actions_column']
    list_filter = ['encounter_type', 'status', 'started_at', 'provider__department']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn']
    ordering = ['-started_at']
    readonly_fields = ['started_at', 'created', 'modified', 'duration_display']
    inlines = [VitalSignInline, OrderInline, AdmissionInline]
    actions = [complete_encounters, export_as_csv]
    
    fieldsets = (
        ('Encounter Information', {
            'fields': ('patient', 'encounter_type', 'status', 'started_at', 'ended_at', 'duration_display')
        }),
        ('Location & Provider', {
            'fields': ('location', 'provider')
        }),
        ('Clinical Information', {
            'fields': ('chief_complaint', 'diagnosis', 'notes')
        }),
    )
    
    def patient_link(self, obj):
        url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
        return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
    patient_link.short_description = 'Patient'
    
    def encounter_type_badge(self, obj):
        colors = {
            'outpatient': 'info',
            'inpatient': 'success',
            'er': 'danger',
            'surgery': 'warning'
        }
        color = colors.get(obj.encounter_type, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_encounter_type_display())
    encounter_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {'active': 'success', 'completed': 'secondary', 'cancelled': 'danger'}
        color = colors.get(obj.status, 'warning')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'
    
    def duration_display(self, obj):
        if obj.ended_at:
            duration = obj.get_duration_minutes()
            if duration:
                hours = duration // 60
                minutes = duration % 60
                return f'{hours}h {minutes}m'
        return '-'
    duration_display.short_description = 'Duration'
    
    def actions_column(self, obj):
        if obj.status == 'active':
            return format_html(
                '<a href="{}" class="button" style="padding: 4px 8px; font-size: 11px;">Complete</a>',
                reverse('admin:hospital_encounter_change', args=[obj.pk])
            )
        return '-'
    actions_column.short_description = 'Actions'
    
    def current_activity_display(self, obj):
        """Display current department activities as badges"""
        try:
            if not obj.current_activity:
                return '-'
            activities = obj.get_activities_list()
            badges = []
            color_map = {
                'Consulting': 'primary',
                'Lab': 'info',
                'Pharmacy': 'warning',
                'Imaging': 'secondary',
            }
            for activity in activities:
                color = color_map.get(activity, 'dark')
                badges.append(
                    format_html(
                        '<span class="badge bg-{}" style="margin-right: 4px;">{}</span>',
                        color, activity
                    )
                )
            return format_html(''.join(badges))
        except Exception:
            return '-'
    current_activity_display.short_description = 'Activities'


@admin.register(VitalSign)
class VitalSignAdmin(admin.ModelAdmin):
    list_display = ['encounter_link', 'recorded_at', 'vitals_display', 'recorded_by']
    list_filter = ['recorded_at', 'encounter__encounter_type']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name']
    ordering = ['-recorded_at']
    readonly_fields = ['recorded_at', 'created', 'modified']
    
    def encounter_link(self, obj):
        url = reverse('admin:hospital_encounter_change', args=[obj.encounter.pk])
        return format_html('<a href="{}">{}</a>', url, obj.encounter.patient.full_name)
    encounter_link.short_description = 'Encounter'
    
    def vitals_display(self, obj):
        parts = []
        if obj.systolic_bp and obj.diastolic_bp:
            parts.append(f'BP: {obj.systolic_bp}/{obj.diastolic_bp}')
        if obj.pulse:
            parts.append(f'Pulse: {obj.pulse}')
        if obj.temperature:
            parts.append(f'Temp: {obj.temperature}°C')
        return ' | '.join(parts) if parts else '-'
    vitals_display.short_description = 'Vitals'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'head_display', 'staff_count', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']
    
    def head_display(self, obj):
        if obj.head_of_department:
            url = reverse('admin:hospital_staff_change', args=[obj.head_of_department.pk])
            return format_html('<a href="{}">{}</a>', url, obj.head_of_department.user.get_full_name())
        return '-'
    head_display.short_description = 'Head of Department'
    
    def staff_count(self, obj):
        count = obj.staff.filter(is_active=True, is_deleted=False).count()
        return format_html('<span class="badge badge-info">{}</span>', count)
    staff_count.short_description = 'Staff'


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['user_link', 'employee_id', 'profession_badge', 'department', 'locum_badge', 'age_display', 'phone_number', 'employment_status', 'is_active']
    list_filter = ['profession', 'department', 'employment_status', 'is_locum', 'is_active', 'gender', 'blood_group']
    search_fields = ['user__first_name', 'user__last_name', 'employee_id', 'phone_number', 'personal_email']
    ordering = ['user__last_name', 'user__first_name']
    readonly_fields = ['employee_id', 'age_display', 'years_of_service_display', 'retirement_date_display']
    
    def get_queryset(self, request):
        """Override to prevent duplicate staff records - only show most recent per user"""
        from hospital.utils_roles import get_deduplicated_staff_queryset
        # Get deduplicated queryset - admin shows all (active and inactive)
        return get_deduplicated_staff_queryset()
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'employee_id', 'profession', 'department', 'employment_status', 'is_locum', 'is_active')
        }),
        ('Professional Details', {
            'fields': ('specialization', 'registration_number', 'license_number')
        }),
        ('Personal Information', {
            'fields': (
                ('date_of_birth', 'age_display'),
                ('gender', 'blood_group'),
                'marital_status',
            )
        }),
        ('Contact Information', {
            'fields': (
                'phone_number',
                'personal_email',
                'address',
                'city',
            )
        }),
        ('Emergency Contact', {
            'fields': (
                'emergency_contact_name',
                'emergency_contact_relationship',
                'emergency_contact_phone',
            )
        }),
        ('Employment Details', {
            'fields': (
                ('date_of_joining', 'years_of_service_display'),
                'retirement_date_display',
            )
        }),
        ('Banking Information', {
            'fields': (
                'bank_name',
                'bank_account_number',
                'bank_branch',
            ),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('staff_notes',),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        # Show full name, or username if name is empty
        display_name = obj.user.get_full_name() or obj.user.username
        return format_html('<a href="{}">{}</a>', url, display_name)
    user_link.short_description = 'User'
    
    def profession_badge(self, obj):
        colors = {
            'doctor': 'danger',
            'nurse': 'success',
            'pharmacist': 'warning',
            'lab_technician': 'info'
        }
        color = colors.get(obj.profession, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_profession_display())
    profession_badge.short_description = 'Profession'
    
    def locum_badge(self, obj):
        color = 'success' if obj.is_locum else 'secondary'
        label = 'Locum' if obj.is_locum else 'Staff'
        return format_html('<span class="badge badge-{}">{}</span>', color, label)
    locum_badge.short_description = 'Locum'
    
    def age_display(self, obj):
        if obj.age:
            return f"{obj.age} years"
        return "-"
    age_display.short_description = 'Age'
    
    def years_of_service_display(self, obj):
        if obj.years_of_service:
            return f"{obj.years_of_service} years"
        return "-"
    years_of_service_display.short_description = 'Years of Service'
    
    def retirement_date_display(self, obj):
        if obj.retirement_date:
            return obj.retirement_date.strftime('%B %d, %Y')
        return "-"
    retirement_date_display.short_description = 'Expected Retirement'


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'ward_type_badge', 'department', 'capacity', 'bed_availability', 'is_active']
    list_filter = ['ward_type', 'department', 'is_active']
    search_fields = ['name', 'code']
    ordering = ['name']
    
    def ward_type_badge(self, obj):
        return format_html('<span class="badge badge-info">{}</span>', obj.get_ward_type_display())
    ward_type_badge.short_description = 'Type'
    
    def bed_availability(self, obj):
        beds = obj.beds.filter(is_active=True, is_deleted=False)
        total = beds.count()
        available = beds.filter(status='available').count()
        occupied = beds.filter(status='occupied').count()
        return format_html(
            '<span style="color: #48bb78;">{} available</span> / <span style="color: #f56565;">{} occupied</span> / {} total',
            available, occupied, total
        )
    bed_availability.short_description = 'Bed Status'


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ['bed_number', 'ward_link', 'bed_type', 'status_badge', 'is_active']
    list_filter = ['bed_type', 'status', 'ward', 'is_active']
    search_fields = ['bed_number', 'ward__name']
    ordering = ['ward', 'bed_number']
    
    def ward_link(self, obj):
        url = reverse('admin:hospital_ward_change', args=[obj.ward.pk])
        return format_html('<a href="{}">{}</a>', url, obj.ward.name)
    ward_link.short_description = 'Ward'
    
    def status_badge(self, obj):
        colors = {'available': 'success', 'occupied': 'danger', 'maintenance': 'warning', 'reserved': 'info'}
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ['patient_link', 'ward', 'bed', 'admit_date', 'status_badge', 'duration', 'admitting_doctor', 'actions_column']
    list_filter = ['status', 'admit_date', 'ward', 'admitting_doctor__department']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name']
    ordering = ['-admit_date']
    readonly_fields = ['admit_date', 'created', 'modified', 'duration_display']
    actions = [discharge_admissions, export_as_csv]
    
    def patient_link(self, obj):
        url = reverse('admin:hospital_patient_change', args=[obj.encounter.patient.pk])
        return format_html('<a href="{}">{}</a>', url, obj.encounter.patient.full_name)
    patient_link.short_description = 'Patient'
    
    def status_badge(self, obj):
        colors = {'admitted': 'success', 'discharged': 'secondary', 'transferred': 'info'}
        color = colors.get(obj.status, 'warning')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'
    
    def duration(self, obj):
        days = obj.get_duration_days()
        return f'{days} days'
    duration.short_description = 'Duration'
    
    def duration_display(self, obj):
        return self.duration(obj)
    duration_display.short_description = 'Length of Stay'
    
    def actions_column(self, obj):
        if obj.status == 'admitted':
            return format_html(
                '<a href="{}" class="button" style="padding: 4px 8px; font-size: 11px; background: #f56565;">Discharge</a>',
                reverse('admin:hospital_admission_change', args=[obj.pk])
            )
        return '-'
    actions_column.short_description = 'Actions'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['encounter_link', 'order_type_badge', 'status_badge', 'priority_badge', 'requested_by', 'requested_at']
    list_filter = ['order_type', 'status', 'priority', 'requested_at', 'requested_by__department']
    search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name']
    ordering = ['-requested_at']
    readonly_fields = ['requested_at', 'created', 'modified']
    
    def encounter_link(self, obj):
        url = reverse('admin:hospital_encounter_change', args=[obj.encounter.pk])
        return format_html('<a href="{}">{}</a>', url, obj.encounter.patient.full_name)
    encounter_link.short_description = 'Encounter'
    
    def order_type_badge(self, obj):
        colors = {'lab': 'info', 'imaging': 'warning', 'medication': 'success', 'procedure': 'danger'}
        color = colors.get(obj.order_type, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_order_type_display())
    order_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {'pending': 'warning', 'in_progress': 'info', 'completed': 'success', 'cancelled': 'danger'}
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'
    
    def priority_badge(self, obj):
        colors = {'routine': 'secondary', 'urgent': 'warning', 'stat': 'danger'}
        color = colors.get(obj.priority, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_priority_display())
    priority_badge.short_description = 'Priority'


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'specimen_type', 'tat_display', 'price_display', 'is_active_badge']
    list_filter = ['specimen_type', 'is_active', 'created']
    search_fields = ['code', 'name']
    ordering = ['name']
    readonly_fields = ['created', 'modified']
    actions = ['activate_tests', 'deactivate_tests', 'bulk_set_price']
    
    fieldsets = (
        ('Test Information', {
            'fields': ('code', 'name', 'specimen_type')
        }),
        ('Pricing & Timing', {
            'fields': ('price', 'tat_minutes')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def tat_display(self, obj):
        hours = obj.tat_minutes // 60
        minutes = obj.tat_minutes % 60
        if hours > 0:
            return f'{hours}h {minutes}m'
        return f'{minutes}m'
    tat_display.short_description = 'Turnaround Time'
    
    def price_display(self, obj):
        if obj.price > 0:
            return format_html('<strong style="color: green;">${}</strong>', obj.price)
        return format_html('<strong style="color: red;">Not Set</strong>')
    price_display.short_description = 'Price'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: gray;">✗ Inactive</span>')
    is_active_badge.short_description = 'Status'
    
    def activate_tests(self, request, queryset):
        """Activate selected lab tests"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} lab test(s) activated successfully.')
    activate_tests.short_description = 'Activate selected tests'
    
    def deactivate_tests(self, request, queryset):
        """Deactivate selected lab tests"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} lab test(s) deactivated successfully.')
    deactivate_tests.short_description = 'Deactivate selected tests'
    
    def bulk_set_price(self, request, queryset):
        """Redirect to bulk pricing page (implement if needed)"""
        self.message_user(request, 'Use the Pricing Management dashboard for bulk price updates: /hms/pricing/')
    bulk_set_price.short_description = 'Bulk update prices →'


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ['patient_link', 'test_name', 'status_badge', 'value_display', 'is_abnormal_badge', 'verified_by', 'verified_at', 'sms_status']
    list_filter = ['status', 'is_abnormal', 'verified_at', 'test', 'created']
    search_fields = ['order__encounter__patient__first_name', 'order__encounter__patient__last_name', 'test__name', 'value']
    ordering = ['-created']
    readonly_fields = ['created', 'modified', 'order_link', 'patient_info', 'test_info', 'auto_abnormal_check']
    actions = ['send_sms_notification']
    
    def send_sms_notification(self, request, queryset):
        """Send SMS notification for selected lab results"""
        from .services.sms_service import sms_service
        success_count = 0
        fail_count = 0
        
        for lab_result in queryset:
            if lab_result.status != 'completed':
                fail_count += 1
                continue
            
            try:
                sms_log = sms_service.send_lab_result_ready(lab_result)
                if sms_log.status == 'sent':
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
        
        if success_count > 0:
            self.message_user(request, f'{success_count} SMS notification(s) sent successfully.')
        if fail_count > 0:
            self.message_user(request, f'{fail_count} SMS notification(s) failed to send.', level='warning')
    
    send_sms_notification.short_description = "Send SMS notification for selected lab results"
    
    def sms_status(self, obj):
        """Show SMS sending status for this lab result"""
        from .models_advanced import SMSLog
        try:
            sms_log = SMSLog.objects.filter(
                related_object_id=obj.pk,
                related_object_type='LabResult',
                is_deleted=False
            ).order_by('-created').first()
            
            if sms_log:
                if sms_log.status == 'sent':
                    return format_html(
                        '<span class="badge badge-success">SMS Sent</span><br>'
                        '<small>{}</small>',
                        sms_log.sent_at.strftime('%Y-%m-%d %H:%M') if sms_log.sent_at else 'Pending'
                    )
                elif sms_log.status == 'failed':
                    return format_html(
                        '<span class="badge badge-danger">SMS Failed</span><br>'
                        '<small>{}</small>',
                        sms_log.error_message[:50] if sms_log.error_message else 'Unknown error'
                    )
            return format_html('<span class="badge badge-secondary">Not Sent</span>')
        except Exception:
            return '-'
    sms_status.short_description = 'SMS Status'
    
    def get_queryset(self, request):
        """Optimize queryset to avoid permission issues"""
        qs = super().get_queryset(request)
        return qs.select_related('order', 'order__encounter', 'order__encounter__patient', 'test', 'verified_by')
    
    # Explicitly allow access - Django defaults require change permission
    def has_module_permission(self, request):
        """Allow access to LabResult module if user is staff"""
        return request.user.is_active and request.user.is_staff
    
    def has_view_permission(self, request, obj=None):
        """Allow viewing if user is staff"""
        return request.user.is_active and request.user.is_staff
    
    def has_add_permission(self, request):
        """Allow adding if user is staff"""
        return request.user.is_active and request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        """Allow editing if user is staff (verified results need superuser)"""
        if not (request.user.is_active and request.user.is_staff):
            return False
        # If result is verified, only superusers can edit
        if obj and hasattr(obj, 'verified_at') and obj.verified_at and not request.user.is_superuser:
            return False
        return True
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete"""
        return request.user.is_active and request.user.is_superuser
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_link', 'patient_info', 'test_info')
        }),
        ('Test Result', {
            'fields': ('status', 'value', 'units', 'range_low', 'range_high', 'auto_abnormal_check', 'is_abnormal')
        }),
        ('Verification', {
            'fields': ('verified_by', 'verified_at', 'notes'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        # Add SMS button link at top
        return fieldsets
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        # If result is verified, make verification fields readonly
        if obj and obj.verified_at:
            readonly.extend(['verified_by', 'verified_at', 'status', 'value', 'units', 'range_low', 'range_high', 'is_abnormal'])
        return readonly
    
    def get_urls(self):
        """Add custom URL for sending SMS"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<uuid:object_id>/send-sms/', self.admin_site.admin_view(self.send_sms_view), name='hospital_labresult_send_sms'),
        ]
        return custom_urls + urls
    
    def send_sms_view(self, request, object_id):
        """Send SMS from admin page"""
        from django.shortcuts import redirect
        from django.contrib import messages
        from .services.sms_service import sms_service
        
        lab_result = self.get_object(request, object_id)
        if not lab_result:
            messages.error(request, 'Lab result not found')
            return redirect('admin:hospital_labresult_changelist')
        
        try:
            patient = lab_result.order.encounter.patient
            if not patient.phone_number or not patient.phone_number.strip():
                messages.error(request, f'Patient {patient.full_name} does not have a phone number')
            else:
                sms_log = sms_service.send_lab_result_ready(lab_result)
                if sms_log.status == 'sent':
                    messages.success(request, f'SMS sent successfully to {patient.full_name} ({patient.phone_number})')
                else:
                    messages.error(request, f'Failed to send SMS: {sms_log.error_message or "Unknown error"}')
        except AttributeError as e:
            messages.error(request, f'Error: Lab result does not have required patient information')
        except Exception as e:
            messages.error(request, f'Error sending SMS: {str(e)}')
        
        return redirect('admin:hospital_labresult_change', object_id)
    
    def order_link(self, obj):
        if not obj or not hasattr(obj, 'order') or not obj.order:
            return '-'
        try:
            # Don't check permissions for reversing URLs - just show the link or ID
            try:
                url = reverse('admin:hospital_order_change', args=[obj.order.pk])
                return format_html('<a href="{}">Order #{}</a>', url, obj.order_id)
            except Exception:
                return format_html('Order #{}', obj.order_id)
        except Exception:
            return '-'
    order_link.short_description = 'Order'
    
    def patient_info(self, obj):
        if not obj or not hasattr(obj, 'order') or not obj.order:
            return '-'
        try:
            order = obj.order
            if not hasattr(order, 'encounter') or not order.encounter:
                return '-'
            encounter = order.encounter
            if not hasattr(encounter, 'patient') or not encounter.patient:
                return '-'
            patient = encounter.patient
            try:
                url = reverse('admin:hospital_patient_change', args=[patient.pk])
                return format_html(
                    '<strong><a href="{}">{}</a></strong><br>'
                    '<small>MRN: {} | DOB: {}</small>',
                    url, patient.full_name or 'Unknown', patient.mrn or '-', 
                    patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else '-'
                )
            except Exception:
                return format_html(
                    '<strong>{}</strong><br>'
                    '<small>MRN: {} | DOB: {}</small>',
                    patient.full_name or 'Unknown', patient.mrn or '-',
                    patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else '-'
                )
        except Exception:
            return '-'
    patient_info.short_description = 'Patient Information'
    
    def test_info(self, obj):
        if obj and obj.test:
            return format_html(
                '<strong>{}</strong><br>'
                '<small>Code: {} | Category: {}</small>',
                obj.test.name, obj.test.code or '-', obj.test.category or '-'
            )
        return '-'
    test_info.short_description = 'Test Information'
    
    def auto_abnormal_check(self, obj):
        if obj and obj.value and obj.range_low and obj.range_high:
            try:
                value = float(obj.value)
                low = float(obj.range_low)
                high = float(obj.range_high)
                is_normal = low <= value <= high
                if is_normal:
                    return format_html('<span class="badge badge-success">Within Normal Range</span>')
                else:
                    return format_html('<span class="badge badge-danger">Outside Normal Range</span>')
            except (ValueError, TypeError):
                pass
        return format_html('<small class="text-muted">Enter value and ranges to check</small>')
    auto_abnormal_check.short_description = 'Range Check'
    
    def patient_link(self, obj):
        if obj and obj.order and obj.order.encounter:
            patient = obj.order.encounter.patient
            url = reverse('admin:hospital_patient_change', args=[patient.pk])
            return format_html('<a href="{}">{}</a>', url, patient.full_name)
        return '-'
    patient_link.short_description = 'Patient'
    
    def test_name(self, obj):
        if obj and obj.test:
            return obj.test.name
        return '-'
    test_name.short_description = 'Test'
    
    def status_badge(self, obj):
        if not obj:
            return '-'
        colors = {'pending': 'warning', 'in_progress': 'info', 'completed': 'success', 'cancelled': 'danger'}
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'
    
    def value_display(self, obj):
        if not obj or not obj.value:
            return '-'
        display = obj.value
        if obj.units:
            display += f' {obj.units}'
        if obj.range_low and obj.range_high:
            display += f' (Range: {obj.range_low}-{obj.range_high})'
        return format_html('{}', display)
    value_display.short_description = 'Result'
    
    def is_abnormal_badge(self, obj):
        if not obj:
            return '-'
        if obj.is_abnormal:
            return format_html('<span class="badge badge-danger">Abnormal</span>')
        return format_html('<span class="badge badge-success">Normal</span>')
    is_abnormal_badge.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        # Auto-verify if status is set to completed
        if obj.status == 'completed' and not obj.verified_at:
            obj.verified_by = getattr(request.user, 'staff_profile', None)
            obj.verified_at = timezone.now()
        # Auto-check abnormal status based on ranges
        if obj.value and obj.range_low and obj.range_high:
            try:
                value = float(obj.value)
                low = float(obj.range_low)
                high = float(obj.range_high)
                obj.is_abnormal = not (low <= value <= high)
            except (ValueError, TypeError):
                pass
        super().save_model(request, obj, form, change)
    
    def response_change(self, request, obj):
        """Add SMS send button to response"""
        from django.utils.html import format_html
        from django.urls import reverse
        
        # Add custom button for sending SMS if result is completed
        if obj.status == 'completed':
            try:
                patient = obj.order.encounter.patient
                if patient.phone_number:
                    send_sms_url = reverse('admin:hospital_labresult_send_sms', args=[obj.pk])
                    msg = format_html(
                        '<div style="margin: 10px 0; padding: 10px; background: #e3f2fd; border-left: 4px solid #2196f3;">'
                        '<strong>Send SMS Notification:</strong> '
                        '<a href="{}" class="button" style="margin-left: 10px;">📱 Send SMS to {}</a>'
                        '</div>',
                        send_sms_url, patient.full_name
                    )
                    self.message_user(request, msg, extra_tags='', level='')
            except (AttributeError, Exception):
                pass
        
        return super().response_change(request, obj)


@admin.register(Drug)
class DrugAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_display', 'generic_name', 'strength', 'form', 'unit_price_display', 'cost_price_display', 'margin_display', 'controlled_badge', 'is_active']
    list_filter = ['category', 'form', 'is_controlled', 'is_active', 'created']
    search_fields = ['name', 'generic_name', 'atc_code', 'category']
    ordering = ['name']
    readonly_fields = ['created', 'modified']
    actions = ['activate_drugs', 'deactivate_drugs']
    
    fieldsets = (
        ('Drug Information', {
            'fields': ('atc_code', 'name', 'generic_name', 'category'),
            'description': 'Select the appropriate drug category. <a href="/hms/drug-classification-guide/" target="_blank">Browse Drug Classification Guide</a> to see all categories with descriptions.'
        }),
        ('Formulation', {
            'fields': ('strength', 'form', 'pack_size', 'is_controlled')
        }),
        ('Pricing', {
            'fields': ('unit_price', 'cost_price'),
            'description': 'Unit Price: Selling price per unit | Cost Price: Purchase cost from supplier'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def category_display(self, obj):
        """Display category with abbreviated name"""
        if hasattr(obj, 'category') and obj.category:
            # Show short category name (first part before dash)
            category_name = obj.get_category_display()
            if ' - ' in category_name:
                return category_name.split(' - ')[0]
            return category_name
        return '-'
    category_display.short_description = 'Category'
    
    def unit_price_display(self, obj):
        price = getattr(obj, 'unit_price', 0)
        if price > 0:
            return format_html('<strong style="color: green;">${}</strong>', price)
        return format_html('<strong style="color: red;">Not Set</strong>')
    unit_price_display.short_description = 'Unit Price'
    
    def cost_price_display(self, obj):
        cost = getattr(obj, 'cost_price', 0)
        if cost > 0:
            return format_html('<span style="color: blue;">${}</span>', cost)
        return format_html('<span style="color: gray;">-</span>')
    cost_price_display.short_description = 'Cost'
    
    def margin_display(self, obj):
        unit_price = getattr(obj, 'unit_price', 0)
        cost_price = getattr(obj, 'cost_price', 0)
        if unit_price > 0 and cost_price > 0:
            margin = unit_price - cost_price
            margin_pct = (margin / cost_price) * 100 if cost_price > 0 else 0
            color = 'green' if margin > 0 else 'red'
            return format_html(
                '<span style="color: {};">${} ({}%)</span>',
                color, round(margin, 2), round(margin_pct, 1)
            )
        return '-'
    margin_display.short_description = 'Profit'
    
    def controlled_badge(self, obj):
        if obj.is_controlled:
            return format_html('<span class="badge badge-danger">Controlled</span>')
        return format_html('<span class="badge badge-success">Regular</span>')
    controlled_badge.short_description = 'Type'
    
    def activate_drugs(self, request, queryset):
        """Activate selected drugs"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'✅ {updated} drug(s) activated successfully.')
    activate_drugs.short_description = 'Activate selected drugs'
    
    def deactivate_drugs(self, request, queryset):
        """Deactivate selected drugs"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'✅ {updated} drug(s) deactivated successfully.')
    deactivate_drugs.short_description = 'Deactivate selected drugs'


class PharmacyStockAdminForm(forms.ModelForm):
    """Allow empty batch_number - will be auto-generated on save"""
    class Meta:
        model = PharmacyStock
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields.get('batch_number'):
            self.fields['batch_number'].required = False
            self.fields['batch_number'].help_text = 'Leave blank to auto-generate (e.g. BATCH-20260309-0001)'
        if self.fields.get('drug'):
            self.fields['drug'].help_text = 'Click the box, then type drug name (e.g. paracetamol) to search'


@admin.register(PharmacyStock)
class PharmacyStockAdmin(admin.ModelAdmin):
    form = PharmacyStockAdminForm
    list_display = ['drug_link', 'batch_number', 'expiry_date', 'quantity_display', 'reorder_level', 'location', 'stock_status']
    list_filter = ['location', 'expiry_date', 'drug__form']
    search_fields = ['drug__name', 'batch_number']
    ordering = ['drug__name', 'expiry_date']
    autocomplete_fields = ['drug']

    def save_model(self, request, obj, form, change):
        # Auto-generate batch number if empty
        if not obj.batch_number or not str(obj.batch_number).strip():
            from django.utils import timezone
            dt = timezone.now()
            prefix = f"BATCH-{dt.strftime('%Y%m%d')}"
            same_prefix = PharmacyStock.objects.filter(
                batch_number__startswith=prefix,
                is_deleted=False
            ).count()
            obj.batch_number = f"{prefix}-{same_prefix + 1:04d}"
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        """Only admins can edit stock - restrict procurement/pharmacy from changing quantities"""
        from .views_procurement import is_admin_user
        if not is_admin_user(request.user):
            return False
        return super().has_change_permission(request, obj)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('drug')
    
    def drug_link(self, obj):
        url = reverse('admin:hospital_drug_change', args=[obj.drug.pk])
        return format_html('<a href="{}">{}</a>', url, obj.drug.name)
    drug_link.short_description = 'Drug'
    
    def quantity_display(self, obj):
        if obj.quantity_on_hand <= obj.reorder_level:
            return format_html('<span style="color: #f56565; font-weight: bold;">{}</span>', obj.quantity_on_hand)
        return obj.quantity_on_hand
    quantity_display.short_description = 'Quantity'
    
    def stock_status(self, obj):
        from django.utils import timezone
        if obj.expiry_date < timezone.now().date():
            return format_html('<span class="badge badge-danger">Expired</span>')
        elif obj.quantity_on_hand <= obj.reorder_level:
            return format_html('<span class="badge badge-warning">Low Stock</span>')
        return format_html('<span class="badge badge-success">In Stock</span>')
    stock_status.short_description = 'Status'


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['patient_link', 'drug_link', 'quantity', 'dose', 'frequency', 'prescribed_by', 'created']
    list_filter = ['prescribed_by__department', 'created']
    search_fields = ['order__encounter__patient__first_name', 'order__encounter__patient__last_name', 'drug__name']
    ordering = ['-created']
    actions = ['send_to_cashier']
    
    def patient_link(self, obj):
        patient = obj.order.encounter.patient
        url = reverse('admin:hospital_patient_change', args=[patient.pk])
        return format_html('<a href="{}">{}</a>', url, patient.full_name)
    patient_link.short_description = 'Patient'
    
    def drug_link(self, obj):
        url = reverse('admin:hospital_drug_change', args=[obj.drug.pk])
        return format_html('<a href="{}">{}</a>', url, obj.drug.name)
    drug_link.short_description = 'Drug'

    def send_to_cashier(self, request, queryset):
        """Create cashier bills for selected prescriptions without leaving admin."""
        queued = 0
        already_paid = 0
        errors = 0
        
        for prescription in queryset:
            try:
                dispensing_record = prescription.dispensing_record
            except (PharmacyDispensing.DoesNotExist, AttributeError):
                dispensing_record = None
            
            if dispensing_record:
                if dispensing_record.payment_receipt:
                    already_paid += 1
                    continue
                if dispensing_record.dispensing_status == 'cancelled':
                    errors += 1
                    continue
                # Queue exists: actually push invoice to cashier (previously this branch did nothing)
                result = AutoBillingService.create_pharmacy_bill(prescription)
                if result.get('success'):
                    queued += 1
                else:
                    errors += 1
                continue

            # Bill may only be created after a pharmacy queue row exists (doctor/signal or explicit queue)
            ensure_queue = AutoBillingService.create_pharmacy_dispensing_record_only(prescription)
            if not ensure_queue.get('success'):
                errors += 1
                continue

            result = AutoBillingService.create_pharmacy_bill(prescription)
            if result.get('success'):
                queued += 1
            else:
                errors += 1
        
        cashier_url = reverse('hospital:cashier_patient_bills')
        message_parts = []
        if queued:
            message_parts.append(f'✅ {queued} item(s) queued for cashier')
        if already_paid:
            message_parts.append(f'💰 {already_paid} already paid')
        if errors:
            message_parts.append(f'⚠️ {errors} failed to queue')
        
        summary = ' | '.join(message_parts) or 'No prescriptions processed.'
        self.message_user(
            request,
            format_html('{} – <a href="{}" target="_blank">Open cashier dashboard</a>', summary, cashier_url)
        )
    send_to_cashier.short_description = 'Send selected prescriptions to cashier'


@admin.register(Payer)
class PayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'payer_type_badge', 'is_active']
    list_filter = ['payer_type', 'is_active']
    search_fields = ['name']
    ordering = ['name']
    
    def payer_type_badge(self, obj):
        colors = {'nhis': 'success', 'private': 'info', 'cash': 'warning', 'corporate': 'primary'}
        color = colors.get(obj.payer_type, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_payer_type_display())
    payer_type_badge.short_description = 'Type'


@admin.register(ServiceCode)
class ServiceCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'category', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['code', 'description']
    ordering = ['code']


# Register DiagnosisCode
try:
    from .models_diagnosis import DiagnosisCode
    
    @admin.register(DiagnosisCode)
    class DiagnosisCodeAdmin(admin.ModelAdmin):
        list_display = ['code', 'short_description', 'category', 'is_common', 'usage_count', 'is_active']
        list_filter = ['category', 'is_common', 'is_active', 'chapter']
        search_fields = ['code', 'description', 'short_description']
        ordering = ['-is_common', 'code']
        list_editable = ['is_common', 'is_active']
        readonly_fields = ['usage_count', 'created', 'modified']
        
        fieldsets = (
            ('Code Information', {
                'fields': ('code', 'short_description', 'description', 'category', 'chapter')
            }),
            ('Usage', {
                'fields': ('is_common', 'is_active', 'usage_count')
            }),
            ('System', {
                'fields': ('created', 'modified', 'is_deleted'),
                'classes': ('collapse',)
            }),
        )
        
        actions = ['mark_as_common', 'mark_as_not_common', 'activate', 'deactivate']
        
        def mark_as_common(self, request, queryset):
            updated = queryset.update(is_common=True)
            self.message_user(request, f'{updated} diagnoses marked as common.')
        mark_as_common.short_description = 'Mark as commonly used'
        
        def mark_as_not_common(self, request, queryset):
            updated = queryset.update(is_common=False)
            self.message_user(request, f'{updated} diagnoses unmarked as common.')
        mark_as_not_common.short_description = 'Remove from common list'
        
        def activate(self, request, queryset):
            updated = queryset.update(is_active=True)
            self.message_user(request, f'{updated} diagnoses activated.')
        activate.short_description = 'Activate selected diagnoses'
        
        def deactivate(self, request, queryset):
            updated = queryset.update(is_active=False)
            self.message_user(request, f'{updated} diagnoses deactivated.')
        deactivate.short_description = 'Deactivate selected diagnoses'
except ImportError:
    pass


@admin.register(PriceBook)
class PriceBookAdmin(admin.ModelAdmin):
    list_display = ['payer', 'service_code', 'unit_price', 'is_active']
    list_filter = ['payer', 'is_active']
    search_fields = ['payer__name', 'service_code__description']
    ordering = ['payer', 'service_code']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'patient_link', 'payer', 'status_badge', 'total_amount', 'balance_display', 'issued_at', 'due_date_warning']
    list_filter = ['status', 'issued_at', 'payer']
    search_fields = ['invoice_number', 'patient__first_name', 'patient__last_name']
    ordering = ['-issued_at']
    readonly_fields = ['issued_at', 'created', 'modified', 'invoice_number']
    inlines = [InvoiceLineInline]
    actions = [mark_invoices_paid, mark_invoices_issued, export_as_csv]
    
    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoice_number', 'patient', 'encounter', 'payer', 'status')
        }),
        ('Financial Information', {
            'fields': ('total_amount', 'balance', 'issued_at', 'due_at')
        }),
    )
    
    def patient_link(self, obj):
        url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
        return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
    patient_link.short_description = 'Patient'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'issued': 'warning',
            'paid': 'success',
            'partially_paid': 'info',
            'overdue': 'danger',
            'cancelled': 'secondary'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'
    
    def balance_display(self, obj):
        balance_str = f"{float(obj.balance):.2f}"
        if obj.balance > 0:
            return format_html('<span style="color: #f56565; font-weight: bold;">GHS {}</span>', balance_str)
        return format_html('<span style="color: #48bb78;">GHS {}</span>', balance_str)
    balance_display.short_description = 'Balance'
    
    def due_date_warning(self, obj):
        days_overdue = obj.get_days_overdue()
        if days_overdue > 0:
            return format_html('<span class="badge badge-danger">{} days overdue</span>', days_overdue)
        elif obj.due_at and obj.due_at.date() < timezone.now().date():
            return format_html('<span class="badge badge-warning">Due</span>')
        return '-'
    due_date_warning.short_description = 'Due Status'


@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ['invoice_link', 'service_code', 'description', 'quantity', 'unit_price', 'line_total']
    list_filter = ['service_code__category']
    search_fields = ['invoice__invoice_number', 'description']
    ordering = ['invoice', 'created']
    
    def invoice_link(self, obj):
        url = reverse('admin:hospital_invoice_change', args=[obj.invoice.pk])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Invoice'


# ==================== NEW FEATURES ADMIN ====================

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['patient_link', 'provider_link', 'appointment_date', 'status_badge', 'department', 'reason_preview']
    list_filter = ['status', 'appointment_date', 'department']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn']
    ordering = ['-appointment_date']
    readonly_fields = ['created', 'modified']
    date_hierarchy = 'appointment_date'
    
    fieldsets = (
        ('Appointment Information', {
            'fields': ('patient', 'provider', 'department', 'appointment_date', 'duration_minutes', 'status')
        }),
        ('Details', {
            'fields': ('reason', 'notes', 'reminder_sent')
        }),
    )
    
    def patient_link(self, obj):
        url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
        return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
    patient_link.short_description = 'Patient'
    
    def provider_link(self, obj):
        url = reverse('admin:hospital_staff_change', args=[obj.provider.pk])
        return format_html('<a href="{}">{}</a>', url, obj.provider.user.get_full_name())
    provider_link.short_description = 'Provider'
    
    def status_badge(self, obj):
        colors = {
            'scheduled': 'info',
            'confirmed': 'success',
            'completed': 'secondary',
            'cancelled': 'danger',
            'no_show': 'warning'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_status_display())
    status_badge.short_description = 'Status'
    
    def reason_preview(self, obj):
        return obj.reason[:50] + '...' if len(obj.reason) > 50 else obj.reason
    reason_preview.short_description = 'Reason'


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ['title', 'patient_link', 'record_type_badge', 'encounter_link', 'created_by_link', 'created', 'has_document']
    list_filter = ['record_type', 'created']
    search_fields = ['title', 'patient__first_name', 'patient__last_name', 'patient__mrn', 'content']
    ordering = ['-created']
    readonly_fields = ['created', 'modified']
    
    fieldsets = (
        ('Record Information', {
            'fields': ('patient', 'encounter', 'record_type', 'title')
        }),
        ('Content', {
            'fields': ('content', 'document')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created', 'modified'),
            'classes': ('collapse',)
        }),
    )
    
    def patient_link(self, obj):
        url = reverse('admin:hospital_patient_change', args=[obj.patient.pk])
        return format_html('<a href="{}">{}</a>', url, obj.patient.full_name)
    patient_link.short_description = 'Patient'
    
    def encounter_link(self, obj):
        if obj.encounter:
            url = reverse('admin:hospital_encounter_change', args=[obj.encounter.pk])
            return format_html('<a href="{}">{}</a>', url, obj.encounter.get_encounter_type_display())
        return '-'
    encounter_link.short_description = 'Encounter'
    
    def created_by_link(self, obj):
        if obj.created_by:
            url = reverse('admin:hospital_staff_change', args=[obj.created_by.pk])
            return format_html('<a href="{}">{}</a>', url, obj.created_by.user.get_full_name())
        return '-'
    created_by_link.short_description = 'Created By'
    
    def record_type_badge(self, obj):
        return format_html('<span class="badge badge-info">{}</span>', obj.get_record_type_display())
    record_type_badge.short_description = 'Type'
    
    def has_document(self, obj):
        if obj.document:
            return format_html('<span class="badge badge-success">📄 Yes</span>')
        return format_html('<span class="badge badge-secondary">No</span>')
    has_document.short_description = 'Document'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient_link', 'notification_type_badge', 'is_read_badge', 'created']
    list_filter = ['notification_type', 'is_read', 'created']
    search_fields = ['title', 'message', 'recipient__username']
    ordering = ['-created']
    readonly_fields = ['read_at', 'created', 'modified']
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('recipient', 'notification_type', 'title', 'message')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Related Object', {
            'fields': ('related_object_type', 'related_object_id'),
            'classes': ('collapse',)
        }),
    )
    
    def recipient_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.recipient.pk])
        return format_html('<a href="{}">{}</a>', url, obj.recipient.username)
    recipient_link.short_description = 'Recipient'
    
    def notification_type_badge(self, obj):
        colors = {
            'appointment_reminder': 'info',
            'lab_result_ready': 'success',
            'invoice_overdue': 'danger',
            'low_stock': 'warning',
            'bed_available': 'success',
            'order_urgent': 'danger'
        }
        color = colors.get(obj.notification_type, 'secondary')
        return format_html('<span class="badge badge-{}">{}</span>', color, obj.get_notification_type_display())
    notification_type_badge.short_description = 'Type'
    
    def is_read_badge(self, obj):
        if obj.is_read:
            return format_html('<span class="badge badge-success">Read</span>')
        return format_html('<span class="badge badge-warning">Unread</span>')
    is_read_badge.short_description = 'Status'


# ==================== CUSTOM USER ADMIN ====================

class StaffInline(admin.StackedInline):
    model = Staff
    can_delete = False
    verbose_name_plural = 'Staff Profile'


class CustomUserAdmin(UserAdmin):
    inlines = (StaffInline,)
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ==================== AMBULANCE SYSTEM ADMIN ====================
try:
    from .models_ambulance import (
        AmbulanceServiceType, AmbulanceUnit, AmbulanceDispatch,
        AmbulanceBilling, AmbulanceServiceCharge, AmbulanceBillingItem
    )
    
    @admin.register(AmbulanceServiceType)
    class AmbulanceServiceTypeAdmin(admin.ModelAdmin):
        list_display = ('service_code', 'service_name', 'service_type', 'base_charge', 'per_mile_charge', 'is_active')
        list_filter = ('service_type', 'is_active')
        search_fields = ('service_code', 'service_name')
        list_editable = ('is_active',)
        readonly_fields = ('id',)
        
        fieldsets = (
            ('Service Information', {
                'fields': ('service_code', 'service_name', 'service_type', 'description')
            }),
            ('Pricing', {
                'fields': ('base_charge', 'per_mile_charge', 'emergency_surcharge', 'equipment_fee')
            }),
            ('Resources', {
                'fields': ('equipment_description', 'crew_size')
            }),
            ('Status', {
                'fields': ('is_active',)
            }),
        )
    
    @admin.register(AmbulanceUnit)
    class AmbulanceUnitAdmin(admin.ModelAdmin):
        list_display = ('unit_number', 'status', 'primary_paramedic', 'primary_emt', 'current_location', 'last_maintenance')
        list_filter = ('status', 'home_station')
        search_fields = ('unit_number', 'license_plate')
        filter_horizontal = ('service_capabilities',)
        
        fieldsets = (
            ('Unit Information', {
                'fields': ('unit_number', 'vehicle_make', 'vehicle_model', 'license_plate', 'year')
            }),
            ('Capabilities', {
                'fields': ('service_capabilities',)
            }),
            ('Current Status', {
                'fields': ('status', 'current_location', 'gps_latitude', 'gps_longitude')
            }),
            ('Crew', {
                'fields': ('primary_paramedic', 'primary_emt')
            }),
            ('Maintenance', {
                'fields': ('mileage', 'last_maintenance', 'next_maintenance_due')
            }),
            ('Station', {
                'fields': ('home_station',)
            }),
        )
    
    @admin.register(AmbulanceDispatch)
    class AmbulanceDispatchAdmin(admin.ModelAdmin):
        list_display = ('dispatch_number', 'ambulance_unit', 'call_type', 'priority', 'call_received_at', 'patient', 'patient_transported')
        list_filter = ('call_type', 'priority', 'patient_transported', 'call_received_at')
        search_fields = ('dispatch_number', 'patient__first_name', 'patient__last_name', 'pickup_address')
        date_hierarchy = 'call_received_at'
        readonly_fields = ('id', 'response_time_minutes', 'total_call_time_minutes')
        
        fieldsets = (
            ('Dispatch Information', {
                'fields': ('dispatch_number', 'ambulance_unit', 'call_type', 'priority', 'chief_complaint')
            }),
            ('Timeline', {
                'fields': ('call_received_at', 'dispatch_time', 'arrival_time', 'transport_start_time', 'hospital_arrival_time', 'call_completed_time'),
                'description': 'Complete timeline of the ambulance call'
            }),
            ('Performance Metrics', {
                'fields': ('response_time_minutes', 'total_call_time_minutes'),
                'classes': ('collapse',)
            }),
            ('Location Details', {
                'fields': ('pickup_address', 'pickup_latitude', 'pickup_longitude', 'destination_address', 'destination_latitude', 'destination_longitude', 'miles_traveled')
            }),
            ('Patient Information', {
                'fields': ('patient', 'encounter')
            }),
            ('Pre-Hospital Care', {
                'fields': ('pre_hospital_report', 'vital_signs_on_scene', 'treatments_administered')
            }),
            ('Outcome', {
                'fields': ('patient_transported', 'transport_refused', 'patient_deceased_on_scene')
            }),
            ('Documentation', {
                'fields': ('pcr_completed', 'run_report_notes')
            }),
        )
    
    @admin.register(AmbulanceBilling)
    class AmbulanceBillingAdmin(admin.ModelAdmin):
        list_display = ('invoice_number', 'dispatch', 'patient', 'service_type', 'total_amount', 'amount_paid', 'balance', 'status')
        list_filter = ('status', 'insurance_claim_filed', 'invoice_date')
        search_fields = ('invoice_number', 'patient__first_name', 'patient__last_name', 'dispatch__dispatch_number')
        date_hierarchy = 'invoice_date'
        readonly_fields = ('id', 'invoice_number', 'subtotal', 'total_amount', 'balance')
        
        fieldsets = (
            ('Billing Reference', {
                'fields': ('invoice_number', 'dispatch', 'service_type', 'patient', 'encounter', 'department')
            }),
            ('Base Charges', {
                'fields': ('base_charge', 'miles_traveled', 'mileage_charge', 'emergency_surcharge', 'equipment_fees')
            }),
            ('Additional Charges', {
                'fields': ('oxygen_charge', 'iv_fluids_charge', 'medical_supplies_charge', 'wait_time_fee', 'other_charges'),
                'classes': ('collapse',)
            }),
            ('Totals', {
                'fields': ('subtotal', 'tax_amount', 'total_amount')
            }),
            ('Payment Information', {
                'fields': ('amount_paid', 'balance', 'status', 'invoice_date', 'payment_date')
            }),
            ('Insurance', {
                'fields': ('insurance_claim_filed', 'insurance_approved_amount'),
                'classes': ('collapse',)
            }),
            ('Notes', {
                'fields': ('billing_notes',),
                'classes': ('collapse',)
            }),
        )
        
        actions = ['mark_as_paid', 'generate_invoice']
        
        def mark_as_paid(self, request, queryset):
            for bill in queryset:
                bill.amount_paid = bill.total_amount
                bill.save()
            self.message_user(request, f"{queryset.count()} bills marked as paid")
        mark_as_paid.short_description = "Mark selected bills as paid"
    
    @admin.register(AmbulanceServiceCharge)
    class AmbulanceServiceChargeAdmin(admin.ModelAdmin):
        list_display = ('charge_code', 'charge_name', 'charge_type', 'unit_price', 'unit_of_measure', 'is_active')
        list_filter = ('charge_type', 'is_active')
        search_fields = ('charge_code', 'charge_name')
        list_editable = ('is_active',)
    
    @admin.register(AmbulanceBillingItem)
    class AmbulanceBillingItemAdmin(admin.ModelAdmin):
        list_display = ('billing', 'service_charge', 'quantity', 'unit_price', 'total_price')
        list_filter = ('service_charge__charge_type',)
        search_fields = ('billing__invoice_number',)
        readonly_fields = ('total_price',)

except ImportError as e:
    print(f"Ambulance models not yet migrated: {e}")


# ==================== ADMIN SITE CUSTOMIZATION ====================

class CustomAdminSite(admin.AdminSite):
    site_header = "🏥 PrimeCare Medical Center - Admin"
    site_title = "PrimeCare Medical Center"
    index_title = "Welcome to PrimeCare Medical Center"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='hms_dashboard'),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        """Custom admin dashboard with statistics"""
        from django.db.models import Count, Sum, Q
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        this_month = today.replace(day=1)
        
        context = {
            'total_patients': Patient.objects.filter(is_deleted=False).count(),
            'total_encounters': Encounter.objects.filter(is_deleted=False).count(),
            'active_encounters': Encounter.objects.filter(status='active', is_deleted=False).count(),
            'current_admissions': Admission.objects.filter(status='admitted', is_deleted=False).count(),
            'total_invoices': Invoice.objects.filter(is_deleted=False).count(),
            'total_revenue': Invoice.objects.filter(status='paid', is_deleted=False).aggregate(
                total=Sum('total_amount')
            )['total'] or 0,
            'outstanding_balance': Invoice.objects.filter(
                status__in=['issued', 'partially_paid', 'overdue'],
                is_deleted=False
            ).aggregate(total=Sum('balance'))['total'] or 0,
            'patients_today': Patient.objects.filter(created__date=today, is_deleted=False).count(),
            'encounters_today': Encounter.objects.filter(started_at__date=today, is_deleted=False).count(),
            'recent_patients': Patient.objects.filter(is_deleted=False).order_by('-created')[:5],
            'recent_encounters': Encounter.objects.filter(is_deleted=False).select_related('patient').order_by('-started_at')[:5],
            'overdue_invoices': Invoice.objects.filter(status='overdue', is_deleted=False)[:5],
            'available_beds': Bed.objects.filter(status='available', is_active=True, is_deleted=False).count(),
            'total_beds': Bed.objects.filter(is_active=True, is_deleted=False).count(),
        }
        
        return TemplateResponse(request, 'admin/hms_dashboard.html', context)


# Use default admin site with customizations
admin.site.site_header = "🏥 PrimeCare Medical Center - Admin"
admin.site.site_title = "PrimeCare Medical Center"
admin.site.index_title = "Welcome to PrimeCare Medical Center"

# Harden Django Admin access:
# Pharmacists (and other non-admin/IT staff) must NOT be able to access /admin/,
# except: Admin/IT groups and Finance/Account roles (accountant, senior_account_officer, etc.)
def _primecare_admin_has_permission(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    # Explicit usernames that always get finance/account admin access (no group required)
    if user.username and user.username.lower() in ('finance', 'accountant', 'ebenezer.donkor'):
        _ensure_staff_for_admin(user)
        return True
    # Allow Admin / IT groups
    admin_it_groups = {'admin', 'administrator', 'it', 'it_staff', 'it_operations', 'it_support'}
    # Allow Finance / Account groups and roles so they can access Insurance Receivable and accounting admin
    finance_account_groups = {'accountant', 'finance', 'senior_account_officer', 'account_officer', 'account_personnel'}
    allowed_groups = admin_it_groups | finance_account_groups
    for g in user.groups.values_list('name', flat=True):
        if not g:
            continue
        normalized = g.lower().replace(' ', '_').replace('&', '_')
        if normalized in allowed_groups:
            _ensure_staff_for_admin(user)
            return True
        if 'account' in normalized or 'finance' in normalized:
            _ensure_staff_for_admin(user)
            return True
    # Also allow by role (Staff profession or role detection) so finance/account users get in even without group
    try:
        from .utils_roles import get_user_role
        role = get_user_role(user)
        if role in ('accountant', 'senior_account_officer', 'account_officer', 'account_personnel'):
            _ensure_staff_for_admin(user)
            return True
    except Exception:
        pass
    # By Staff profession: any profession containing "account" or "finance"
    try:
        from .models import Staff
        staff = Staff.objects.filter(user=user, is_deleted=False).first()
        if staff and staff.profession:
            p = (staff.profession or '').lower()
            if 'account' in p or 'finance' in p:
                _ensure_staff_for_admin(user)
                return True
    except Exception:
        pass
    return False


def _ensure_staff_for_admin(user):
    """Set is_staff=True so Django admin views (staff_member_required) allow access without redirect to login."""
    if getattr(user, 'is_staff', False):
        return
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.filter(pk=user.pk).update(is_staff=True)
        user.is_staff = True
    except Exception:
        pass

# Apply the permission gate to the admin site globally
admin.site.has_permission = _primecare_admin_has_permission

# Override admin index view to include statistics
from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse

original_index = admin.site.index

@staff_member_required
def custom_admin_index(request, extra_context=None):
    """Custom admin index - accounting-friendly for accountants, standard for others"""
    from .utils_roles import get_user_role
    
    user_role = get_user_role(request.user)
    
    # Check if user is accountant - show accounting-friendly interface
    # Also check if superuser has accountant profession (for Robbert)
    is_accountant_user = False
    if user_role == 'accountant':
        is_accountant_user = True
    elif request.user.is_superuser:
        # Check if superuser has accountant profession
        try:
            from .models import Staff
            staff = Staff.objects.filter(user=request.user, is_deleted=False).first()
            if staff and staff.profession == 'accountant':
                is_accountant_user = True
        except:
            pass
    
    if is_accountant_user:
        try:
            from .admin_accounting_friendly import accounting_friendly_admin_index
            return accounting_friendly_admin_index(request, extra_context)
        except ImportError:
            pass  # Fall through to default if module not available
    
    # For others (superusers, admins), show standard admin with statistics
    from django.db.models import Sum
    
    extra_context = extra_context or {}
    extra_context.update({
        'total_patients': Patient.objects.filter(is_deleted=False).count(),
        'total_encounters': Encounter.objects.filter(is_deleted=False).count(),
        'active_encounters': Encounter.objects.filter(status='active', is_deleted=False).count(),
        'current_admissions': Admission.objects.filter(status='admitted', is_deleted=False).count(),
        'total_invoices': Invoice.objects.filter(is_deleted=False).count(),
        'total_revenue': Invoice.objects.filter(status='paid', is_deleted=False).aggregate(
            total=Sum('total_amount')
        )['total'] or 0,
        'outstanding_balance': Invoice.objects.filter(
            status__in=['issued', 'partially_paid', 'overdue'],
            is_deleted=False
        ).aggregate(total=Sum('balance'))['total'] or 0,
        'patients_today': Patient.objects.filter(created__date=timezone.now().date(), is_deleted=False).count(),
        'encounters_today': Encounter.objects.filter(started_at__date=timezone.now().date(), is_deleted=False).count(),
        'recent_patients': Patient.objects.filter(is_deleted=False).order_by('-created')[:5],
        'recent_encounters': Encounter.objects.filter(is_deleted=False).select_related('patient').order_by('-started_at')[:5],
        'overdue_invoices': Invoice.objects.filter(status='overdue', is_deleted=False)[:5],
        'available_beds': Bed.objects.filter(status='available', is_active=True, is_deleted=False).count(),
        'total_beds': Bed.objects.filter(is_active=True, is_deleted=False).count(),
    })
    
    return original_index(request, extra_context)

admin.site.index = custom_admin_index

# Import and register advanced admin classes
try:
    from . import admin_advanced  # noqa
    from . import admin_insurance  # noqa
except ImportError:
    pass

# Import and register workflow and accounting admin classes
try:
    from . import admin_workflow  # noqa
    from . import admin_accounting  # noqa
    from . import admin_hr  # noqa
    from . import admin_reminders  # noqa
    from . import admin_specialists  # noqa
except ImportError:
    pass

# Import procurement admin
try:
    from . import admin_procurement  # noqa
except ImportError:
    pass

# Import pricing admin
try:
    from . import admin_pricing  # noqa
except ImportError:
    pass

# Import notification admin
try:
    from . import admin_notification  # noqa
except ImportError:
    pass

# Import walk-in pharmacy admin
try:
    from . import admin_pharmacy_walkin
except ImportError:
    pass

# Import blood bank admin
try:
    from . import admin_blood_bank  # noqa
except ImportError:
    pass

# Import login tracking admin
try:
    from . import admin_login_tracking  # noqa
except ImportError:
    pass

"""
Admin interface for Legacy Patient Data
Shows the 35,019 imported patient records
"""

from django.contrib import admin
from .models_legacy_patients import LegacyPatient


@admin.register(LegacyPatient)
class LegacyPatientAdmin(admin.ModelAdmin):
    """
    Admin interface for legacy patient data (35,019 imported records)
    """
    
    list_display = [
        'mrn_display',
        'full_name',
        'DOB',
        'sex',
        'display_phone',
        'city',
        'pricelevel',
        'date',
        'migration_link'
    ]
    
    list_filter = [
        'sex',
        'pricelevel',
        'city',
        'state'
    ]
    
    search_fields = [
        'pid',
        'fname',
        'lname',
        'mname',
        'phone_cell',
        'phone_home',
        'email',
        'pubpid'
    ]
    
    readonly_fields = [
        'id',
        'pid',
        'pmc_mrn',
        'mrn_display',
        'date',
        'regdate',
        'full_name',
        'display_phone'
    ]
    
    list_per_page = 50
    
    def get_readonly_fields(self, request, obj=None):
        """Make all fields read-only"""
        if obj:  # Editing an existing object
            return [field.name for field in self.model._meta.fields]
        return self.readonly_fields
    
    fieldsets = (
        ('Patient Identification', {
            'fields': ('mrn_display', 'id', 'pid', 'pubpid', 'full_name'),
            'description': '⚠️ This is legacy data from the old system. To migrate this patient to HMS, use the migration dashboard.'
        }),
        ('Personal Information', {
            'fields': ('title', 'fname', 'lname', 'mname', 'DOB', 'sex')
        }),
        ('Contact Information', {
            'fields': (
                'phone_cell',
                'phone_home',
                'phone_contact',
                'phone_biz',
                'email',
                'email_direct',
                'display_phone'
            )
        }),
        ('Address', {
            'fields': ('street', 'city', 'state', 'postal_code', 'country_code', 'county')
        }),
        ('Guardian/Emergency Contact', {
            'fields': (
                'guardiansname',
                'guardianphone',
                'guardianemail',
                'guardianrelationship',
                'contact_relationship',
                'mothersname'
            ),
            'classes': ('collapse',)
        }),
        ('Registration', {
            'fields': ('date', 'regdate', 'reg_type', 'referral_source')
        }),
        ('Provider/Referral', {
            'fields': ('providerID', 'ref_providerID', 'referrer', 'referrerID'),
            'classes': ('collapse',)
        }),
        ('Insurance/Financial', {
            'fields': ('financial', 'pricelevel', 'status', 'billing_note'),
            'classes': ('collapse',)
        }),
        ('Demographics', {
            'fields': ('race', 'ethnicity', 'religion', 'language'),
            'classes': ('collapse',)
        }),
        ('HIPAA/Privacy', {
            'fields': ('hipaa_allowsms', 'hipaa_allowemail', 'allow_patient_portal'),
            'classes': ('collapse',)
        }),
        ('Other Information', {
            'fields': ('drivers_license', 'ss', 'occupation', 'pharmacy_id', 'nia_pin'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs
    
    def changelist_view(self, request, extra_context=None):
        """Add helpful message to changelist"""
        from django.contrib import messages
        from django.urls import reverse
        from django.utils.html import format_html
        
        extra_context = extra_context or {}
        
        # Add link to migration dashboard
        migration_url = reverse('hospital:migration_dashboard')
        extra_context['migration_dashboard_link'] = migration_url
        
        # Show info message on first load
        if not request.GET:
            messages.info(
                request,
                format_html(
                    'This is read-only legacy patient data. To migrate patients to HMS, use the '
                    '<a href="{}" target="_blank" style="color: white; text-decoration: underline;">'
                    'Migration Dashboard</a>',
                    migration_url
                )
            )
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def has_add_permission(self, request):
        """Disable adding new records (this is legacy data)"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable changing records (this is read-only legacy data)"""
        # Allow viewing the list, but not editing individual records
        if obj is None:
            return True  # Can view list
        return False  # Cannot edit individual records
    
    def has_delete_permission(self, request, obj=None):
        """Disable deleting records (preserve legacy data)"""
        return False
    
    # Custom display methods
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'
    
    def display_phone(self, obj):
        return obj.display_phone
    display_phone.short_description = 'Phone'
    
    def mrn_display(self, obj):
        return obj.mrn_display
    mrn_display.short_description = 'PMC MRN'
    
    def migration_link(self, obj):
        """Link to migrate this patient"""
        from django.utils.html import format_html
        from django.urls import reverse
        
        # Check if already migrated
        from hospital.models import Patient
        mrn = obj.mrn_display
        if Patient.objects.filter(mrn=mrn, is_deleted=False).exists():
            patient = Patient.objects.get(mrn=mrn, is_deleted=False)
            url = reverse('admin:hospital_patient_change', args=[patient.pk])
            return format_html(
                '<span style="color: green;">✓ Migrated</span> | <a href="{}" target="_blank">View in HMS</a>',
                url
            )
        else:
            url = reverse('hospital:legacy_patient_detail', args=[obj.pid])
            return format_html(
                '<a href="{}" class="button" target="_blank">Migrate Patient</a>',
                url
            )
    migration_link.short_description = 'Migration Status'


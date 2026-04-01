"""
Admin interface for Legacy Patient Data
Shows the 35,019 imported patient records
"""

from django.contrib import admin
from django.contrib import messages
from django.shortcuts import redirect
from django.db import ProgrammingError, OperationalError
from django.urls import reverse

try:
    from .models_legacy_patients import LegacyPatient
    LEGACY_PATIENT_AVAILABLE = True
except Exception:
    LegacyPatient = None
    LEGACY_PATIENT_AVAILABLE = False


if LEGACY_PATIENT_AVAILABLE:
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
            """Optimize queryset - with error handling"""
            try:
                # Check if table exists first
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'patient_data'
                        );
                    """)
                    table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    return LegacyPatient.objects.none()
                
                qs = super().get_queryset(request)
                return qs
            except (ProgrammingError, OperationalError):
                # Return empty queryset if table doesn't exist
                return LegacyPatient.objects.none()
            except Exception:
                # Any other error - return empty queryset
                return LegacyPatient.objects.none()
        
        def changelist_view(self, request, extra_context=None):
            """Add helpful message to changelist - with error handling"""
            from django.utils.html import format_html
            
            try:
                extra_context = extra_context or {}
                
                # Add link to migration dashboard
                try:
                    migration_url = reverse('hospital:migration_dashboard')
                    extra_context['migration_dashboard_link'] = migration_url
                except Exception:
                    migration_url = None
                
                # Show info message on first load
                if not request.GET and migration_url:
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
            except (ProgrammingError, OperationalError) as e:
                # Table doesn't exist - redirect with message
                messages.error(
                    request,
                    'Legacy patient table (patient_data) does not exist in the database. '
                    'This table is only available when connected to the legacy MySQL database. '
                    'Legacy patients have been migrated to the main Patient model.'
                )
                return redirect('admin:index')
            except Exception as e:
                messages.error(request, f'Error loading legacy patients: {str(e)}')
                return redirect('admin:index')
        
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
            
            try:
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
                    try:
                        url = reverse('hospital:legacy_patient_detail', args=[obj.pid])
                        return format_html(
                            '<a href="{}" class="button" target="_blank">Migrate Patient</a>',
                            url
                        )
                    except Exception:
                        return 'Not migrated'
            except Exception:
                return 'N/A'
        migration_link.short_description = 'Migration Status'


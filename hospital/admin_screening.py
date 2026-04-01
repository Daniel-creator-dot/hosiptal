"""
Admin for Pre-employment and Pre-admission screening (templates and reports).
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

try:
    from .models_screening import ScreeningCheckTemplate, ScreeningReport
except ImportError:
    ScreeningCheckTemplate = None
    ScreeningReport = None


if ScreeningCheckTemplate:

    @admin.register(ScreeningCheckTemplate)
    class ScreeningCheckTemplateAdmin(admin.ModelAdmin):
        list_display = ['name', 'code', 'category', 'for_company_display', 'lab_imaging_counts', 'sort_order', 'is_active']
        list_filter = ['category', 'is_active']
        search_fields = ['name', 'code', 'description', 'for_company']
        ordering = ['category', 'sort_order', 'name']
        filter_horizontal = ['lab_tests', 'imaging_items']
        fieldsets = (
            (None, {
                'fields': ('name', 'code', 'category', 'description', 'for_company', 'is_active', 'sort_order'),
            }),
            ('Lab tests', {
                'fields': ('lab_tests',),
                'description': 'Lab tests to order when this template is applied.',
            }),
            ('Imaging studies', {
                'fields': ('imaging_items',),
                'description': 'Imaging studies (from catalog) to order when this template is applied.',
            }),
            ('Physical exam sections', {
                'fields': ('physical_exam_sections',),
                'description': 'Optional: list of section names for the report (e.g. General, Cardiovascular).',
            }),
        )

        def for_company_display(self, obj):
            return obj.for_company or '— (general)'
        for_company_display.short_description = 'For company'

        def lab_imaging_counts(self, obj):
            lab = obj.lab_tests.filter(is_active=True, is_deleted=False).count()
            img = obj.imaging_items.filter(is_active=True, is_deleted=False).count()
            return format_html('{} lab · {} imaging', lab, img)
        lab_imaging_counts.short_description = 'Lab · Imaging'


if ScreeningReport:

    @admin.register(ScreeningReport)
    class ScreeningReportAdmin(admin.ModelAdmin):
        list_display = ['encounter_link', 'patient_name', 'overall_result', 'reported_by', 'reported_at']
        list_filter = ['overall_result', 'reported_at']
        search_fields = ['encounter__patient__first_name', 'encounter__patient__last_name', 'result_notes']
        readonly_fields = ['encounter', 'reported_at', 'approved_at']
        fieldsets = (
            (None, {'fields': ('encounter', 'template_used')}),
            ('Result', {'fields': ('overall_result', 'result_notes')}),
            ('Summaries', {
                'fields': ('lab_summary', 'imaging_summary', 'physical_exam_notes', 'general_remarks', 'recommended_actions'),
            }),
            ('Requesting', {'fields': ('requesting_organization', 'requesting_contact')}),
            ('Sign-off', {'fields': ('reported_by', 'reported_at', 'approved_by', 'approved_at')}),
        )

        def encounter_link(self, obj):
            if not obj.encounter_id:
                return '—'
            url = reverse('admin:hospital_encounter_change', args=[obj.encounter_id])
            return format_html('<a href="{}">{}</a>', url, str(obj.encounter))
        encounter_link.short_description = 'Encounter'

        def patient_name(self, obj):
            return obj.encounter.patient.full_name if obj.encounter_id else '—'
        patient_name.short_description = 'Patient'

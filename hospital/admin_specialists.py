"""
Admin interface for Specialist models
"""
from django.contrib import admin
from .models_specialists import (
    Specialty, SpecialistProfile, DentalChart, ToothCondition, DentalProcedure,
    CardiologyChart, OphthalmologyChart, SpecialistConsultation, Referral,
    DentalProcedureCatalog
)


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created']
    list_filter = ['is_active', 'created']
    search_fields = ['name', 'code', 'description']
    prepopulated_fields = {'code': ('name',)}


@admin.register(SpecialistProfile)
class SpecialistProfileAdmin(admin.ModelAdmin):
    list_display = ['staff', 'specialty', 'experience_years', 'consultation_fee', 'is_active']
    list_filter = ['specialty', 'is_active', 'experience_years']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'qualification']
    autocomplete_fields = ['staff']


@admin.register(DentalProcedureCatalog)
class DentalProcedureCatalogAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'procedure_type', 'default_price', 'currency', 'is_active']
    list_filter = ['procedure_type', 'is_active', 'currency']
    search_fields = ['code', 'name', 'description']
    ordering = ['code']
    
    fieldsets = (
        ('Procedure Information', {
            'fields': ('code', 'name', 'procedure_type', 'description')
        }),
        ('Pricing', {
            'fields': ('default_price', 'currency', 'is_active')
        }),
    )


@admin.register(DentalChart)
class DentalChartAdmin(admin.ModelAdmin):
    list_display = ['patient', 'chart_date', 'created_by', 'created']
    list_filter = ['chart_date', 'created']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn']
    autocomplete_fields = ['patient', 'encounter', 'created_by']
    date_hierarchy = 'chart_date'


@admin.register(ToothCondition)
class ToothConditionAdmin(admin.ModelAdmin):
    list_display = ['dental_chart', 'tooth_number', 'condition_type', 'surface', 'procedure_date']
    list_filter = ['condition_type', 'surface', 'procedure_date']
    search_fields = ['tooth_number', 'notes']
    autocomplete_fields = ['dental_chart']


@admin.register(DentalProcedure)
class DentalProcedureAdmin(admin.ModelAdmin):
    list_display = ['procedure_name', 'dental_chart', 'procedure_type', 'status', 'fee', 'procedure_date']
    list_filter = ['procedure_type', 'status', 'procedure_date']
    search_fields = ['procedure_code', 'procedure_name', 'teeth', 'notes']
    autocomplete_fields = ['dental_chart', 'performed_by']
    date_hierarchy = 'procedure_date'


@admin.register(CardiologyChart)
class CardiologyChartAdmin(admin.ModelAdmin):
    list_display = ['patient', 'chart_date', 'heart_rate', 'blood_pressure', 'created_by']
    list_filter = ['chart_date', 'created']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn']
    autocomplete_fields = ['patient', 'encounter', 'created_by']
    date_hierarchy = 'chart_date'


@admin.register(OphthalmologyChart)
class OphthalmologyChartAdmin(admin.ModelAdmin):
    list_display = ['patient', 'chart_date', 'visual_acuity_re_right', 'iop_right', 'created_by']
    list_filter = ['chart_date', 'created']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__mrn']
    autocomplete_fields = ['patient', 'encounter', 'created_by']
    date_hierarchy = 'chart_date'


@admin.register(SpecialistConsultation)
class SpecialistConsultationAdmin(admin.ModelAdmin):
    list_display = ['patient', 'specialist', 'consultation_date', 'created']
    list_filter = ['consultation_date', 'specialist__specialty', 'created']
    search_fields = ['patient__first_name', 'patient__last_name', 'chief_complaint']
    autocomplete_fields = ['patient', 'encounter', 'specialist']
    date_hierarchy = 'consultation_date'


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['patient', 'specialist', 'specialty', 'referring_doctor', 'status', 'priority', 'referred_date']
    list_filter = ['status', 'priority', 'specialty', 'referred_date']
    search_fields = ['patient__first_name', 'patient__last_name', 'reason', 'clinical_summary']
    autocomplete_fields = ['patient', 'encounter', 'referring_doctor', 'specialist', 'specialty']
    readonly_fields = ['referred_date', 'completed_date']
    date_hierarchy = 'referred_date'
    
    fieldsets = (
        ('Patient Information', {
            'fields': ('patient', 'encounter')
        }),
        ('Referral Details', {
            'fields': ('referring_doctor', 'specialty', 'specialist', 'reason', 'clinical_summary', 'priority', 'status')
        }),
        ('Dates', {
            'fields': ('referred_date', 'appointment_date', 'consultation_date', 'completed_date')
        }),
        ('Specialist Response', {
            'fields': ('specialist_notes', 'declined_reason')
        }),
    )


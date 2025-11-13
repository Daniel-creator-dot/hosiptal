"""
Admin configuration for HR Activities models
"""
from django.contrib import admin
from .models_hr_activities import (
    HospitalActivity, ActivityRSVP, StaffRecognition,
    RecruitmentPosition, Candidate, WellnessProgram,
    WellnessParticipation, StaffSurvey, SurveyResponse,
    StaffActivity, LeaveBalanceAlert, StaffLeaveCounter
)


@admin.register(HospitalActivity)
class HospitalActivityAdmin(admin.ModelAdmin):
    list_display = ['title', 'activity_type', 'start_date', 'end_date', 'priority', 'is_mandatory', 'is_published']
    list_filter = ['activity_type', 'priority', 'is_mandatory', 'is_published', 'start_date']
    search_fields = ['title', 'description', 'location']
    filter_horizontal = ['departments', 'specific_staff']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'activity_type', 'priority')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'start_time', 'end_time', 'location')
        }),
        ('Organization', {
            'fields': ('organizer',)
        }),
        ('Target Audience', {
            'fields': ('all_staff', 'departments', 'specific_staff')
        }),
        ('Settings', {
            'fields': ('is_mandatory', 'requires_rsvp', 'max_participants')
        }),
        ('Attachments', {
            'fields': ('attachment', 'external_link')
        }),
        ('Publishing', {
            'fields': ('is_published',)
        }),
    )


@admin.register(ActivityRSVP)
class ActivityRSVPAdmin(admin.ModelAdmin):
    list_display = ['staff', 'activity', 'response', 'responded_at']
    list_filter = ['response', 'responded_at']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'activity__title']


@admin.register(StaffRecognition)
class StaffRecognitionAdmin(admin.ModelAdmin):
    list_display = ['staff', 'recognition_type', 'title', 'awarded_date', 'is_public']
    list_filter = ['recognition_type', 'is_public', 'awarded_date']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'title', 'description']
    date_hierarchy = 'awarded_date'


@admin.register(RecruitmentPosition)
class RecruitmentPositionAdmin(admin.ModelAdmin):
    list_display = ['position_title', 'department', 'employment_type', 'status', 'number_of_positions', 'posted_date']
    list_filter = ['status', 'employment_type', 'is_urgent', 'posted_date']
    search_fields = ['position_title', 'job_description']
    date_hierarchy = 'posted_date'


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'position', 'status', 'application_date', 'interview_date']
    list_filter = ['status', 'application_date']
    search_fields = ['first_name', 'last_name', 'email']
    date_hierarchy = 'application_date'
    
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = 'Name'


@admin.register(WellnessProgram)
class WellnessProgramAdmin(admin.ModelAdmin):
    list_display = ['program_name', 'program_type', 'start_date', 'end_date', 'is_active']
    list_filter = ['program_type', 'is_active', 'start_date']
    search_fields = ['program_name', 'description']
    date_hierarchy = 'start_date'


@admin.register(WellnessParticipation)
class WellnessParticipationAdmin(admin.ModelAdmin):
    list_display = ['staff', 'program', 'enrolled_date', 'is_completed', 'rating']
    list_filter = ['is_completed', 'enrolled_date']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'program__program_name']


@admin.register(StaffSurvey)
class StaffSurveyAdmin(admin.ModelAdmin):
    list_display = ['title', 'survey_type', 'start_date', 'end_date', 'is_active', 'is_anonymous']
    list_filter = ['survey_type', 'is_active', 'is_anonymous', 'start_date']
    search_fields = ['title', 'description']
    filter_horizontal = ['target_departments']
    date_hierarchy = 'start_date'


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ['survey', 'staff', 'submitted_at']
    list_filter = ['submitted_at', 'survey']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'survey__title']
    date_hierarchy = 'submitted_at'


@admin.register(StaffActivity)
class StaffActivityAdmin(admin.ModelAdmin):
    list_display = ['staff', 'title', 'activity_date', 'activity_time', 'is_completed']
    list_filter = ['is_completed', 'activity_date']
    search_fields = ['staff__user__first_name', 'staff__user__last_name', 'title']
    date_hierarchy = 'activity_date'


@admin.register(LeaveBalanceAlert)
class LeaveBalanceAlertAdmin(admin.ModelAdmin):
    list_display = ['staff', 'alert_type', 'is_acknowledged', 'created']
    list_filter = ['alert_type', 'is_acknowledged']
    search_fields = ['staff__user__first_name', 'staff__user__last_name']


@admin.register(StaffLeaveCounter)
class StaffLeaveCounterAdmin(admin.ModelAdmin):
    list_display = ['staff', 'days_until_next_leave', 'next_leave_date', 'last_updated']
    search_fields = ['staff__user__first_name', 'staff__user__last_name']

"""
Admin interface for Consulting Rooms Management
"""
from django.contrib import admin
from .models_consulting_rooms import ConsultingRoom, DoctorRoomAssignment, RoomAvailability


@admin.register(ConsultingRoom)
class ConsultingRoomAdmin(admin.ModelAdmin):
    list_display = ['room_number', 'room_name', 'department', 'status', 'is_active', 'capacity']
    list_filter = ['status', 'is_active', 'department']
    search_fields = ['room_number', 'room_name']
    ordering = ['room_number']
    
    fieldsets = (
        ('Room Information', {
            'fields': ('room_number', 'room_name', 'department')
        }),
        ('Status & Availability', {
            'fields': ('status', 'is_active', 'capacity')
        }),
        ('Additional Information', {
            'fields': ('equipment', 'notes'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DoctorRoomAssignment)
class DoctorRoomAssignmentAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'room', 'assignment_date', 'start_time', 'end_time', 'is_active']
    list_filter = ['is_active', 'assignment_date', 'room']
    search_fields = ['doctor__username', 'doctor__first_name', 'doctor__last_name', 'room__room_number']
    ordering = ['-assignment_date', '-start_time']
    date_hierarchy = 'assignment_date'
    
    fieldsets = (
        ('Assignment Details', {
            'fields': ('doctor', 'room', 'assignment_date')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'is_active')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['assignment_date', 'start_time']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ['doctor', 'room']
        return self.readonly_fields


@admin.register(RoomAvailability)
class RoomAvailabilityAdmin(admin.ModelAdmin):
    list_display = ['room', 'day_of_week', 'start_time', 'end_time', 'is_available']
    list_filter = ['is_available', 'day_of_week', 'room']
    search_fields = ['room__room_number', 'room__room_name']
    ordering = ['room', 'day_of_week', 'start_time']



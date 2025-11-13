"""
Telemedicine URL Configuration
"""
from django.urls import path
from . import views_telemedicine
from . import views_telemedicine_enhanced

app_name = 'telemedicine'

urlpatterns = [
    # Main Dashboard
    path('', views_telemedicine.telemedicine_dashboard, name='telemedicine_dashboard'),
    
    # Consultation Management
    path('consultation/<uuid:consultation_id>/', views_telemedicine.consultation_detail, name='consultation_detail'),
    path('consultation/<uuid:consultation_id>/start/', views_telemedicine.start_consultation, name='start_consultation'),
    path('consultation/<uuid:consultation_id>/room/', views_telemedicine.consultation_room, name='consultation_room'),
    path('consultation/<uuid:consultation_id>/end/', views_telemedicine.end_consultation, name='end_consultation'),
    
    # Messaging
    path('consultation/<uuid:consultation_id>/send-message/', views_telemedicine.send_message, name='send_message'),
    
    # AI Features
    path('ai/symptom-checker/', views_telemedicine.ai_symptom_checker, name='ai_symptom_checker'),
    path('consultation/<uuid:consultation_id>/ai-image-analysis/', views_telemedicine.ai_image_analysis, name='ai_image_analysis'),
    
    # Scheduling
    path('schedule/', views_telemedicine.schedule_consultation, name='schedule_consultation'),
    
    # Prescription Management
    path('consultation/<uuid:consultation_id>/prescriptions/', views_telemedicine.prescription_management, name='prescription_management'),
    
    # Lab Order Management
    path('consultation/<uuid:consultation_id>/lab-orders/', views_telemedicine.lab_order_management, name='lab_order_management'),
    
    # Chat Interface
    path('chat/', views_telemedicine.chat_interface, name='chat_interface'),
    path('consultation/<uuid:consultation_id>/messages/', views_telemedicine.chat_messages, name='chat_messages'),
    
    # Temporary Booking
    path('temporary-booking/', views_telemedicine.temporary_booking, name='temporary_booking'),
    
    # Enhanced Telemedicine Features
    path('command-center/', views_telemedicine_enhanced.telemedicine_worldclass_dashboard, name='command_center'),
    path('virtual-waiting-room/', views_telemedicine_enhanced.virtual_waiting_room_display, name='virtual_waiting_room'),
    path('ai-symptom-checker/', views_telemedicine_enhanced.ai_symptom_checker_interface, name='ai_symptom_checker_enhanced'),
    path('analytics/', views_telemedicine_enhanced.consultation_analytics_dashboard, name='analytics_dashboard'),
    path('patient-checkin/', views_telemedicine_enhanced.patient_self_checkin, name='patient_checkin'),
]

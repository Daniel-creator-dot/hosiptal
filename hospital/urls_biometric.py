"""
URL Configuration for Biometric Authentication System
"""
from django.urls import path
from . import views_biometric

app_name = 'biometric'

urlpatterns = [
    # Front Desk Login
    path('login/', views_biometric.biometric_login_page, name='login'),
    path('api/authenticate/', views_biometric.biometric_authenticate, name='api_authenticate'),
    
    # Enrollment
    path('enrollment/', views_biometric.biometric_enrollment_page, name='enrollment'),
    path('api/enroll/', views_biometric.biometric_enroll, name='api_enroll'),
    
    # Staff Dashboard
    path('my-profile/', views_biometric.my_biometric_profile, name='my_profile'),
    
    # Admin Dashboard & Reports
    path('dashboard/', views_biometric.biometric_dashboard, name='dashboard'),
    path('reports/', views_biometric.biometric_reports, name='reports'),
    
    # Device Management
    path('api/device/heartbeat/', views_biometric.device_heartbeat, name='device_heartbeat'),
]


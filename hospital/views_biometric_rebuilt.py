"""
WORLD-CLASS BIOMETRIC SYSTEM - COMPLETELY REBUILT
Outstanding enrollment and authentication with bulletproof logic
Simple, secure, and highly accurate
"""
import base64
import json
import hashlib
import pickle
import numpy as np
from io import BytesIO
from PIL import Image
from decimal import Decimal
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction

from .models import Staff
from .models_biometric import (
    BiometricType,
    StaffBiometric,
    BiometricAuthenticationLog,
    BiometricSystemSettings,
    BiometricEnrollmentSession,
)
from .services.biometric_service import biometric_auth_service

import logging
logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')


# ==================== ENROLLMENT ====================

@login_required
def enrollment_hub(request):
    """
    World-Class Biometric Enrollment Hub
    Step-by-step enrollment with live feedback
    """
    # Check if user has staff profile
    try:
        staff = request.user.staff
    except:
        messages.error(request, "Staff profile not found. Please contact HR.")
        return redirect('hospital:dashboard')
    
    # Get existing biometrics
    existing_biometrics = StaffBiometric.objects.filter(
        staff=staff,
        is_active=True,
        is_deleted=False
    ).select_related('biometric_type')
    
    # Get available biometric types
    biometric_types = BiometricType.objects.filter(is_active=True, is_deleted=False)
    
    # System settings
    settings = BiometricSystemSettings.get_settings()
    
    context = {
        'staff': staff,
        'existing_biometrics': existing_biometrics,
        'biometric_types': biometric_types,
        'settings': settings,
        'has_face': existing_biometrics.filter(biometric_type__name='face').exists(),
    }
    
    return render(request, 'hospital/biometric/enrollment_rebuilt.html', context)


@login_required
@require_http_methods(["POST"])
def enroll_biometric(request):
    """
    WORLD-CLASS ENROLLMENT ENDPOINT
    Captures face image and creates biometric template
    """
    try:
        # Get staff
        try:
            staff = request.user.staff
        except:
            return JsonResponse({
                'success': False,
                'error': 'Staff profile not found'
            }, status=403)
        
        # Parse request
        data = json.loads(request.body) if request.body else {}
        
        # Get image data
        image_base64 = data.get('image_data')
        if not image_base64:
            return JsonResponse({
                'success': False,
                'error': 'No image data provided'
            }, status=400)
        
        # Get biometric type (default to face)
        biometric_type = BiometricType.objects.filter(
            name='face',
            is_active=True,
            is_deleted=False
        ).first()
        
        if not biometric_type:
            # Create default face recognition type
            biometric_type = BiometricType.objects.create(
                name='face',
                display_name='Face Recognition',
                description='Facial biometric authentication',
                is_active=True,
                requires_liveness_check=True,
                min_confidence_score=Decimal('75.00')
            )
        
        # Decode image
        try:
            if ',' in image_base64:
                image_base64 = image_base64.split(',')[1]
            image_bytes = base64.b64decode(image_base64)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid image format: {str(e)}'
            }, status=400)
        
        # Process enrollment using biometric service
        start_time = timezone.now()
        
        result = biometric_auth_service.enroll_staff_face(
            staff=staff,
            image_data=image_bytes,
            biometric_type=biometric_type,
            operator=request.user
        )
        
        if result['success']:
            # Create enrollment record
            biometric = result['biometric']
            
            return JsonResponse({
                'success': True,
                'message': 'Face enrolled successfully! You can now use biometric login.',
                'biometric': {
                    'id': str(biometric.id),
                    'type': biometric.biometric_type.display_name,
                    'quality_score': float(biometric.quality_score),
                    'enrolled_at': biometric.enrolled_at.strftime('%Y-%m-%d %H:%M:%S'),
                },
                'stats': {
                    'total_samples': 1,
                    'quality': 'Excellent' if biometric.quality_score > 90 else 'Good',
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Enrollment failed')
            }, status=400)
    
    except Exception as e:
        logger.exception("Enrollment error")
        return JsonResponse({
            'success': False,
            'error': f'System error: {str(e)}'
        }, status=500)


# ==================== AUTHENTICATION ====================

def biometric_login_page(request):
    """
    World-Class Biometric Login Interface
    Auto-detects available biometric devices (Face Camera + Fingerprint Scanner)
    """
    # Get system settings
    settings = BiometricSystemSettings.get_settings()
    
    if not settings.system_enabled:
        messages.error(request, "Biometric authentication is currently disabled.")
        return redirect('admin:login')
    
    # Get all active biometric types
    biometric_types = BiometricType.objects.filter(
        is_active=True,
        is_deleted=False
    )
    
    face_type = biometric_types.filter(name='face').first()
    fingerprint_type = biometric_types.filter(name='fingerprint').first()
    
    # Count enrolled staff per type
    enrolled_stats = {}
    for bio_type in biometric_types:
        enrolled_stats[bio_type.name] = StaffBiometric.objects.filter(
            biometric_type=bio_type,
            is_active=True,
            is_deleted=False
        ).count()
    
    # Statistics for display
    stats = {
        'total_enrolled': StaffBiometric.objects.filter(
            is_active=True,
            is_deleted=False
        ).count(),
        'authenticated_today': BiometricAuthenticationLog.objects.filter(
            timestamp__date=timezone.now().date(),
            status='success'
        ).count(),
        'face_enrolled': enrolled_stats.get('face', 0),
        'fingerprint_enrolled': enrolled_stats.get('fingerprint', 0),
    }
    
    context = {
        'settings': settings,
        'biometric_types': biometric_types,
        'face_type': face_type,
        'fingerprint_type': fingerprint_type,
        'stats': stats,
        'allow_password_fallback': settings.allow_password_fallback,
    }
    
    return render(request, 'hospital/biometric/login_auto_detect.html', context)


@csrf_exempt  # For biometric terminal access
@require_http_methods(["POST"])
def authenticate_biometric(request):
    """
    WORLD-CLASS AUTHENTICATION ENDPOINT
    Auto-detects and processes Face or Fingerprint authentication
    """
    try:
        # Parse request
        data = json.loads(request.body) if request.body else {}
        
        # Get biometric type from request
        biometric_type_name = data.get('biometric_type', 'face')
        
        # Get image/fingerprint data
        image_base64 = data.get('image_data')
        fingerprint_data = data.get('fingerprint_data')
        
        if not image_base64 and not fingerprint_data:
            return JsonResponse({
                'success': False,
                'message': 'No biometric data provided'
            }, status=400)
        
        # Get biometric type
        biometric_type = BiometricType.objects.filter(
            name=biometric_type_name,
            is_active=True,
            is_deleted=False
        ).first()
        
        if not biometric_type:
            return JsonResponse({
                'success': False,
                'message': f'{biometric_type_name.title()} authentication not configured'
            }, status=500)
        
        # Decode data
        try:
            if biometric_type_name == 'fingerprint' and fingerprint_data:
                # Process fingerprint data
                biometric_bytes = fingerprint_data.encode() if isinstance(fingerprint_data, str) else fingerprint_data
            else:
                # Process face image
                if ',' in image_base64:
                    image_base64 = image_base64.split(',')[1]
                biometric_bytes = base64.b64decode(image_base64)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Invalid data: {str(e)}'
            }, status=400)
        
        # Get IP and location
        ip_address = get_client_ip(request)
        location = data.get('location', 'Login Terminal')
        
        # Authenticate using biometric service
        auth_result = biometric_auth_service.authenticate_staff(
            image_data=biometric_bytes,
            biometric_type=biometric_type,
            device=None,
            location=location,
            ip_address=ip_address,
            create_attendance=True,
            create_login=True
        )
        
        success = auth_result[0]
        staff = auth_result[1]
        message = auth_result[2]
        metadata = auth_result[3]
        
        if success and staff:
            # Log the user in to Django session
            auth_login(request, staff.user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Get staff details
            staff_info = {
                'id': str(staff.id),
                'name': staff.user.get_full_name(),
                'employee_id': staff.employee_id,
                'profession': staff.get_profession_display(),
                'department': staff.department.name if staff.department else 'N/A',
                'email': staff.user.email,
            }
            
            # Build redirect URL based on role
            redirect_url = '/hms/'
            if staff.profession == 'doctor':
                redirect_url = '/hms/staff/dashboard/'
            elif staff.profession == 'nurse':
                redirect_url = '/hms/staff/dashboard/'
            elif staff.profession == 'pharmacist':
                redirect_url = '/hms/pharmacy/'
            elif staff.profession == 'lab_tech':
                redirect_url = '/hms/laboratory/'
            elif staff.profession == 'radiologist':
                redirect_url = '/hms/imaging/'
            
            return JsonResponse({
                'success': True,
                'message': f'Welcome back, {staff.user.get_full_name()}!',
                'staff': staff_info,
                'confidence': float(metadata.get('confidence', 0)),
                'quality': float(metadata.get('quality_score', 0)),
                'redirect_url': redirect_url
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message or 'Face not recognized. Please try again.'
            })
    
    except Exception as e:
        logger.exception("Authentication error")
        return JsonResponse({
            'success': False,
            'message': f'System error: {str(e)}'
        }, status=500)


# ==================== UTILITIES ====================

@login_required
def my_biometric_profile(request):
    """View and manage personal biometric enrollments"""
    try:
        staff = request.user.staff
    except:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:dashboard')
    
    # Get biometrics
    biometrics = StaffBiometric.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('biometric_type').order_by('-enrolled_at')
    
    # Get recent authentication logs
    recent_auth = BiometricAuthenticationLog.objects.filter(
        staff=staff
    ).order_by('-timestamp')[:20]
    
    # Statistics
    stats = {
        'total_enrolled': biometrics.filter(is_active=True).count(),
        'total_authentications': BiometricAuthenticationLog.objects.filter(
            staff=staff,
            status='success'
        ).count(),
        'last_auth': recent_auth.filter(status='success').first(),
    }
    
    context = {
        'staff': staff,
        'biometrics': biometrics,
        'recent_auth': recent_auth,
        'stats': stats,
    }
    
    return render(request, 'hospital/biometric/my_profile_rebuilt.html', context)


@login_required
@require_http_methods(["POST"])
def delete_biometric(request, biometric_id):
    """Delete/deactivate biometric enrollment"""
    try:
        staff = request.user.staff
    except:
        return JsonResponse({'success': False, 'error': 'Staff profile not found'}, status=403)
    
    biometric = get_object_or_404(
        StaffBiometric,
        id=biometric_id,
        staff=staff,
        is_deleted=False
    )
    
    # Soft delete
    biometric.is_active = False
    biometric.is_deleted = True
    biometric.save()
    
    messages.success(request, f'{biometric.biometric_type.display_name} enrollment removed.')
    
    return JsonResponse({
        'success': True,
        'message': 'Biometric removed successfully'
    })


@require_http_methods(["GET"])
def detect_devices(request):
    """
    AUTO-DETECT AVAILABLE BIOMETRIC DEVICES
    Returns list of connected fingerprint scanners and cameras
    """
    devices = {
        'camera': False,
        'fingerprint': False,
        'devices': []
    }
    
    try:
        # Check if browser supports camera (getUserMedia)
        # This will be checked client-side via JavaScript
        devices['camera'] = True  # Assume camera available (JS will confirm)
        
        # Check for fingerprint devices via Web Authentication API
        # Modern browsers support this for fingerprint readers
        devices['fingerprint'] = False  # Will be detected by JS
        
        # Get configured biometric types
        biometric_types = BiometricType.objects.filter(
            is_active=True,
            is_deleted=False
        ).values('name', 'display_name')
        
        devices['available_types'] = list(biometric_types)
        
        return JsonResponse({
            'success': True,
            'devices': devices
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


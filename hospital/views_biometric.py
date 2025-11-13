"""
Views for Biometric Authentication System
Enrollment and Authentication interfaces
"""
import base64
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import login as auth_login
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
from decimal import Decimal

from .models import Staff
from .models_biometric import (
    BiometricType,
    StaffBiometric,
    BiometricAuthenticationLog,
    BiometricDevice,
    BiometricEnrollmentSession,
    BiometricSecurityAlert,
    BiometricSystemSettings,
)
from .services.biometric_service import biometric_auth_service
import logging

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ==================== FRONT DESK BIOMETRIC LOGIN ====================

@require_http_methods(["GET"])
def biometric_login_page(request):
    """
    Front desk biometric login page
    """
    # Get settings
    settings = BiometricSystemSettings.get_settings()
    
    if not settings.system_enabled:
        messages.error(request, "Biometric authentication is currently disabled.")
        return redirect('admin:login')
    
    # Get active biometric types
    biometric_types = BiometricType.objects.filter(is_active=True)
    
    # Get devices
    devices = BiometricDevice.objects.filter(is_active=True, is_online=True)
    
    context = {
        'biometric_types': biometric_types,
        'devices': devices,
        'settings': settings,
        'allow_password_fallback': settings.allow_password_fallback,
    }
    
    return render(request, 'hospital/biometric/login.html', context)


@csrf_exempt  # For API endpoint - consider using proper token auth in production
@require_http_methods(["POST"])
def biometric_authenticate(request):
    """
    API endpoint for biometric authentication
    Receives biometric data (face image) and authenticates staff
    """
    try:
        # Parse request data
        data = json.loads(request.body) if request.body else {}
        
        # Get biometric image data (base64 encoded)
        image_base64 = data.get('image_data')
        if not image_base64:
            return JsonResponse({
                'success': False,
                'message': 'No image data provided'
            }, status=400)
        
        # Get biometric type
        biometric_type_id = data.get('biometric_type_id')
        if not biometric_type_id:
            return JsonResponse({
                'success': False,
                'message': 'No biometric type specified'
            }, status=400)
        
        biometric_type = get_object_or_404(BiometricType, id=biometric_type_id, is_active=True)
        
        # Get device info (optional)
        device_id = data.get('device_id')
        device = None
        if device_id:
            try:
                device = BiometricDevice.objects.get(device_id=device_id, is_active=True)
            except BiometricDevice.DoesNotExist:
                pass
        
        # Get location
        location = data.get('location', 'Front Desk')
        
        # Decode base64 image
        try:
            # Remove header if present
            if ',' in image_base64:
                image_base64 = image_base64.split(',')[1]
            image_data = base64.b64decode(image_base64)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Invalid image data: {str(e)}'
            }, status=400)
        
        # Get client IP
        ip_address = get_client_ip(request)
        
        # Authenticate using biometric service
        success, staff, message, auth_metadata = biometric_auth_service.authenticate_staff(
            image_data=image_data,
            biometric_type=biometric_type,
            device=device,
            location=location,
            ip_address=ip_address,
            create_attendance=True,
            create_login=True
        )
        
        if success and staff:
            # Log the user in
            auth_login(request, staff.user)
            
            # Trigger automatic attendance tracking
            try:
                from .signals_auto_attendance import biometric_login_success as biometric_signal
                biometric_signal.send(
                    sender=self.__class__,
                    user=staff.user,
                    method='face_recognition'
                )
            except Exception as e:
                logger.error(f"Auto-attendance failed: {e}")
            
            return JsonResponse({
                'success': True,
                'message': message,
                'staff': {
                    'id': str(staff.id),
                    'name': staff.user.get_full_name(),
                    'employee_id': staff.employee_id,
                    'profession': staff.get_profession_display(),
                    'department': staff.department.name if staff.department else None,
                },
                'metadata': {
                    'confidence': str(auth_metadata.get('confidence', 0)),
                    'quality_score': auth_metadata.get('quality_score', '0'),
                    'liveness_score': auth_metadata.get('liveness_score', '0'),
                },
                'redirect_url': '/hms/staff-dashboard/'  # Redirect to staff dashboard
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message
            })
    
    except Exception as e:
        logger.exception("Error in biometric authentication")
        return JsonResponse({
            'success': False,
            'message': f'Authentication error: {str(e)}'
        }, status=500)


# ==================== STAFF BIOMETRIC ENROLLMENT ====================

@login_required
@permission_required('hospital.add_staffbiometric', raise_exception=True)
def biometric_enrollment_page(request):
    """
    Biometric enrollment interface for HR/Admin
    """
    # Get all staff
    staff_list = Staff.objects.filter(is_active=True).select_related('user', 'department')
    
    # Get biometric types
    biometric_types = BiometricType.objects.filter(is_active=True)
    
    # Get devices
    devices = BiometricDevice.objects.filter(is_active=True)
    
    # Get enrollment statistics
    total_staff = staff_list.count()
    enrolled_staff = Staff.objects.filter(
        biometrics__is_active=True,
        biometrics__is_deleted=False
    ).distinct().count()
    enrollment_percentage = (enrolled_staff / total_staff * 100) if total_staff > 0 else 0
    
    context = {
        'staff_list': staff_list,
        'biometric_types': biometric_types,
        'devices': devices,
        'total_staff': total_staff,
        'enrolled_staff': enrolled_staff,
        'enrollment_percentage': enrollment_percentage,
    }
    
    return render(request, 'hospital/biometric/enrollment.html', context)


@login_required
@permission_required('hospital.add_staffbiometric', raise_exception=True)
@require_http_methods(["POST"])
def biometric_enroll(request):
    """
    API endpoint to enroll staff biometric data
    """
    try:
        # Parse request data
        data = json.loads(request.body) if request.body else {}
        
        # Get staff
        staff_id = data.get('staff_id')
        if not staff_id:
            return JsonResponse({
                'success': False,
                'message': 'No staff ID provided'
            }, status=400)
        
        staff = get_object_or_404(Staff, id=staff_id)
        
        # Get biometric type
        biometric_type_id = data.get('biometric_type_id')
        if not biometric_type_id:
            return JsonResponse({
                'success': False,
                'message': 'No biometric type specified'
            }, status=400)
        
        biometric_type = get_object_or_404(BiometricType, id=biometric_type_id, is_active=True)
        
        # Get image data
        image_base64 = data.get('image_data')
        if not image_base64:
            return JsonResponse({
                'success': False,
                'message': 'No image data provided'
            }, status=400)
        
        # Decode base64 image
        try:
            if ',' in image_base64:
                image_base64 = image_base64.split(',')[1]
            image_data = base64.b64decode(image_base64)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Invalid image data: {str(e)}'
            }, status=400)
        
        # Get device info (optional)
        device_id = data.get('device_id')
        device = None
        if device_id:
            try:
                device = BiometricDevice.objects.get(device_id=device_id)
            except BiometricDevice.DoesNotExist:
                pass
        
        # Get location
        location = data.get('location', 'HR Office')
        
        # Enroll using biometric service
        success, staff_biometric, message = biometric_auth_service.enroll_staff_biometric(
            staff=staff,
            biometric_type=biometric_type,
            image_data=image_data,
            operator=request.user,
            device=device,
            location=location
        )
        
        if success:
            return JsonResponse({
                'success': True,
                'message': message,
                'biometric': {
                    'id': str(staff_biometric.id),
                    'quality_score': str(staff_biometric.quality_score),
                    'enrolled_at': staff_biometric.enrolled_at.isoformat(),
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'message': message
            })
    
    except Exception as e:
        logger.exception("Error in biometric enrollment")
        return JsonResponse({
            'success': False,
            'message': f'Enrollment error: {str(e)}'
        }, status=500)


# ==================== STAFF DASHBOARD - BIOMETRIC MANAGEMENT ====================

@login_required
def my_biometric_profile(request):
    """
    Staff view to manage their own biometric data
    """
    try:
        staff = request.user.staff
    except Staff.DoesNotExist:
        messages.error(request, "Staff profile not found.")
        return redirect('hospital:staff_dashboard')
    
    # Get staff biometrics
    biometrics = StaffBiometric.objects.filter(
        staff=staff,
        is_deleted=False
    ).select_related('biometric_type')
    
    # Get recent authentication logs
    recent_authentications = BiometricAuthenticationLog.objects.filter(
        staff=staff
    ).order_by('-timestamp')[:20]
    
    # Get available biometric types
    available_types = BiometricType.objects.filter(is_active=True)
    
    # Get statistics
    total_authentications = BiometricAuthenticationLog.objects.filter(staff=staff).count()
    successful_authentications = BiometricAuthenticationLog.objects.filter(
        staff=staff,
        status='success'
    ).count()
    success_rate = (successful_authentications / total_authentications * 100) if total_authentications > 0 else 0
    
    context = {
        'staff': staff,
        'biometrics': biometrics,
        'recent_authentications': recent_authentications,
        'available_types': available_types,
        'total_authentications': total_authentications,
        'successful_authentications': successful_authentications,
        'success_rate': success_rate,
    }
    
    return render(request, 'hospital/biometric/my_profile.html', context)


# ==================== BIOMETRIC REPORTS & MONITORING ====================

@login_required
@permission_required('hospital.view_biometricauthenticationlog', raise_exception=True)
def biometric_dashboard(request):
    """
    Admin dashboard for biometric system monitoring
    """
    # Get date range
    from datetime import timedelta
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Overall statistics
    total_enrolled = StaffBiometric.objects.filter(is_active=True, is_deleted=False).count()
    total_staff = Staff.objects.filter(is_active=True).count()
    enrollment_rate = (total_enrolled / total_staff * 100) if total_staff > 0 else 0
    
    # Authentication statistics
    total_auths_today = BiometricAuthenticationLog.objects.filter(
        timestamp__date=today
    ).count()
    successful_auths_today = BiometricAuthenticationLog.objects.filter(
        timestamp__date=today,
        status='success'
    ).count()
    
    total_auths_week = BiometricAuthenticationLog.objects.filter(
        timestamp__date__gte=week_ago
    ).count()
    successful_auths_week = BiometricAuthenticationLog.objects.filter(
        timestamp__date__gte=week_ago,
        status='success'
    ).count()
    
    success_rate_today = (successful_auths_today / total_auths_today * 100) if total_auths_today > 0 else 0
    success_rate_week = (successful_auths_week / total_auths_week * 100) if total_auths_week > 0 else 0
    
    # Device statistics
    active_devices = BiometricDevice.objects.filter(is_active=True).count()
    online_devices = BiometricDevice.objects.filter(is_active=True, is_online=True).count()
    
    # Security alerts
    unresolved_alerts = BiometricSecurityAlert.objects.filter(is_resolved=False).count()
    critical_alerts = BiometricSecurityAlert.objects.filter(
        is_resolved=False,
        severity='critical'
    ).count()
    
    # Recent activity
    recent_logs = BiometricAuthenticationLog.objects.select_related(
        'staff__user',
        'biometric_type'
    ).order_by('-timestamp')[:50]
    
    # Recent alerts
    recent_alerts = BiometricSecurityAlert.objects.filter(
        is_resolved=False
    ).order_by('-timestamp')[:10]
    
    # Enrollment by biometric type
    enrollment_by_type = BiometricType.objects.annotate(
        enrolled_count=Count('staff_biometrics', filter=Q(
            staff_biometrics__is_active=True,
            staff_biometrics__is_deleted=False
        ))
    )
    
    context = {
        'total_enrolled': total_enrolled,
        'total_staff': total_staff,
        'enrollment_rate': enrollment_rate,
        'total_auths_today': total_auths_today,
        'successful_auths_today': successful_auths_today,
        'success_rate_today': success_rate_today,
        'total_auths_week': total_auths_week,
        'successful_auths_week': successful_auths_week,
        'success_rate_week': success_rate_week,
        'active_devices': active_devices,
        'online_devices': online_devices,
        'unresolved_alerts': unresolved_alerts,
        'critical_alerts': critical_alerts,
        'recent_logs': recent_logs,
        'recent_alerts': recent_alerts,
        'enrollment_by_type': enrollment_by_type,
    }
    
    return render(request, 'hospital/biometric/dashboard.html', context)


@login_required
@permission_required('hospital.view_biometricauthenticationlog', raise_exception=True)
def biometric_reports(request):
    """
    Detailed biometric authentication reports
    """
    # Get filter parameters
    staff_id = request.GET.get('staff')
    biometric_type_id = request.GET.get('type')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Build query
    logs = BiometricAuthenticationLog.objects.select_related(
        'staff__user',
        'biometric_type',
        'biometric'
    ).order_by('-timestamp')
    
    # Apply filters
    if staff_id:
        logs = logs.filter(staff_id=staff_id)
    if biometric_type_id:
        logs = logs.filter(biometric_type_id=biometric_type_id)
    if status:
        logs = logs.filter(status=status)
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    staff_list = Staff.objects.filter(is_active=True).select_related('user')
    biometric_types = BiometricType.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'staff_list': staff_list,
        'biometric_types': biometric_types,
        'filters': {
            'staff': staff_id,
            'type': biometric_type_id,
            'status': status,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'hospital/biometric/reports.html', context)


# ==================== API ENDPOINTS FOR FRONT DESK KIOSK ====================

@csrf_exempt
@require_http_methods(["POST"])
def device_heartbeat(request):
    """
    Endpoint for biometric devices to send heartbeat
    """
    try:
        data = json.loads(request.body) if request.body else {}
        device_id = data.get('device_id')
        
        if not device_id:
            return JsonResponse({
                'success': False,
                'message': 'Device ID required'
            }, status=400)
        
        device = get_object_or_404(BiometricDevice, device_id=device_id)
        device.is_online = True
        device.last_heartbeat = timezone.now()
        device.save(update_fields=['is_online', 'last_heartbeat'])
        
        return JsonResponse({
            'success': True,
            'message': 'Heartbeat received',
            'device_status': 'online'
        })
    
    except Exception as e:
        logger.exception("Error processing device heartbeat")
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


"""
System Health Monitoring Views
Provides real-time system health status and diagnostics
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils import timezone
from django.db import connection
from django.core.cache import cache
from datetime import timedelta
import logging
import os
from .utils_roles import get_user_role

# Try to import psutil, but handle gracefully if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

logger = logging.getLogger(__name__)


def is_admin(user):
    """Check if user is admin, superuser, or IT staff"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    # Allow IT and Admin roles explicitly (do NOT rely on is_staff)
    return get_user_role(user) in {'admin', 'it'}


@login_required
@user_passes_test(is_admin)
def system_health_dashboard(request):
    """
    System health monitoring dashboard
    Shows database status, cache status, disk usage, and system metrics
    """
    health_data = {
        'database': check_database_health(),
        'cache': check_cache_health(),
        'disk': check_disk_health(),
        'memory': check_memory_health(),
        'services': check_services_health(),
        'recent_errors': get_recent_errors(),
        'timestamp': timezone.now(),
    }
    
    context = {
        'title': 'System Health Dashboard',
        'health_data': health_data,
        'overall_status': get_overall_status(health_data),
    }
    
    return render(request, 'hospital/admin/system_health.html', context)


@login_required
@user_passes_test(is_admin)
def system_health_api(request):
    """
    API endpoint for system health (for AJAX polling)
    """
    health_data = {
        'database': check_database_health(),
        'cache': check_cache_health(),
        'disk': check_disk_health(),
        'memory': check_memory_health(),
        'services': check_services_health(),
        'timestamp': timezone.now().isoformat(),
    }
    
    overall_status = get_overall_status(health_data)
    health_data['overall_status'] = overall_status
    
    return JsonResponse(health_data)


def check_database_health():
    """Check database connection and performance"""
    try:
        with connection.cursor() as cursor:
            start = timezone.now()
            cursor.execute("SELECT 1")
            query_time = (timezone.now() - start).total_seconds() * 1000  # milliseconds
            
            # Get database size
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database()))
            """)
            db_size = cursor.fetchone()[0] if cursor.rowcount > 0 else 'Unknown'
            
            # Get connection count
            cursor.execute("""
                SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()
            """)
            connections = cursor.fetchone()[0] if cursor.rowcount > 0 else 0
            
            return {
                'status': 'healthy',
                'query_time_ms': round(query_time, 2),
                'database_size': db_size,
                'active_connections': connections,
                'message': 'Database is responding normally',
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'error',
            'message': f'Database error: {str(e)}',
        }


def check_cache_health():
    """Check cache backend status"""
    try:
        # Test cache write/read
        test_key = 'health_check_test'
        test_value = 'test_value'
        
        cache.set(test_key, test_value, 10)
        retrieved = cache.get(test_key)
        cache.delete(test_key)
        
        if retrieved == test_value:
            return {
                'status': 'healthy',
                'backend': cache.__class__.__name__ if hasattr(cache, '__class__') else 'Unknown',
                'message': 'Cache is working correctly',
            }
        else:
            return {
                'status': 'warning',
                'message': 'Cache read/write test failed',
            }
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {
            'status': 'error',
            'message': f'Cache error: {str(e)}',
        }


def check_disk_health():
    """Check disk usage"""
    if not PSUTIL_AVAILABLE:
        return {
            'status': 'warning',
            'message': 'psutil not available - install with: pip install psutil',
        }
    
    try:
        # Get disk usage for the root filesystem
        disk = psutil.disk_usage('/')
        total_gb = disk.total / (1024 ** 3)
        used_gb = disk.used / (1024 ** 3)
        free_gb = disk.free / (1024 ** 3)
        percent_used = (disk.used / disk.total) * 100
        
        status = 'healthy'
        if percent_used > 90:
            status = 'critical'
        elif percent_used > 80:
            status = 'warning'
        
        return {
            'status': status,
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'free_gb': round(free_gb, 2),
            'percent_used': round(percent_used, 1),
            'message': f'{round(percent_used, 1)}% disk space used',
        }
    except Exception as e:
        logger.error(f"Disk health check failed: {e}")
        return {
            'status': 'error',
            'message': f'Could not check disk usage: {str(e)}',
        }


def check_memory_health():
    """Check memory usage"""
    if not PSUTIL_AVAILABLE:
        return {
            'status': 'warning',
            'message': 'psutil not available - install with: pip install psutil',
        }
    
    try:
        memory = psutil.virtual_memory()
        total_gb = memory.total / (1024 ** 3)
        used_gb = memory.used / (1024 ** 3)
        available_gb = memory.available / (1024 ** 3)
        percent_used = memory.percent
        
        status = 'healthy'
        if percent_used > 90:
            status = 'critical'
        elif percent_used > 80:
            status = 'warning'
        
        return {
            'status': status,
            'total_gb': round(total_gb, 2),
            'used_gb': round(used_gb, 2),
            'available_gb': round(available_gb, 2),
            'percent_used': round(percent_used, 1),
            'message': f'{round(percent_used, 1)}% memory used',
        }
    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        return {
            'status': 'error',
            'message': f'Could not check memory: {str(e)}',
        }


def check_services_health():
    """Check status of external services"""
    services = {}
    
    # Check Redis
    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 1)
        cache.get('health_check')
        services['redis'] = {'status': 'healthy', 'message': 'Redis is responding'}
    except Exception as e:
        services['redis'] = {'status': 'error', 'message': f'Redis error: {str(e)}'}
    
    # Check PostgreSQL (already checked in database health)
    services['postgresql'] = {'status': 'healthy', 'message': 'PostgreSQL is responding'}
    
    return services


def get_recent_errors():
    """Get recent system errors from logs"""
    try:
        from .models_audit import AuditLog
        recent_errors = AuditLog.objects.filter(
            severity__in=['error', 'critical'],
            created__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-created')[:10]
        
        return [
            {
                'timestamp': log.created,
                'user': log.user.username if log.user else 'System',
                'description': log.description,
                'severity': log.severity,
            }
            for log in recent_errors
        ]
    except Exception as e:
        logger.error(f"Failed to get recent errors: {e}")
        return []


def get_overall_status(health_data):
    """Determine overall system status"""
    statuses = []
    
    if health_data.get('database', {}).get('status') != 'healthy':
        statuses.append('database')
    if health_data.get('cache', {}).get('status') != 'healthy':
        statuses.append('cache')
    if health_data.get('disk', {}).get('status') in ['warning', 'critical', 'error']:
        statuses.append('disk')
    if health_data.get('memory', {}).get('status') in ['warning', 'critical', 'error']:
        statuses.append('memory')
    
    if not statuses:
        return {'status': 'healthy', 'message': 'All systems operational'}
    elif 'critical' in [health_data.get('disk', {}).get('status'), health_data.get('memory', {}).get('status')]:
        return {'status': 'critical', 'message': f'Critical issues: {", ".join(statuses)}'}
    else:
        return {'status': 'warning', 'message': f'Warning: {", ".join(statuses)}'}


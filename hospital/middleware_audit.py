"""
Audit Middleware
Automatically logs user actions and system events
"""
import logging
from django.conf import settings
from .middleware_thread_local import set_current_request, clear_current_request

logger = logging.getLogger(__name__)


class AuditMiddleware:
    """
    Middleware to automatically log user actions for audit purposes
    Logs critical operations like create, update, delete, and access
    """
    
    # Actions that should be logged
    LOGGED_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    LOGGED_PATHS = [
        # Patient & Clinical
        '/hms/patients/',
        '/hms/encounters/',
        '/hms/prescriptions/',
        '/hms/orders/',
        '/hms/invoices/',
        '/hms/pharmacy/',
        '/hms/laboratory/',
        '/hms/imaging/',
        '/hms/procedures/',
        
        # Accounting & Finance
        '/hms/accounting/',
        '/hms/finance/',
        '/hms/payments/',
        '/hms/billing/',
        '/hms/invoices/',
        '/hms/claims/',
        
        # HR & Staff Management
        '/hms/hr/',
        '/hms/staff/',
        '/hms/leaves/',
        '/hms/payroll/',
        '/hms/attendance/',
        '/hms/shifts/',
        '/hms/training/',
        '/hms/performance/',
        '/hms/recruitment/',
        
        # Insurance
        '/hms/insurance/',
        '/hms/claims/',
        
        # Procurement & Inventory
        '/hms/procurement/',
        '/hms/inventory/',
        '/hms/stores/',
        
        # Administration
        '/hms/admin/',
        '/hms/settings/',
        '/hms/reports/',
        '/hms/audit-logs/',
        '/hms/activity-logs/',
    ]
    
    # Paths to exclude from logging (too noisy)
    EXCLUDED_PATHS = [
        '/static/',
        '/media/',
        '/api/hospital/sync-check/',
        '/api/hospital/dashboard-updates/',
        '/health/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Store request in thread-local storage for signals to access
        set_current_request(request)
        try:
            # Skip logging for excluded paths
            if not any(request.path.startswith(excluded) for excluded in self.EXCLUDED_PATHS):
                # Only log authenticated users and critical operations
                should_log = (
                    request.user.is_authenticated and
                    request.method in self.LOGGED_METHODS and
                    any(request.path.startswith(path) for path in self.LOGGED_PATHS)
                )
                if should_log:
                    try:
                        from .models_audit import ActivityLog
                        from .activity_log_context import resolve_activity_context

                        ip_address = self.get_client_ip(request)
                        user_agent = request.META.get('HTTP_USER_AGENT', '')
                        session_key = request.session.session_key if hasattr(request, 'session') else ''

                        activity_type = f"{request.method.lower()}_{request.path.split('/')[2] if len(request.path.split('/')) > 2 else 'unknown'}"

                        try:
                            description, meta = resolve_activity_context(request)
                        except Exception as ctx_exc:
                            logger.debug("Activity context resolution failed: %s", ctx_exc)
                            description = f"{request.method} {request.path}"
                            meta = {
                                "path": request.path,
                                "method": request.method,
                                "query_params": dict(request.GET),
                            }

                        try:
                            if getattr(settings, 'AUDIT_LOG_ASYNC', True):
                                from hms.tasks import persist_audit_activity_log

                                try:
                                    persist_audit_activity_log.delay(
                                        user_id=request.user.id,
                                        activity_type=activity_type,
                                        description=description[:255],
                                        ip_address=ip_address,
                                        user_agent=user_agent[:500],
                                        session_key=session_key or '',
                                        metadata=meta or {},
                                    )
                                except Exception as enqueue_exc:
                                    logger.warning(
                                        'Async audit enqueue failed, falling back to sync: %s',
                                        enqueue_exc,
                                    )
                                    ActivityLog.log_activity(
                                        user=request.user,
                                        activity_type=activity_type,
                                        description=description[:255],
                                        ip_address=ip_address,
                                        user_agent=user_agent[:500],
                                        session_key=session_key,
                                        metadata=meta,
                                    )
                            else:
                                ActivityLog.log_activity(
                                    user=request.user,
                                    activity_type=activity_type,
                                    description=description[:255],
                                    ip_address=ip_address,
                                    user_agent=user_agent[:500],
                                    session_key=session_key,
                                    metadata=meta,
                                )
                        except Exception as e:
                            logger.warning(f"Failed to log activity: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to import ActivityLog: {e}")
        except Exception as e:
            logger.error(f"Audit middleware error: {e}")
        try:
            return self.get_response(request)
        finally:
            clear_current_request()
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


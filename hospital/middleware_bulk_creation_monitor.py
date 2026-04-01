"""
Bulk Creation Monitor Middleware
Logs and prevents bulk creation attempts across the system
"""
import logging
import time
from django.http import JsonResponse
from django.utils import timezone
from collections import defaultdict

logger = logging.getLogger('hospital.bulk_creation_monitor')

class BulkCreationMonitorMiddleware:
    """
    Monitors and prevents bulk creation attempts
    Tracks creation requests per user/IP to detect bulk operations
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Track creation attempts: {user_id: {endpoint: [timestamps]}}
        self.creation_attempts = defaultdict(lambda: defaultdict(list))
        # Time window for bulk detection (seconds)
        self.TIME_WINDOW = 10
        # Max creations per endpoint per time window
        self.MAX_CREATIONS_PER_WINDOW = 3
        # Cleanup interval (remove old entries)
        self.last_cleanup = time.time()
        self.CLEANUP_INTERVAL = 60  # Cleanup every 60 seconds
        
    def __call__(self, request):
        # Cleanup old entries periodically
        current_time = time.time()
        if current_time - self.last_cleanup > self.CLEANUP_INTERVAL:
            self._cleanup_old_entries(current_time)
            self.last_cleanup = current_time
        
        # Check for bulk creation attempts
        if request.method == 'POST':
            endpoint = request.path
            # Safety check: request.user may not be available if AuthenticationMiddleware hasn't run yet
            user_id = None
            username = 'Anonymous'
            if hasattr(request, 'user') and request.user.is_authenticated:
                user_id = request.user.id
                username = request.user.username
            ip_address = self._get_client_ip(request)
            
            # Check if this is a creation endpoint
            if self._is_creation_endpoint(endpoint):
                timestamp = time.time()
                
                # Track attempt
                if user_id:
                    self.creation_attempts[user_id][endpoint].append(timestamp)
                    
                    # Check for bulk creation
                    recent_attempts = [
                        ts for ts in self.creation_attempts[user_id][endpoint]
                        if timestamp - ts < self.TIME_WINDOW
                    ]
                    
                    if len(recent_attempts) > self.MAX_CREATIONS_PER_WINDOW:
                        # BULK CREATION DETECTED!
                        logger.critical(
                            f"🚨 BULK CREATION DETECTED! "
                            f"User: {username} (ID: {user_id}), "
                            f"Endpoint: {endpoint}, "
                            f"Attempts in {self.TIME_WINDOW}s: {len(recent_attempts)}, "
                            f"IP: {ip_address}, "
                            f"Auto-save: {request.POST.get('auto_save') == 'true' or request.META.get('HTTP_X_AUTO_SAVE') == 'true'}"
                        )
                        
                        # Log request details
                        logger.critical(
                            f"Request details - "
                            f"Method: {request.method}, "
                            f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}, "
                            f"Referer: {request.META.get('HTTP_REFERER', 'None')}"
                        )
                        
                        # Return error response
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Bulk creation detected. Please wait before creating another record.',
                            'error_code': 'BULK_CREATION_DETECTED'
                        }, status=429)  # 429 Too Many Requests
                    
                    # Log normal creation attempt
                    logger.info(
                        f"Creation attempt - "
                        f"User: {username}, "
                        f"Endpoint: {endpoint}, "
                        f"Recent attempts: {len(recent_attempts)}, "
                        f"Auto-save: {request.POST.get('auto_save') == 'true' or request.META.get('HTTP_X_AUTO_SAVE') == 'true'}"
                    )
        
        response = self.get_response(request)
        return response
    
    def _is_creation_endpoint(self, endpoint):
        """Check if endpoint is a creation endpoint"""
        creation_patterns = [
            '/patients/new',
            '/patient-registration',
            '/patient_create',
            '/appointments/new',
            '/appointments/create',
            '/frontdesk/appointments/create',
            '/marketing/objectives/create',
            '/marketing/tasks/create',
            '/sms/send',
            '/sms/bulk',
            '/create',
            '/new',
        ]
        
        return any(pattern in endpoint for pattern in creation_patterns)
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _cleanup_old_entries(self, current_time):
        """Remove entries older than TIME_WINDOW"""
        cutoff_time = current_time - self.TIME_WINDOW
        
        for user_id in list(self.creation_attempts.keys()):
            for endpoint in list(self.creation_attempts[user_id].keys()):
                # Keep only recent timestamps
                self.creation_attempts[user_id][endpoint] = [
                    ts for ts in self.creation_attempts[user_id][endpoint]
                    if ts > cutoff_time
                ]
                
                # Remove empty lists
                if not self.creation_attempts[user_id][endpoint]:
                    del self.creation_attempts[user_id][endpoint]
            
            # Remove users with no endpoints
            if not self.creation_attempts[user_id]:
                del self.creation_attempts[user_id]











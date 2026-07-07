"""
Custom middleware for HMS
"""
import re
from django.conf import settings
from django.http import HttpResponseBadRequest


class PermissiveHostMiddleware:
    """
    In DEBUG mode, allow requests from any private IP address.
    This makes it easier to access the application from other devices on the network.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only apply in DEBUG mode. Read HTTP_HOST directly — get_host() validates
        # ALLOWED_HOSTS and raises DisallowedHost before we can whitelist private IPs.
        if settings.DEBUG:
            raw_host = request.META.get('HTTP_HOST', '')
            host = raw_host.split(':')[0] if raw_host else ''

            if self._is_private_ip(host) and host not in settings.ALLOWED_HOSTS:
                settings.ALLOWED_HOSTS.append(host)

        response = self.get_response(request)
        return response

    def _is_private_ip(self, host):
        """Check if host is a private/local IP address"""
        if not host:
            return False
        
        # Localhost variants
        if host in ['localhost', '127.0.0.1', '0.0.0.0', '::1']:
            return True
        
        # Private IP ranges:
        # 192.168.0.0/16 (192.168.0.0 - 192.168.255.255)
        # 10.0.0.0/8 (10.0.0.0 - 10.255.255.255)
        # 172.16.0.0/12 (172.16.0.0 - 172.31.255.255)
        private_ip_patterns = [
            r'^192\.168\.',  # 192.168.x.x
            r'^10\.',        # 10.x.x.x
            r'^172\.(1[6-9]|2[0-9]|3[0-1])\.',  # 172.16-31.x.x
        ]
        
        for pattern in private_ip_patterns:
            if re.match(pattern, host):
                return True
        
        return False







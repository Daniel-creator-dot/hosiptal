"""
Auto-Save Middleware
Handles auto-save requests and converts them to JSON responses
"""
import json
from django.http import JsonResponse
from django.utils import timezone


class AutoSaveMiddleware:
    """
    Middleware to handle auto-save requests
    Detects auto-save requests and ensures JSON responses
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return self.process_response(request, response)
    
    def process_response(self, request, response):
        # Check if this is an auto-save request
        is_auto_save = (
            request.method == 'POST' and (
                request.POST.get('auto_save') == 'true' or
                request.META.get('HTTP_X_AUTO_SAVE') == 'true'
            )
        )
        
        # If it's an auto-save request and response is not JSON, convert it
        if is_auto_save and response.status_code in [200, 302, 301]:
            # Check if response is already JSON
            content_type = response.get('Content-Type', '')
            if 'application/json' not in content_type:
                # If it's an HTML response (redirect or form submission), return success JSON
                if 'text/html' in content_type or response.status_code in [302, 301]:
                    redirect_url = None
                    if hasattr(response, 'url'):
                        redirect_url = response.url
                    elif 'Location' in response:
                        redirect_url = response['Location']
                    
                    return JsonResponse({
                        'status': 'saved',
                        'message': 'Auto-saved successfully',
                        'timestamp': timezone.now().isoformat(),
                        'redirect': redirect_url
                    })
        
        return response


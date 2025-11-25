"""
Auto-Save Decorators
Decorators to make views auto-save compatible
"""
from functools import wraps
from django.http import JsonResponse
from django.utils import timezone
import json


def autosave_compatible(view_func):
    """
    Decorator that makes a view auto-save compatible
    If request is an auto-save, returns JSON instead of redirecting
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if this is an auto-save request
        is_auto_save = (
            request.POST.get('auto_save') == 'true' or
            request.META.get('HTTP_X_AUTO_SAVE') == 'true'
        )
        
        # Call the original view
        response = view_func(request, *args, **kwargs)
        
        # If it's an auto-save request and response is a redirect, convert to JSON
        if is_auto_save:
            if response.status_code in [302, 301]:  # Redirect
                return JsonResponse({
                    'status': 'saved',
                    'message': 'Auto-saved successfully',
                    'timestamp': timezone.now().isoformat(),
                    'redirect': response.url if hasattr(response, 'url') else None
                })
            elif response.status_code == 200:
                # Check if it's HTML, convert to JSON
                content_type = response.get('Content-Type', '')
                if 'text/html' in content_type:
                    return JsonResponse({
                        'status': 'saved',
                        'message': 'Auto-saved successfully',
                        'timestamp': timezone.now().isoformat()
                    })
        
        return response
    
    return wrapper







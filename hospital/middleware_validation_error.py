"""
Catch ValidationError (e.g. invalid UUID) and return a safe JSON error for API requests.
Prevents raw messages like ['"INVALID" is not a valid UUID.'] from reaching the client.
"""
from django.http import JsonResponse
from django.core.exceptions import ValidationError


class ValidationErrorJSONMiddleware:
    """
    For requests that expect JSON (e.g. fetch/XHR), catch ValidationError
    and return a plain string error so the client never sees the raw list message.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not isinstance(exception, ValidationError):
            return None
        # Only convert to JSON for API-like paths or when Accept asks for JSON
        accept = request.META.get('HTTP_ACCEPT', '') or ''
        path = request.path or ''
        if 'application/json' in accept or '/api/' in path or path.rstrip('/').endswith('-modern'):
            safe_msg = 'Invalid request. Please try again.'
            if hasattr(exception, 'messages') and exception.messages:
                first = exception.messages[0] if exception.messages else ''
                if isinstance(first, str) and ('UUID' in first or 'INVALID' in first.upper()):
                    safe_msg = 'Please select a store from the list.'
            return JsonResponse({'error': safe_msg}, status=400)
        return None

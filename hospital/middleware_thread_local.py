"""
Thread Local Storage for Request Context
Allows signals to access the current request and user
"""
import threading

# Thread-local storage for request context
_thread_locals = threading.local()


def get_current_request():
    """Get the current request from thread-local storage"""
    return getattr(_thread_locals, 'request', None)


def get_current_user():
    """Get the current user from thread-local storage"""
    request = get_current_request()
    if request and hasattr(request, 'user'):
        return request.user
    return None


def set_current_request(request):
    """Set the current request in thread-local storage"""
    _thread_locals.request = request


def clear_current_request():
    """Clear the current request from thread-local storage"""
    if hasattr(_thread_locals, 'request'):
        delattr(_thread_locals, 'request')







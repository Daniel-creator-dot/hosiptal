from django.middleware.csrf import get_token


def global_csrf_token(request):
    """
    Expose the current CSRF token to all templates so that
    JavaScript can read it via meta tags when cookies are HttpOnly.
    """
    return {
        'global_csrf_token': get_token(request),
    }







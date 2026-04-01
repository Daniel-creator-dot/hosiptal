"""
Views for HMS project.
"""
from django.shortcuts import render, redirect
from django.http import HttpResponse
import logging

logger = logging.getLogger(__name__)


def home(request):
    """
    Homepage view for the HMS application.
    Redirects to HMS dashboard.
    """
    try:
        logger.info("Home view accessed")
        # Redirect to HMS dashboard instead of showing landing page
        return redirect('/hms/')
    except Exception as e:
        logger.error(f"Error in home view: {e}", exc_info=True)
        return HttpResponse(f"Error: {e}", status=500)


def favicon(request):
    """
    Return empty favicon response to avoid 404 errors.
    Browsers automatically request this, but it's not critical.
    Returns a 1x1 transparent PNG to satisfy browser requests.
    """
    # Return a minimal 1x1 transparent PNG favicon
    # This is a valid PNG that browsers will accept
    transparent_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
    return HttpResponse(transparent_png, content_type='image/png')


def handler404(request, exception):
    """Custom 404 error handler - always accessible"""
    try:
        return render(request, 'hospital/errors/404.html', {
            'dashboard_url': '/hms/',
            'login_url': '/hms/login/',
        }, status=404)
    except Exception as e:
        logger.error(f"Error rendering 404 page: {e}", exc_info=True)
        # Fallback minimal HTML if template fails
        return HttpResponse(
            '<html><body><h1>404 - Page Not Found</h1>'
            '<p>The page you requested does not exist.</p>'
            '<p><a href="/hms/">Go to Dashboard</a> | <a href="/hms/login/">Login</a></p>'
            '</body></html>',
            status=404
        )


def handler500(request):
    """Custom 500 error handler - always accessible"""
    try:
        return render(request, 'hospital/errors/500.html', {
            'dashboard_url': '/hms/',
            'login_url': '/hms/login/',
        }, status=500)
    except Exception as e:
        logger.error(f"Error rendering 500 page: {e}", exc_info=True)
        # Fallback minimal HTML if template fails
        return HttpResponse(
            '<html><body><h1>500 - Server Error</h1>'
            '<p>An unexpected error occurred. Please try again later.</p>'
            '<p><a href="/hms/">Go to Dashboard</a> | <a href="/hms/login/">Login</a></p>'
            '</body></html>',
            status=500
        )


def handler403(request, exception):
    """Custom 403 error handler - always accessible"""
    try:
        return render(request, 'hospital/errors/403.html', {
            'dashboard_url': '/hms/',
            'login_url': '/hms/login/',
            'exception': str(exception) if exception else None,
        }, status=403)
    except Exception as e:
        logger.error(f"Error rendering 403 page: {e}", exc_info=True)
        # Fallback minimal HTML if template fails
        return HttpResponse(
            '<html><body><h1>403 - Access Denied</h1>'
            '<p>You do not have permission to access this resource.</p>'
            '<p><a href="/hms/">Go to Dashboard</a> | <a href="/hms/login/">Login</a></p>'
            '</body></html>',
            status=403
        )

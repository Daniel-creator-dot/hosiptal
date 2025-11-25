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
    Return empty response for favicon.ico to avoid 400 errors.
    Browsers automatically request this, but it's not critical.
    """
    return HttpResponse(status=204)


def handler404(request, exception):
    """Custom 404 error handler"""
    return render(request, 'hospital/errors/404.html', status=404)


def handler500(request):
    """Custom 500 error handler"""
    return render(request, 'hospital/errors/500.html', status=500)


def handler403(request, exception):
    """Custom 403 error handler"""
    return render(request, 'hospital/errors/403.html', status=403)

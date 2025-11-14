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

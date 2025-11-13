"""
Views for HMS project.
"""
from django.shortcuts import render
from django.http import HttpResponse


def home(request):
    """
    Homepage view for the HMS application.
    """
    context = {
        'title': 'Hospital Management System',
        'services': [
            {'name': 'Admin Panel', 'url': '/admin/', 'description': 'System administration'},
            {'name': 'API', 'url': '/api/', 'description': 'REST API endpoints'},
            {'name': 'Health Check', 'url': '/health/', 'description': 'System health monitoring'},
            {'name': 'Prometheus Metrics', 'url': '/prometheus/', 'description': 'System metrics'},
            {'name': 'MinIO Console', 'url': 'http://localhost:9001/', 'description': 'File storage management'},
        ]
    }
    return render(request, 'home.html', context)

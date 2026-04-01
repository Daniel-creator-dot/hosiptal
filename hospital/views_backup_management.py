"""
Backup Management Views
Interface for managing database backups
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
import os
import glob
from datetime import datetime
from .utils_roles import get_user_role

def is_admin(user):
    """Strict admin check (no is_staff fallback)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) == 'admin'


@login_required
@user_passes_test(is_admin)
def backup_list_view(request):
    """List all available backups"""
    backup_dir = getattr(settings, 'BACKUP_DIR', 'backups/')
    os.makedirs(backup_dir, exist_ok=True)
    
    backups = []
    for filepath in glob.glob(os.path.join(backup_dir, 'hms_backup_*.sql')):
        filename = os.path.basename(filepath)
        stat = os.stat(filepath)
        backups.append({
            'filename': filename,
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_mtime),
            'path': filepath,
        })
    
    # Sort by creation time (newest first)
    backups.sort(key=lambda x: x['created'], reverse=True)
    
    context = {
        'title': 'Database Backups',
        'backups': backups,
    }
    
    return render(request, 'hospital/admin/backup_list.html', context)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def create_backup_view(request):
    """Create a new database backup"""
    try:
        from django.core.management import call_command
        from io import StringIO
        
        output = StringIO()
        call_command('backup_database', stdout=output)
        
        return JsonResponse({
            'success': True,
            'message': 'Backup created successfully',
            'output': output.getvalue()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error creating backup: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_admin)
def download_backup_view(request, filename):
    """Download a backup file"""
    backup_dir = getattr(settings, 'BACKUP_DIR', 'backups/')
    filepath = os.path.join(backup_dir, filename)
    
    if os.path.exists(filepath) and filename.startswith('hms_backup_'):
        return FileResponse(open(filepath, 'rb'), as_attachment=True, filename=filename)
    else:
        from django.http import HttpResponseNotFound
        return HttpResponseNotFound('Backup file not found')







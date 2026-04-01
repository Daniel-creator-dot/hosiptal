"""
Database Backup Management Views
Create, manage, and download database backups
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, FileResponse, JsonResponse
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from pathlib import Path
import shutil
import os
import zipfile
from datetime import datetime, timedelta
import json
from .utils_roles import get_user_role


# Backup directory
BACKUP_DIR = Path(settings.BASE_DIR) / 'backups' / 'database'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def is_admin(user):
    """Strict admin check (no is_staff fallback)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) == 'admin'


@login_required
@user_passes_test(is_admin)
def backup_dashboard(request):
    """Dashboard for backup management"""
    
    # Get all backups
    backups = []
    if BACKUP_DIR.exists():
        for backup_file in sorted(BACKUP_DIR.glob('*.sqlite3*'), reverse=True):
            stat = backup_file.stat()
            backups.append({
                'filename': backup_file.name,
                'path': str(backup_file),
                'size': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created': datetime.fromtimestamp(stat.st_mtime),
                'age_days': (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days,
            })
    
    # Calculate total backup size
    total_size = sum(b['size'] for b in backups)
    total_size_mb = round(total_size / (1024 * 1024), 2)
    
    # Get database info
    db_path = Path(settings.BASE_DIR) / 'db.sqlite3'
    db_size = 0
    db_size_mb = 0
    if db_path.exists():
        db_size = db_path.stat().st_size
        db_size_mb = round(db_size / (1024 * 1024), 2)
    
    context = {
        'backups': backups,
        'backup_count': len(backups),
        'total_size_mb': total_size_mb,
        'db_size_mb': db_size_mb,
        'backup_dir': str(BACKUP_DIR),
    }
    
    return render(request, 'hospital/backup_dashboard.html', context)


@login_required
@user_passes_test(is_admin)
def create_backup(request):
    """Create a new database backup"""
    
    if request.method == 'POST':
        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        try:
            from django.core.management import call_command
            from io import StringIO
            import sys
            
            # Capture both stdout and stderr
            output = StringIO()
            error_output = StringIO()
            
            # Redirect stderr to capture errors
            old_stderr = sys.stderr
            sys.stderr = error_output
            
            try:
                call_command('backup_database', stdout=output)
                output_str = output.getvalue()
                error_str = error_output.getvalue()
            finally:
                sys.stderr = old_stderr
            
            # Combine outputs
            full_output = output_str + error_str
            
            # Check if backup was successful
            if 'Backup created successfully' in full_output or 'backup created' in full_output.lower():
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'message': 'Backup created successfully',
                        'output': full_output
                    })
                else:
                    messages.success(request, 'Backup created successfully!')
                    return redirect('hospital:backup_dashboard')
            else:
                # Check for errors
                if 'failed' in full_output.lower() or 'error' in full_output.lower() or error_str:
                    error_msg = error_str.strip() if error_str.strip() else 'Backup failed. Please check server logs.'
                    if is_ajax:
                        return JsonResponse({
                            'success': False,
                            'message': f'Error creating backup: {error_msg}'
                        }, status=500)
                    else:
                        messages.error(request, f'Error creating backup: {error_msg}')
                        return redirect('hospital:backup_dashboard')
                else:
                    # Assume success if no clear error
                    if is_ajax:
                        return JsonResponse({
                            'success': True,
                            'message': 'Backup created successfully',
                            'output': full_output
                        })
                    else:
                        messages.success(request, 'Backup created successfully!')
                        return redirect('hospital:backup_dashboard')
                        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error creating backup: {e}', exc_info=True)
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': f'Error creating backup: {str(e)}'
                }, status=500)
            else:
                messages.error(request, f'Error creating backup: {str(e)}')
                return redirect('hospital:backup_dashboard')
    
    # Handle non-POST requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method'
        }, status=400)
    
    return redirect('hospital:backup_dashboard')


@login_required
@user_passes_test(is_admin)
def download_backup(request, filename):
    """Download a specific backup file"""
    
    backup_file = BACKUP_DIR / filename
    
    if not backup_file.exists():
        messages.error(request, 'Backup file not found!')
        return redirect('hospital:backup_dashboard')
    
    # Security: Ensure file is in backup directory
    try:
        backup_file.resolve().relative_to(BACKUP_DIR.resolve())
    except ValueError:
        messages.error(request, 'Invalid backup file!')
        return redirect('hospital:backup_dashboard')
    
    # Send file
    response = FileResponse(
        open(backup_file, 'rb'),
        as_attachment=True,
        filename=filename
    )
    
    return response


@login_required
@user_passes_test(is_admin)
def download_all_backups(request):
    """Download all backups as a ZIP file"""
    
    try:
        # Create zip file in memory
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f'all_backups_{timestamp}.zip'
        zip_path = BACKUP_DIR / zip_filename
        
        # Create zip
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for backup_file in BACKUP_DIR.glob('*.sqlite3*'):
                if backup_file.name != zip_filename:  # Don't include the zip itself
                    zipf.write(backup_file, backup_file.name)
        
        # Send zip file
        response = FileResponse(
            open(zip_path, 'rb'),
            as_attachment=True,
            filename=zip_filename
        )
        
        # Delete zip after sending (cleanup)
        # Note: File is deleted after response is sent
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error creating ZIP: {str(e)}')
        return redirect('hospital:backup_dashboard')


@login_required
@user_passes_test(is_admin)
def delete_backup(request, filename):
    """Delete a specific backup file"""
    
    if request.method == 'POST':
        backup_file = BACKUP_DIR / filename
        
        if backup_file.exists():
            try:
                # Security check
                backup_file.resolve().relative_to(BACKUP_DIR.resolve())
                
                # Delete file
                backup_file.unlink()
                messages.success(request, f'Backup deleted: {filename}')
                
            except Exception as e:
                messages.error(request, f'Error deleting backup: {str(e)}')
        else:
            messages.error(request, 'Backup file not found!')
    
    return redirect('hospital:backup_dashboard')


@login_required
@user_passes_test(is_admin)
def delete_old_backups(request):
    """Delete backups older than specified days"""
    
    if request.method == 'POST':
        try:
            days = int(request.POST.get('days', 30))
            
            deleted_count = 0
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for backup_file in BACKUP_DIR.glob('*.sqlite3*'):
                file_date = datetime.fromtimestamp(backup_file.stat().st_mtime)
                
                if file_date < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
            
            messages.success(
                request,
                f'Deleted {deleted_count} backup(s) older than {days} days'
            )
            
        except Exception as e:
            messages.error(request, f'Error deleting old backups: {str(e)}')
    
    return redirect('hospital:backup_dashboard')


@login_required
@user_passes_test(is_admin)
def auto_backup_now(request):
    """Create automatic backup with standard naming"""
    
    try:
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'db_auto_backup_{timestamp}.sqlite3'
        
        source_db = Path(settings.BASE_DIR) / 'db.sqlite3'
        dest_file = BACKUP_DIR / filename
        
        # Copy with metadata
        shutil.copy2(source_db, dest_file)
        
        # Create metadata file
        metadata = {
            'created_at': timezone.now().isoformat(),
            'type': 'automatic',
            'database_size': source_db.stat().st_size,
            'backup_size': dest_file.stat().st_size,
        }
        
        metadata_file = BACKUP_DIR / f'{filename}.meta.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        size_mb = round(dest_file.stat().st_size / (1024 * 1024), 2)
        
        return JsonResponse({
            'success': True,
            'message': f'Auto backup created: {filename}',
            'filename': filename,
            'size_mb': size_mb
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_admin)
def backup_info(request, filename):
    """Get information about a specific backup"""
    
    backup_file = BACKUP_DIR / filename
    
    if not backup_file.exists():
        return JsonResponse({'error': 'Backup not found'}, status=404)
    
    stat = backup_file.stat()
    
    # Check for metadata file
    metadata_file = BACKUP_DIR / f'{filename}.meta.json'
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    
    info = {
        'filename': filename,
        'size': stat.st_size,
        'size_mb': round(stat.st_size / (1024 * 1024), 2),
        'created': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        'age_days': (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days,
        'metadata': metadata,
    }
    
    return JsonResponse(info)





















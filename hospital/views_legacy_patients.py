"""
Legacy Patient Management Views
Views for doctors and staff to manage legacy patients
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
import re
from datetime import datetime

from .models import Patient, Encounter, Staff
from .models_legacy_patients import LegacyPatient
from .models_legacy_mapping import LegacyIDMapping


@login_required
def legacy_patient_list(request):
    """View all legacy patients with migration status"""
    # Get search query
    search_query = request.GET.get('q', '')
    filter_status = request.GET.get('status', 'all')  # all, migrated, not_migrated
    
    # Get all legacy patients
    legacy_patients = LegacyPatient.objects.all().order_by('-id')
    
    # Apply search filter
    if search_query:
        legacy_patients = legacy_patients.filter(
            Q(fname__icontains=search_query) |
            Q(lname__icontains=search_query) |
            Q(pid__icontains=search_query) |
            Q(phone_cell__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Get migration status for each
    results = []
    for lp in legacy_patients:
        mrn = f'PMC-LEG-{str(lp.pid).zfill(6)}'
        django_patient = Patient.objects.filter(mrn=mrn, is_deleted=False).first()
        
        # Apply status filter
        if filter_status == 'migrated' and not django_patient:
            continue
        elif filter_status == 'not_migrated' and django_patient:
            continue
        
        results.append({
            'legacy_patient': lp,
            'django_patient': django_patient,
            'is_migrated': bool(django_patient),
            'mrn': mrn
        })
    
    # Pagination
    paginator = Paginator(results, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_legacy = LegacyPatient.objects.count()
    total_migrated = Patient.objects.filter(mrn__startswith='PMC-LEG-', is_deleted=False).count()
    total_not_migrated = total_legacy - total_migrated
    migration_percentage = (total_migrated / total_legacy * 100) if total_legacy > 0 else 0
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'filter_status': filter_status,
        'total_legacy': total_legacy,
        'total_migrated': total_migrated,
        'total_not_migrated': total_not_migrated,
        'migration_percentage': round(migration_percentage, 1),
    }
    
    return render(request, 'hospital/legacy_patients/list.html', context)


@login_required
def legacy_patient_detail(request, pid):
    """View details of a legacy patient"""
    legacy_patient = get_object_or_404(LegacyPatient, pid=pid)
    mrn = f'PMC-LEG-{str(legacy_patient.pid).zfill(6)}'
    
    # Check if migrated
    django_patient = Patient.objects.filter(mrn=mrn, is_deleted=False).first()
    
    # Get encounters if migrated
    encounters = []
    if django_patient:
        encounters = Encounter.objects.filter(
            patient=django_patient,
            is_deleted=False
        ).select_related('provider').order_by('-started_at')[:10]
    
    context = {
        'legacy_patient': legacy_patient,
        'django_patient': django_patient,
        'encounters': encounters,
        'is_migrated': bool(django_patient),
        'mrn': mrn,
    }
    
    return render(request, 'hospital/legacy_patients/detail.html', context)


@login_required
def migrate_legacy_patient(request, pid):
    """Migrate a single legacy patient to Django system"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    legacy_patient = get_object_or_404(LegacyPatient, pid=pid)
    mrn = f'PMC-LEG-{str(legacy_patient.pid).zfill(6)}'
    
    # Check if already migrated
    existing = Patient.objects.filter(mrn=mrn, is_deleted=False).first()
    if existing:
        messages.warning(request, f'Patient {legacy_patient.full_name} is already migrated (MRN: {mrn})')
        return redirect('hospital:legacy_patient_detail', pid=pid)
    
    try:
        # Migrate patient
        with transaction.atomic():
            # Parse DOB
            dob = parse_date(legacy_patient.DOB) or '2000-01-01'
            
            # Parse gender
            gender = parse_gender(legacy_patient.sex)
            
            # Clean names
            first_name = clean_name(legacy_patient.fname or 'Unknown')
            last_name = clean_name(legacy_patient.lname or 'Patient')
            middle_name = clean_name(legacy_patient.mname or '')
            
            # Create Django patient
            patient = Patient.objects.create(
                mrn=mrn,
                first_name=first_name,
                last_name=last_name,
                middle_name=middle_name,
                date_of_birth=dob,
                gender=gender,
                phone_number=clean_phone(legacy_patient.phone_cell or legacy_patient.phone_home or ''),
                email=legacy_patient.email or '',
                address=build_address(legacy_patient),
                next_of_kin_name=legacy_patient.guardiansname or legacy_patient.mothersname or '',
                next_of_kin_phone=clean_phone(legacy_patient.guardianphone or ''),
                next_of_kin_relationship=legacy_patient.guardianrelationship or '',
            )
            
            # Create mapping record
            LegacyIDMapping.objects.create(
                legacy_table='patient_data',
                legacy_id=str(legacy_patient.pid),
                new_model='Patient',
                new_id=patient.id,
                migration_batch='manual_migration',
                notes=f'Manually migrated by {request.user.username} from PID {legacy_patient.pid}'
            )
        
        messages.success(request, f'Successfully migrated {patient.full_name} (MRN: {patient.mrn})')
        return redirect('hospital:patient_detail', pk=patient.pk)
        
    except Exception as e:
        messages.error(request, f'Error migrating patient: {str(e)}')
        return redirect('hospital:legacy_patient_detail', pid=pid)


@login_required
def migration_dashboard(request):
    """Dashboard showing migration status and tools"""
    # Get migration statistics
    total_legacy = LegacyPatient.objects.count()
    total_django = Patient.objects.filter(is_deleted=False).count()
    total_migrated = Patient.objects.filter(mrn__startswith='PMC-LEG-', is_deleted=False).count()
    total_not_migrated = total_legacy - total_migrated
    migration_percentage = (total_migrated / total_legacy * 100) if total_legacy > 0 else 0
    
    # Get recent migrations
    recent_migrations = LegacyIDMapping.objects.filter(
        legacy_table='patient_data'
    ).select_related().order_by('-migrated_at')[:20]
    
    # Get unmigrated patients sample
    unmigrated_sample = []
    for lp in LegacyPatient.objects.all()[:100]:
        mrn = f'PMC-LEG-{str(lp.pid).zfill(6)}'
        if not Patient.objects.filter(mrn=mrn, is_deleted=False).exists():
            unmigrated_sample.append(lp)
            if len(unmigrated_sample) >= 10:
                break
    
    # Get recent migrated patients
    recent_migrated = Patient.objects.filter(
        mrn__startswith='PMC-LEG-',
        is_deleted=False
    ).order_by('-created')[:10]
    
    context = {
        'total_legacy': total_legacy,
        'total_django': total_django,
        'total_migrated': total_migrated,
        'total_not_migrated': total_not_migrated,
        'migration_percentage': round(migration_percentage, 1),
        'recent_migrations': recent_migrations,
        'unmigrated_sample': unmigrated_sample,
        'recent_migrated': recent_migrated,
    }
    
    return render(request, 'hospital/legacy_patients/migration_dashboard.html', context)


@login_required
def bulk_migrate_patients(request):
    """Trigger bulk migration of legacy patients"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    # Get parameters
    limit = int(request.POST.get('limit', 100))
    
    # Run migration in background (you could use Celery for this)
    from django.core.management import call_command
    
    try:
        # Call the migration command
        call_command('bulk_migrate_legacy', batch_size=limit, skip_existing=True)
        
        messages.success(request, f'Bulk migration started for up to {limit} patients. Check migration dashboard for progress.')
        return redirect('hospital:migration_dashboard')
        
    except Exception as e:
        messages.error(request, f'Error starting bulk migration: {str(e)}')
        return redirect('hospital:migration_dashboard')


# Helper functions
def parse_date(date_str):
    """Parse various date formats"""
    if not date_str or str(date_str) in ['0000-00-00', '', 'None']:
        return None
    
    try:
        return datetime.strptime(str(date_str)[:10], '%Y-%m-%d').date()
    except:
        return None


def parse_gender(sex):
    """Parse gender"""
    if not sex:
        return 'O'
    sex_upper = str(sex).upper()
    if sex_upper in ['M', 'MALE']:
        return 'M'
    elif sex_upper in ['F', 'FEMALE']:
        return 'F'
    return 'O'


def clean_name(name):
    """Clean name field"""
    if not name:
        return ''
    name = re.sub(r'\d+', '', str(name))
    name = re.sub(r'[^\w\s\-]', '', name)
    return name.strip()


def clean_phone(phone):
    """Clean phone number"""
    if not phone:
        return ''
    phone = re.sub(r'[^\d\+]', '', str(phone))
    return phone[:17]


def build_address(legacy_patient):
    """Build address from legacy fields"""
    parts = []
    if legacy_patient.street:
        parts.append(str(legacy_patient.street))
    if legacy_patient.city:
        parts.append(str(legacy_patient.city))
    if legacy_patient.state:
        parts.append(str(legacy_patient.state))
    
    return ', '.join(filter(None, parts)) or ''



















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
from django.db import transaction, ProgrammingError, OperationalError, connection
import re
from datetime import datetime

from .models import Patient, Encounter, Staff
try:
    from .models_legacy_patients import LegacyPatient
    LEGACY_PATIENT_AVAILABLE = True
except Exception:
    LegacyPatient = None
    LEGACY_PATIENT_AVAILABLE = False

from .models_legacy_mapping import LegacyIDMapping


def _legacy_table_exists():
    """Check if patient_data table exists"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'patient_data'
                );
            """)
            return cursor.fetchone()[0]
    except Exception:
        return False


@login_required
def legacy_patient_list(request):
    """View all legacy patients with migration status"""
    if not LEGACY_PATIENT_AVAILABLE or not _legacy_table_exists():
        messages.warning(request, 'Legacy patient table (patient_data) does not exist in the database.')
        return redirect('hospital:dashboard')
    
    # Get search query
    search_query = request.GET.get('q', '')
    filter_status = request.GET.get('status', 'all')  # all, migrated, not_migrated
    
    try:
        # Get all legacy patients
        legacy_patients = LegacyPatient.objects.all().order_by('-id')
    except (ProgrammingError, OperationalError):
        messages.error(request, 'Legacy patient table is not accessible.')
        return redirect('hospital:dashboard')
    
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
    try:
        total_legacy = LegacyPatient.objects.count()
        total_migrated = Patient.objects.filter(mrn__startswith='PMC-LEG-', is_deleted=False).count()
        total_not_migrated = total_legacy - total_migrated
        migration_percentage = (total_migrated / total_legacy * 100) if total_legacy > 0 else 0
    except (ProgrammingError, OperationalError):
        total_legacy = 0
        total_migrated = 0
        total_not_migrated = 0
        migration_percentage = 0
    
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
    if not LEGACY_PATIENT_AVAILABLE or not _legacy_table_exists():
        messages.warning(request, 'Legacy patient table (patient_data) does not exist in the database.')
        return redirect('hospital:dashboard')
    
    try:
        legacy_patient = get_object_or_404(LegacyPatient, pid=pid)
    except (ProgrammingError, OperationalError):
        messages.error(request, 'Legacy patient table is not accessible.')
        return redirect('hospital:dashboard')
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
    
    if not LEGACY_PATIENT_AVAILABLE or not _legacy_table_exists():
        messages.warning(request, 'Legacy patient table (patient_data) does not exist in the database.')
        return redirect('hospital:dashboard')
    
    try:
        legacy_patient = get_object_or_404(LegacyPatient, pid=pid)
    except (ProgrammingError, OperationalError):
        messages.error(request, 'Legacy patient table is not accessible.')
        return redirect('hospital:dashboard')
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
    # Check if legacy table exists
    legacy_table_exists = _legacy_table_exists()
    
    if not LEGACY_PATIENT_AVAILABLE or not legacy_table_exists:
        messages.info(
            request,
            'Legacy patient table (patient_data) does not exist in the database. '
            'This table is only available when connected to the legacy MySQL database. '
            'Legacy patients have been migrated to the main Patient model.'
        )
        # Show dashboard with only Django patient stats
        total_django = Patient.objects.filter(is_deleted=False).count()
        total_migrated = Patient.objects.filter(mrn__startswith='PMC-LEG-', is_deleted=False).count()
        
        context = {
            'total_legacy': 0,
            'total_django': total_django,
            'total_migrated': total_migrated,
            'total_not_migrated': 0,
            'migration_percentage': 100.0 if total_migrated > 0 else 0.0,
            'recent_migrations': [],
            'unmigrated_sample': [],
            'recent_migrated': Patient.objects.filter(
                mrn__startswith='PMC-LEG-',
                is_deleted=False
            ).order_by('-created')[:10],
            'legacy_table_exists': False,
        }
        return render(request, 'hospital/legacy_patients/migration_dashboard.html', context)
    
    try:
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
            'legacy_table_exists': True,
        }
        
        return render(request, 'hospital/legacy_patients/migration_dashboard.html', context)
        
    except (ProgrammingError, OperationalError) as e:
        messages.error(request, f'Error accessing legacy patient data: {str(e)}')
        # Return dashboard with default values
        total_django = Patient.objects.filter(is_deleted=False).count()
        total_migrated = Patient.objects.filter(mrn__startswith='PMC-LEG-', is_deleted=False).count()
        
        context = {
            'total_legacy': 0,
            'total_django': total_django,
            'total_migrated': total_migrated,
            'total_not_migrated': 0,
            'migration_percentage': 100.0 if total_migrated > 0 else 0.0,
            'recent_migrations': [],
            'unmigrated_sample': [],
            'recent_migrated': Patient.objects.filter(
                mrn__startswith='PMC-LEG-',
                is_deleted=False
            ).order_by('-created')[:10],
            'legacy_table_exists': False,
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



















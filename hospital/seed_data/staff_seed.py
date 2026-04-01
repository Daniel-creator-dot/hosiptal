"""
Reusable helpers for seeding baseline staff data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Dict, List, Optional, Tuple

from django.apps import apps
from django.contrib.auth.models import User
from django.db import transaction

# Staff data from spreadsheet (shared with management commands and auto-seeding)
STAFF_DATA: List[Dict[str, Optional[str]]] = [
    # Nurses - dates in DD/MM/YYYY format
    {'name': 'Matron Maegaret Ansong', 'phone': '0244489832', 'dob': None, 'dept': 'Nurses', 'profession': 'nurse'},
    {'name': 'Mary Ellis', 'phone': '0245934819', 'dob': '10/6/1988', 'dept': 'Nurses', 'profession': 'nurse'},
    {'name': 'Patience Xorlali Zakli', 'phone': '0533893821', 'dob': None, 'dept': 'Nurses', 'profession': 'nurse'},
    {'name': 'Vida Blankson', 'phone': '0558105165', 'dob': None, 'dept': 'Nurses', 'profession': 'nurse'},
    # Cashier - dates in DD/MM/YYYY format
    {'name': 'Fortune Fafa Dogbe', 'phone': '', 'dob': '14/11/1999', 'dept': 'Cashier', 'profession': 'cashier'},
    {'name': 'Rebecca', 'phone': '0242045148', 'dob': None, 'dept': 'Cashier', 'profession': 'cashier'},
    # Laboratory - dates in DD/MM/YYYY format
    {'name': 'Evans Osei Asare', 'phone': '0552534425', 'dob': '3/12/1993', 'dept': 'Laboratory', 'profession': 'lab_technician'},
    # Pharmacy - dates in DD/MM/YYYY format
    {'name': 'Gordon Boadu', 'phone': '0540922916', 'dob': '2/5/1992', 'dept': 'Pharmacy', 'profession': 'pharmacist'},
    # BD (Business Development) - dates in DD/MM/YYYY format
    {'name': 'Awudi Mawusi Mercy', 'phone': '0240064493', 'dob': '29/08/1989', 'dept': 'BD', 'profession': 'admin'},
    {'name': 'Jeremiah Anthony Amissah', 'phone': '0247904675', 'dob': None, 'dept': 'BD', 'profession': 'admin'},
    # Accounts - dates in DD/MM/YYYY format
    {'name': 'Robbert Kwame Gbologah', 'phone': '0243187872', 'dob': '1/7/1972', 'dept': 'Accounts', 'profession': 'admin'},
    {'name': 'Nana Yaa B. Asamoah', 'phone': '0209017207', 'dob': '4/12/2003', 'dept': 'Accounts', 'profession': 'admin'},
    # Front Office - dates in DD/MM/YYYY format
    {'name': 'Mavis Ananga', 'phone': '0200024081', 'dob': '5/10/1994', 'dept': 'Front Office', 'profession': 'receptionist'},
    # IT Support - dates in DD/MM/YYYY format
    {'name': 'Johnson Kpatabui Mawuna', 'phone': '0249563432', 'dob': '6/5/1998', 'dept': 'IT Support', 'profession': 'admin'},
    # Scan - dates in DD/MM/YYYY format
    {'name': 'Dorcas Adjei', 'phone': '0559873407', 'dob': '20/08/1996', 'dept': 'Scan', 'profession': 'radiologist'},
    # Sanitation
    {'name': 'Monica Ofori', 'phone': '0595242528', 'dob': None, 'dept': 'Sanitation', 'profession': 'admin'},
    {'name': 'Esther Ogbonna', 'phone': '0248872876', 'dob': None, 'dept': 'Sanitation', 'profession': 'admin'},
    {'name': 'Janet Oppong', 'phone': '0249483660', 'dob': None, 'dept': 'Sanitation', 'profession': 'admin'},
    # X-ray - dates in DD/MM/YYYY format
    {'name': 'Charity Kotey', 'phone': '0557400195', 'dob': '8/5/1996', 'dept': 'X-ray', 'profession': 'radiologist'},
]


def _log(writer: Optional[Callable[[str], None]], message: str) -> None:
    """Write log output to provided writer or stdout."""
    if writer:
        writer(message)
    else:
        print(message)


def parse_name(full_name: str) -> Tuple[str, str]:
    """Parse full name into first and last name parts."""
    parts = (full_name or '').strip().split()
    if len(parts) >= 2:
        first_name = parts[0]
        last_name = ' '.join(parts[1:])
    elif len(parts) == 1:
        first_name = parts[0]
        last_name = ''
    else:
        first_name = 'Unknown'
        last_name = 'Unknown'
    return first_name, last_name


def parse_dob(dob_str: Optional[str]) -> Optional[date]:
    """Parse DD/MM/YYYY or YYYY-MM-DD strings safely."""
    if not dob_str or dob_str == '----':
        return None
    try:
        if '/' in dob_str:
            parts = dob_str.split('/')
            if len(parts) == 3 and all(p for p in parts):
                day, month, year = parts
                if year == '----':
                    return None
                return datetime(int(year), int(month), int(day)).date()
        return datetime.strptime(dob_str, '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None


def format_phone(phone: Optional[str]) -> str:
    """Normalize phone numbers to +233XXXXXXXXX when possible."""
    if not phone or not phone.strip():
        return ''
    cleaned = phone.strip()
    if cleaned.startswith('0'):
        return '+233' + cleaned[1:]
    if not cleaned.startswith('+'):
        return '+233' + cleaned
    return cleaned


@dataclass
class SeedResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return len(STAFF_DATA)


def _ensure_departments(log_writer: Optional[Callable[[str], None]]) -> Dict[str, object]:
    """Create required departments if they do not already exist."""
    Department = apps.get_model('hospital', 'Department')  # Lazy load to avoid circulars
    departments: Dict[str, object] = {}
    dept_names = [
        'Nurses', 'Cashier', 'Laboratory', 'Pharmacy', 'BD', 'Accounts',
        'Front Office', 'IT Support', 'Scan', 'Sanitation', 'X-ray',
        'HR',
    ]
    for dept_name in dept_names:
        dept_code = dept_name.upper().replace(' ', '_')[:10]
        department, created = Department.objects.get_or_create(
            name=dept_name,
            defaults={
                'code': dept_code,
                'description': f'{dept_name} Department',
                'is_active': True,
            },
        )
        departments[dept_name] = department
        if created:
            _log(log_writer, f'[staff-seed] Created department: {dept_name}')
    return departments


def _build_username(first_name: str, last_name: str) -> str:
    """Generate a unique username in firstname.lastname format."""
    base = f"{first_name.lower()}.{last_name.lower().replace(' ', '')}".strip('.')
    if not base:
        base = 'staff'
    base = base[:30]
    username = base
    counter = 1
    while User.objects.filter(username=username).exists():
        suffix = str(counter)
        username = f"{base[:30 - len(suffix)]}{suffix}"
        counter += 1
    return username


def seed_staff_dataset(update: bool = False, stdout_writer: Optional[Callable[[str], None]] = None) -> SeedResult:
    """
    Seed baseline staff records.

    Args:
        update: Update existing staff with seed data when True.
        stdout_writer: Optional callable for logging output (e.g., BaseCommand.stdout.write).
    """
    Staff = apps.get_model('hospital', 'Staff')

    result = SeedResult()
    departments = _ensure_departments(stdout_writer)

    with transaction.atomic():
        for staff_info in STAFF_DATA:
            first_name, last_name = parse_name(staff_info.get('name', ''))
            dob = parse_dob(staff_info.get('dob'))
            phone = format_phone(staff_info.get('phone'))
            dept = departments[staff_info['dept']]

            # First, try to find existing user by name (to avoid creating duplicates with numbered suffixes)
            user = None
            user_created = False
            
            # Try to find user by exact name match first
            existing_user = User.objects.filter(
                first_name__iexact=first_name,
                last_name__iexact=last_name
            ).first()
            
            if existing_user:
                # User exists with this name - use it
                user = existing_user
                user_created = False
                # Update user info if needed
                if user.first_name != first_name or user.last_name != last_name:
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save(update_fields=['first_name', 'last_name'])
            else:
                # No user with this name exists - create new one
                username = _build_username(first_name, last_name)
                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': f'{username}@hospital.local',
                        'is_staff': True,
                    },
                )
                if not user_created:
                    # Username exists but name doesn't match - update name
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save(update_fields=['first_name', 'last_name'])

            employee_id = f"EMP{user.id:06d}"
            
            # Check for existing staff by user (OneToOneField should prevent duplicates, but check anyway)
            existing_staff = Staff.objects.filter(user=user, is_deleted=False).first()
            
            if existing_staff:
                # Staff already exists for this user
                if update:
                    existing_staff.employee_id = employee_id
                    existing_staff.profession = staff_info['profession']
                    existing_staff.department = dept
                    existing_staff.phone_number = phone
                    if dob:
                        existing_staff.date_of_birth = dob
                    existing_staff.is_active = True
                    existing_staff.save()
                    result.updated += 1
                    _log(stdout_writer, f'[staff-seed] Updated: {staff_info["name"]}')
                else:
                    result.skipped += 1
                    _log(stdout_writer, f'[staff-seed] Skipped (exists): {staff_info["name"]}')
            else:
                # Check if employee_id already exists (prevent duplicates)
                if Staff.objects.filter(employee_id=employee_id, is_deleted=False).exists():
                    # Employee ID conflict - generate new one
                    counter = 1
                    while Staff.objects.filter(employee_id=employee_id, is_deleted=False).exists():
                        employee_id = f"EMP{user.id:06d}-{counter}"
                        counter += 1
                
                staff = Staff.objects.create(
                    user=user,
                    employee_id=employee_id,
                    profession=staff_info['profession'],
                    department=dept,
                    phone_number=phone,
                    date_of_birth=dob,
                    is_active=True,
                )
                result.created += 1
                _log(stdout_writer, f'[staff-seed] Created: {staff_info["name"]}')

    return result


def ensure_staff_seeded(stdout_writer: Optional[Callable[[str], None]] = None) -> Optional[SeedResult]:
    """
    Seed staff data if no staff exist yet.

    Returns SeedResult when seeding happens, or None if data already exists.
    """
    Staff = apps.get_model('hospital', 'Staff')
    if Staff.objects.exists():
        _log(stdout_writer, '[staff-seed] Staff records already present; skipping bootstrap.')
        return None
    _log(stdout_writer, '[staff-seed] No staff records detected. Seeding baseline staff data...')
    return seed_staff_dataset(update=False, stdout_writer=stdout_writer)



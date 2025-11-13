"""
Management command to import staff from spreadsheet data.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime
from hospital.models import Department, Staff


# Staff data from the spreadsheet
STAFF_DATA = [
    # Nurses - dates in DD/MM/YYYY format
    {'name': 'Matron Maegaret Ansong', 'phone': '0244489832', 'dob': None, 'dept': 'Nurses', 'profession': 'nurse'},  # 10/10/----
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
    {'name': 'Mavis Ananga', 'phone': '0543325547', 'dob': '5/10/1994', 'dept': 'Front Office', 'profession': 'receptionist'},
    
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


def parse_name(full_name):
    """Parse full name into first and last name"""
    parts = full_name.strip().split()
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


def parse_dob(dob_str):
    """Parse date of birth string in DD/MM/YYYY format"""
    if not dob_str or dob_str == '----':
        return None
    try:
        # Handle DD/MM/YYYY format
        if '/' in dob_str:
            parts = dob_str.split('/')
            if len(parts) == 3 and all(p.isdigit() for p in parts if p != '----'):
                day, month, year = parts
                if year == '----' or not year:
                    return None
                return datetime(int(year), int(month), int(day)).date()
        # Handle YYYY-MM-DD format
        return datetime.strptime(dob_str, '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None


def format_phone(phone):
    """Format phone number"""
    if not phone or not phone.strip():
        return ''
    phone = phone.strip()
    # Convert to international format if starts with 0
    if phone.startswith('0'):
        phone = '+233' + phone[1:]
    elif not phone.startswith('+'):
        phone = '+233' + phone
    return phone


class Command(BaseCommand):
    help = 'Import staff from spreadsheet data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing staff members',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting staff import...'))
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        # Create or get departments
        departments = {}
        for dept_name in ['Nurses', 'Cashier', 'Laboratory', 'Pharmacy', 'BD', 'Accounts', 
                          'Front Office', 'IT Support', 'Scan', 'Sanitation', 'X-ray']:
            dept_code = dept_name.upper().replace(' ', '_')[:10]
            dept, created = Department.objects.get_or_create(
                name=dept_name,
                defaults={
                    'code': dept_code,
                    'description': f'{dept_name} Department',
                    'is_active': True
                }
            )
            departments[dept_name] = dept
            if created:
                self.stdout.write(f'Created department: {dept_name}')
        
        # Import staff
        for staff_info in STAFF_DATA:
            first_name, last_name = parse_name(staff_info['name'])
            
            # Generate username
            username = f"{first_name.lower()}.{last_name.lower().replace(' ', '')}"[:30]
            username_base = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{counter}"[:30]
                counter += 1
            
            # Parse date of birth
            dob = parse_dob(staff_info.get('dob'))
            
            # Format phone
            phone = format_phone(staff_info.get('phone', ''))
            
            # Get department
            dept = departments[staff_info['dept']]
            
            # Get or create user
            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f'{username}@hospital.local',
                    'is_staff': True,
                }
            )
            
            if not user_created:
                # Update user info
                user.first_name = first_name
                user.last_name = last_name
                user.save()
            
            # Get or create staff
            employee_id = f"EMP{user.id:06d}"
            staff, staff_created = Staff.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': employee_id,
                    'profession': staff_info['profession'],
                    'department': dept,
                    'phone_number': phone,
                    'date_of_birth': dob,
                    'is_active': True,
                }
            )
            
            if not staff_created:
                if options['update']:
                    # Update existing staff
                    staff.employee_id = employee_id
                    staff.profession = staff_info['profession']
                    staff.department = dept
                    staff.phone_number = phone
                    if dob:
                        staff.date_of_birth = dob
                    staff.is_active = True
                    staff.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f'Updated: {staff_info["name"]}'))
                else:
                    skipped_count += 1
                    self.stdout.write(self.style.WARNING(f'Skipped (exists): {staff_info["name"]}'))
            else:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {staff_info["name"]}'))
        
        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS(f'Import Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Updated: {updated_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Skipped: {skipped_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Total: {len(STAFF_DATA)}'))
        self.stdout.write(self.style.SUCCESS('=' * 50))


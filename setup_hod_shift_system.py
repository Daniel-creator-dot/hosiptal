"""
Setup script for HOD Shift/Timetable System
Designates specific staff as Heads of Department:
- Gordon Boadu (Pharmacy)
- Dr. Nana Kofi Aboagye Yeboah (Medicine)
- Mary Ellis (Nurses)
- Evans Osei Asare (Laboratory)

Grants them access to:
- Create shifts and timetables
- Monitor shift attendance
- Approve procurement
- Approve leave requests
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from django.contrib.auth.models import User
from hospital.models import Staff, Department
from hospital.models_hod_simple import HeadOfDepartment
from hospital.models_hr import ShiftTemplate

def find_or_create_department(name):
    """Find or create a department - with flexible name matching"""
    # Try exact match first
    dept = Department.objects.filter(name__iexact=name, is_active=True).first()
    
    if not dept:
        # Try case-insensitive partial match
        dept = Department.objects.filter(name__icontains=name, is_active=True).first()
    
    if not dept:
        # Try common variations
        variations = {
            'Medicine': ['Medical', 'General Medicine', 'Doctors'],
            'Nurses': ['Nursing', 'Nurse'],
            'Laboratory': ['Lab', 'Laboratory Services'],
            'Pharmacy': ['Pharmaceutical', 'Drug Store'],
        }
        if name in variations:
            for variant in variations[name]:
                dept = Department.objects.filter(name__icontains=variant, is_active=True).first()
                if dept:
                    print(f"  ℹ️  Found department as: {dept.name} (searched for: {name})")
                    break
    
    if not dept:
        # Create if not found
        dept, created = Department.objects.get_or_create(
            name=name,
            defaults={'code': name.upper()[:10], 'is_active': True}
        )
        if created:
            print(f"  ✅ Created department: {name}")
    else:
        print(f"  ✅ Found department: {dept.name}")
    
    return dept

def find_staff_by_name(name_pattern):
    """Find staff by name pattern - improved search"""
    name_parts = name_pattern.split()
    
    # Try exact match on full name first
    if len(name_parts) >= 2:
        staff = Staff.objects.filter(
            user__first_name__icontains=name_parts[0],
            user__last_name__icontains=name_parts[-1],
            is_deleted=False
        ).first()
        if staff:
            return staff
        
        # Try reverse (last name first)
        staff = Staff.objects.filter(
            user__first_name__icontains=name_parts[-1],
            user__last_name__icontains=name_parts[0],
            is_deleted=False
        ).first()
        if staff:
            return staff
    
    # Try first name
    if name_parts:
        staff = Staff.objects.filter(
            user__first_name__icontains=name_parts[0],
            is_deleted=False
        ).first()
        if staff:
            return staff
    
    # Try last name
    if len(name_parts) > 1:
        staff = Staff.objects.filter(
            user__last_name__icontains=name_parts[-1],
            is_deleted=False
        ).first()
        if staff:
            return staff
    
    # Try searching in full name (combining first and last)
    if len(name_parts) >= 2:
        full_name = ' '.join(name_parts)
        # Try Q objects for better matching
        from django.db.models import Q
        staff = Staff.objects.filter(
            Q(user__first_name__icontains=name_parts[0]) | 
            Q(user__last_name__icontains=name_parts[-1]),
            is_deleted=False
        ).first()
    
    return staff

def setup_hod(staff_name, dept_name, username_hint=None):
    """Setup a Head of Department"""
    print(f"\n{'='*70}")
    print(f"Setting up HOD: {staff_name} → {dept_name}")
    print(f"{'='*70}")
    
    # Find department
    department = find_or_create_department(dept_name)
    
    # Find staff - try multiple methods
    staff = None
    
    # Method 1: Try username hint first
    if username_hint:
        try:
            user = User.objects.filter(username__icontains=username_hint, is_active=True).first()
            if user:
                staff = Staff.objects.filter(user=user, is_deleted=False).first()
                if staff:
                    print(f"  ✓ Found via username hint: {username_hint}")
        except Exception as e:
            pass
    
    # Method 2: Try name search
    if not staff:
        staff = find_staff_by_name(staff_name)
        if staff:
            print(f"  ✓ Found via name search")
    
    # Method 3: Try searching all staff with partial name match
    if not staff:
        from django.db.models import Q
        name_parts = staff_name.split()
        if name_parts:
            q = Q()
            for part in name_parts:
                q |= Q(user__first_name__icontains=part) | Q(user__last_name__icontains=part)
            staff = Staff.objects.filter(q, is_deleted=False).first()
            if staff:
                print(f"  ✓ Found via partial name match")
    
    if not staff:
        print(f"  ❌ Staff not found: {staff_name}")
        print(f"     Searched for username hint: {username_hint}")
        print(f"     Please verify the staff member exists in the system.")
        
        # Show similar names
        print(f"\n     Similar staff members found:")
        similar = Staff.objects.filter(is_deleted=False)[:10]
        for s in similar:
            print(f"       - {s.user.get_full_name()} ({s.user.username}) - {s.department.name if s.department else 'No dept'}")
        return False
    
    print(f"  ✅ Found staff: {staff.user.get_full_name()} ({staff.user.username})")
    
    # Delete any existing HOD designation for this staff (to avoid conflicts)
    HeadOfDepartment.objects.filter(staff=staff).delete()
    
    # Create new HOD designation
    hod, created = HeadOfDepartment.objects.get_or_create(
        staff=staff,
        department=department,
        defaults={
            'can_manage_schedules': True,
            'can_approve_procurement': True,
            'can_approve_leave': True,
            'is_active': True
        }
    )
    
    if not created:
        # Update existing
        hod.department = department
        hod.can_manage_schedules = True
        hod.can_approve_procurement = True
        hod.can_approve_leave = True
        hod.is_active = True
        hod.save()
        print(f"  ✅ Updated existing HOD designation")
    else:
        print(f"  ✅ Created new HOD designation")
    
    return True

def create_shift_templates(department):
    """Create default shift templates for a department"""
    templates = [
        {'name': 'Morning Shift', 'shift_type': 'day', 'start_time': '06:00', 'end_time': '14:00'},
        {'name': 'Afternoon Shift', 'shift_type': 'evening', 'start_time': '14:00', 'end_time': '22:00'},
        {'name': 'Night Shift', 'shift_type': 'night', 'start_time': '22:00', 'end_time': '06:00'},
        {'name': 'Day Shift', 'shift_type': 'day', 'start_time': '08:00', 'end_time': '17:00'},
    ]
    
    created = 0
    for template_data in templates:
        template, created_flag = ShiftTemplate.objects.get_or_create(
            name=template_data['name'],
            department=department,
            defaults={
                'shift_type': template_data['shift_type'],
                'start_time': template_data['start_time'],
                'end_time': template_data['end_time'],
                'is_active': True,
            }
        )
        if created_flag:
            created += 1
    
    if created > 0:
        print(f"  ✅ Created {created} shift templates")
    return created

def main():
    print("\n" + "="*70)
    print(" " * 20 + "HOD SHIFT SYSTEM SETUP")
    print("="*70)
    print()
    
    # Setup HODs - All 4 Heads of Department
    hods = [
        ('Gordon Boadu', 'Pharmacy', 'gordon.boadu'),
        ('Nana Kofi Aboagye Yeboah', 'Medicine', 'drnanakofi.yeboah'),  # Dr. Yeboah
        ('Mary Ellis', 'Nurses', 'mary.ellis'),
        ('Evans Osei Asare', 'Laboratory', 'evans.oseiasare'),
    ]
    
    success_count = 0
    for staff_name, dept_name, username_hint in hods:
        if setup_hod(staff_name, dept_name, username_hint):
            success_count += 1
            
            # Create shift templates for the department
            try:
                department = Department.objects.get(name=dept_name)
                create_shift_templates(department)
            except Department.DoesNotExist:
                pass
    
    print(f"\n{'='*70}")
    print(f"SETUP COMPLETE")
    print(f"{'='*70}")
    print(f"✅ Successfully set up {success_count}/{len(hods)} HODs")
    print()
    print("ACCESS URLS:")
    print("  - Shift Monitoring: /hms/hod/shift-monitoring/")
    print("  - Create Shifts: /hms/hod/shift/create-enhanced/")
    print("  - Attendance Report: /hms/hod/shift-attendance-report/")
    print()
    print("HODs can now:")
    print("  ✅ Create shifts for their department")
    print("  ✅ Monitor attendance vs scheduled shifts")
    print("  ✅ See shortages and absences in real-time")
    print("  ✅ Generate attendance compliance reports")
    print()

if __name__ == '__main__':
    main()






"""
Setup General Medicine Department and Maternity Department
- Creates General Medicine department for doctors
- Creates Maternity/Midwifery department for midwives
- Moves Dr. Ayisi from nurses to General Medicine department
- Adds all doctors to General Medicine department
- Ensures midwives are in Maternity department (separate from General Medicine)
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from django.contrib.auth import get_user_model
from hospital.models import Staff, Department

User = get_user_model()


def setup_general_medicine_and_dr_ayisi():
    """Setup General Medicine department (for doctors) and Maternity department (for midwives)"""
    
    print("=" * 60)
    print("SETTING UP DEPARTMENTS: GENERAL MEDICINE AND MATERNITY")
    print("=" * 60)
    print()
    
    # Step 1: Create or get General Medicine department (for doctors)
    print("Step 1: Creating/Verifying General Medicine Department (for doctors)...")
    general_medicine, created = Department.objects.get_or_create(
        name='General Medicine',
        defaults={
            'code': 'GEN-MED',
            'description': 'General Medicine Department - Primary care and general medical services for doctors',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if created:
        print(f"  ✅ Created General Medicine department: {general_medicine.name}")
    else:
        print(f"  ✅ General Medicine department already exists: {general_medicine.name}")
    
    # Ensure it's active
    general_medicine.is_active = True
    general_medicine.is_deleted = False
    general_medicine.save()
    print()
    
    # Step 1b: Create or get Maternity/Midwifery department (for midwives - SEPARATE from General Medicine)
    print("Step 1b: Creating/Verifying Maternity Department (for midwives - separate from General Medicine)...")
    maternity_dept, created_maternity = Department.objects.get_or_create(
        name='Maternity',
        defaults={
            'code': 'MATERNITY',
            'description': 'Maternity and Midwifery Department - Antenatal, delivery, and postnatal care services',
            'is_active': True,
            'is_deleted': False,
        }
    )
    
    if created_maternity:
        print(f"  ✅ Created Maternity department: {maternity_dept.name}")
    else:
        print(f"  ✅ Maternity department already exists: {maternity_dept.name}")
    
    # Ensure it's active
    maternity_dept.is_active = True
    maternity_dept.is_deleted = False
    maternity_dept.save()
    print()
    
    # Step 2: Find Dr. Ayisi
    print("Step 2: Finding Dr. Ayisi...")
    dr_ayisi_staff = None
    
    # Try multiple ways to find Dr. Ayisi
    search_terms = ['ayisi', 'kwadwo', 'drayisi']
    
    for term in search_terms:
        staff_list = Staff.objects.filter(
            user__username__icontains=term
        ).exclude(is_deleted=True)
        
        if staff_list.exists():
            dr_ayisi_staff = staff_list.first()
            print(f"  ✅ Found Dr. Ayisi: {dr_ayisi_staff.user.get_full_name()} (Username: {dr_ayisi_staff.user.username})")
            print(f"     Current Profession: {dr_ayisi_staff.profession}")
            print(f"     Current Department: {dr_ayisi_staff.department.name if dr_ayisi_staff.department else 'None'}")
            break
    
    if not dr_ayisi_staff:
        # Try by first/last name
        dr_ayisi_staff = Staff.objects.filter(
            user__first_name__icontains='kwadwo',
            user__last_name__icontains='ayisi'
        ).exclude(is_deleted=True).first()
        
        if dr_ayisi_staff:
            print(f"  ✅ Found Dr. Ayisi by name: {dr_ayisi_staff.user.get_full_name()}")
            print(f"     Current Profession: {dr_ayisi_staff.profession}")
            print(f"     Current Department: {dr_ayisi_staff.department.name if dr_ayisi_staff.department else 'None'}")
    
    if not dr_ayisi_staff:
        print("  ❌ ERROR: Dr. Ayisi not found!")
        print("     Please ensure Dr. Ayisi exists in the system.")
        return False
    
    print()
    
    # Step 3: Move Dr. Ayisi to General Medicine and ensure he's a doctor
    print("Step 3: Moving Dr. Ayisi to General Medicine Department...")
    old_dept = dr_ayisi_staff.department.name if dr_ayisi_staff.department else 'None'
    old_profession = dr_ayisi_staff.profession
    
    dr_ayisi_staff.department = general_medicine
    dr_ayisi_staff.profession = 'doctor'  # Ensure he's a doctor, not a nurse
    dr_ayisi_staff.save()
    
    print(f"  ✅ Updated Dr. Ayisi:")
    print(f"     Department: {old_dept} → {general_medicine.name}")
    print(f"     Profession: {old_profession} → doctor")
    print()
    
    # Step 4: Add all doctors to General Medicine department
    print("Step 4: Adding all doctors to General Medicine Department...")
    all_doctors = Staff.objects.filter(
        profession='doctor',
        is_deleted=False,
        is_active=True
    ).exclude(department=general_medicine)
    
    doctor_count = all_doctors.count()
    
    if doctor_count > 0:
        updated_count = all_doctors.update(department=general_medicine)
        print(f"  ✅ Added {updated_count} doctor(s) to General Medicine:")
        for doctor in all_doctors:
            print(f"     - {doctor.user.get_full_name()} ({doctor.user.username})")
    else:
        print(f"  ✅ All doctors are already in General Medicine department")
    
    # Also update Dr. Ayisi if he wasn't in the queryset
    if dr_ayisi_staff not in all_doctors:
        print(f"     - {dr_ayisi_staff.user.get_full_name()} (already in General Medicine)")
    
    print()
    
    # Step 5: Ensure midwives are in Maternity department (NOT General Medicine)
    print("Step 5: Ensuring midwives are in Maternity Department (separate from General Medicine)...")
    midwives_not_in_maternity = Staff.objects.filter(
        profession='midwife',
        is_deleted=False,
        is_active=True
    ).exclude(department=maternity_dept)
    
    midwife_count = midwives_not_in_maternity.count()
    
    if midwife_count > 0:
        updated_midwives = midwives_not_in_maternity.update(department=maternity_dept)
        print(f"  ✅ Moved {updated_midwives} midwife/midwives to Maternity department:")
        for midwife in midwives_not_in_maternity:
            print(f"     - {midwife.user.get_full_name()} ({midwife.user.username})")
    else:
        print(f"  ✅ All midwives are already in Maternity department")
    
    total_midwives_in_maternity = Staff.objects.filter(
        profession='midwife',
        department=maternity_dept,
        is_deleted=False,
        is_active=True
    ).count()
    
    print(f"  ✅ Total midwives in Maternity department: {total_midwives_in_maternity}")
    print()
    
    # Step 6: Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ General Medicine Department: {general_medicine.name} (for doctors)")
    print(f"✅ Maternity Department: {maternity_dept.name} (for midwives - SEPARATE)")
    print(f"✅ Dr. Ayisi moved to: {general_medicine.name}")
    print(f"✅ Dr. Ayisi profession: doctor")
    
    total_doctors_in_general_medicine = Staff.objects.filter(
        profession='doctor',
        department=general_medicine,
        is_deleted=False,
        is_active=True
    ).count()
    
    print(f"✅ Total doctors in General Medicine: {total_doctors_in_general_medicine}")
    print(f"✅ Total midwives in Maternity: {total_midwives_in_maternity}")
    print()
    print("⚠️  IMPORTANT: General Medicine and Maternity are TWO SEPARATE departments:")
    print(f"   - General Medicine ({general_medicine.name}) = for doctors")
    print(f"   - Maternity ({maternity_dept.name}) = for midwives")
    print()
    
    print("=" * 60)
    print("✅ SETUP COMPLETE!")
    print("=" * 60)
    
    return True


if __name__ == '__main__':
    try:
        setup_general_medicine_and_dr_ayisi()
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)















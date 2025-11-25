"""
Setup Script for Comprehensive Laboratory Management System
Run this after migrations to populate initial data
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hms.settings')
django.setup()

from hospital.models_laboratory import (
    LabTestCategory, SpecimenType, LabTestPanel
)
from hospital.models import LabTest
from datetime import date, timedelta

def setup_lab_categories():
    """Create lab test categories"""
    categories = [
        {
            'name': 'Chemistry',
            'code': 'CHEM',
            'description': 'Clinical Chemistry Tests',
            'icon': 'bi-flask',
            'color': '#007bff',
            'display_order': 1
        },
        {
            'name': 'Hematology',
            'code': 'HEMA',
            'description': 'Blood Cell Counts and Coagulation',
            'icon': 'bi-droplet',
            'color': '#dc3545',
            'display_order': 2
        },
        {
            'name': 'Microbiology',
            'code': 'MICRO',
            'description': 'Cultures and Sensitivity Testing',
            'icon': 'bi-virus',
            'color': '#28a745',
            'display_order': 3
        },
        {
            'name': 'Immunology',
            'code': 'IMMUNO',
            'description': 'Serology and Immunology',
            'icon': 'bi-shield-check',
            'color': '#ffc107',
            'display_order': 4
        },
        {
            'name': 'Urinalysis',
            'code': 'URINE',
            'description': 'Urine Analysis',
            'icon': 'bi-eyedropper',
            'color': '#17a2b8',
            'display_order': 5
        },
    ]
    
    created = 0
    for cat_data in categories:
        cat, created_flag = LabTestCategory.objects.get_or_create(
            code=cat_data['code'],
            defaults=cat_data
        )
        if created_flag:
            created += 1
            print(f"✅ Created category: {cat.name}")
        else:
            print(f"ℹ️  Category exists: {cat.name}")
    
    return created


def setup_specimen_types():
    """Create specimen types"""
    specimens = [
        {
            'name': 'Whole Blood (EDTA)',
            'code': 'EDTA',
            'description': 'For CBC, blood film, HbA1c',
            'container_type': 'EDTA Tube',
            'color_code': 'Purple/Lavender',
            'volume_required_ml': 3.0,
            'storage_temp': '2-8°C',
            'shelf_life_hours': 24,
            'special_handling': 'Mix gently after collection. Do not refrigerate.'
        },
        {
            'name': 'Serum',
            'code': 'SERUM',
            'description': 'For chemistry tests, hormones, serology',
            'container_type': 'Plain Tube (Red top)',
            'color_code': 'Red',
            'volume_required_ml': 5.0,
            'storage_temp': '2-8°C',
            'shelf_life_hours': 48,
            'special_handling': 'Allow to clot for 30min before centrifuging.'
        },
        {
            'name': 'Plasma (Sodium Fluoride)',
            'code': 'FLUORIDE',
            'description': 'For glucose testing',
            'container_type': 'Fluoride Tube',
            'color_code': 'Gray',
            'volume_required_ml': 3.0,
            'storage_temp': '2-8°C',
            'shelf_life_hours': 72,
            'special_handling': 'Mix immediately after collection.'
        },
        {
            'name': 'Urine (Random)',
            'code': 'URINE',
            'description': 'For urinalysis',
            'container_type': 'Sterile Container',
            'color_code': 'Clear',
            'volume_required_ml': 50.0,
            'storage_temp': '2-8°C',
            'shelf_life_hours': 2,
            'special_handling': 'Process within 2 hours. Clean catch technique.'
        },
        {
            'name': 'Stool',
            'code': 'STOOL',
            'description': 'For parasitology, culture',
            'container_type': 'Stool Container',
            'color_code': 'Clear',
            'volume_required_ml': 10.0,
            'storage_temp': 'Room Temperature',
            'shelf_life_hours': 24,
            'special_handling': 'Fresh specimen preferred. No preservatives unless specified.'
        },
        {
            'name': 'Sputum',
            'code': 'SPUTUM',
            'description': 'For TB, culture',
            'container_type': 'Sputum Container',
            'color_code': 'Clear',
            'volume_required_ml': 5.0,
            'storage_temp': 'Room Temperature',
            'shelf_life_hours': 24,
            'special_handling': 'Early morning specimen preferred.'
        },
    ]
    
    created = 0
    for spec_data in specimens:
        spec, created_flag = SpecimenType.objects.get_or_create(
            code=spec_data['code'],
            defaults=spec_data
        )
        if created_flag:
            created += 1
            print(f"✅ Created specimen type: {spec.name}")
        else:
            print(f"ℹ️  Specimen type exists: {spec.name}")
    
    return created


def setup_common_tests():
    """Create common lab tests"""
    tests = [
        # Chemistry
        {'code': 'GLU', 'name': 'Glucose (Fasting)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 15.00},
        {'code': 'CREAT', 'name': 'Creatinine', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 15.00},
        {'code': 'UREA', 'name': 'Urea', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 15.00},
        {'code': 'NA', 'name': 'Sodium', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 15.00},
        {'code': 'K', 'name': 'Potassium', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 15.00},
        {'code': 'CL', 'name': 'Chloride', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 15.00},
        {'code': 'ALT', 'name': 'ALT (SGPT)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 20.00},
        {'code': 'AST', 'name': 'AST (SGOT)', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 20.00},
        {'code': 'ALP', 'name': 'Alkaline Phosphatase', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 20.00},
        {'code': 'TBIL', 'name': 'Total Bilirubin', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 20.00},
        {'code': 'ALB', 'name': 'Albumin', 'specimen_type': 'Serum', 'tat_minutes': 60, 'price': 20.00},
        {'code': 'CHOL', 'name': 'Total Cholesterol', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': 25.00},
        {'code': 'HDL', 'name': 'HDL Cholesterol', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': 25.00},
        {'code': 'LDL', 'name': 'LDL Cholesterol', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': 25.00},
        {'code': 'TRIG', 'name': 'Triglycerides', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': 25.00},
        
        # Hematology
        {'code': 'CBC', 'name': 'Complete Blood Count', 'specimen_type': 'Whole Blood (EDTA)', 'tat_minutes': 30, 'price': 30.00},
        {'code': 'HB', 'name': 'Hemoglobin', 'specimen_type': 'Whole Blood (EDTA)', 'tat_minutes': 30, 'price': 10.00},
        {'code': 'WBC', 'name': 'White Blood Cell Count', 'specimen_type': 'Whole Blood (EDTA)', 'tat_minutes': 30, 'price': 10.00},
        {'code': 'PLT', 'name': 'Platelet Count', 'specimen_type': 'Whole Blood (EDTA)', 'tat_minutes': 30, 'price': 10.00},
        {'code': 'ESR', 'name': 'ESR (Westergren)', 'specimen_type': 'Whole Blood (EDTA)', 'tat_minutes': 60, 'price': 15.00},
        
        # Microbiology
        {'code': 'URINE-CS', 'name': 'Urine Culture & Sensitivity', 'specimen_type': 'Urine (Random)', 'tat_minutes': 2880, 'price': 50.00},
        {'code': 'STOOL-CS', 'name': 'Stool Culture', 'specimen_type': 'Stool', 'tat_minutes': 2880, 'price': 50.00},
        
        # Serology
        {'code': 'HIV', 'name': 'HIV Screening', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': 30.00},
        {'code': 'HBSAG', 'name': 'Hepatitis B Surface Antigen', 'specimen_type': 'Serum', 'tat_minutes': 120, 'price': 35.00},
    ]
    
    created = 0
    for test_data in tests:
        test, created_flag = LabTest.objects.get_or_create(
            code=test_data['code'],
            defaults=test_data
        )
        if created_flag:
            created += 1
            print(f"✅ Created test: {test.name}")
        else:
            print(f"ℹ️  Test exists: {test.name}")
    
    return created


def setup_test_panels():
    """Create common test panels"""
    # Get category
    chemistry = LabTestCategory.objects.filter(code='CHEM').first()
    
    if not chemistry:
        print("❌ Chemistry category not found. Run setup_lab_categories() first.")
        return 0
    
    # Lipid Profile
    lipid_tests = LabTest.objects.filter(code__in=['CHOL', 'HDL', 'LDL', 'TRIG'])
    if lipid_tests.count() == 4:
        panel, created = LabTestPanel.objects.get_or_create(
            code='LIPID',
            defaults={
                'name': 'Lipid Profile',
                'category': chemistry,
                'description': 'Complete lipid panel - fasting required',
                'price': 80.00,  # Individual total would be 100
                'discount_percent': 20.00,
                'tat_minutes': 120,
                'requires_fasting': True,
                'is_active': True,
                'special_instructions': '12-hour fasting required'
            }
        )
        if created:
            panel.tests.set(lipid_tests)
            print(f"✅ Created panel: {panel.name}")
            return 1
        else:
            print(f"ℹ️  Panel exists: {panel.name}")
    
    return 0


def main():
    """Run all setup functions"""
    print("\n🧪 Setting up Comprehensive Laboratory Management System...\n")
    
    print("📁 Creating Lab Categories...")
    cat_count = setup_lab_categories()
    
    print("\n🧫 Creating Specimen Types...")
    spec_count = setup_specimen_types()
    
    print("\n🔬 Creating Common Lab Tests...")
    test_count = setup_common_tests()
    
    print("\n📋 Creating Test Panels...")
    panel_count = setup_test_panels()
    
    print("\n" + "="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print(f"Created:")
    print(f"  - {cat_count} Lab Categories")
    print(f"  - {spec_count} Specimen Types")
    print(f"  - {test_count} Lab Tests")
    print(f"  - {panel_count} Test Panels")
    print("\nNext Steps:")
    print("1. Run: python manage.py migrate")
    print("2. Access lab system at: http://127.0.0.1:8000/hms/lab/")
    print("3. Configure equipment in Django admin")
    print("4. Setup reference ranges in admin")
    print("5. Train staff on new system")
    print("\n📚 Read COMPREHENSIVE_LAB_SYSTEM_GUIDE.md for full documentation")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
































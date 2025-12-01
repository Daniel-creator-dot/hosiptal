"""
Test script to verify duplicate prevention is working
Run this while the server is running
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_duplicate_prevention():
    """Test that duplicate patients cannot be created"""
    print("=" * 70)
    print("TESTING DUPLICATE PREVENTION")
    print("=" * 70)
    print()
    
    # Test data
    test_patient = {
        'first_name': 'Test',
        'last_name': 'Duplicate',
        'date_of_birth': '1990-01-01',
        'phone_number': '0241234567',
        'email': 'test.duplicate@example.com',
        'gender': 'M',
    }
    
    print(f"Test Patient Data:")
    print(f"  Name: {test_patient['first_name']} {test_patient['last_name']}")
    print(f"  Phone: {test_patient['phone_number']}")
    print(f"  Email: {test_patient['email']}")
    print()
    
    # Get CSRF token first (need to login or get from form)
    print("⚠️  Note: This test requires manual testing through the web interface")
    print("   because CSRF protection requires a logged-in session.")
    print()
    print("=" * 70)
    print("MANUAL TEST INSTRUCTIONS")
    print("=" * 70)
    print()
    print("1. Open your browser and go to:")
    print(f"   {BASE_URL}/hms/patients/new/")
    print()
    print("2. Fill in the form with:")
    print(f"   First Name: {test_patient['first_name']}")
    print(f"   Last Name: {test_patient['last_name']}")
    print(f"   Date of Birth: {test_patient['date_of_birth']}")
    print(f"   Phone: {test_patient['phone_number']}")
    print(f"   Email: {test_patient['email']}")
    print()
    print("3. Click 'Register Patient'")
    print("   ✅ Should create patient successfully")
    print()
    print("4. Go back to registration form:")
    print(f"   {BASE_URL}/hms/patients/new/")
    print()
    print("5. Fill in the EXACT SAME information again")
    print()
    print("6. Click 'Register Patient' again")
    print("   ❌ Should show duplicate error message")
    print("   ❌ Should NOT create a second patient")
    print()
    print("=" * 70)
    print("WHAT TO LOOK FOR")
    print("=" * 70)
    print()
    print("✅ SUCCESS INDICATORS:")
    print("   - First registration: Success message, patient created")
    print("   - Second registration: Error message about duplicate")
    print("   - Only ONE patient in patient list")
    print()
    print("❌ FAILURE INDICATORS:")
    print("   - Second registration creates another patient")
    print("   - No error message shown")
    print("   - Two patients with same name/phone in list")
    print()
    print("=" * 70)
    print("CHECK PATIENT LIST")
    print("=" * 70)
    print()
    print(f"After testing, check the patient list:")
    print(f"   {BASE_URL}/hms/patients/")
    print()
    print("Search for 'Test Duplicate' - should only find ONE patient")
    print()
    print("=" * 70)

if __name__ == '__main__':
    try:
        # Check if server is running
        response = requests.get(BASE_URL, timeout=3)
        if response.status_code == 200:
            print("✅ Server is running!")
            print()
        else:
            print(f"⚠️  Server responded with status {response.status_code}")
            print()
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to server!")
        print(f"   Make sure the server is running at {BASE_URL}")
        print()
        exit(1)
    except Exception as e:
        print(f"⚠️  Warning: {e}")
        print()
    
    test_duplicate_prevention()


# 🔧 Patient Card Troubleshooting Guide

## Issue: "Nothing Shows" - Blank Page or Missing Content

### Quick Fixes

#### 1. **Check if QR Profile Exists**

The patient card requires a QR profile to be generated. Check:

```python
# In Django shell or Python
from hospital.models import Patient, PatientQRCode

# Get a patient
patient = Patient.objects.filter(is_deleted=False).first()
print(f"Patient: {patient.full_name}")
print(f"MRN: {patient.mrn}")

# Check QR profile
qr_profile = getattr(patient, 'qr_profile', None)
if qr_profile:
    print(f"QR Profile exists: {qr_profile}")
    print(f"Has QR image: {bool(qr_profile.qr_code_image)}")
    print(f"Has token: {bool(qr_profile.qr_token)}")
else:
    print("No QR profile - generating one...")
    qr_profile = patient.ensure_qr_profile()
    print(f"QR Profile created: {qr_profile}")
```

#### 2. **Force QR Generation for All Patients**

If QR codes are missing, regenerate them:

```python
from hospital.models import Patient, PatientQRCode

# Generate QR for all patients without one
patients_without_qr = Patient.objects.filter(
    is_deleted=False
).exclude(
    id__in=PatientQRCode.objects.values_list('patient_id', flat=True)
)

for patient in patients_without_qr:
    print(f"Generating QR for {patient.full_name} ({patient.mrn})")
    qr_profile = patient.ensure_qr_profile()
    qr_profile.refresh_qr(force_token=True)
    print(f"✓ Generated QR for {patient.mrn}")

print(f"\nGenerated QR codes for {patients_without_qr.count()} patients")
```

#### 3. **Check Browser Console**

Open browser developer tools (F12) and check:
- **Console tab**: Look for JavaScript errors
- **Network tab**: Check if images/CSS are loading
- **Elements tab**: See if HTML is rendering

#### 4. **Verify URL Access**

The patient card URL format is:
```
/hms/patients/<patient_uuid>/qr-card/
```

Example:
```
/hms/patients/123e4567-e89b-12d3-a456-426614174000/qr-card/
```

#### 5. **Check Permissions**

Ensure you're logged in as a user with patient access. The view requires:
- `@login_required` decorator
- User must be authenticated

#### 6. **Verify Template Loading**

Check if the template exists:
```
hospital/templates/hospital/patient_qr_card.html
```

#### 7. **Check Static Files**

The template uses:
- Bootstrap Icons CDN (should load automatically)
- Google Fonts CDN (should load automatically)

If these don't load, the page may look broken.

#### 8. **Common Issues**

**Issue: QR Code Image Not Generating**
```python
# Check if PIL/Pillow is installed
python -c "from PIL import Image; print('PIL OK')"

# Check if qrcode library is installed
python -c "import qrcode; print('qrcode OK')"
```

**Issue: Media Files Not Serving**
Check Django settings:
```python
# settings.py
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# urls.py (project level)
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Issue: Template Variables Not Available**
Check the view is passing all required context:
- `patient`
- `qr_profile`
- `hospital_settings`
- `generated_at`

### Step-by-Step Debugging

1. **Open Patient Detail Page**
   - Go to: `/hms/patients/`
   - Click on any patient
   - Look for "Print QR Card" button

2. **Check QR Card Link**
   - The button should link to: `/hms/patients/<uuid>/qr-card/`
   - Click it and see what happens

3. **Check Server Logs**
   ```bash
   # Look for errors in Django logs
   # Check terminal where server is running
   ```

4. **Test Direct Access**
   - Try accessing the QR card URL directly
   - Replace `<uuid>` with actual patient UUID

5. **Generate QR Manually**
   ```python
   from hospital.models import Patient
   
   patient = Patient.objects.filter(is_deleted=False).first()
   qr_profile = patient.ensure_qr_profile()
   qr_profile.refresh_qr(force_token=True)
   print(f"QR generated: {qr_profile.qr_code_image}")
   ```

### Expected Behavior

**Working Card Shows:**
- ✅ Patient photo or initials placeholder
- ✅ Patient name and MRN
- ✅ Patient information (DOB, age, gender)
- ✅ QR code image (320x320px)
- ✅ Security features list
- ✅ Hospital branding
- ✅ Print button

**If Nothing Shows:**
- ❌ Blank white page = Template error
- ❌ Error message = Check server logs
- ❌ Missing QR = Generate QR profile
- ❌ Missing images = Check media file serving

### Quick Test Script

Run this to test everything:

```python
# test_patient_card.py
from hospital.models import Patient, PatientQRCode
from django.utils import timezone

# Get first patient
patient = Patient.objects.filter(is_deleted=False).first()

if not patient:
    print("❌ No patients found!")
    exit(1)

print(f"✓ Found patient: {patient.full_name} ({patient.mrn})")

# Ensure QR profile
qr_profile = patient.ensure_qr_profile()
print(f"✓ QR profile: {qr_profile}")

# Check QR image
if qr_profile.qr_code_image:
    print(f"✓ QR image exists: {qr_profile.qr_code_image.url}")
else:
    print("⚠️ No QR image - generating...")
    qr_profile.refresh_qr(force_token=True)
    print(f"✓ QR image generated: {qr_profile.qr_code_image.url}")

# Check token
if qr_profile.qr_token:
    print(f"✓ Token exists: {qr_profile.qr_token[:8]}...")
else:
    print("⚠️ No token - generating...")
    qr_profile.refresh_qr(force_token=True)

# Test URL
from django.urls import reverse
qr_card_url = reverse('hospital:patient_qr_card', args=[patient.pk])
print(f"✓ QR Card URL: {qr_card_url}")

print("\n✅ All checks passed! Patient card should work.")
```

### Still Not Working?

1. **Check Django Server**
   - Is server running?
   - Any errors in console?

2. **Check Database**
   - Can you query patients?
   - Are QR profiles being created?

3. **Check Permissions**
   - Are you logged in?
   - Do you have patient access?

4. **Clear Browser Cache**
   - Hard refresh: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)

5. **Try Different Browser**
   - Test in Chrome, Firefox, Edge

6. **Check File Permissions**
   - Can Django write to media folder?
   - Are image files being saved?

---

**Need More Help?**
- Check Django error logs
- Enable DEBUG mode temporarily
- Check browser console for JavaScript errors
- Verify all dependencies are installed





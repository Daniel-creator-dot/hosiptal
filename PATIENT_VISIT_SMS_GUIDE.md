# 📱 Patient Visit & SMS Notification System Guide

## ✅ **What's Been Implemented**

### 1. 🎉 **Automatic SMS for New Patient Registration**
When you register a new patient, they will automatically receive a welcome SMS with:
- Welcome message
- Their Medical Record Number (MRN)
- Instructions to keep the MRN for future visits
- Hospital contact information

### 2. 🏥 **Quick Visit Creation for Returning Patients**
A new "Create New Visit" button on the patient detail page allows you to:
- Quickly create a visit/encounter when a patient comes in
- Select visit type (Outpatient, Emergency, Inpatient, Surgery)
- Enter the chief complaint/reason for visit
- Automatically proceed to vital signs recording

---

## 📋 **How to Use the Features**

### **New Patient Registration with SMS**

1. **Navigate to Patients**
   - Go to `Patients` → `New Patient`
   - Or visit: http://127.0.0.1:8000/hms/patients/new/

2. **Fill in Patient Details**
   - Enter all required information
   - **IMPORTANT**: Make sure to enter the patient's phone number in format: `+233XXXXXXXXX` or `0XXXXXXXXX`

3. **Submit Form**
   - Click "Save" or "Submit"
   - The system will:
     - ✅ Create the patient record
     - ✅ Generate a unique MRN
     - ✅ Send welcome SMS automatically
     - ✅ Create an initial encounter/visit
     - ✅ Redirect to vital signs recording

4. **SMS Confirmation**
   - You'll see a success message: *"Patient registered successfully! Welcome SMS sent to [phone number]."*
   - If phone number is missing: *"Patient registered successfully! No phone number provided for SMS."*
   - If SMS fails: *"Patient registered successfully, but SMS could not be sent: [error]"*

**Sample Welcome SMS:**
```
Welcome to PrimeCare Hospital, John!

Your Medical Record Number (MRN): PMC-20251104-0001
Please keep this number for future visits.

Thank you for choosing us for your healthcare needs.

PrimeCare Hospital
Call us: [Hospital Contact]
```

---

### **Creating a Visit for Returning Patients**

#### **Method 1: From Patient Detail Page (Quick & Easy!)**

1. **Find the Patient**
   - Go to `Patients` → Search for patient by name or MRN
   - Click on patient to view details

2. **Click "Create New Visit"**
   - On the patient detail page, you'll see a green **"Create New Visit"** button
   - Click it

3. **Fill Visit Details**
   - **Visit Type**: Select from dropdown
     - Outpatient Visit (default)
     - Emergency
     - Inpatient
     - Surgery
   - **Chief Complaint**: Enter reason for visit
     - e.g., "Fever and cough for 3 days"
     - e.g., "Follow-up for hypertension"
     - e.g., "Regular checkup"

4. **Submit**
   - Click **"Create Visit & Record Vitals"**
   - System will:
     - ✅ Create the encounter/visit
     - ✅ Record who created it
     - ✅ Redirect to vital signs recording

#### **Method 2: From Encounters Menu (Full Form)**

1. **Navigate to Encounters**
   - Go to `Encounters` → `New Encounter`

2. **Fill Detailed Form**
   - Select patient
   - Enter all encounter details
   - Submit

---

## 🔧 **System Configuration**

### **SMS Service Settings**

The SMS service is already configured with:
- **Provider**: SMS Notify GH
- **API Key**: `3316dce1-fd2a-4b4e-b6b2-60b30be375bb`
- **Sender ID**: `PrimeCare`
- **API URL**: `https://sms.smsnotifygh.com/smsapi`

**To Update Settings** (if needed):
Add to your `.env` file or `settings.py`:
```python
SMS_API_KEY = 'your-api-key'
SMS_SENDER_ID = 'YourName'
SMS_API_URL = 'https://sms.smsnotifygh.com/smsapi'
```

### **Phone Number Format**

The system accepts multiple formats and auto-converts:
- `+233XXXXXXXXX` ✅ (Recommended)
- `0XXXXXXXXX` ✅ (Converts to +233)
- `233XXXXXXXXX` ✅

**Examples:**
- `+233244123456`
- `0244123456` → Converts to `233244123456`

---

## 📊 **SMS Log Tracking**

All SMS messages are logged in the database:
- **Recipient Phone**
- **Message Content**
- **Status** (pending, sent, failed)
- **Timestamp**
- **Error Messages** (if any)
- **Provider Response**

**To View SMS Logs:**
1. Go to Django Admin: http://127.0.0.1:8000/admin
2. Navigate to `Hospital` → `SMS Logs`
3. View all sent/failed messages

---

## 🎯 **SMS Message Types**

The system supports various SMS types:
- `patient_registration` - Welcome SMS for new patients (NEW!)
- `appointment_reminder` - Appointment reminders
- `lab_result_ready` - Lab results ready notification
- `payment_reminder` - Outstanding balance reminders
- `leave_approved` - Staff leave approval
- `leave_rejected` - Staff leave rejection
- `birthday_wish` - Staff birthday wishes
- `general` - General messages

---

## 🚀 **Workflow Examples**

### **Scenario 1: New Patient Walk-in**

1. **Patient arrives at reception**
2. Receptionist: Click `Patients` → `New Patient`
3. Fill form with patient details including phone number
4. Submit form
5. ✅ System sends welcome SMS
6. ✅ Auto-creates initial visit
7. Receptionist: Record patient's vital signs
8. Patient proceeds to consultation

### **Scenario 2: Returning Patient Visit**

1. **Patient arrives at reception**
2. Receptionist: Search for patient by name/MRN
3. Click on patient to view details
4. Click **"Create New Visit"** button (green button)
5. Select visit type and enter chief complaint
6. Submit
7. ✅ Visit created
8. Record vital signs
9. Patient proceeds to consultation

### **Scenario 3: Emergency Patient**

1. **Patient arrives at Emergency**
2. Staff: Quick search for patient OR register new patient
3. If existing: Click **"Create New Visit"**
4. Select **"Emergency"** as visit type
5. Enter chief complaint
6. Submit
7. ✅ Emergency visit created
8. Proceed with emergency protocol

---

## 🛠️ **Troubleshooting**

### **SMS Not Sending**

**Problem**: Patient registered but SMS didn't send

**Solutions:**
1. **Check Phone Number**
   - Must be valid Ghana number
   - Should start with +233 or 0
   - Should be 10 digits (local) or 12 digits (with country code)

2. **Check SMS Balance**
   - Log into SMS Notify GH account
   - Verify you have sufficient balance

3. **Check SMS Logs**
   - Go to Admin → SMS Logs
   - Find the entry and check error message

4. **Test SMS Service**
   - Go to `SMS` → `Send SMS`
   - Send a test message

### **"Create New Visit" Button Not Showing**

**Solutions:**
1. **Refresh the page** (Ctrl + Shift + R)
2. **Clear browser cache**
3. **Check if servers are running**
4. **Verify URL routing** is correct

### **Visit Creation Fails**

**Solutions:**
1. **Check user permissions** - User must be logged in
2. **Verify patient exists** - Patient must not be deleted
3. **Check for error messages** in the browser
4. **Check Django logs** in terminal

---

## 📱 **Testing the SMS Feature**

### **Test 1: New Patient Registration**

```bash
# From your browser:
1. Go to: http://127.0.0.1:8000/hms/patients/new/
2. Fill in patient details
3. Phone: +233244123456 (use your real number for testing)
4. Submit
5. Check your phone for SMS
```

### **Test 2: Check SMS Logs**

```bash
# From Django shell:
python manage.py shell

from hospital.models_advanced import SMSLog
logs = SMSLog.objects.filter(message_type='patient_registration').order_by('-created')[:5]
for log in logs:
    print(f"{log.recipient_name}: {log.status} - {log.message[:50]}...")
```

### **Test 3: Manual SMS Send**

```python
# From Django shell:
from hospital.services.sms_service import sms_service

sms_service.send_sms(
    phone_number='+233244123456',
    message='Test message from PrimeCare Hospital',
    message_type='general'
)
```

---

## 📞 **Quick Access URLs**

| Feature | URL |
|---------|-----|
| Dashboard | http://127.0.0.1:8000/hms/ |
| New Patient | http://127.0.0.1:8000/hms/patients/new/ |
| Patient List | http://127.0.0.1:8000/hms/patients/ |
| Encounters | http://127.0.0.1:8000/hms/encounters/ |
| SMS Dashboard | http://127.0.0.1:8000/hms/sms/ |
| Admin Panel | http://127.0.0.1:8000/admin/ |

---

## ✅ **Benefits of This System**

### **For Patients:**
- ✅ Instant confirmation of registration
- ✅ Receive their MRN immediately
- ✅ Professional welcome experience
- ✅ Easy reference for future visits

### **For Staff:**
- ✅ Quick visit creation (2 clicks!)
- ✅ No need to remember to send welcome messages
- ✅ Automated workflow
- ✅ Better patient tracking
- ✅ Improved patient engagement

### **For Hospital:**
- ✅ Professional image
- ✅ Better patient experience
- ✅ Reduced registration errors
- ✅ Improved patient retention
- ✅ Complete audit trail (SMS logs)

---

## 🎊 **Summary**

**What happens when you register a new patient:**
1. ✅ Patient record created
2. ✅ MRN auto-generated
3. ✅ Welcome SMS sent automatically
4. ✅ Initial visit/encounter created
5. ✅ Redirected to vital signs recording

**What happens when you create a visit for returning patient:**
1. ✅ Visit/encounter created
2. ✅ Patient flow initiated
3. ✅ Redirected to vital signs recording
4. ✅ Ready for consultation

**Everything is automated and logged!** 🎉

---

## 💡 **Pro Tips**

1. **Always get patient phone numbers** - Enable SMS benefits
2. **Use the Quick Visit button** - Faster than full encounter form
3. **Check SMS logs regularly** - Monitor delivery
4. **Keep SMS balance topped up** - Avoid service interruption
5. **Train all reception staff** - Ensure consistent usage

---

## 📝 **Next Steps / Future Enhancements**

Possible future additions:
- ✨ Send appointment reminder SMS 24h before
- ✨ Send lab results ready notifications
- ✨ Send payment/invoice reminders
- ✨ Send medication pickup reminders
- ✨ Bulk SMS for announcements
- ✨ SMS templates management UI

---

## 🆘 **Need Help?**

**Check SMS Logs:**
```bash
python manage.py shell
from hospital.models_advanced import SMSLog
SMSLog.objects.filter(status='failed').order_by('-created')[:10]
```

**Verify Database:**
```bash
python manage.py verify_database
```

**Check Celery Status:**
- Celery worker should be running for background tasks
- Celery beat should be running for scheduled tasks

---

## ✨ **YOU'RE ALL SET!**

The system is ready to:
1. ✅ Send SMS to new patients automatically
2. ✅ Create visits quickly for returning patients
3. ✅ Track all SMS communications
4. ✅ Provide better patient experience

**Start registering patients and creating visits!** 🎉

---

*Last Updated: November 4, 2025*
*HMS Version: 1.0*
































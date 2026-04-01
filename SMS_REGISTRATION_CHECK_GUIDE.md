# 📱 SMS Registration Check Guide

## ✅ **SMS Registration System Status**

The SMS registration system is **properly configured** and ready to use. When a patient is registered with a phone number, an automatic welcome SMS will be sent.

---

## 🔍 **How to Check SMS After Registration**

### **Method 1: Check Registration Message**
After registering a patient, you'll see one of these messages:

- ✅ **Success**: `Patient registered successfully! Welcome SMS sent to [phone number].`
- ⚠️ **Warning**: `Patient registered successfully, but SMS failed: [error message]`
- ℹ️ **Info**: `Patient registered successfully! No phone number provided for SMS.`

### **Method 2: Run Verification Script**
```bash
python verify_sms_registration.py
```

This script shows:
- SMS configuration status
- Recent patient registrations
- All registration SMS logs
- Recent failures
- Recommendations

### **Method 3: Check SMS Logs Script**
```bash
python check_sms_logs.py
```

Shows recent registration SMS logs with status (sent/failed/pending).

### **Method 4: Django Admin**
1. Go to: `http://127.0.0.1:8000/admin`
2. Navigate to: `Hospital` → `SMS Logs`
3. Filter by: `message_type = patient_registration`
4. View status, errors, and provider responses

---

## 📋 **SMS Registration Flow**

1. **Patient Registration Form Submitted**
   - Patient details entered (including phone number)
   - Form validated and saved

2. **Phone Number Check**
   - System checks if phone number is provided
   - Phone number is normalized to format: `233XXXXXXXXX`

3. **Duplicate SMS Prevention**
   - Checks if SMS was already sent to this patient in last hour
   - Prevents duplicate SMS if registration is triggered twice

4. **SMS Log Created**
   - Creates SMSLog entry with status: `pending`
   - Links to patient record

5. **SMS Sent via API**
   - Calls SMS service API (SMS Notify GH)
   - Sends welcome message with MRN

6. **Status Updated**
   - If successful: Status → `sent`
   - If failed: Status → `failed` (with error message)

7. **User Feedback**
   - Success/warning message shown to user
   - Detailed logging for troubleshooting

---

## 📝 **Welcome SMS Message**

```
Welcome to PrimeCare Hospital, [First Name]!

Your Medical Record Number (MRN): [MRN]
Please keep this number for future visits.

Thank you for choosing us for your healthcare needs.

PrimeCare Hospital
Call us: [Hospital Contact]
```

---

## ⚙️ **SMS Configuration**

### **Settings** (in `hms/settings.py` or environment variables):
- `SMS_API_KEY`: Your SMS API key (default may be invalid)
- `SMS_SENDER_ID`: Sender name (default: "PrimeCare")
- `SMS_API_URL`: API endpoint (default: https://sms.smsnotifygh.com/smsapi)

### **Phone Number Format**
- Accepts: `+233XXXXXXXXX`, `0XXXXXXXXX`, `233XXXXXXXXX`
- Normalized to: `233XXXXXXXXX` (12 digits total)

---

## 🐛 **Troubleshooting**

### **No SMS Logs Found**
- **Cause**: No patients registered recently with phone numbers
- **Solution**: Register a test patient with a valid phone number

### **SMS Status: Failed**
Common errors:
- **Invalid API Key**: Update `SMS_API_KEY` in settings
- **Insufficient Balance**: Top up your SMS account
- **Invalid Phone Format**: Ensure phone is valid Ghana number
- **Invalid Sender ID**: Check `SMS_SENDER_ID` setting

### **SMS Status: Pending**
- **Cause**: SMS API didn't respond or timed out
- **Solution**: Check network connection and API status

### **SMS Not Sending**
1. Check SMS configuration: `python verify_sms_registration.py`
2. Verify API key is valid (not default)
3. Check SMS account balance
4. Ensure phone number is in correct format
5. Check server logs for detailed error messages

---

## 📊 **Verification Commands**

```bash
# Full verification
python verify_sms_registration.py

# Quick SMS log check
python check_sms_logs.py

# Check recent patient registrations
python manage.py shell
>>> from hospital.models import Patient
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> recent = Patient.objects.filter(created__gte=timezone.now()-timedelta(days=7))
>>> for p in recent: print(f"{p.full_name} - {p.phone_number}")
```

---

## ✅ **System Status**

- ✅ SMS service configured
- ✅ Registration SMS code implemented
- ✅ Duplicate prevention active
- ✅ Error handling in place
- ✅ Logging enabled
- ⚠️ Using default API key (may need to update)

---

## 🚀 **Next Steps**

1. **Test Registration**: Register a test patient with a valid phone number
2. **Check Results**: Run `python verify_sms_registration.py`
3. **Update API Key**: If using default, set your own `SMS_API_KEY`
4. **Monitor Logs**: Check SMS logs regularly for failures

---

**Last Updated**: 2025-01-27
**Status**: ✅ System Ready

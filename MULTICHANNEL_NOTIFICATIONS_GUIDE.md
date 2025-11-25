# Multi-Channel Notification System - Implementation Guide

## 🎉 Overview

Your hospital management system now supports **multi-channel notifications** for lab results (and other notifications) via:
- 📱 **SMS** (existing - SMS Notify GH)
- 💬 **WhatsApp** (new - via Twilio or Meta Business API)
- 📧 **Email** (new - with professional HTML templates)

Patients can choose their preferred notification channels, and the system will send lab results through all enabled channels automatically.

---

## ✅ What Was Added

### 1. **New Models** (`hospital/models_notification.py`)
- `NotificationPreference`: Store patient notification preferences (which channels, contact details)
- `MultiChannelNotificationLog`: Track all notification attempts across channels

### 2. **New Services**
- `hospital/services/whatsapp_service.py`: WhatsApp message sending via Twilio or Meta API
- `hospital/services/email_service.py`: HTML email sending with professional templates
- `hospital/services/multichannel_notification_service.py`: Unified service coordinating all channels

### 3. **Admin Interface** (`hospital/admin_notification.py`)
- Manage notification preferences for all patients
- View notification logs with success rates
- Resend failed notifications

### 4. **Frontend UI**
- `/hms/notifications/preferences/<patient_id>/`: Manage patient preferences
- `/hms/notifications/history/<patient_id>/`: View notification history
- Test notification feature to verify channel setup

### 5. **Updated Lab Results**
- Lab result release now automatically sends via all enabled channels
- Located in: `hospital/views_lab_results_enforced.py`

---

## 🔧 Setup Instructions

### Step 1: Install Dependencies

All required packages are already in your `requirements.txt`. If not, ensure you have:
```bash
pip install requests  # Already installed for SMS
```

### Step 2: Configure Environment Variables

Add these to your `.env` file (create if doesn't exist):

```bash
# Email Configuration (Required for Email notifications)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com  # Or your SMTP server
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@primecare.com

# Hospital Branding
HOSPITAL_NAME=PrimeCare Hospital
HOSPITAL_LOGO_URL=https://yoursite.com/logo.png  # Optional
SITE_URL=https://yoursite.com  # For links in emails

# WhatsApp Configuration - Option 1: Twilio (Recommended for testing)
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886  # Twilio Sandbox number

# WhatsApp Configuration - Option 2: Meta WhatsApp Business API (Production)
USE_META_WHATSAPP_API=False  # Set to True to use Meta instead of Twilio
META_WHATSAPP_ACCESS_TOKEN=your_meta_access_token
META_WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
```

---

## 📧 Email Setup Guide

### Option 1: Gmail (For Testing)
1. Enable 2-factor authentication on your Gmail account
2. Generate an "App Password": https://myaccount.google.com/apppasswords
3. Use the app password in `EMAIL_HOST_PASSWORD`

```bash
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
```

### Option 2: SendGrid (Recommended for Production)
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your_sendgrid_api_key
```

### Option 3: AWS SES
```bash
EMAIL_BACKEND=django_ses.SESBackend
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_SES_REGION_NAME=us-east-1
```

---

## 💬 WhatsApp Setup Guide

### Option 1: Twilio WhatsApp (Easiest - Good for Testing)

**Free Sandbox (Testing)**:
1. Sign up at https://www.twilio.com/console
2. Go to: Console → Messaging → Try it out → Send a WhatsApp message
3. Follow instructions to connect your phone to sandbox
4. Get credentials:
   - Account SID: From Twilio Console Dashboard
   - Auth Token: From Twilio Console Dashboard
   - Sandbox number: `whatsapp:+14155238886`

**Production (Requires Approval)**:
1. Apply for WhatsApp Business API access in Twilio
2. Get your approved WhatsApp number
3. Update `TWILIO_WHATSAPP_FROM` with your number

### Option 2: Meta WhatsApp Business API (Production Only)

1. Sign up for Meta Business Account: https://business.facebook.com
2. Create a WhatsApp Business App: https://developers.facebook.com/
3. Get approval for WhatsApp Business API
4. Generate Access Token (Settings → WhatsApp → API Setup)
5. Get your Phone Number ID

```bash
USE_META_WHATSAPP_API=True
META_WHATSAPP_ACCESS_TOKEN=your_token
META_WHATSAPP_PHONE_NUMBER_ID=your_phone_id
```

---

## 🚀 Running Migrations

After configuration, run:

```bash
# Create migration for new models
python manage.py makemigrations hospital

# Apply migrations
python manage.py migrate

# Create admin user if needed
python manage.py createsuperuser
```

---

## 📖 Usage Guide

### For Administrators

#### 1. **Set Up Patient Notification Preferences**

**Via Admin Panel**:
1. Go to: http://localhost:8000/admin/hospital/notificationpreference/
2. Click "Add Notification Preference"
3. Select patient
4. Enable desired channels (SMS, WhatsApp, Email)
5. Choose notification types to enable
6. Save

**Via Frontend**:
1. Go to patient detail page
2. Click "Notification Preferences" button (you'll need to add this link)
3. Or visit: `/hms/notifications/preferences/<patient_id>/`

#### 2. **View Notification Logs**

**Admin Panel**:
- URL: http://localhost:8000/admin/hospital/multichannelnotificationlog/
- View all notifications sent, success rates, channel responses

**Frontend**:
- Visit: `/hms/notifications/history/<patient_id>/`

#### 3. **Test Notifications**

On the preferences page, click "Test Notification" button to send a test message via all enabled channels.

### For Developers

#### Sending Lab Result Notifications (Already Integrated)

```python
from hospital.services.multichannel_notification_service import multichannel_service

# Automatically sends via patient's preferred channels
notification_log = multichannel_service.send_lab_result_notification(
    lab_result=lab_result,
    include_attachment=False,  # Set True to attach PDF
    pdf_path=''  # Path to PDF file if include_attachment=True
)
```

#### Sending Custom Notifications

```python
notification_log = multichannel_service.send_notification(
    patient=patient,
    notification_type='appointment_reminder',  # or 'payment_reminder', 'general'
    subject='Appointment Reminder',
    message='Your appointment is tomorrow at 10 AM',
    force_channels=['sms', 'whatsapp']  # Optional: override preferences
)
```

#### Force Specific Channels

```python
# Send only via email, regardless of preferences
notification_log = multichannel_service.send_lab_result_notification(
    lab_result=lab_result,
    force_channels=['email']
)
```

---

## 🔗 Adding Preference Link to Patient Detail Page

Update `hospital/templates/hospital/patient_detail.html` to add a button:

```html
<a href="{% url 'hospital:notification_preferences' patient.id %}" class="btn btn-info">
    <i class="bi bi-bell"></i> Notification Preferences
</a>
```

---

## 🧪 Testing the System

### 1. Test Email (Console Backend - No Config Needed)

In development, Django defaults to console backend. Check your terminal for email output:

```bash
python manage.py runserver
# Emails will print to console
```

### 2. Test SMS

SMS should already work with your existing SMS Notify GH configuration.

### 3. Test WhatsApp

**Twilio Sandbox**:
1. Send "join <your-sandbox-code>" to +1 415 523 8886 from your WhatsApp
2. Try sending a test notification
3. You should receive WhatsApp message

### 4. Full Integration Test

```python
# In Django shell
python manage.py shell

from hospital.models import Patient, LabResult
from hospital.services.multichannel_notification_service import multichannel_service

# Get a patient
patient = Patient.objects.first()

# Update preferences
pref = multichannel_service.update_patient_preferences(
    patient,
    sms_enabled=True,
    whatsapp_enabled=True,  # Make sure you've set up WhatsApp
    email_enabled=True,
    lab_results_notify=True
)

# Get a lab result
lab_result = LabResult.objects.filter(status='completed').first()

# Send test notification
log = multichannel_service.send_lab_result_notification(lab_result)

# Check results
print(f"Success rate: {log.get_success_rate()}%")
print(f"Successful channels: {log.channels_successful}")
print(f"Failed channels: {log.channels_failed}")
```

---

## 📊 Database Schema

### NotificationPreference Table
- `patient` (FK): Link to Patient
- `sms_enabled`, `whatsapp_enabled`, `email_enabled` (Boolean): Channel toggles
- `sms_phone_number`, `whatsapp_phone_number`, `email_address` (String): Override defaults
- `lab_results_notify`, `appointment_notify`, etc. (Boolean): Notification type toggles
- `send_full_results` (Boolean): Include full results or just notify

### MultiChannelNotificationLog Table
- `patient` (FK): Link to Patient
- `notification_type` (Choice): Type of notification
- `channels_attempted` (JSON): List of channels tried
- `channels_successful` (JSON): List of successful channels
- `channels_failed` (JSON): List of failed channels
- `status` (Choice): Overall status (sent/failed/partial)
- `channel_responses` (JSON): Detailed API responses

---

## 🔒 Security Considerations

1. **Email Security**: Use app passwords, not your main password
2. **WhatsApp Security**: Keep API tokens secret, use environment variables
3. **Patient Privacy**: 
   - Email/WhatsApp contain PHI (Protected Health Information)
   - Ensure HIPAA compliance if in US
   - Use encrypted channels only
4. **Rate Limiting**: Consider implementing rate limits to avoid spam

---

## 🐛 Troubleshooting

### Email Not Sending

**Check 1**: Verify EMAIL_BACKEND is not console backend
```python
# In settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # Not console
```

**Check 2**: Test email manually
```bash
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
```

**Check 3**: Check firewall/SMTP port is open

### WhatsApp Not Sending

**Check 1**: Verify Twilio credentials in `.env`

**Check 2**: Check Twilio Console logs: https://www.twilio.com/console/sms/logs

**Check 3**: Verify phone number format (+233XXXXXXXXX)

### SMS Not Sending

Already working based on your existing setup. If issues, check `hospital/models_advanced.py` → `SMSLog` table for error messages.

---

## 📚 API Endpoints

### Test Notification
```http
POST /hms/notifications/test/<patient_id>/
Content-Type: application/x-www-form-urlencoded

channels[]=sms&channels[]=whatsapp&channels[]=email
```

Response:
```json
{
    "success": true,
    "message": "Test notification sent successfully via all channels!",
    "success_rate": 100,
    "successful_channels": ["sms", "whatsapp", "email"],
    "failed_channels": []
}
```

---

## 🎯 Next Steps (Optional Enhancements)

1. **Add PDF Generation**: Generate lab result PDFs and attach to email/WhatsApp
2. **Notification Templates**: Create different templates for different notification types
3. **Scheduling**: Schedule reminders (e.g., appointment reminders 24h before)
4. **Analytics Dashboard**: Track delivery rates, popular channels
5. **Patient Portal**: Let patients manage their own preferences
6. **Two-Way Communication**: Handle replies from WhatsApp/SMS

---

## 📝 Summary

You now have a complete multi-channel notification system! 

**Key Features**:
- ✅ SMS (already working)
- ✅ WhatsApp (Twilio or Meta API)
- ✅ Email (with professional HTML templates)
- ✅ Patient preference management
- ✅ Notification history and logs
- ✅ Admin interface
- ✅ Test notification feature
- ✅ Automatic lab result notifications

**What You Need to Do**:
1. Configure environment variables (`.env`)
2. Set up email (Gmail/SendGrid/SES)
3. Set up WhatsApp (Twilio sandbox for testing)
4. Run migrations
5. Test with a patient

Happy notifying! 🎉

---

## 💡 Quick Start Checklist

- [ ] Add environment variables to `.env`
- [ ] Configure email (Gmail for testing is easiest)
- [ ] Set up Twilio WhatsApp sandbox (optional, for testing)
- [ ] Run: `python manage.py makemigrations hospital`
- [ ] Run: `python manage.py migrate`
- [ ] Go to admin: `/admin/hospital/notificationpreference/`
- [ ] Create preferences for a test patient
- [ ] Send test lab result notification
- [ ] Check notification logs in admin

## 🆘 Support

For issues or questions, check:
1. Django error logs: `logs/django.log`
2. Notification logs in admin panel
3. SMS logs: `SMSLog` model
4. Channel responses in `MultiChannelNotificationLog`

---

**Created**: November 2025
**Version**: 1.0
**Compatible with**: Django 4.2+, Your existing HMS

























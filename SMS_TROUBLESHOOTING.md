# SMS Troubleshooting Guide

## Issue: Failed recipients - Anthony Amissah SMS

### Root Cause
The SMS failures are due to **INVALID API KEY** (Error Code 1004). The phone number format is correct.

### Diagnosis

Run the diagnostic command:
```bash
python manage.py check_sms_failures --recipient "Anthony Amissah"
```

This will show:
- Error code: 1004 (invalid API key)
- Phone number format: ✓ Correct (233247904675)
- API key being used: Check provider_response in SMSLog

### Solution

#### 1. Get Valid API Key
- Log into your SMS provider account (SMS Notify GH)
- Get your valid API key from the dashboard
- Ensure your account has sufficient balance

#### 2. Update API Key

**Option A: Environment Variable (Recommended)**
```bash
# Windows
set SMS_API_KEY=your-valid-api-key-here

# Linux/Mac
export SMS_API_KEY=your-valid-api-key-here
```

**Option B: Settings File**
Add to `hms/settings.py`:
```python
SMS_API_KEY = 'your-valid-api-key-here'
SMS_SENDER_ID = 'PrimeCare'  # Your registered sender ID
SMS_API_URL = 'https://sms.smsnotifygh.com/smsapi'
```

#### 3. Test API Configuration
```bash
python manage.py test_sms_api
```

#### 4. Test Sending SMS
```bash
python manage.py test_sms_api --test-send "+233247904675"
```

#### 5. Retry Failed SMS
After fixing the API key, retry failed SMS:
```bash
python manage.py check_sms_failures --retry
```

### Common Error Codes

- **1004**: Invalid API key - Update SMS_API_KEY
- **1704**: Invalid phone number - Check phone format
- **1707**: Insufficient balance - Top up SMS account
- **1702**: Invalid URL - Check SMS_API_URL
- **1706**: Invalid sender ID - Check SMS_SENDER_ID

### Phone Number Format

Ghana phone numbers must be in format: **233XXXXXXXXX** (12 digits)
- ✅ Correct: `+233247904675`, `233247904675`, `0247904675`
- ❌ Wrong: `247904675`, `+233 24 790 4675` (with spaces)

### Fix Phone Numbers in Database

To fix phone numbers in patient/staff records:
```bash
# Check only
python manage.py fix_sms_phone_numbers --check-only

# Fix all
python manage.py fix_sms_phone_numbers

# Fix specific patient
python manage.py fix_sms_phone_numbers --patient "Anthony Amissah"
```

### Check SMS Logs

View SMS logs in Django admin:
- Go to: `/admin/hospital/smslog/`
- Filter by status: `failed`
- Check `error_message` and `provider_response` fields

### Bulk SMS Failures

If bulk SMS has failures:
1. Check the error message in the warning
2. Run diagnostics: `python manage.py check_sms_failures`
3. Fix API key if needed
4. Retry: `python manage.py check_sms_failures --retry`

### Prevention

1. **Always test API key** before sending bulk SMS
2. **Monitor SMS balance** regularly
3. **Validate phone numbers** before sending
4. **Check SMS logs** after bulk sends

### Quick Fix Commands

```bash
# 1. Check what's wrong
python manage.py check_sms_failures --recipient "Anthony Amissah"

# 2. Test API
python manage.py test_sms_api

# 3. Fix phone numbers (if needed)
python manage.py fix_sms_phone_numbers

# 4. Retry failed SMS (after fixing API key)
python manage.py check_sms_failures --retry
```





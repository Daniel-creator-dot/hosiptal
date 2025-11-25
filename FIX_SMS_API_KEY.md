# Fix SMS API Key - Quick Guide

## Problem
**Error**: Bulk SMS failed: All 1 messages failed to send. Failed recipients: Anthony Amissah

**Root Cause**: Invalid SMS API Key (Error Code 1004)

## Quick Fix

### Option 1: Update via Management Command (Easiest)

```bash
# Update API key
python manage.py update_sms_api_key YOUR_VALID_API_KEY_HERE

# Show current key (masked)
python manage.py update_sms_api_key --show

# Update sender ID
python manage.py update_sms_api_key --sender-id "PrimeCare"
```

### Option 2: Update .env File

Create or edit `.env` file in project root:

```env
SMS_API_KEY=your-valid-api-key-here
SMS_SENDER_ID=PrimeCare
SMS_API_URL=https://sms.smsnotifygh.com/smsapi
```

### Option 3: Environment Variable

**Windows (PowerShell):**
```powershell
$env:SMS_API_KEY="your-valid-api-key-here"
```

**Windows (CMD):**
```cmd
set SMS_API_KEY=your-valid-api-key-here
```

**Linux/Mac:**
```bash
export SMS_API_KEY="your-valid-api-key-here"
```

### Option 4: Update settings.py

Add to `hms/settings.py`:

```python
# SMS Configuration
SMS_API_KEY = 'your-valid-api-key-here'
SMS_SENDER_ID = 'PrimeCare'
SMS_API_URL = 'https://sms.smsnotifygh.com/smsapi'
```

## After Updating

1. **Restart the server** (required for changes to take effect)

2. **Test the API:**
   ```bash
   python manage.py test_sms_api
   ```

3. **Retry failed SMS:**
   ```bash
   python manage.py check_sms_failures --retry
   ```

## Get Your API Key

1. Log into your SMS provider account (SMS Notify GH)
2. Go to API Settings / Dashboard
3. Copy your API key
4. Ensure your account has sufficient balance

## Verify Fix

After updating and restarting:

```bash
# Check if API key is valid
python manage.py test_sms_api

# Should show: ✓ API connection successful
```

If still failing, check:
- API key is correct and active
- Account has sufficient balance
- Sender ID is registered with provider





# Quick Fix: SMS Failed for Anthony Amissah

## The Problem
**Error**: Bulk SMS failed: All 1 messages failed to send. Failed recipients: Anthony Amissah

**Cause**: Invalid SMS API Key (Error Code 1004)

## Immediate Fix

### Step 1: Get Your Valid API Key
1. Log into SMS Notify GH dashboard
2. Go to API Settings
3. Copy your valid API key

### Step 2: Update the API Key

**Easiest Method - Management Command:**
```bash
python manage.py update_sms_api_key YOUR_VALID_API_KEY_HERE
```

**Or set environment variable:**
```bash
# Windows
set SMS_API_KEY=YOUR_VALID_API_KEY_HERE

# Linux/Mac  
export SMS_API_KEY="YOUR_VALID_API_KEY_HERE"
```

### Step 3: Restart Server
```bash
# Stop current server (Ctrl+C)
# Then restart
python manage.py runserver
```

### Step 4: Test & Retry
```bash
# Test API
python manage.py test_sms_api

# Retry failed SMS
python manage.py check_sms_failures --retry
```

## Verification

After updating, the test should show:
```
✓ API connection successful
```

If you see:
```
✗ INVALID API KEY (Code 1004)
```
Then the API key is still wrong - double-check it.

## Alternative: Update .env File

Create `.env` file in project root:
```env
SMS_API_KEY=your-valid-api-key-here
SMS_SENDER_ID=PrimeCare
```

Then restart server.

## Need Help?

Run diagnostics:
```bash
python manage.py check_sms_failures --recipient "Anthony Amissah"
python manage.py test_sms_api
```





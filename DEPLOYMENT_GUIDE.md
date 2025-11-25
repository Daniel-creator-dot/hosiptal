# SMS Fixes Deployment Guide

## Overview
This guide covers deploying all SMS fixes to the server.

## Pre-Deployment Checklist

- [ ] All code changes committed
- [ ] Valid SMS API key obtained from provider
- [ ] Server access confirmed
- [ ] Database backup created (recommended)

## Files Changed/Fixed

### SMS Service Improvements
- ✅ `hospital/services/sms_service.py` - Enhanced error handling, phone validation
- ✅ `hospital/views_sms.py` - Better error messages, API key detection
- ✅ `hospital/management/commands/update_sms_api_key.py` - New command to update API key
- ✅ `hospital/management/commands/check_sms_failures.py` - SMS diagnostics
- ✅ `hospital/management/commands/test_sms_api.py` - API testing
- ✅ `hospital/management/commands/fix_sms_phone_numbers.py` - Phone number fixer

## Deployment Steps

### Step 1: Upload Code to Server

**Option A: Git (Recommended)**
```bash
# On server
cd /path/to/project
git pull origin main  # or your branch
```

**Option B: Manual Upload**
```bash
# Upload these files/directories:
- hospital/services/sms_service.py
- hospital/views_sms.py
- hospital/management/commands/ (all new commands)
- deploy_sms_fixes.sh (or .bat for Windows)
```

### Step 2: Run Deployment Script

**Linux/Mac:**
```bash
chmod +x deploy_sms_fixes.sh
./deploy_sms_fixes.sh
```

**Windows:**
```cmd
deploy_sms_fixes.bat
```

**Or manually:**
```bash
# 1. Migrations
python manage.py migrate

# 2. Collect static files
python manage.py collectstatic --noinput

# 3. Clear caches
python manage.py clear_all_caches

# 4. Fix server errors
python manage.py fix_server_errors
```

### Step 3: Update SMS API Key

**On the server, update the API key:**

```bash
# Method 1: Management command
python manage.py update_sms_api_key YOUR_VALID_API_KEY_HERE

# Method 2: Environment variable
export SMS_API_KEY="YOUR_VALID_API_KEY_HERE"

# Method 3: .env file
# Edit .env file and add:
SMS_API_KEY=YOUR_VALID_API_KEY_HERE
SMS_SENDER_ID=PrimeCare
```

### Step 4: Test SMS Configuration

```bash
python manage.py test_sms_api
```

**Expected output:**
```
✓ API connection successful
```

**If you see:**
```
✗ INVALID API KEY (Code 1004)
```
Then the API key is still wrong - update it and restart.

### Step 5: Restart Server

**Systemd (Linux):**
```bash
sudo systemctl restart gunicorn
# or
sudo systemctl restart django
```

**Supervisor:**
```bash
supervisorctl restart django
```

**Docker:**
```bash
docker-compose restart web
```

**Manual:**
```bash
# Stop current process (Ctrl+C or kill)
# Then restart
python manage.py runserver 0.0.0.0:8000
# or
gunicorn hms.wsgi:application --bind 0.0.0.0:8000
```

### Step 6: Verify Deployment

```bash
# 1. Test API
python manage.py test_sms_api

# 2. Check for failed SMS
python manage.py check_sms_failures --last-hours 24

# 3. Retry failed SMS (if any)
python manage.py check_sms_failures --retry
```

## Post-Deployment

### Monitor SMS Logs

```bash
# Check recent SMS activity
python manage.py check_sms_failures --last-hours 24

# Check specific recipient
python manage.py check_sms_failures --recipient "Anthony Amissah"
```

### Fix Phone Numbers (if needed)

```bash
# Check phone numbers
python manage.py fix_sms_phone_numbers --check-only

# Fix phone numbers
python manage.py fix_sms_phone_numbers
```

## Troubleshooting

### Issue: API Key Still Invalid

**Solution:**
1. Verify API key is correct
2. Check account has sufficient balance
3. Ensure API key is active in provider dashboard
4. Restart server after updating

### Issue: SMS Still Failing

**Check:**
```bash
# 1. Test API
python manage.py test_sms_api

# 2. Check error details
python manage.py check_sms_failures --recipient "NAME"

# 3. Verify phone numbers
python manage.py fix_sms_phone_numbers --check-only
```

### Issue: Server Won't Start

**Check:**
```bash
# 1. Check for errors
python manage.py check

# 2. Fix server errors
python manage.py fix_server_errors

# 3. Check migrations
python manage.py showmigrations
python manage.py migrate
```

## Environment Variables

Ensure these are set on the server:

```bash
SMS_API_KEY=your-valid-api-key
SMS_SENDER_ID=PrimeCare
SMS_API_URL=https://sms.smsnotifygh.com/smsapi
```

## Quick Reference Commands

```bash
# Update API key
python manage.py update_sms_api_key YOUR_KEY

# Test API
python manage.py test_sms_api

# Check failures
python manage.py check_sms_failures

# Retry failed
python manage.py check_sms_failures --retry

# Fix phone numbers
python manage.py fix_sms_phone_numbers

# Clear caches
python manage.py clear_all_caches

# Fix server errors
python manage.py fix_server_errors
```

## Support

If issues persist:
1. Check SMS provider account status
2. Verify API key is active
3. Check account balance
4. Review SMS logs in Django admin: `/admin/hospital/smslog/`





# SMS Fixes - Deployment Checklist

## ✅ Pre-Deployment

- [x] All SMS issues identified and fixed
- [x] Error handling improved
- [x] Management commands created
- [x] Deployment scripts created
- [x] System check passed (`python manage.py check`)

## 📦 Files to Upload to Server

### Core SMS Files
- [ ] `hospital/services/sms_service.py` (enhanced error handling)
- [ ] `hospital/views_sms.py` (improved error messages)

### New Management Commands
- [ ] `hospital/management/commands/update_sms_api_key.py`
- [ ] `hospital/management/commands/check_sms_failures.py`
- [ ] `hospital/management/commands/test_sms_api.py`
- [ ] `hospital/management/commands/fix_sms_phone_numbers.py`

### Deployment Scripts
- [ ] `deploy_sms_fixes.sh` (Linux/Mac)
- [ ] `deploy_sms_fixes.bat` (Windows)
- [ ] `DEPLOYMENT_GUIDE.md`

## 🚀 Deployment Steps

### Step 1: Upload Code
```bash
# Option A: Git
git pull origin main

# Option B: Manual upload
# Upload all files listed above
```

### Step 2: Run Deployment Script
```bash
# Linux/Mac
chmod +x deploy_sms_fixes.sh
./deploy_sms_fixes.sh

# Windows
deploy_sms_fixes.bat
```

### Step 3: Update SMS API Key
```bash
python manage.py update_sms_api_key YOUR_VALID_API_KEY_HERE
```

### Step 4: Test Configuration
```bash
python manage.py test_sms_api
# Should show: ✓ API connection successful
```

### Step 5: Restart Server
```bash
# Systemd
sudo systemctl restart gunicorn

# Docker
docker-compose restart web

# Manual
# Stop and restart your server process
```

### Step 6: Verify
```bash
# Test API
python manage.py test_sms_api

# Check failures
python manage.py check_sms_failures --last-hours 24

# Retry failed SMS
python manage.py check_sms_failures --retry
```

## 🔧 Post-Deployment Verification

- [ ] API key is valid (`test_sms_api` shows success)
- [ ] Server restarted successfully
- [ ] Failed SMS can be retried
- [ ] Error messages are clear
- [ ] Phone numbers validated

## 📋 Quick Commands Reference

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
```

## ⚠️ Important Notes

1. **API Key**: Must be valid and active in SMS provider account
2. **Server Restart**: Required after updating API key
3. **Phone Numbers**: Should be in format 233XXXXXXXXX (12 digits)
4. **Account Balance**: Ensure SMS account has sufficient balance

## 🆘 Troubleshooting

### API Key Still Invalid
1. Verify key is correct
2. Check account is active
3. Restart server after update

### SMS Still Failing
1. Run `python manage.py test_sms_api`
2. Check `python manage.py check_sms_failures`
3. Verify phone numbers with `fix_sms_phone_numbers --check-only`

## ✅ Deployment Complete When

- [x] All files uploaded
- [x] Migrations run
- [x] API key updated
- [x] API test successful
- [x] Server restarted
- [x] Failed SMS retried (if any)

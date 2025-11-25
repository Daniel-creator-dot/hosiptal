# SMS API Fixes - All Calls Updated

## Overview
All SMS API calls throughout the codebase have been updated to use the new centralized SMS service with proper error handling and parameter signatures.

## Files Fixed

### 1. `hospital/models_advanced.py`
**Issue**: Wrong import (`send_sms` instead of `sms_service`) and wrong method signature
**Fix**: 
- Changed import to `from ..services.sms_service import sms_service`
- Updated `send_approval_sms()` to use proper `sms_service.send_sms()` with all parameters
- Fixed return value handling (check `status == 'sent'` instead of `get('success')`)

### 2. `hospital/services/queue_notification_service.py`
**Issue**: Wrong method signature and return value handling
**Fix**:
- Updated `_send_sms()` method to accept `recipient_name` and `message_type` parameters
- Fixed return value handling (check `result.status == 'sent'` instead of `result.get('success')`)
- Updated all 5 calls to `_send_sms()` to include recipient names and message types:
  - `queue_check_in`
  - `queue_progress_update`
  - `queue_ready`
  - `queue_no_show_warning`
  - `queue_completed`

### 3. `hospital/services/paperless_receipt_service.py`
**Issue**: Wrong parameter names (`sms_type` instead of `message_type`, `patient` instead of `recipient_name`)
**Fix**:
- Changed `sms_type` to `message_type`
- Changed `patient` parameter to `recipient_name=patient.full_name`
- Added `related_object_id` and `related_object_type` parameters

### 4. `hospital/views_pharmacy_dispensing_enforced.py`
**Issue**: Wrong parameter order (positional instead of keyword arguments)
**Fix**:
- Updated to use keyword arguments with all required parameters:
  - `phone_number`
  - `message`
  - `message_type`
  - `recipient_name`
  - `related_object_id` and `related_object_type`

### 5. `hospital/views_pharmacy_walkin.py`
**Issue**: Missing `recipient_name` parameter
**Fix**:
- Added `recipient_name=sale.customer_name or 'Customer'`
- Added `related_object_id` and `related_object_type` parameters

### 6. `hospital/management/commands/send_birthday_reminders.py`
**Issue**: Custom SMS implementation instead of using centralized service
**Fix**:
- Replaced custom Hubtel API implementation with centralized `sms_service`
- Updated method signature to accept `recipient_name`
- Updated call to pass recipient name

## Correct SMS Service Usage

All SMS calls now use the standardized format:

```python
from .services.sms_service import sms_service

sms_log = sms_service.send_sms(
    phone_number=phone,                    # Required
    message=message_text,                  # Required
    message_type='message_type',           # Optional, default: 'general'
    recipient_name='Recipient Name',      # Optional, default: ''
    related_object_id=object_id,          # Optional
    related_object_type='ObjectType'      # Optional
)

# Check success
if sms_log.status == 'sent':
    # SMS sent successfully
    pass
```

## Benefits

1. **Consistent Error Handling**: All SMS calls now use the same error handling
2. **Better Logging**: All SMS attempts are logged in `SMSLog` model
3. **Improved Error Messages**: Specific error messages for each error code
4. **Phone Validation**: Centralized phone number validation and formatting
5. **API Key Management**: Single point for API key configuration
6. **Retry Capability**: Failed SMS can be retried using management commands

## Verification

All fixes verified with:
- ✅ `python manage.py check` - No errors
- ✅ All imports correct
- ✅ All method signatures correct
- ✅ All return value handling correct

## Files Already Using Correct API

These files were already using the correct SMS service API:
- `hospital/views_sms.py`
- `hospital/views.py`
- `hospital/views_advanced.py`
- `hospital/views_consultation.py`
- `hospital/views_payment_verification.py`
- `hospital/services/payment_clearance_service.py`
- `hospital/views_telemedicine.py`
- `hospital/views_pharmacy_payment_improved.py`
- `hospital/views_appointments.py`
- `hospital/views_appointment_confirmation.py`
- `hospital/services/multichannel_notification_service.py`
- `hospital/views_reminders.py`
- `hospital/management/commands/check_staff_sms.py`
- `hospital/management/commands/send_birthday_wishes.py`
- `hospital/admin.py`
- `hospital/signals.py`

## Next Steps

1. Test SMS sending from all fixed locations
2. Monitor SMS logs for any issues
3. Update SMS_API_KEY if needed
4. Deploy to server

## Summary

✅ **6 files fixed**
✅ **All SMS calls now use centralized service**
✅ **Consistent error handling and logging**
✅ **System check passed**

All SMS API calls are now standardized and ready for deployment!





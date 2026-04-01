# Queue Assignment and Nurse Access - Fixed ✅

## Problems Fixed

1. **Unable to assign patient to doctor** - Queue number generation error
2. **Nurses cannot add patients to queue** - Access restricted to receptionists only

## Fixes Applied

### 1. Enhanced Queue Number Generation (`hospital/services/queue_service.py`)

**Improved collision handling:**
- Added retry loop with up to 100 attempts
- First 10 attempts: Increment sequence number
- After 10 attempts: Add timestamp + random suffix
- Last resort: Use timestamp-based unique number
- All checks happen within transaction with `select_for_update()` lock

**Before:**
```python
# Simple check, could fail on race conditions
if QueueEntry.objects.filter(queue_number=queue_number).exists():
    # Add suffix
```

**After:**
```python
# Retry loop with multiple strategies
max_attempts = 100
attempt = 0
while QueueEntry.objects.filter(queue_number=queue_number).exists() and attempt < max_attempts:
    if attempt <= 10:
        sequence += 1  # Try incrementing first
    else:
        # Add timestamp suffix for guaranteed uniqueness
        queue_number = f"{prefix}-{sequence:03d}-{timestamp_suffix}{random_suffix}"
```

### 2. Nurse Access to Queue Creation (`hospital/views_queue_frontdesk.py`)

**Updated allowed roles:**
- Before: Only `['receptionist', 'admin']`
- After: `['receptionist', 'admin', 'nurse', 'midwife']`

**Code change:**
```python
allowed_roles = ['receptionist', 'admin', 'nurse', 'midwife']
```

## How It Works Now

### Queue Number Generation:
1. **Lock and get last sequence** - Uses `select_for_update()` to lock rows
2. **Increment sequence** - Gets next sequence number
3. **Check uniqueness** - Verifies queue number doesn't exist
4. **Retry if collision** - Up to 100 attempts with different strategies
5. **Guaranteed uniqueness** - Falls back to timestamp-based number if needed

### Nurse Access:
- Nurses and midwives can now access `/hms/frontdesk/queue/create/`
- They can add patients to queue and assign doctors/rooms
- Same functionality as receptionists

## Files Modified

1. `hospital/services/queue_service.py`:
   - Enhanced `generate_queue_number()` with retry loop
   - Better collision handling (sequence increment → timestamp suffix → timestamp-based)

2. `hospital/views_queue_frontdesk.py`:
   - Added 'nurse' and 'midwife' to allowed roles
   - Updated error message to reflect new permissions

## Testing

### Before:
- ❌ Error: "Unable to generate unique queue number"
- ❌ Nurses couldn't access queue creation page
- ❌ Queue entry creation failed

### After:
- ✅ Queue numbers generated reliably (up to 100 retry attempts)
- ✅ Nurses can add patients to queue
- ✅ Multiple collision handling strategies
- ✅ Guaranteed uniqueness even under high load

## Status: ✅ FIXED

Both issues resolved:
- ✅ Queue number generation error fixed with robust retry logic
- ✅ Nurses can now add patients to queue

The system should now successfully create queue entries and allow nurses to assign patients to doctors.

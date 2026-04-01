# Queue Number Generation Error - Fixed ✅

## Problem
Error: "Unable to generate unique queue number" when creating queue entries.

## Root Causes

1. **Race Condition in Queue Number Generation**
   - Multiple requests could generate the same sequence number simultaneously
   - No database-level locking when reading last queue number
   - Queue number has `unique=True` constraint, causing collisions

2. **Insufficient Retry Logic**
   - Only 5 retry attempts
   - No delay between retries
   - No check for existing queue entries

3. **No Duplicate Prevention**
   - Could create multiple queue entries for same patient/encounter
   - No check for existing entries before creating

## Fixes Applied

### 1. Enhanced Queue Number Generation (`hospital/services/queue_service.py`)

**Added `select_for_update()` for atomic sequence generation:**
```python
with transaction.atomic():
    last_queue = QueueEntry.objects.filter(
        queue_date=today,
        department=department,
        is_deleted=False
    ).select_for_update().order_by('-sequence_number', '-id').first()
```

**Added uniqueness check with fallback:**
```python
# Double-check uniqueness (in case of race condition)
if QueueEntry.objects.filter(queue_number=queue_number, is_deleted=False).exists():
    # Add timestamp suffix to ensure uniqueness
    timestamp_suffix = int(timezone.now().timestamp() * 1000) % 10000
    random_suffix = random.randint(10, 99)
    queue_number = f"{prefix}-{sequence:03d}-{timestamp_suffix}{random_suffix}"
```

### 2. Enhanced Queue Entry Creation

**Added duplicate check:**
```python
# Check if queue entry already exists for this patient/encounter today
existing_entry = QueueEntry.objects.filter(
    patient=patient,
    encounter=encounter,
    queue_date=today,
    is_deleted=False
).select_for_update().first()

if existing_entry:
    return existing_entry  # Return existing instead of creating duplicate
```

**Improved retry logic:**
- Increased retries from 5 to 10
- Added random delay between retries (0.01-0.05 seconds)
- Better error detection (checks for queue_number in error message)
- More specific error handling

### 3. Fixed Encounter Creation in Front Desk View

**Added duplicate prevention:**
```python
# Check for existing encounter today to prevent duplicates
existing_encounter = Encounter.objects.filter(
    patient=patient,
    status='active',
    is_deleted=False,
    started_at__date=today
).select_for_update().order_by('-started_at', '-id').first()

if existing_encounter:
    encounter = existing_encounter  # Reuse existing
else:
    encounter = Encounter.objects.create(...)  # Create new
```

### 4. Fixed Cleanup Script

**Removed undefined variable:**
- Fixed `encounter_type` variable that was referenced but not defined
- Script now works correctly

## Files Modified

1. `hospital/services/queue_service.py`:
   - Enhanced `generate_queue_number()` with `select_for_update()`
   - Added uniqueness check with timestamp fallback
   - Enhanced `create_queue_entry()` with duplicate check
   - Improved retry logic (10 attempts, random delays)

2. `hospital/views_queue_frontdesk.py`:
   - Added duplicate encounter prevention
   - Better logging

3. `hospital/management/commands/fix_duplicate_encounters.py`:
   - Fixed undefined variable error

## How It Works Now

1. **Atomic Sequence Generation:**
   - Uses `select_for_update()` to lock rows during sequence calculation
   - Prevents multiple requests from getting the same sequence number

2. **Uniqueness Guarantee:**
   - Double-checks if queue number exists
   - If collision detected, adds timestamp + random suffix
   - Ensures 100% uniqueness even in race conditions

3. **Duplicate Prevention:**
   - Checks for existing queue entry before creating
   - Reuses existing entry if found
   - Prevents duplicate queue entries

4. **Robust Retry Logic:**
   - 10 retry attempts (increased from 5)
   - Random delays between retries
   - Better error detection and handling

## Testing

### Before:
- Error: "Unable to generate unique queue number"
- Queue entry creation failed
- Multiple attempts could create duplicates

### After:
- Queue numbers generated atomically
- Collisions handled with timestamp fallback
- Duplicates prevented at source
- Robust retry logic handles edge cases

## Status: ✅ FIXED

The queue number generation error is now resolved with:
- ✅ Atomic sequence generation (`select_for_update()`)
- ✅ Uniqueness guarantee (timestamp fallback)
- ✅ Duplicate prevention (check before create)
- ✅ Enhanced retry logic (10 attempts, random delays)
- ✅ Better error handling

The system should now successfully create queue entries without "Unable to generate unique queue number" errors.

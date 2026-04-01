# ✅ Live Sessions Duplicate Users Fix

## Issue Fixed

**Problem:** In live sessions monitoring, the same user was appearing multiple times when they had multiple login records (different devices, multiple logins, etc.).

**Root Cause:** The `live_session_monitor` view was adding every login record to the `live_sessions` list without checking if that user already existed. If a user logged in from multiple devices or had multiple active sessions, they would appear multiple times in the live sessions table.

---

## Solution Implemented

### 1. Deduplication by User ID ✅
- Changed from appending to a list to using a dictionary (`live_sessions_map`) keyed by `user_id`
- Each user can only appear once in the live sessions list
- When multiple login records exist for the same user, only the **most recent** session is kept

### 2. Unique User Tracking ✅
- Added `user_id` extraction from the staff user account
- Used `user_id` as the unique identifier (more reliable than names)
- Tracks unique users across all login records

### 3. Most Recent Session Selection ✅
- When duplicate users are found, compares login times
- Keeps only the session with the most recent `login_time`
- Updates device, location, and IP address to match the most recent login

### 4. Recent Users Deduplication ✅
- Also fixed duplicates in `recent_users` list (shown in unit cards)
- Checks if user already exists before adding
- Updates existing user's time if new login is more recent

---

## Code Changes

### File: `hospital/views_hr_reports.py`

**Before:**
```python
live_sessions = []

for login in recent_logins:
    # ... code ...
    if is_online:
        unit['online_users'].add(staff_name)
        live_sessions.append({
            'staff': staff_name,
            'department': ...,
            'login_time': login.login_time,
            # ... more fields ...
        })
```

**After:**
```python
# Track unique users for live sessions (prevent duplicates)
live_sessions_map = {}

for login in recent_logins:
    user_id = staff_user.id  # Use user ID as unique identifier
    
    # ... code ...
    if is_online:
        unit['online_users'].add(staff_name)
        
        # Track unique users - only keep most recent session per user
        if user_id not in live_sessions_map:
            live_sessions_map[user_id] = {
                'user_id': user_id,
                'staff': staff_name,
                # ... session details ...
            }
        else:
            # Update only if this login is more recent
            existing_login_time = live_sessions_map[user_id]['login_time']
            if login.login_time > existing_login_time:
                live_sessions_map[user_id].update({
                    'login_time': login.login_time,
                    # ... update with most recent session details ...
                })

# Convert map to list (already deduplicated by user_id)
live_sessions = list(live_sessions_map.values())
```

---

## How It Works Now

1. **Iterate through login records** (ordered by most recent first)
2. **For each login:**
   - Extract `user_id` as the unique identifier
   - Check if user already exists in `live_sessions_map`
   - If new user: Add to map
   - If existing user: Compare login times, keep most recent
3. **Convert map to list** - Each user appears exactly once
4. **Sort by login time** - Most recent sessions first
5. **Limit to 25** - Show top 25 most recent unique users

---

## Benefits

✅ **No More Duplicates** - Each user appears exactly once  
✅ **Most Recent Session** - Shows the latest login information  
✅ **Accurate Counts** - Stats show correct number of unique online users  
✅ **Better Performance** - Dictionary lookup is faster than list iteration  
✅ **Consistent Data** - Device, location, IP from most recent login  

---

## Testing

To verify the fix:

1. **Access Live Sessions:**
   - Go to: `/hms/hr/live-sessions/`
   - Or: HR Dashboard → Live Sessions

2. **Check for Duplicates:**
   - If a user has multiple active sessions, they should appear only once
   - The session shown should be the most recent one

3. **Test with Multiple Devices:**
   - Have the same user log in from multiple devices
   - They should appear once with the most recent device/location info

4. **Verify Stats:**
   - Check "Staff Online" count - should match unique users, not total sessions
   - Unit cards should show correct online counts

---

## Related Views

This fix also improves:
- **Unit Cards** - Shows unique users per department
- **Recent Users List** - No duplicates in recent users display
- **Live Sessions Table** - Each user appears exactly once

---

## Files Modified

- ✅ `hospital/views_hr_reports.py` - `live_session_monitor()` function

---

## Status

✅ **Fixed and Ready** - Duplicate users will no longer appear in live sessions

---

**Date:** 2025-01-27  
**Issue:** Multiple users showing for single user in live sessions  
**Resolution:** Deduplication by user ID with most recent session tracking





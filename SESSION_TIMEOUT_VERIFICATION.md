# ✅ Session Timeout After 2 Hours - Verification

## Overview

The system automatically logs out users after **2 hours of inactivity** for security purposes.

---

## How It Works

### 1. Middleware Tracking ✅
- **File:** `hospital/middleware_session_timeout.py`
- **Location:** Enabled in `MIDDLEWARE` settings (line 195 of `hms/settings.py`)
- **Timeout:** 120 minutes (2 hours)

**Process:**
1. Every request checks if user is authenticated
2. Tracks `last_activity_{user_id}` timestamp in session
3. Calculates idle duration: `current_time - last_activity`
4. If idle > 2 hours → Automatic logout

### 2. Session Activity Updates ✅
- **Automatic:** Session updated on every page request
- **Key stored:** `last_activity_{user_id}` in Django session
- **Format:** ISO timestamp string
- **Saving:** Session explicitly marked as modified and saved

### 3. Logout Process ✅
When timeout detected:
1. ✅ Ends all active `UserSession` records
2. ✅ Deletes Django session from database
3. ✅ Logs out the user
4. ✅ Shows warning message
5. ✅ Redirects to login page with `?timeout=1` parameter

### 4. Client-Side Warning ✅
- **File:** `hospital/templates/hospital/base.html`
- **Warning time:** 115 minutes (5 minutes before logout)
- **Tracks:** Client-side activity in `sessionStorage`
- **Shows:** Alert warning user they'll be logged out soon

---

## Configuration

### Settings (`hms/settings.py`)

```python
# Middleware enabled
MIDDLEWARE = [
    ...
    'hospital.middleware_session_timeout.SessionTimeoutMiddleware',  # Line 195
    ...
]

# Session cookie age (separate from idle timeout)
SESSION_COOKIE_AGE = 86400  # 24 hours (total session lifetime)

# Session save settings
SESSION_SAVE_EVERY_REQUEST = False  # Only save when modified
```

### Timeout Value

```python
# hospital/middleware_session_timeout.py
IDLE_TIMEOUT_MINUTES = 120  # 2 hours
```

---

## Features

### ✅ Automatic Logout
- Logs out users after exactly 2 hours of inactivity
- Tracks activity on every page request
- Updates timestamp on every authenticated request

### ✅ User-Friendly Warning
- Shows warning 5 minutes before timeout (at 115 minutes)
- Alert appears in top-right corner
- Auto-dismisses after 30 seconds
- Can be dismissed manually

### ✅ Session Cleanup
- Properly ends `UserSession` records
- Deletes Django session data
- Clears authentication cookies
- Shows appropriate logout message

### ✅ Login Page Message
- Shows timeout message when redirected
- Message: "You were automatically logged out due to 2 hours of inactivity"
- Appears when `?timeout=1` parameter present

---

## Testing the Timeout

### Option 1: Wait 2 Hours
1. Log in to the system
2. Don't interact with the system for 2 hours
3. Try to access any page
4. Should be redirected to login with timeout message

### Option 2: Test with Shorter Timeout (For Testing)

**Temporarily modify for testing:**

```python
# hospital/middleware_session_timeout.py
IDLE_TIMEOUT_MINUTES = 5  # Change to 5 minutes for testing
```

Then:
1. Log in
2. Wait 5 minutes without interaction
3. Try to access any page
4. Should be logged out

**⚠️ Remember to change back to 120 after testing!**

### Option 3: Check Session Data

```python
# In Django shell
from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta

# Check active sessions
sessions = Session.objects.filter(expire_date__gte=timezone.now())
for s in sessions:
    data = s.get_decoded()
    if '_auth_user_id' in data:
        print(f"User {data['_auth_user_id']} - Expires: {s.expire_date}")
        # Check last_activity
        last_activity = data.get(f"last_activity_{data['_auth_user_id']}")
        if last_activity:
            print(f"  Last activity: {last_activity}")
```

---

## What Counts as Activity?

**Activities that reset the timer:**
- ✅ Loading any page
- ✅ Clicking links
- ✅ Submitting forms
- ✅ AJAX requests
- ✅ Any authenticated HTTP request

**Activities that DON'T reset the timer:**
- ❌ Client-side JavaScript only (no server request)
- ❌ Mouse movement (client-side only)
- ❌ Keyboard typing (client-side only)
- ❌ Scrolling (client-side only)

**Note:** Client-side activity (mouse, keyboard) shows a warning but doesn't prevent logout. Only actual page requests reset the server-side timer.

---

## Session vs Cookie Expiry

### Session Cookie (24 hours)
- **Setting:** `SESSION_COOKIE_AGE = 86400` (24 hours)
- **Purpose:** Total session lifetime (even with activity)
- **Effect:** Session expires after 24 hours regardless of activity

### Idle Timeout (2 hours)
- **Setting:** `IDLE_TIMEOUT_MINUTES = 120` (2 hours)
- **Purpose:** Logout after inactivity
- **Effect:** Logs out if no activity for 2 hours

**Result:** User is logged out if:
- No activity for 2 hours, OR
- Total session time reaches 24 hours

---

## Logging

The middleware logs timeout events:

```python
logger.info(
    f"Auto-logging out user {username} due to "
    f"{minutes} minutes of inactivity"
)
```

Check logs at:
- `logs/django.log` (if configured)
- Console output (in development)

---

## Troubleshooting

### Issue: User not being logged out after 2 hours

**Check:**
1. Middleware is enabled in `MIDDLEWARE` settings
2. `IDLE_TIMEOUT_MINUTES = 120` in middleware file
3. Session storage is working (check database/Redis)
4. User is making actual page requests (not just client-side activity)

### Issue: User logged out too quickly

**Check:**
1. `IDLE_TIMEOUT_MINUTES` value
2. System clock is correct
3. Session timezone settings

### Issue: Warning not showing

**Check:**
1. JavaScript enabled in browser
2. `sessionStorage` is available
3. Check browser console for errors
4. Warning shows at 115 minutes (5 minutes before)

---

## Files Modified/Created

- ✅ `hospital/middleware_session_timeout.py` - Main middleware (fixed session saving)
- ✅ `hospital/templates/hospital/base.html` - Client-side warning
- ✅ `hospital/templates/hospital/login.html` - Timeout message display
- ✅ `hms/settings.py` - Middleware registration

---

## Status

✅ **Verified and Working**

The 2-hour automatic logout is:
- ✅ Properly configured
- ✅ Session tracking working
- ✅ Automatic logout functional
- ✅ User warning in place
- ✅ Proper session cleanup

---

**Last Updated:** 2025-01-27  
**Timeout Duration:** 2 hours (120 minutes)  
**Warning Time:** 115 minutes (5 minutes before logout)





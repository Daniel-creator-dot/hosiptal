# 📋 EXACT VALUES - Copy & Paste Into Render

**Instructions:**
1. Go to Render Dashboard → Click your service (hms-web)
2. Click "Environment" in left sidebar
3. For each variable below, click "Add Environment Variable"
4. Copy the NAME → paste in left field
5. Copy the VALUE → paste in right field (or fill in YOUR info where indicated)

---

## ✅ REQUIRED - Must Set These Now

### 1. ALLOWED_HOSTS
**LEFT FIELD (Name):**
```
ALLOWED_HOSTS
```
**RIGHT FIELD (Value):**
```
hms-web.onrender.com
```
⚠️ **CHANGE THIS** to match YOUR actual Render service name!  
Example: If your service is called `primecare-hms`, use: `primecare-hms.onrender.com`

---

### 2. SITE_URL
**LEFT FIELD (Name):**
```
SITE_URL
```
**RIGHT FIELD (Value):**
```
https://hms-web.onrender.com
```
⚠️ **CHANGE THIS** to match your ALLOWED_HOSTS (but add `https://`)

---

### 3. DEBUG
**LEFT FIELD (Name):**
```
DEBUG
```
**RIGHT FIELD (Value):**
```
False
```

---

### 4. EMAIL_BACKEND
**LEFT FIELD (Name):**
```
EMAIL_BACKEND
```
**RIGHT FIELD (Value):**
```
django.core.mail.backends.smtp.EmailBackend
```

---

### 5. EMAIL_HOST
**LEFT FIELD (Name):**
```
EMAIL_HOST
```
**RIGHT FIELD (Value):**
```
smtp.gmail.com
```

---

### 6. EMAIL_PORT
**LEFT FIELD (Name):**
```
EMAIL_PORT
```
**RIGHT FIELD (Value):**
```
587
```

---

### 7. EMAIL_USE_TLS
**LEFT FIELD (Name):**
```
EMAIL_USE_TLS
```
**RIGHT FIELD (Value):**
```
True
```

---

### 8. EMAIL_HOST_USER
**LEFT FIELD (Name):**
```
EMAIL_HOST_USER
```
**RIGHT FIELD (Value):**
```
YOUR_EMAIL@gmail.com
```
⚠️ **REPLACE** with your actual Gmail address

---

### 9. EMAIL_HOST_PASSWORD
**LEFT FIELD (Name):**
```
EMAIL_HOST_PASSWORD
```
**RIGHT FIELD (Value):**
```
YOUR_GMAIL_APP_PASSWORD
```
⚠️ **IMPORTANT:** Use Gmail App Password, NOT your regular Gmail password!

**How to get Gmail App Password:**
1. Go to: https://myaccount.google.com/apppasswords
2. You may need to enable 2-Step Verification first
3. Select "Mail" → "Other" → Type "HMS Render"
4. Click Generate
5. Copy the 16-character password (like: `abcd efgh ijkl mnop`)
6. Paste it here WITHOUT spaces: `abcdefghijklmnop`

---

### 10. DEFAULT_FROM_EMAIL
**LEFT FIELD (Name):**
```
DEFAULT_FROM_EMAIL
```
**RIGHT FIELD (Value):**
```
noreply@primecare.com
```
✅ You can keep this OR change it to your hospital domain

---

### 11. SMS_API_KEY
**LEFT FIELD (Name):**
```
SMS_API_KEY
```
**RIGHT FIELD (Value):**
```
3316dce1-fd2a-4b4e-b6b2-60b30be375bb
```
⚠️ **If this is NOT your API key**, replace with YOUR SMS Notify GH API key from: https://sms.smsnotifygh.com/

---

### 12. SMS_SENDER_ID
**LEFT FIELD (Name):**
```
SMS_SENDER_ID
```
**RIGHT FIELD (Value):**
```
PrimeCare
```
✅ You can keep this OR change it to your hospital name (max 11 characters)

---

### 13. SMS_API_URL
**LEFT FIELD (Name):**
```
SMS_API_URL
```
**RIGHT FIELD (Value):**
```
https://sms.smsnotifygh.com/smsapi
```

---

### 14. HOSPITAL_NAME
**LEFT FIELD (Name):**
```
HOSPITAL_NAME
```
**RIGHT FIELD (Value):**
```
PrimeCare Hospital
```
✅ You can keep this OR change to your actual hospital name

---

### 15. USE_REDIS_CACHE
**LEFT FIELD (Name):**
```
USE_REDIS_CACHE
```
**RIGHT FIELD (Value):**
```
True
```

---

### 16. DATABASE_CONN_MAX_AGE
**LEFT FIELD (Name):**
```
DATABASE_CONN_MAX_AGE
```
**RIGHT FIELD (Value):**
```
600
```

---

### 17. DATABASE_CONN_HEALTH_CHECKS
**LEFT FIELD (Name):**
```
DATABASE_CONN_HEALTH_CHECKS
```
**RIGHT FIELD (Value):**
```
True
```

---

## 🔵 OPTIONAL - Can Add Later

### 18. CORS_ALLOWED_ORIGINS (Only if you have a separate frontend)
**LEFT FIELD (Name):**
```
CORS_ALLOWED_ORIGINS
```
**RIGHT FIELD (Value):**
```
https://your-frontend-domain.com
```
⚠️ Only add this if you have a separate frontend application

---

### 19. HOSPITAL_LOGO_URL (Optional)
**LEFT FIELD (Name):**
```
HOSPITAL_LOGO_URL
```
**RIGHT FIELD (Value):**
```
https://yourdomain.com/logo.png
```
⚠️ Only add if you have a logo hosted online

---

### 20. SENTRY_DSN (Optional - for error tracking)
**LEFT FIELD (Name):**
```
SENTRY_DSN
```
**RIGHT FIELD (Value):**
```
your-sentry-dsn-from-sentry.io
```
⚠️ Only add if you're using Sentry for error tracking

---

## ❌ DO NOT ADD THESE (Auto-Generated)

Render automatically sets these - DO NOT add them manually:
- ❌ **SECRET_KEY** (auto-generated)
- ❌ **DATABASE_URL** (auto-connected from PostgreSQL)
- ❌ **REDIS_URL** (auto-connected from Redis)
- ❌ **PORT** (auto-set by Render)

---

## ✅ After Adding All Variables

1. Scroll to bottom of Environment page
2. Click **"Save Changes"** button (blue button)
3. Wait 2-3 minutes while Render redeploys
4. Check "Logs" tab to see deployment progress
5. When done, visit your app: `https://your-service-name.onrender.com/health/`

---

## 🎯 Summary: What to Change

You MUST change these values to YOUR information:

1. **ALLOWED_HOSTS** → Your Render service URL
2. **SITE_URL** → Your Render service URL with https://
3. **EMAIL_HOST_USER** → Your Gmail address
4. **EMAIL_HOST_PASSWORD** → Your Gmail App Password (get from Google)
5. **SMS_API_KEY** → Your SMS Notify GH API key (if different)

Everything else can stay as shown (or customize later).

---

## 📞 Need Help?

**Can't get Gmail App Password?**
1. Go to: https://myaccount.google.com/security
2. Enable "2-Step Verification"
3. Go to: https://myaccount.google.com/apppasswords
4. Select "Mail" and "Other"
5. Type "HMS" and click Generate
6. Copy the 16-character password

**Don't have SMS API Key?**
- Sign up at: https://sms.smsnotifygh.com/
- Get your API key from dashboard
- Replace the value above

---

**🎉 That's it! After saving, your HMS will be live on Render!**


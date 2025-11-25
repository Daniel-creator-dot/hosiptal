# 🚀 How to Import .env File to Render

**Fastest way to set all environment variables at once!**

---

## Step 1: Edit the .env.render File

1. Open the file **`.env.render`** in your project
2. Change these values to YOUR information:

### YOU MUST CHANGE:

```env
# Line 7-8: Change to your actual Render service URL
ALLOWED_HOSTS=your-service-name.onrender.com  # ← CHANGE THIS
SITE_URL=https://your-service-name.onrender.com  # ← CHANGE THIS

# Line 14-15: Change to your Gmail info
EMAIL_HOST_USER=YOUR_EMAIL@gmail.com  # ← CHANGE THIS
EMAIL_HOST_PASSWORD=YOUR_GMAIL_APP_PASSWORD  # ← CHANGE THIS
```

**How to get Gmail App Password:**
1. Go to: https://myaccount.google.com/apppasswords
2. Enable 2-Step Verification if needed
3. Select "Mail" → "Other (Custom name)" → Type "HMS"
4. Click "Generate"
5. Copy the 16-character password
6. Paste it in EMAIL_HOST_PASSWORD (remove spaces)

### YOU CAN KEEP (or change if needed):

```env
# SMS API Key - Keep this or use your own
SMS_API_KEY=84c879bb-f9f9-4666-84a8-9f70a9b238cc

# Hospital name - Change to your hospital
HOSPITAL_NAME=PrimeCare Hospital

# Everything else - Keep as is
```

3. **Save the file**

---

## Step 2: Import to Render

### Method A: Copy File Content (Recommended)

1. **Copy entire content** of `.env.render` file
2. Go to **Render Dashboard** → https://dashboard.render.com
3. Click your **`hms-web`** service
4. Click **"Environment"** in left sidebar
5. Click **"Add from .env"** button
6. **Paste** the entire content in the text box
7. Click **"Import"** or **"Add"**
8. Click **"Save Changes"** at bottom
9. Wait 2-3 minutes for redeploy

### Method B: Upload File

1. Go to **Render Dashboard** → https://dashboard.render.com
2. Click your **`hms-web`** service
3. Click **"Environment"** in left sidebar
4. Click **"Add from .env"** button
5. Click **"Upload file"** or drag-and-drop
6. Select your **`.env.render`** file
7. Click **"Import"**
8. Click **"Save Changes"** at bottom
9. Wait 2-3 minutes for redeploy

---

## Step 3: Verify Import

After importing, you should see all these variables in Render:

- ✅ DEBUG
- ✅ ALLOWED_HOSTS
- ✅ SITE_URL
- ✅ EMAIL_BACKEND
- ✅ EMAIL_HOST
- ✅ EMAIL_PORT
- ✅ EMAIL_USE_TLS
- ✅ EMAIL_HOST_USER
- ✅ EMAIL_HOST_PASSWORD
- ✅ DEFAULT_FROM_EMAIL
- ✅ SMS_API_KEY
- ✅ SMS_SENDER_ID
- ✅ SMS_API_URL
- ✅ HOSPITAL_NAME
- ✅ USE_REDIS_CACHE
- ✅ DATABASE_CONN_MAX_AGE
- ✅ DATABASE_CONN_HEALTH_CHECKS

**Total: 17 variables**

---

## Step 4: Check Deployment

1. Go to **"Logs"** tab
2. Watch for deployment to complete
3. Look for: `"Starting gunicorn..."` and `"Listening at: http://0.0.0.0:10000"`
4. Visit your app: `https://your-service-name.onrender.com/health/`
5. Should see: `{"status": "ok"}`

---

## 🎯 Quick Checklist

Before importing:

- [ ] Opened `.env.render` file
- [ ] Changed `ALLOWED_HOSTS` to my Render URL
- [ ] Changed `SITE_URL` to my Render URL with https://
- [ ] Changed `EMAIL_HOST_USER` to my Gmail
- [ ] Changed `EMAIL_HOST_PASSWORD` to my Gmail App Password
- [ ] Saved the file
- [ ] Copied entire file content

In Render Dashboard:

- [ ] Went to my service → Environment
- [ ] Clicked "Add from .env"
- [ ] Pasted content
- [ ] Clicked "Save Changes"
- [ ] Waited for redeploy

After deployment:

- [ ] Checked logs for successful deployment
- [ ] Visited /health/ endpoint
- [ ] Created superuser
- [ ] Tested login

---

## 🆘 Troubleshooting

### "File format invalid" Error

**Fix:** Make sure the file has this format:
```
VARIABLE_NAME=value
ANOTHER_VARIABLE=another_value
```

No spaces around `=`, no quotes needed.

### Variables Not Showing

**Fix:** 
1. Try Method A (copy-paste) instead of upload
2. Make sure file is saved as plain text
3. Check no special characters in file

### Deployment Failed

**Fix:**
1. Check you changed `ALLOWED_HOSTS` to your actual URL
2. Verify `EMAIL_HOST_PASSWORD` is correct App Password
3. Check logs for specific error

### Email Still Not Working

**Fix:**
1. Make sure you used Gmail App Password, not regular password
2. Test: Go to Shell → `python manage.py sendtestemail test@example.com`
3. Check EMAIL_HOST_USER has @gmail.com

---

## ✅ Success!

After importing and redeploying, your HMS should be fully configured and ready to use!

**Next steps:**
1. Create superuser: Go to Shell → `python manage.py createsuperuser`
2. Access admin: `https://your-service-name.onrender.com/admin/`
3. Test features: Create patient, send SMS, send email

---

## 📝 Notes

- **AUTO-SET**: Render automatically sets `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `PORT` - don't add these
- **Comments**: Lines starting with `#` are ignored (safe to keep)
- **Empty lines**: Ignored (safe to keep)
- **Override**: If variable already exists, import will override it

---

**🎉 Much faster than adding variables one by one!**











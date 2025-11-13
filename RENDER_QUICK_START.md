# 🚀 Render Quick Start - 5 Minutes to Production

Get your HMS live on Render in 5 minutes!

---

## ⚡ One-Click Deploy (Fastest)

### Step 1: Push to GitHub (1 minute)

```bash
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

### Step 2: Connect to Render (2 minutes)

1. Go to [dashboard.render.com](https://dashboard.render.com)
2. Click **"New"** → **"Blueprint"**
3. Connect GitHub → Select your `chm` repository
4. Click **"Apply"**

✅ **Done!** Render automatically creates:
- Web Service (Django)
- PostgreSQL Database
- Redis Cache
- Celery Workers

### Step 3: Configure Required Variables (2 minutes)

Go to `hms-web` service → Environment:

**Required (Must set these now):**

```env
ALLOWED_HOSTS=your-app-name.onrender.com
SITE_URL=https://your-app-name.onrender.com
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
SMS_API_KEY=your-sms-api-key
```

**Optional (Can set later):**

```env
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
HOSPITAL_NAME=Your Hospital Name
```

---

## 🎯 Post-Deployment (Next 5 minutes)

### 1. Create Superuser

In Render Dashboard → `hms-web` → **Shell**:

```bash
python manage.py createsuperuser
```

### 2. Verify Everything Works

Visit these URLs (replace with your actual domain):

- ✅ Health Check: `https://your-app.onrender.com/health/`
- ✅ Admin Panel: `https://your-app.onrender.com/admin/`
- ✅ HMS Dashboard: `https://your-app.onrender.com/hms/`

---

## 🎉 That's It!

Your HMS is now live and automatically deploys on every push to `main` branch!

---

## 📋 Service URLs (After Deployment)

| Service | URL |
|---------|-----|
| **Web App** | `https://hms-web.onrender.com` |
| **Admin** | `https://hms-web.onrender.com/admin/` |
| **API** | `https://hms-web.onrender.com/api/` |
| **Health** | `https://hms-web.onrender.com/health/` |

---

## 🔧 If Something Goes Wrong

### Build Fails?

1. Check **Logs** tab in Render Dashboard
2. Most common issue: Missing environment variable
3. Make sure `build.sh` is executable:
   ```bash
   git update-index --chmod=+x build.sh
   git commit -m "Make build.sh executable"
   git push
   ```

### Can't Access Admin?

1. Verify `ALLOWED_HOSTS` includes your Render domain
2. Create superuser (see step above)
3. Clear browser cache

### Database Connection Error?

1. Wait 2-3 minutes (database takes time to initialize)
2. Check `DATABASE_URL` is automatically set
3. Verify PostgreSQL service is "Live" (green)

---

## 💡 Pro Tips

### 1. Get Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification
3. Generate App Password for "Mail"
4. Use that password in `EMAIL_HOST_PASSWORD`

### 2. Keep Service Awake (Free Tier)

Free tier services sleep after 15 minutes of inactivity.

**Quick Fix**: Use [UptimeRobot](https://uptimerobot.com) (free) to ping your app every 10 minutes.

### 3. Custom Domain (Optional)

1. Render Dashboard → `hms-web` → Settings → Custom Domains
2. Add domain: `hms.yourdomain.com`
3. Add CNAME record in your DNS:
   ```
   Name: hms
   Value: hms-web.onrender.com
   ```
4. Wait 10-30 minutes for SSL certificate

---

## 📊 What Was Created?

Your `render.yaml` automatically set up:

| Resource | Type | Description |
|----------|------|-------------|
| `hms-web` | Web Service | Django application |
| `hms-db` | PostgreSQL | Database (1GB free) |
| `hms-redis` | Redis | Cache (25MB free) |
| `hms-celery-worker` | Worker | Background tasks |
| `hms-celery-beat` | Worker | Scheduled tasks |

---

## 🆓 Free Tier Limits

| Resource | Free Tier | Upgrade Cost |
|----------|-----------|--------------|
| Web Service | 750 hrs/month, sleeps after 15 min | $7/month for 24/7 |
| PostgreSQL | 1GB, expires in 90 days | $7/month persistent |
| Redis | 25MB | $7/month for 100MB |
| Bandwidth | 100GB/month | Included in upgrades |

**Total for Production**: ~$21/month (all services upgraded)

---

## 🔄 Auto-Deploy

Already configured! Every push to `main` automatically deploys:

```bash
git add .
git commit -m "Update feature"
git push
# Render automatically deploys! 🚀
```

Watch deployment in Render Dashboard → Logs.

---

## ✅ Final Checklist

Before sharing with users:

- [ ] Superuser created
- [ ] Email sending works (test it!)
- [ ] SMS sending works (test it!)
- [ ] Admin panel accessible
- [ ] All pages load without errors
- [ ] SSL certificate active (🔒 in browser)
- [ ] Custom domain configured (optional)

---

## 📖 Need More Details?

See `RENDER_DEPLOYMENT_GUIDE.md` for:
- Advanced configuration
- Troubleshooting
- Performance optimization
- Monitoring setup
- Security hardening

---

## 🆘 Quick Help

**Deployment failed?**
```bash
# Check logs in Render Dashboard
# Common fixes:
git update-index --chmod=+x build.sh
pip freeze > requirements.txt
git commit -am "Fix dependencies"
git push
```

**Environment variable missing?**
- Go to service → Environment → Add variable
- Click "Save Changes"
- Wait for automatic redeploy

**Need to run commands?**
- Go to service → Shell
- Run any Django management command

---

## 🎓 What's Next?

After successful deployment:

1. ✅ Configure monitoring (Sentry)
2. ✅ Set up database backups
3. ✅ Add team members in Render
4. ✅ Review security settings
5. ✅ Load test with real data

---

**🎊 Congratulations!** You're now live on Render!

Your app auto-deploys on every GitHub push. No servers to manage, no DevOps headaches!

---

**Questions?** Check `RENDER_DEPLOYMENT_GUIDE.md` or Render's [documentation](https://render.com/docs).

---

*Setup Time: ~5 minutes | Full Production Setup: ~15 minutes*


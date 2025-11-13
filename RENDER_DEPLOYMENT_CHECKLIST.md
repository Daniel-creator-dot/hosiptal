# ✅ Render Deployment Checklist

Use this checklist to ensure smooth deployment to Render.

---

## 📦 Pre-Deployment Preparation

### Code Repository

- [ ] All code committed to Git
- [ ] Code pushed to GitHub `main` branch
- [ ] Repository is public or Render has access
- [ ] All deployment files present:
  - [ ] `render.yaml`
  - [ ] `build.sh`
  - [ ] `Dockerfile`
  - [ ] `requirements.txt`
  - [ ] `env.render.example`
  - [ ] `.renderignore`

### Credentials Ready

- [ ] **Email SMTP Credentials**
  - [ ] SMTP host (e.g., smtp.gmail.com)
  - [ ] Email address
  - [ ] App-specific password (for Gmail)
  
- [ ] **SMS API Credentials**
  - [ ] SMS Notify GH API key
  - [ ] SMS sender ID
  
- [ ] **Optional Services**
  - [ ] Twilio WhatsApp credentials
  - [ ] Sentry DSN for error tracking
  - [ ] Domain name for custom domain

### Settings Review

- [ ] `settings.py` uses environment variables
- [ ] `SECRET_KEY` from env (not hardcoded)
- [ ] `DEBUG` from env (set to False in production)
- [ ] `ALLOWED_HOSTS` from env
- [ ] `DATABASE_URL` configured with `dj_database_url`
- [ ] Static files configured with WhiteNoise
- [ ] Security settings enabled for production

---

## 🚀 Deployment Steps

### 1. Create Render Account

- [ ] Sign up at [render.com](https://render.com)
- [ ] Verify email address
- [ ] Connect GitHub account

### 2. Deploy Blueprint

- [ ] Go to Render Dashboard
- [ ] Click "New" → "Blueprint"
- [ ] Select your HMS repository
- [ ] Review services to be created:
  - [ ] Web service (`hms-web`)
  - [ ] PostgreSQL (`hms-db`)
  - [ ] Redis (`hms-redis`)
  - [ ] Celery worker
  - [ ] Celery beat
- [ ] Click "Apply"

### 3. Monitor Initial Build

- [ ] Watch build logs for `hms-web`
- [ ] Verify build completes successfully
- [ ] Check all services show green status
- [ ] Note the service URL (e.g., `https://hms-web.onrender.com`)

---

## ⚙️ Configuration

### 4. Set Environment Variables

Go to `hms-web` → Environment, add these variables:

#### Required Variables

- [ ] `ALLOWED_HOSTS` = `your-app.onrender.com`
- [ ] `SITE_URL` = `https://your-app.onrender.com`
- [ ] `EMAIL_HOST` = `smtp.gmail.com` (or your SMTP server)
- [ ] `EMAIL_HOST_USER` = `your-email@gmail.com`
- [ ] `EMAIL_HOST_PASSWORD` = `your-app-password`
- [ ] `EMAIL_PORT` = `587`
- [ ] `EMAIL_USE_TLS` = `True`
- [ ] `DEFAULT_FROM_EMAIL` = `noreply@yourdomain.com`
- [ ] `SMS_API_KEY` = `your-sms-api-key`
- [ ] `SMS_SENDER_ID` = `PrimeCare` (or your sender ID)

#### Optional Variables

- [ ] `CORS_ALLOWED_ORIGINS` = `https://your-frontend.com`
- [ ] `HOSPITAL_NAME` = `Your Hospital Name`
- [ ] `HOSPITAL_LOGO_URL` = `https://...`
- [ ] `SENTRY_DSN` = `https://...` (for error tracking)
- [ ] `TWILIO_ACCOUNT_SID` = `...` (for WhatsApp)
- [ ] `TWILIO_AUTH_TOKEN` = `...` (for WhatsApp)

**Note**: These are auto-set by Render (don't change):
- `SECRET_KEY` (auto-generated)
- `DATABASE_URL` (from PostgreSQL service)
- `REDIS_URL` (from Redis service)
- `PORT` (set by Render)

### 5. Save and Redeploy

- [ ] Click "Save Changes"
- [ ] Wait for automatic redeploy
- [ ] Monitor logs for successful restart

---

## 👤 Post-Deployment Setup

### 6. Create Superuser

- [ ] Go to `hms-web` → Shell
- [ ] Run: `python manage.py createsuperuser`
- [ ] Enter username, email, and password
- [ ] Verify creation successful

### 7. Run Database Setup

- [ ] Check migrations: `python manage.py showmigrations`
- [ ] Run if needed: `python manage.py migrate`
- [ ] Create cache table: `python manage.py createcachetable`

---

## 🧪 Testing & Verification

### 8. Basic Functionality Tests

#### Health Check
- [ ] Visit: `https://your-app.onrender.com/health/`
- [ ] Should see: `{"status": "ok"}`

#### Admin Panel
- [ ] Visit: `https://your-app.onrender.com/admin/`
- [ ] Login with superuser credentials
- [ ] Verify admin dashboard loads
- [ ] Check static files load correctly

#### HMS Dashboard
- [ ] Visit: `https://your-app.onrender.com/hms/`
- [ ] Verify login page appears
- [ ] Test login functionality
- [ ] Navigate through main pages

### 9. Integration Tests

#### Email
- [ ] Send test email from admin
- [ ] Or run: `python manage.py sendtestemail test@example.com`
- [ ] Verify email received

#### SMS
- [ ] Test SMS notification
- [ ] Verify SMS received
- [ ] Check SMS logs

#### Database
- [ ] Create test patient record
- [ ] Verify data persists
- [ ] Test database queries

#### Background Tasks
- [ ] Verify Celery worker is running
- [ ] Check Celery beat scheduler
- [ ] Test background task execution

### 10. Performance Tests

- [ ] Page load times under 3 seconds
- [ ] Static files load quickly
- [ ] No console errors in browser
- [ ] No 500 errors in logs
- [ ] Database queries optimized

---

## 🔐 Security Verification

### 11. Security Checks

- [ ] HTTPS/SSL active (🔒 in browser)
- [ ] No mixed content warnings
- [ ] CORS configured correctly
- [ ] CSRF protection working
- [ ] Admin requires authentication
- [ ] No sensitive data in logs
- [ ] Environment variables not exposed
- [ ] Debug mode is OFF (`DEBUG=False`)

### 12. Security Headers

Check headers at [securityheaders.com](https://securityheaders.com):

- [ ] `Strict-Transport-Security` present
- [ ] `X-Frame-Options` set
- [ ] `X-Content-Type-Options` set
- [ ] `X-XSS-Protection` enabled
- [ ] `Content-Security-Policy` configured

---

## 📊 Monitoring Setup

### 13. Enable Monitoring

- [ ] Set up error tracking (Sentry)
- [ ] Configure log alerts
- [ ] Set up uptime monitoring
- [ ] Enable application metrics

### 14. Backup Configuration

- [ ] Verify database backup schedule
- [ ] Test database restore process
- [ ] Document backup procedures
- [ ] Set up backup notifications

---

## 🌐 Domain Configuration (Optional)

### 15. Custom Domain Setup

- [ ] Go to `hms-web` → Settings → Custom Domains
- [ ] Add custom domain
- [ ] Add DNS records at domain registrar:
  ```
  Type: CNAME
  Name: hms (or www)
  Value: hms-web.onrender.com
  TTL: 3600
  ```
- [ ] Wait for DNS propagation (5-30 minutes)
- [ ] Verify SSL certificate provisioned
- [ ] Update `ALLOWED_HOSTS` with new domain
- [ ] Update `SITE_URL` with new domain
- [ ] Update `CORS_ALLOWED_ORIGINS` if needed

---

## 📱 User Acceptance Testing

### 16. Core Features Testing

#### Patient Management
- [ ] Register new patient
- [ ] Search for patient
- [ ] Update patient information
- [ ] View patient history

#### Appointments
- [ ] Book appointment
- [ ] Cancel appointment
- [ ] Send appointment reminders
- [ ] View appointment calendar

#### Laboratory
- [ ] Create lab order
- [ ] Record lab results
- [ ] Print lab report
- [ ] Send results notification

#### Pharmacy
- [ ] Dispense medication
- [ ] Check drug stock
- [ ] Generate prescription
- [ ] Track medication history

#### Billing
- [ ] Create invoice
- [ ] Process payment
- [ ] Generate receipt
- [ ] View financial reports

#### Accounting
- [ ] Record transaction
- [ ] View balance sheet
- [ ] Generate financial reports
- [ ] Track revenue streams

---

## 📈 Performance Optimization

### 17. Optimize for Production

- [ ] Enable Redis caching (`USE_REDIS_CACHE=True`)
- [ ] Configure database connection pooling
- [ ] Optimize slow database queries
- [ ] Enable static file compression
- [ ] Set up CDN (optional)
- [ ] Configure query caching

### 18. Scale Resources (If Needed)

- [ ] Upgrade web service plan (if slow)
- [ ] Increase worker concurrency
- [ ] Add more Redis memory
- [ ] Expand database storage
- [ ] Enable auto-scaling (paid plans)

---

## 📚 Documentation

### 19. Team Documentation

- [ ] Document deployment process
- [ ] Create admin user guide
- [ ] Document environment variables
- [ ] Write troubleshooting guide
- [ ] Create backup/restore procedures

### 20. User Training

- [ ] Train staff on production system
- [ ] Provide user manuals
- [ ] Create video tutorials
- [ ] Set up support channels

---

## 🎯 Go-Live Preparation

### 21. Final Checks Before Go-Live

- [ ] All tests passing
- [ ] All integrations working
- [ ] Monitoring active
- [ ] Backups configured
- [ ] Team trained
- [ ] Support plan ready
- [ ] Rollback plan documented
- [ ] Communication plan ready

### 22. Go-Live

- [ ] Announce maintenance window (if migrating)
- [ ] Migrate production data (if applicable)
- [ ] Update DNS to point to Render
- [ ] Monitor application closely
- [ ] Verify all functionality
- [ ] Communicate go-live to users

---

## 🔄 Post-Go-Live

### 23. Monitor First 24 Hours

- [ ] Check error logs every 2 hours
- [ ] Monitor user feedback
- [ ] Watch performance metrics
- [ ] Verify backup completion
- [ ] Check email/SMS delivery
- [ ] Monitor database performance

### 24. First Week Tasks

- [ ] Daily log review
- [ ] User feedback collection
- [ ] Performance optimization
- [ ] Bug fixes as needed
- [ ] Documentation updates

---

## 💰 Cost Management

### 25. Review and Optimize Costs

- [ ] Review current resource usage
- [ ] Identify unused services
- [ ] Optimize database queries
- [ ] Review plan requirements
- [ ] Set up billing alerts
- [ ] Plan for scaling needs

---

## 🎓 Maintenance Plan

### 26. Ongoing Maintenance

#### Daily
- [ ] Check error logs
- [ ] Monitor uptime
- [ ] Verify backups

#### Weekly
- [ ] Review performance metrics
- [ ] Check security logs
- [ ] Update documentation

#### Monthly
- [ ] Update dependencies
- [ ] Review and optimize costs
- [ ] Security audit
- [ ] Performance review
- [ ] Backup testing

---

## ✅ Deployment Complete!

**Congratulations!** When all items are checked, your HMS is successfully deployed on Render!

### Key URLs to Bookmark

- 🌐 Application: `https://your-app.onrender.com`
- 🔧 Admin Panel: `https://your-app.onrender.com/admin/`
- 📊 Render Dashboard: `https://dashboard.render.com`
- 📝 Documentation: See `RENDER_DEPLOYMENT_GUIDE.md`

### Next Steps

1. Monitor application performance
2. Collect user feedback
3. Plan feature updates
4. Regular maintenance
5. Scale as needed

---

## 🆘 Need Help?

- 📖 See `RENDER_DEPLOYMENT_GUIDE.md` for detailed help
- 📖 See `RENDER_QUICK_START.md` for quick reference
- 🌐 Visit [Render Documentation](https://render.com/docs)
- 💬 Join [Render Community](https://community.render.com)

---

**Deployment Date**: _____________  
**Deployed By**: _____________  
**Production URL**: _____________  
**Superuser Email**: _____________  

---

*Print this checklist and check off items as you complete them!*


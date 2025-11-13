# Testing Your HMS URLs

## ✅ Working URLs (after login)

1. **Dashboard**: http://localhost:8000/hms/
2. **Patients List**: http://localhost:8000/hms/patients/
3. **Encounters**: http://localhost:8000/hms/encounters/
4. **Admissions**: http://localhost:8000/hms/admissions/
5. **Invoices**: http://localhost:8000/hms/invoices/

## 🔐 Login First!

Before accessing any HMS pages, you need to login:

**Admin Login**: http://localhost:8000/admin/login/

- Username: `admin`
- Password: `admin123`

After logging in, you'll be automatically redirected to the dashboard at `/hms/`.

## How It Works

1. Access any protected URL (e.g., `/hms/patients/`)
2. Django redirects to `/admin/login/?next=/hms/patients/`
3. Login with admin credentials
4. You're automatically redirected back to the page you originally requested

## If You Still Get 404

1. Clear your browser cache
2. Make sure you're logged in at `/admin/login/` first
3. Try accessing the dashboard directly: http://localhost:8000/hms/

## Quick Test

```
1. Go to: http://localhost:8000/admin/login/
2. Login with: admin / admin123
3. Then go to: http://localhost:8000/hms/
```


# Server Restart and Cache Clearing Guide

## Quick Commands

### Clear All Caches
```bash
python manage.py clear_all_caches
```

### Fix Server Errors
```bash
python manage.py fix_server_errors
```

### Restart Server (Windows)
```bash
restart_server.bat
```

### Restart Server (Linux/Mac)
```bash
chmod +x restart_server.sh
./restart_server.sh
```

## Complete Server Restart Process

### 1. Clear All Caches
```bash
python manage.py clear_all_caches
```
This clears:
- Django default cache
- Session cache
- Redis cache (if available)
- Static files

### 2. Check for Errors
```bash
python manage.py fix_server_errors
```
This checks:
- Database connection
- Cache connection
- Pending migrations
- Settings validation
- Static files configuration

### 3. Restart the Server

#### For Local Development:
```bash
python manage.py runserver
```

#### For Docker:
```bash
docker-compose restart web
docker-compose restart redis  # Optional: restart Redis too
```

#### For Production (Gunicorn):
```bash
# Stop
pkill -f gunicorn

# Start
gunicorn hms.wsgi:application --bind 0.0.0.0:8000
```

## Troubleshooting

### Server Misbehaving?

1. **Clear all caches:**
   ```bash
   python manage.py clear_all_caches
   ```

2. **Check for errors:**
   ```bash
   python manage.py fix_server_errors
   ```

3. **Run migrations (if needed):**
   ```bash
   python manage.py migrate
   ```

4. **Collect static files:**
   ```bash
   python manage.py collectstatic --noinput
   ```

5. **Restart the server**

### Cache Issues?

- **Clear Django cache only:**
  ```bash
  python manage.py clear_all_caches --django-only
  ```

- **Clear Redis only:**
  ```bash
  python manage.py clear_all_caches --redis-only
  ```

- **Clear static files only:**
  ```bash
  python manage.py clear_all_caches --static-only
  ```

### Database Connection Issues?

1. Check database is running
2. Verify DATABASE_URL in settings
3. Test connection:
   ```bash
   python manage.py dbshell
   ```

### Redis Connection Issues?

1. Check Redis is running
2. Verify REDIS_URL in settings
3. Test connection:
   ```bash
   redis-cli ping
   ```

## All Fixed Issues

✅ **Queue NameError** - Fixed in `views_role_specific.py`
✅ **Optional model imports** - All dashboard views now use safe imports
✅ **Cache clearing** - Management command created
✅ **Server diagnostics** - Error checking command created
✅ **Restart scripts** - Created for Windows and Linux/Mac

## Next Steps After Restart

1. Test the medical dashboard: `/hms/medical-dashboard/`
2. Check other role dashboards
3. Verify cache is working
4. Monitor server logs for any new errors





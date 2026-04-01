# Fix Passwords Not Working

## Issue
Passwords are not working for user login.

## Solution

### Step 1: Reset All Passwords
Run this command to reset all user passwords to a default password:

```bash
docker-compose exec web python manage.py reset_all_passwords --password admin123
```

This will:
- Reset all user passwords to `admin123`
- Use Django's `set_password()` which properly hashes passwords
- Save users with hashed passwords

### Step 2: Fix Login Issues
Run this command to fix any login-related issues:

```bash
docker-compose exec web python manage.py fix_all_logins --create-superuser
```

This will:
- Activate all inactive users
- Unlock all locked accounts
- Reset failed login attempts
- Create superuser if needed

### Step 3: Test Login
1. Go to `/hms/login/`
2. Try logging in with:
   - Username: `admin` (or any username)
   - Password: `admin123`

### Step 4: Reset Specific User Password
To reset password for a specific user:

```bash
docker-compose exec web python manage.py reset_all_passwords --username admin --password newpassword123
```

## Default Credentials After Reset

- **Username:** `admin` (or your username)
- **Password:** `admin123` (or the password you set)

⚠️ **IMPORTANT:** Change passwords after first login!

## If Passwords Still Don't Work

1. **Check password hash format:**
   ```bash
   docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); u = User.objects.first(); print('Password hash:', u.password[:50] if u else 'No user')"
   ```
   - Should start with `pbkdf2_sha256$` or similar
   - If it's plain text, passwords weren't hashed correctly

2. **Check authentication backend:**
   - Settings should have `EmailOrUsernameModelBackend` in `AUTHENTICATION_BACKENDS`
   - Check `hms/settings.py` line 579-584

3. **Check user is active:**
   ```bash
   docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); u = User.objects.first(); print('Is active:', u.is_active if u else 'No user')"
   ```

4. **Check login attempts:**
   - Account might be locked due to failed attempts
   - Run `fix_all_logins` to unlock

## Commands Summary

```bash
# Reset all passwords
docker-compose exec web python manage.py reset_all_passwords --password admin123

# Fix login issues
docker-compose exec web python manage.py fix_all_logins --create-superuser

# Reset specific user
docker-compose exec web python manage.py reset_all_passwords --username admin --password newpassword123
```







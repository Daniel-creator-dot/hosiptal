# 🐳 Docker Update - Accounting Fixes

**Date:** January 13, 2026  
**Purpose:** Update Docker Desktop with all accounting fixes

---

## 📋 Changes Included

### 1. Trial Balance Fix
- ✅ Revenue accounts now display in **Credit column** (not Debit)
- ✅ Balance calculation corrected for revenue accounts
- ✅ Template variables fixed (`accounts`, `as_of_date`, `balance_difference`)

### 2. Revenue Duplicate Prevention
- ✅ Enhanced `accounting_sync_service.py` to check for existing entries
- ✅ Prevents duplicate GL entries for same payment receipt
- ✅ Improved logging for duplicate detection

### 3. Insurance Receivables Verification
- ✅ Account 1201 verified and confirmed correct
- ✅ No duplicate entries found
- ✅ Account ready for use

### 4. Enhanced Duplicate Detection
- ✅ Updated `fix_accounting_duplicates` management command
- ✅ Detects duplicates by reference number, account, and amount
- ✅ Keeps oldest entry, removes newer duplicates

---

## 🚀 How to Update

### Option 1: Use the Batch Script (Windows)
```batch
UPDATE_DOCKER_ACCOUNTING_FIXES.bat
```

### Option 2: Manual Update
```bash
# 1. Stop containers
docker-compose down

# 2. Rebuild with latest code
docker-compose build --no-cache web celery celery-beat

# 3. Start database
docker-compose up -d db redis

# 4. Run migrations
docker-compose run --rm web python manage.py migrate --noinput

# 5. Collect static files
docker-compose run --rm web python manage.py collectstatic --no-input --clear

# 6. Start all services
docker-compose up -d
```

---

## ✅ Verification Steps

After updating, verify:

1. **Trial Balance Display**
   - Navigate to: `http://localhost:8000/hms/accounting/trial-balance/`
   - Check that revenue accounts show in **Credit column**
   - Verify totals balance correctly

2. **Revenue Accounts**
   - Revenue accounts should show positive balances in Credit column
   - No revenue accounts should appear in Debit column (unless negative)

3. **Insurance Receivables**
   - Account 1201 should show zero balance (if no entries)
   - Account should appear correctly in trial balance

4. **Service Status**
   ```bash
   docker-compose ps
   ```
   All services should show as "Up"

---

## 📝 Files Changed

- `hospital/views_accounting.py` - Trial balance calculation fix
- `hospital/services/accounting_sync_service.py` - Duplicate prevention
- `hospital/management/commands/fix_accounting_duplicates.py` - Enhanced duplicate detection

---

## 🔍 Troubleshooting

### If services don't start:
```bash
# Check logs
docker-compose logs web
docker-compose logs celery

# Restart specific service
docker-compose restart web
```

### If database connection fails:
```bash
# Check database status
docker-compose ps db

# Check database logs
docker-compose logs db
```

### If static files aren't updating:
```bash
# Force collect static files
docker-compose run --rm web python manage.py collectstatic --no-input --clear
```

---

## 📊 Expected Results

After update:
- ✅ Trial balance shows revenue in Credit column
- ✅ No duplicate revenue entries
- ✅ Insurance receivables account verified
- ✅ All accounting calculations correct
- ✅ Services running smoothly

---

**Status:** ✅ Ready to Deploy

# Quick Fix for Duplicates - Instructions

## Problem
The duplicate removal script needs the database to be running. 

## Solution Options

### Option 1: Start Docker Database (Recommended)

1. **Start Docker Desktop** (if not already running)

2. **Start the database:**
   ```bash
   docker-compose up -d db
   ```

3. **Wait 10 seconds** for database to be ready

4. **Run duplicate fix:**
   ```bash
   python manage.py remove_all_duplicates --dry-run
   python manage.py remove_all_duplicates
   ```

   OR use the batch file:
   ```bash
   START_DATABASE_AND_FIX_DUPLICATES.bat
   ```

### Option 2: Use Docker Container

If you're running the app in Docker:

```bash
# Check for duplicates
docker-compose exec web python manage.py remove_all_duplicates --dry-run

# Remove duplicates
docker-compose exec web python manage.py remove_all_duplicates
```

### Option 3: Manual Database Start

If Docker isn't available, ensure PostgreSQL is running locally:

1. **Start PostgreSQL service** (Windows):
   ```powershell
   net start postgresql-x64-15
   ```
   (Adjust version number as needed)

2. **Verify connection:**
   ```bash
   python manage.py dbshell
   ```

3. **Run duplicate fix:**
   ```bash
   python manage.py remove_all_duplicates --dry-run
   python manage.py remove_all_duplicates
   ```

## What the Script Does

1. **Finds duplicates by:**
   - MRN (Medical Record Number)
   - Name + Phone Number
   - Email address
   - National ID
   - Staff by user/employee_id
   - Encounters by patient+time+type

2. **Removes duplicates by:**
   - Keeping the oldest record (first created)
   - Merging related data (encounters, invoices, etc.) to primary
   - Soft-deleting duplicates (sets `is_deleted=True`)

3. **Protects data:**
   - All data is preserved
   - Related records are moved to primary
   - Can be undone if needed

## After Running

The system now has **6 layers of duplicate protection**:
1. ✅ JavaScript - Prevents double-submission
2. ✅ Form Validation - Checks before submission  
3. ✅ View Validation - Transaction-based checks
4. ✅ API Validation - Serializer checks
5. ✅ Model Save - Final safety net
6. ✅ Database Constraints - Unique constraints

**No more duplicates will be created!** 🎉







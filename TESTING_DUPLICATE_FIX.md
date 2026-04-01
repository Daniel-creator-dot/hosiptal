# Testing Guide: Duplicate Patient Creation Fix

## How to Test if Duplicates Are Fixed

### Test 1: Basic Registration
1. Go to: `/hms/patients/new/`
2. Fill out form with:
   - First Name: `Test`
   - Last Name: `Patient`
   - Phone: `0241234567`
   - Email: `test@example.com`
3. Click "Register Patient"
4. **Expected:** Only ONE patient created
5. **Check:** Patient list should show only one entry

### Test 2: Duplicate Prevention
1. Register a patient (same as Test 1)
2. Try to register the SAME patient again (same name + phone)
3. **Expected:** Error message: "Duplicate patient detected!"
4. **Check:** Patient list should still show only one entry

### Test 3: Browser Refresh Protection
1. Register a patient
2. **DO NOT** click any link
3. Press F5 or refresh browser
4. **Expected:** Browser should ask "Resubmit form?" - Click Cancel
5. **If you click OK:** Should redirect without creating duplicate (303 redirect)

### Test 4: Double-Click Protection
1. Fill out patient form
2. Rapidly double-click "Register Patient" button
3. **Expected:** Button disabled after first click, only ONE patient created

### Test 5: Network Tab Verification
1. Open browser DevTools (F12)
2. Go to Network tab
3. Register a patient
4. **Expected:** Only ONE POST request to `/patients/new/` or `/patient-registration/`
5. **If you see TWO:** There's a JavaScript issue causing double submission

### Test 6: Database Constraint Verification
1. Try to insert duplicate directly in database:
   ```sql
   INSERT INTO hospital_patient (first_name, last_name, phone_number, ...)
   VALUES ('Test', 'Patient', '0241234567', ...);
   ```
2. **Expected:** Database error: "duplicate key value violates unique constraint"

### Test 7: Log Verification
1. Check Django logs after registration
2. **Expected:** See only ONE log entry: "About to save patient: ..."
3. **If you see TWO:** Form is being submitted twice

## Debugging if Duplicates Still Occur

### Step 1: Check Logs
```bash
docker-compose logs web | grep "About to save patient"
```
- Should see only ONE entry per registration
- If you see multiple, form is being submitted multiple times

### Step 2: Check Network Requests
1. Open DevTools → Network tab
2. Filter by "patient"
3. Register a patient
4. Count POST requests
5. **Should be only ONE**

### Step 3: Check Session Token
1. Check browser console for: "Form submitting with token: ..."
2. Each submission should have a UNIQUE token
3. If same token appears twice, session management is broken

### Step 4: Check Database Constraints
```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'hospital_patient' 
AND indexname LIKE '%unique%';
```
- Should show 2 unique indexes
- If missing, run: `python manage.py add_patient_unique_constraint`

### Step 5: Check for Multiple Form Submissions
1. Check if auto-save is triggering:
   - Look for requests with `auto_save=true` in Network tab
   - Should be NONE for patient registration
2. Check if JavaScript is submitting twice:
   - Look for multiple `form.submit()` calls in console
   - Should be only ONE

## Common Issues and Solutions

### Issue: Duplicates Still Created
**Possible Causes:**
1. Form submitted multiple times (check Network tab)
2. Auto-save still triggering (check for `auto_save=true` requests)
3. Database constraints not matching (check phone normalization)
4. Race condition (should be fixed with `select_for_update()`)

**Solution:**
- Check logs for "About to save patient" count
- Check Network tab for POST request count
- Verify database constraints exist

### Issue: False Duplicate Errors
**Possible Causes:**
1. Phone number normalization mismatch
2. Case sensitivity in name matching
3. Existing patient with similar data

**Solution:**
- Check exact phone number format
- Check if existing patient has same name+phone
- Use "Proceed with duplicate" if it's a different person

### Issue: Database Constraint Errors
**Possible Causes:**
1. Constraint too strict
2. Phone number format inconsistency
3. Email case sensitivity

**Solution:**
- Check constraint definition
- Verify phone normalization logic
- Check email case handling

## Verification Commands

### Check for Existing Duplicates
```bash
docker-compose exec web python manage.py remove_all_duplicates --dry-run
```

### Check Database Constraints
```bash
docker-compose exec db psql -U hms_user -d hms_db -c "SELECT indexname FROM pg_indexes WHERE tablename = 'hospital_patient' AND indexname LIKE '%unique%';"
```

### Check Recent Patient Creations
```bash
docker-compose exec db psql -U hms_user -d hms_db -c "SELECT mrn, first_name, last_name, phone_number, created_at FROM hospital_patient WHERE is_deleted = false ORDER BY created_at DESC LIMIT 10;"
```

## Success Criteria

✅ **All tests pass:**
- Only ONE patient created per registration
- Duplicate attempts are blocked
- Browser refresh doesn't create duplicates
- Double-click doesn't create duplicates
- Network tab shows only ONE POST request
- Logs show only ONE "About to save patient" entry

---

**If all tests pass, duplicates are FIXED!** 🎉







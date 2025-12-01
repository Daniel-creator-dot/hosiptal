# 🧪 Test Duplicate Prevention - Step by Step

## ✅ Server Status
The local server should be running at: **http://localhost:8000**

## 🎯 Test Steps

### Step 1: Open Patient Registration
1. Open your browser
2. Go to: **http://localhost:8000/hms/patients/new/**
3. Login if required

### Step 2: Register First Patient
Fill in the form with:
- **First Name:** `Test`
- **Last Name:** `Duplicate`
- **Date of Birth:** `1990-01-01`
- **Phone Number:** `0241234567`
- **Email:** `test.duplicate@example.com`
- **Gender:** `Male`

Click **"Register Patient"**

**Expected Result:**
- ✅ Success message appears
- ✅ Patient is created
- ✅ You are redirected to record vitals page
- ✅ Note the MRN (e.g., PMC2025000123)

### Step 3: Try to Register Same Patient Again
1. Go back to: **http://localhost:8000/hms/patients/new/**
2. Fill in the **EXACT SAME** information:
   - **First Name:** `Test`
   - **Last Name:** `Duplicate`
   - **Date of Birth:** `1990-01-01`
   - **Phone Number:** `0241234567`
   - **Email:** `test.duplicate@example.com`
   - **Gender:** `Male`

3. Click **"Register Patient"** again

**Expected Result:**
- ❌ **Error message appears:** "⚠️ Duplicate patient detected!"
- ❌ **Form does NOT submit**
- ❌ **No second patient is created**

### Step 4: Verify in Patient List
1. Go to: **http://localhost:8000/hms/patients/**
2. Search for "Test Duplicate"
3. **Should find only ONE patient**

## ✅ Success Criteria

### What Should Happen:
1. ✅ First registration succeeds
2. ✅ Second registration shows duplicate error
3. ✅ Only ONE patient exists in database
4. ✅ Error message is clear and visible

### What Should NOT Happen:
1. ❌ Second patient is created
2. ❌ No error message shown
3. ❌ Two patients with same name/phone
4. ❌ Form submits without validation

## 🔍 Additional Tests

### Test 1: Different Phone Format
1. Register: `0241234567`
2. Try again with: `+233241234567`
3. **Should detect as duplicate** (phone normalization)

### Test 2: Double-Click Prevention
1. Fill out form
2. Rapidly click "Register Patient" multiple times
3. **Should only create ONE patient**
4. Button should disable after first click

### Test 3: Browser Refresh
1. Register patient successfully
2. Press F5 to refresh
3. **Should NOT resubmit form**
4. Should redirect or show success page

## 🐛 If Duplicates Still Occur

### Check These:
1. **Server logs** - Look for duplicate detection messages
2. **Browser console** - Check for JavaScript errors (F12)
3. **Database** - Check if two patients were actually created
4. **Network tab** - See if form is submitted multiple times

### Debug Commands:
```bash
# Check for duplicates in database
python manage.py shell
>>> from hospital.models import Patient
>>> Patient.objects.filter(first_name='Test', last_name='Duplicate', is_deleted=False).count()
# Should return 1, not 2
```

## 📊 Test Results

After testing, document:
- [ ] First registration: ✅ Success / ❌ Failed
- [ ] Second registration: ✅ Blocked / ❌ Created duplicate
- [ ] Error message: ✅ Shown / ❌ Not shown
- [ ] Patient count: ✅ One / ❌ Two

## 🎉 Expected Outcome

**If everything works:**
- Only ONE patient should be created
- Duplicate error should appear on second attempt
- System should prevent duplicates at multiple levels

---

**Ready to test?** Go to: http://localhost:8000/hms/patients/new/


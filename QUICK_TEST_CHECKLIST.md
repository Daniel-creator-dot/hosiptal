# ✅ Quick Test Checklist - Front Desk Payer Selection

## 🧪 Pre-Test Checks

### 1. Code Verification
- [x] `hospital/forms.py` - Added payer_type, corporate, cash fields
- [x] `hospital/views.py` - Added payer type handling logic
- [x] `hospital/templates/hospital/patient_form.html` - Added JavaScript
- [x] `hospital/services/insurance_exclusion_service.py` - Cash protection

### 2. Run Test Script
```bash
TEST_PAYER_SELECTION.bat
```

---

## 🎯 Browser Test Steps

### Step 1: Start Server
```bash
python manage.py runserver
```

### Step 2: Navigate to Registration
- URL: `http://127.0.0.1:8000/hms/patients/create/`
- Or click "Register Patient" from reception dashboard

### Step 3: Visual Check
Look for new section:
- **"💳 Payment Type & Billing Information"**
- **"Payment Type"** dropdown with options:
  - Select Payment Type...
  - Insurance
  - Corporate
  - Cash

### Step 4: Test Insurance Selection
1. Select "Insurance" from dropdown
2. ✅ Should see:
   - Insurance Company dropdown
   - Insurance Plan dropdown
   - Insurance ID field
   - Insurance Member ID field
   - Manual entry fields

### Step 5: Test Corporate Selection
1. Select "Corporate" from dropdown
2. ✅ Should see:
   - Corporate Company dropdown
   - Employee ID field
3. ✅ Insurance fields should be hidden

### Step 6: Test Cash Selection
1. Select "Cash" from dropdown
2. ✅ Should see:
   - Receiving Point field
3. ✅ Other fields should be hidden

### Step 7: Test Form Submission
1. Fill in patient details
2. Select a payment type and fill relevant fields
3. Submit form
4. ✅ Check success message mentions payer type
5. ✅ Verify patient record has correct payer set

---

## 🔍 Debug Checklist

### If Payment Type dropdown doesn't appear:
- [ ] Check browser console (F12) for errors
- [ ] Verify server restarted after changes
- [ ] Hard refresh: `Ctrl+Shift+R`
- [ ] Check HTML source for `id="id_payer_type"`

### If fields don't show/hide:
- [ ] Check JavaScript console for errors
- [ ] Verify `togglePayerFields()` function exists
- [ ] Check div IDs: `insurance_fields`, `corporate_fields`, `cash_fields`
- [ ] Verify JavaScript runs on page load

### If form submission fails:
- [ ] Check Django server logs
- [ ] Verify all required fields filled
- [ ] Check for validation errors
- [ ] Verify database models exist (CorporateAccount, etc.)

---

## 📊 Expected Results

### Insurance Patient:
- Creates `PatientInsurance` enrollment
- Links to insurance `Payer`
- Sets `patient.primary_insurance` to insurance payer
- Stores insurance ID and member ID

### Corporate Patient:
- Creates `CorporateEmployee` enrollment
- Links to corporate `Payer`
- Sets `patient.primary_insurance` to corporate payer
- Stores employee ID

### Cash Patient:
- Links to Cash `Payer`
- Sets `patient.primary_insurance` to cash payer
- Stores receiving point in patient notes

---

## ✅ Success Criteria

- [ ] Payment Type dropdown visible
- [ ] Fields show/hide correctly based on selection
- [ ] Form submits successfully for all three types
- [ ] Patient records have correct payer set
- [ ] No JavaScript errors in console
- [ ] No Django errors in server logs

---

## 🐛 Common Issues & Fixes

### Issue: "ModuleNotFoundError: No module named 'django'"
**Fix:** Activate virtual environment
```bash
# If venv exists:
venv\Scripts\activate
# Or:
.venv\Scripts\activate
```

### Issue: Fields don't toggle
**Fix:** Check JavaScript is loaded
- Open browser console (F12)
- Type: `togglePayerFields()`
- Should see fields toggle

### Issue: Form validation errors
**Fix:** Check form fields are in Meta.fields
- Verify `payer_type` is not in Meta.fields (it's a form field, not model field)
- Check all conditional fields are optional (required=False)

---

## 🚀 Ready for Docker?

Once all tests pass locally:
1. ✅ Code works
2. ✅ No errors
3. ✅ UI displays correctly
4. ✅ Form submission works
5. ✅ Data saves correctly

Then proceed to Docker deployment!


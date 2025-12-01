# 🚀 Server Started - Testing Instructions

## ✅ Server is Running!

The Django development server should now be starting.

---

## 🌐 Access the Application

### Main URLs:
- **Home/Login**: http://127.0.0.1:8000/
- **Patient Registration**: http://127.0.0.1:8000/hms/patients/create/
- **Reception Dashboard**: http://127.0.0.1:8000/hms/reception-dashboard/

---

## 🎯 Test the New Payer Selection Feature

### Step 1: Navigate to Patient Registration
1. Go to: http://127.0.0.1:8000/hms/patients/create/
2. Or: Login → Reception Dashboard → "Register Patient"

### Step 2: Find the New Section
Look for: **"💳 Payment Type & Billing Information"**

### Step 3: Test Each Payment Type

#### Test Insurance:
1. Select "Insurance" from "Payment Type" dropdown
2. ✅ Should see:
   - Insurance Company dropdown
   - Insurance Plan dropdown
   - Insurance ID field
   - Insurance Member ID field

#### Test Corporate:
1. Select "Corporate" from "Payment Type" dropdown
2. ✅ Should see:
   - Corporate Company dropdown
   - Employee ID field
3. ✅ Insurance fields should be hidden

#### Test Cash:
1. Select "Cash" from "Payment Type" dropdown
2. ✅ Should see:
   - Receiving Point field
3. ✅ Other fields should be hidden

### Step 4: Submit Form
1. Fill in patient details
2. Select a payment type and fill relevant fields
3. Submit the form
4. ✅ Check success message
5. ✅ Verify patient was created with correct payer

---

## 🔍 Debug Tips

### If you don't see the Payment Type dropdown:
1. **Hard refresh**: Press `Ctrl+Shift+R`
2. **Check console**: Press `F12` → Look for JavaScript errors
3. **Check HTML**: Right-click → View Source → Search for `id_payer_type`

### If fields don't toggle:
1. **Open console** (F12)
2. **Type**: `togglePayerFields()`
3. **Check for errors** in console

### If form submission fails:
1. **Check server logs** in the terminal
2. **Check for validation errors** on the form
3. **Verify database** is running (if using Docker)

---

## 📊 What to Verify

- [ ] Payment Type dropdown appears
- [ ] All 3 options available (Insurance, Corporate, Cash)
- [ ] Fields show/hide correctly
- [ ] Form submits successfully
- [ ] Patient record has correct payer set
- [ ] No JavaScript errors
- [ ] No Django errors in terminal

---

## 🎉 Success Indicators

✅ **Visual**: Payment Type dropdown visible and working  
✅ **Functional**: Fields toggle based on selection  
✅ **Data**: Patient records saved with correct payer type  
✅ **No Errors**: Clean console and server logs

---

## 🛑 To Stop Server

Press `Ctrl+C` in the terminal where the server is running.

---

**Happy Testing! 🚀**


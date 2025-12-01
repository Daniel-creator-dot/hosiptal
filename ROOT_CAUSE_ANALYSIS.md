# ROOT CAUSE: Why Duplicates Are Created

## The Problem

**Auto-Save JavaScript is causing duplicate patient creation!**

### How It Happens:

1. **Auto-Save Script** (`hospital/static/hospital/js/auto-save.js`) is loaded on ALL pages
2. It automatically submits forms when user types in fields
3. User fills out patient form
4. **TWO submissions happen:**
   - User clicks "Register Patient" button → Normal POST submission
   - Auto-save script ALSO submits form → Auto-save POST submission
5. **Result: TWO patients created with same data!**

### Evidence:

1. `hospital/templates/hospital/base.html` line 739:
   ```html
   <script src="{% static 'hospital/js/auto-save.js' %}"></script>
   ```
   This loads on EVERY page, including patient registration form.

2. `auto-save.js` line 80-86:
   ```javascript
   input.addEventListener('input', () => {
       this.scheduleAutoSave(form, action, method);
   });
   ```
   It submits the form automatically when user types!

3. `auto-save.js` line 118:
   ```javascript
   formData.append('auto_save', 'true');
   ```
   It adds `auto_save=true` flag, but the view doesn't check for it!

4. `hospital/views.py` patient_create view:
   - Does NOT check for `auto_save` flag
   - Processes ALL POST requests the same way
   - Creates patient for BOTH manual submission AND auto-save submission

## The Fix

### Option 1: Disable Auto-Save on Patient Form (RECOMMENDED)
Add `data-no-autosave` attribute to patient form template.

### Option 2: Check Auto-Save Flag in View
Skip patient creation if `auto_save=true` in POST data.

### Option 3: Remove Auto-Save from Base Template
Only load auto-save on specific pages that need it.

## Why This Wasn't Caught Before

1. Auto-save was designed for draft forms (like appointments, notes)
2. Patient registration should NOT be auto-saved (it's a final submission)
3. The auto-save script doesn't distinguish between draft forms and final forms
4. No check in the view to prevent auto-save from creating actual records

## Solution

**Disable auto-save on patient registration form** - it should only be submitted when user clicks "Register Patient", not automatically.


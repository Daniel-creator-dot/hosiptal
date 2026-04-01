# 📍 Where to Find the Payer Type System

## 🗂️ File Locations

### 1. **Backend Services** (Core Logic)

**Location**: `d:\chm\hospital\services\visit_payer_sync_service.py`
- **What it does**: Syncs payer type across patient, encounter, and invoice
- **Key function**: `verify_and_set_payer_type()` - Main sync logic

**Location**: `d:\chm\hospital\services\pricing_engine_service.py`
- **What it does**: Gets correct prices based on payer type
- **Key function**: `get_service_price()` - Returns price for service

### 2. **Front Desk Views** (User Interface)

**Location**: `d:\chm\hospital\views_frontdesk_visit.py`
- **Views**:
  - `frontdesk_visit_create` - Create visit with payer verification
  - `frontdesk_visit_update_payer` - Update payer type
  - `frontdesk_visit_pricing_preview` - Preview pricing

### 3. **Auto-Sync Signal** (Automatic Processing)

**Location**: `d:\chm\hospital\signals_visit_payer_sync.py`
- **What it does**: Automatically syncs payer type when encounter is created
- **Triggered**: Every time a new encounter/visit is created

### 4. **URL Routes** (Web Access)

**Location**: `d:\chm\hospital\urls.py` (lines ~278, ~658-700)
- **Routes added**:
  ```python
  path('frontdesk/visit/create/<uuid:patient_id>/', ...)
  path('frontdesk/visit/<uuid:encounter_id>/update-payer/', ...)
  path('frontdesk/visit/<uuid:encounter_id>/pricing-preview/', ...)
  ```

### 5. **Signal Registration**

**Location**: `d:\chm\hospital\apps.py` (lines ~120-130)
- **What it does**: Loads the auto-sync signal when Django starts

## 🌐 How to Access in the System

### Option 1: Direct URL Access

1. **Create Visit with Payer Verification**
   ```
   http://localhost:8000/hms/frontdesk/visit/create/<patient_id>/
   ```
   Replace `<patient_id>` with actual patient UUID

2. **Update Payer Type for Existing Visit**
   ```
   http://localhost:8000/hms/frontdesk/visit/<encounter_id>/update-payer/
   ```
   Replace `<encounter_id>` with actual encounter UUID

3. **Preview Pricing**
   ```
   http://localhost:8000/hms/frontdesk/visit/<encounter_id>/pricing-preview/?service_code_id=<service_id>
   ```

### Option 2: Through Patient Detail Page

1. Go to: **Patients** → **Patient List**
2. Click on a patient
3. On patient detail page, you'll see:
   - "Create New Visit" button (existing)
   - This uses `patient_quick_visit_create` view

**Note**: The existing visit creation (`patient_quick_visit_create`) will automatically sync payer type via the signal, but doesn't show payer type selection UI yet.

### Option 3: Modify Existing Visit Creation

The existing visit creation is at:
- **View**: `hospital/views.py` → `patient_quick_visit_create` (line ~2417)
- **Template**: `hospital/templates/hospital/quick_visit_form.html`

You can add payer type selection to this existing form.

## 🔧 Integration Points

### Current Visit Creation Flow

1. **Patient Detail Page** → Click "Create New Visit"
   - URL: `/hms/patients/<patient_id>/quick-visit/`
   - View: `patient_quick_visit_create` in `views.py`
   - Template: `quick_visit_form.html`

2. **What Happens**:
   - Encounter is created
   - Signal `sync_encounter_payer_type` automatically runs
   - Payer type is synced from patient's `primary_insurance`
   - Invoice is created with correct payer

### New Front Desk Visit Flow (What I Created)

1. **New Route**: `/hms/frontdesk/visit/create/<patient_id>/`
   - View: `frontdesk_visit_create` in `views_frontdesk_visit.py`
   - Shows payer type selection/verification
   - Allows front desk to confirm or change payer type

## 📝 To Add Payer Type Selection to Existing Form

You can modify the existing `quick_visit_form.html` template to include payer type selection:

**File**: `d:\chm\hospital\templates\hospital\quick_visit_form.html`

Add this section before the "Create Visit" button:

```html
<!-- Payer Type Selection -->
<div class="mb-4">
    <label for="payer_type" class="form-label fw-bold">
        Payment Type <span class="text-danger">*</span>
    </label>
    <select name="payer_type" id="payer_type" class="form-select form-select-lg" required>
        <option value="">Select Payment Type...</option>
        <option value="cash" {% if current_payer_type == 'cash' %}selected{% endif %}>Cash Payment</option>
        <option value="insurance" {% if current_payer_type == 'insurance' %}selected{% endif %}>Insurance</option>
        <option value="corporate" {% if current_payer_type == 'corporate' %}selected{% endif %}>Corporate</option>
    </select>
    <small class="form-text text-muted">
        Current: {{ patient.primary_insurance.name|default:"Cash" }} 
        ({{ patient.primary_insurance.payer_type|default:"cash" }})
    </small>
</div>
```

Then update the view to handle payer_type:

**File**: `d:\chm\hospital\views.py` → `patient_quick_visit_create` function

Add after encounter creation (around line 2439):

```python
# Sync payer type
from hospital.services.visit_payer_sync_service import visit_payer_sync_service
payer_type = request.POST.get('payer_type')
if payer_type:
    sync_result = visit_payer_sync_service.verify_and_set_payer_type(
        encounter=encounter,
        payer_type=payer_type
    )
```

## 🧪 Testing the System

### Test 1: Check Signal is Working

1. Create a visit using existing form
2. Check Django logs - should see:
   ```
   [INIT] Visit payer sync signals loaded [OK]
   Auto-synced payer type for encounter...
   ```

### Test 2: Use New Front Desk View

1. Get a patient ID (UUID)
2. Navigate to:
   ```
   http://localhost:8000/hms/frontdesk/visit/create/<patient_id>/
   ```
3. You should see payer type selection

### Test 3: Verify Pricing

1. Create visit for insurance patient
2. Add a service to invoice
3. Check invoice line - should use insurance price (not cash price)

### Test 4: Verify Claims

1. Create visit for insurance patient
2. Add service to invoice
3. Check: `/hms/admin/hospital/insuranceclaimitem/`
4. Should see claim item created automatically

## 📊 Documentation Files

1. **Full Documentation**: `d:\chm\FRONT_DESK_PAYER_TYPE_SYSTEM_COMPLETE.md`
2. **Quick Summary**: `d:\chm\VISIT_PAYER_TYPE_IMPLEMENTATION_SUMMARY.md`
3. **This Guide**: `d:\chm\WHERE_TO_FIND_PAYER_TYPE_SYSTEM.md`

## 🎯 Quick Access Summary

| What | Where | How to Access |
|------|-------|---------------|
| **Sync Service** | `hospital/services/visit_payer_sync_service.py` | Import in Python code |
| **Front Desk Views** | `hospital/views_frontdesk_visit.py` | Via URLs below |
| **Auto-Sync Signal** | `hospital/signals_visit_payer_sync.py` | Runs automatically |
| **Create Visit (New)** | `/hms/frontdesk/visit/create/<patient_id>/` | Direct URL |
| **Update Payer** | `/hms/frontdesk/visit/<encounter_id>/update-payer/` | Direct URL |
| **Existing Visit Form** | `/hms/patients/<patient_id>/quick-visit/` | Patient detail page |

## 💡 Recommendation

**To see payer type selection in the existing visit form** (the one shown in your screenshot):

1. Modify `quick_visit_form.html` to add payer type dropdown
2. Update `patient_quick_visit_create` view to handle payer_type
3. The sync service will automatically handle the rest

Or use the new front desk view I created which already has payer type selection built in.

---

**All files are in**: `d:\chm\hospital\` directory

# 🎯 Front Desk Payer Type System - Complete Implementation

## ✅ Overview

Comprehensive system for front desk to verify and set payer type (Cash, Insurance, Corporate) during patient visits, ensuring proper pricing and claims creation.

## 🏗️ Architecture

### Components Created

1. **VisitPayerSyncService** (`hospital/services/visit_payer_sync_service.py`)
   - Senior Engineering & Pricing Officer service
   - Verifies and syncs payer type across patient, encounter, and invoice
   - Ensures proper pricing category selection
   - Creates insurance claims automatically

2. **Front Desk Visit Views** (`hospital/views_frontdesk_visit.py`)
   - `frontdesk_visit_create` - Create visit with payer type verification
   - `frontdesk_visit_update_payer` - Update payer type for existing visit
   - `frontdesk_visit_pricing_preview` - Preview pricing for services

3. **Auto-Sync Signal** (`hospital/signals_visit_payer_sync.py`)
   - Automatically syncs payer type when encounter is created
   - Ensures consistency across the system

## 🔄 How It Works

### Step 1: Patient Registration
- Front desk selects payer type: Cash, Insurance, or Corporate
- System creates appropriate enrollment (insurance/corporate) or sets cash payer
- Patient's `primary_insurance` field is set to appropriate Payer

### Step 2: Visit Creation
When front desk creates a visit/encounter:

1. **Payer Type Verification**
   - System checks patient's current payer type
   - Front desk can verify or update if needed
   - Sync service ensures consistency

2. **Automatic Sync**
   - Patient's `primary_insurance` is verified
   - Encounter invoice gets correct payer
   - Pricing category is determined

3. **Pricing Application**
   - Pricing engine uses correct payer type
   - Services are priced according to:
     - Cash → Cash prices (highest)
     - Corporate → Corporate prices (middle)
     - Insurance → Insurance prices (lowest) or company-specific rates

### Step 3: Service Billing
When services are added to invoice:

1. **Price Lookup**
   - System uses `PricingEngineService` to get correct price
   - Based on patient's payer type and service code
   - Uses flexible pricing system (ServicePrice + PricingCategory)

2. **Invoice Creation**
   - Invoice is created with correct payer
   - Invoice lines use correct prices
   - Total reflects payer-specific pricing

### Step 4: Claims Creation
For insurance patients:

1. **Automatic Claim Creation**
   - Signal (`signals_insurance.py`) creates claim items automatically
   - Only for insurance patients (not cash)
   - Respects exclusion rules

2. **Claim Tracking**
   - Claims are grouped by month and payer
   - Status tracking: pending → submitted → paid
   - Financial reconciliation

## 📋 Front Desk Workflow

### Creating a Visit

1. **Navigate to Patient**
   - Go to patient detail page
   - Click "Create Visit" or use front desk visit creation

2. **Verify Payer Type**
   - System shows current payer type
   - Front desk can:
     - Confirm current payer type
     - Change to different payer type
     - Update insurance/corporate details

3. **Select Department**
   - Choose department (e.g., Outpatient, Emergency)
   - Enter chief complaint

4. **Submit**
   - System creates encounter
   - Syncs payer type automatically
   - Creates queue entry if needed
   - Shows confirmation with payer type

### Updating Payer Type

If payer type needs to be changed during visit:

1. Go to encounter detail page
2. Click "Update Payer Type"
3. Select new payer type
4. System automatically:
   - Updates patient's primary_insurance
   - Updates encounter invoice payer
   - Recalculates prices (if services already added)

## 💰 Pricing Logic

### Priority Order

1. **Insurance-Specific Pricing**
   - If patient has specific insurance company (e.g., COSMO, GLICO)
   - Uses that company's negotiated rates

2. **Corporate Pricing**
   - If patient is corporate employee
   - Uses corporate pricing category
   - May include company-specific discounts

3. **General Insurance Pricing**
   - If patient has insurance but no specific company match
   - Uses general insurance pricing category

4. **Cash Pricing** (Default)
   - Walk-in cash patients
   - Highest price tier

### Pricing Categories

- **CASH** - Cash Patients (highest prices)
- **CORP** - Corporate (middle prices)
- **INS** - General Insurance (lower prices)
- **NHIS** - National Health Insurance Scheme
- **INS-COSMO** - COSMO Insurance specific
- **INS-GLI** - GLICO Insurance specific
- **INS-NMH** - NMH Insurance specific
- etc.

## 🎫 Claims Management

### Automatic Claims Creation

When invoice line is created for insurance patient:

```python
# Signal automatically creates claim
InsuranceClaimItem.objects.create(
    patient=patient,
    payer=invoice.payer,
    invoice=invoice,
    invoice_line=line,
    billed_amount=line.line_total,
    claim_status='pending'
)
```

### Monthly Claims Aggregation

Claims are automatically grouped by:
- Payer (insurance company)
- Month and year
- Status (pending, submitted, paid)

### Claim Submission

1. View monthly claims: `/hms/insurance/monthly-claims/`
2. Review and verify claims
3. Submit to insurance company
4. Track payment status

## 🔧 Technical Details

### Service: VisitPayerSyncService

**Methods:**

1. `verify_and_set_payer_type(encounter, payer_type, payer)`
   - Verifies payer type
   - Updates patient, encounter, invoice
   - Returns sync result

2. `ensure_claims_created(encounter)`
   - Creates insurance claims for insurance patients
   - Only for non-excluded services
   - Returns creation summary

### Signal: sync_encounter_payer_type

- Triggered when encounter is created
- Automatically syncs payer type
- Non-blocking (won't fail encounter creation if sync fails)

### Views

- `frontdesk_visit_create` - Create visit with payer verification
- `frontdesk_visit_update_payer` - Update payer type
- `frontdesk_visit_pricing_preview` - Preview service pricing

## 📍 URLs

```
/frontdesk/visit/create/<patient_id>/          - Create visit
/frontdesk/visit/<encounter_id>/update-payer/   - Update payer type
/frontdesk/visit/<encounter_id>/pricing-preview/ - Preview pricing
```

## ✅ Benefits

1. **Proper Pricing**
   - Correct prices applied automatically
   - No manual price entry needed
   - Consistent across all services

2. **Claims Management**
   - Automatic claim creation
   - Proper tracking and reconciliation
   - Monthly aggregation ready

3. **Data Consistency**
   - Payer type synced across patient, encounter, invoice
   - No discrepancies
   - Audit trail maintained

4. **Front Desk Efficiency**
   - Simple payer type selection
   - Automatic verification
   - Clear confirmation messages

## 🚀 Usage

### For Front Desk Staff

1. **Patient Arrives**
   - Search/select patient
   - Click "Create Visit"

2. **Verify Payer Type**
   - Check current payer type shown
   - Update if needed (e.g., patient brought insurance card)
   - Confirm

3. **Complete Visit**
   - Services are automatically priced correctly
   - Claims created automatically (for insurance)
   - Invoice ready for payment

### For Administrators

1. **Monitor Pricing**
   - Check pricing dashboard: `/hms/pricing/`
   - Verify prices are correct for each payer type

2. **Review Claims**
   - Monthly claims: `/hms/insurance/monthly-claims/`
   - Verify all insurance patients have claims
   - Submit to insurance companies

3. **Audit Trail**
   - Check encounter notes for payer type changes
   - Review invoice payer assignments
   - Verify claim creation

## 🔍 Verification

### Check Payer Type Sync

```python
from hospital.services.visit_payer_sync_service import visit_payer_sync_service

encounter = Encounter.objects.get(id='...')
result = visit_payer_sync_service.verify_and_set_payer_type(encounter)
print(result['message'])
```

### Check Pricing

```python
from hospital.services.pricing_engine_service import PricingEngineService

pricing_engine = PricingEngineService()
price = pricing_engine.get_service_price(
    service_code=service_code,
    patient=patient
)
print(f"Price: GHS {price}")
```

### Check Claims

```python
from hospital.models_insurance import InsuranceClaimItem

claims = InsuranceClaimItem.objects.filter(
    encounter=encounter,
    is_deleted=False
)
print(f"Claims created: {claims.count()}")
```

## 📝 Files Created/Modified

1. `hospital/services/visit_payer_sync_service.py` - NEW
2. `hospital/views_frontdesk_visit.py` - NEW
3. `hospital/signals_visit_payer_sync.py` - NEW
4. `hospital/urls.py` - MODIFIED (added routes)
5. `hospital/apps.py` - MODIFIED (added signal import)

## 🎯 Next Steps

1. ✅ **System Implemented** - All components created
2. 🔄 **Test Workflow** - Test visit creation with different payer types
3. 🔄 **Verify Pricing** - Check prices are applied correctly
4. 🔄 **Test Claims** - Verify claims are created for insurance patients
5. 🔄 **Train Staff** - Train front desk on new workflow

---

**Status**: ✅ COMPLETE  
**Date**: 2026-01-14  
**Role**: Senior Engineering & Pricing Officer Implementation

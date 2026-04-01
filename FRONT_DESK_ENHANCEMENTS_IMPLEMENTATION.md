# Front Desk Enhancements - Implementation Plan

## Features to Implement

1. **Doctor Assignment at Visit Creation** ✅
   - Add doctor selection field to visit creation page
   - Assign doctor to encounter/provider field
   - Send notification to assigned doctor

2. **Consultation Charges When Doctor Starts Consultation** ✅
   - Detect when consultation starts (when doctor accesses consultation view for first time)
   - Add consultation charge to invoice
   - Use pricing from database

3. **Cash Patient Deposits at Cashier** ✅
   - Add deposit recording option in cashier dashboard
   - Link deposits to patient accounts
   - Auto-apply to invoices

4. **Import Prices from Database** ✅
   - Import consultation prices (S00023 - cash: 100, corp: 120, ins: 120)
   - Import lab test prices
   - Import other service prices

5. **Lab Test Display - Show Codes** ✅
   - Update templates to show codes instead of just names
   - Display format: "CODE - Name" or just "CODE"

## Implementation Steps

### Step 1: Doctor Assignment in Visit Creation
- Modify `patient_quick_visit_create` view
- Modify `patient_qr_checkin_api` view  
- Update templates to include doctor selection
- Add notification when doctor is assigned

### Step 2: Consultation Charges
- Detect consultation start in `consultation_view`
- Call `add_consultation_charge` when consultation starts
- Ensure pricing is imported from database

### Step 3: Cashier Deposit Integration
- Add deposit recording link in cashier dashboard
- Ensure deposit recording works for cash patients

### Step 4: Price Import
- Create/update command to import from billing.sql
- Import consultation prices: S00023
- Import lab test prices by code
- Update ServiceCode and Pricing models

### Step 5: Lab Test Display Fix
- Update consultation templates
- Show codes prominently
- Update lab test selection UI

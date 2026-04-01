# Lab Tests and Imaging Studies Import - Complete Implementation

## Overview
This document describes the complete implementation of importing lab tests and imaging studies from `db_3.zip` and enabling doctors to prescribe them with prices, plus nurse assignment functionality.

## What Was Implemented

### 1. Database Models

#### ImagingCatalog Model (`hospital/models_advanced.py`)
- **Purpose**: Catalog of available imaging studies for ordering
- **Fields**:
  - `code`: Procedure code (unique)
  - `name`: Imaging study name
  - `modality`: Type (xray, ct, mri, ultrasound, etc.)
  - `body_part`: Body part or region
  - `study_type`: Type of study
  - `price`: Price for the imaging study
  - `description`: Description
  - `is_active`: Whether available for ordering

### 2. Import Script (`import_lab_imaging_from_db3.py`)

#### Features:
- Extracts lab tests from `lab_order_code.sql`
- Extracts imaging studies from `diag_imaging_order_code.sql`
- Maps prices from `prices.sql` (supports multiple price levels: cash, corp, insurance, etc.)
- Automatically determines:
  - Lab test specimen types (Blood, Urine, Stool, etc.)
  - Imaging modalities (X-Ray, CT, MRI, Ultrasound, etc.)
  - Body parts for imaging studies
- Creates/updates database records

#### Usage:
```bash
python import_lab_imaging_from_db3.py
```

### 3. Enhanced Consultation View

#### Doctor Prescription Features:
- **Lab Tests**: 
  - Shows all available lab tests with prices
  - Allows multiple test selection
  - Displays prices when selecting tests
  - Creates `Order` and `LabResult` records

- **Imaging Studies**:
  - Shows imaging studies grouped by modality
  - Displays prices for each study
  - Allows selection from `ImagingCatalog`
  - Creates `Order` and `ImagingStudy` records
  - Automatically sets modality, body part, and study type

### 4. Nurse Assignment System

#### New Views (`hospital/views_nurse_assignment.py`):

1. **`nurse_patient_assignment`**:
   - Shows patients who have vitals recorded but no doctor assigned
   - Lists available doctors
   - Allows nurses to assign patients to doctors

2. **`assign_patient_to_doctor`**:
   - Handles assignment of patient to doctor
   - Updates queue entry with assigned doctor
   - Updates encounter provider
   - Updates workflow stage

3. **`view_patient_assignments`**:
   - Shows all patient assignments (both front desk and nurse assignments)
   - Groups by doctor
   - Shows assignment history

#### URLs Added:
- `/nurse/assign-patients/` - Main assignment page
- `/nurse/assign-patient/<encounter_id>/` - Assign specific patient
- `/nurse/view-assignments/` - View all assignments

### 5. Workflow Integration

#### After Vitals Recording:
- Vitals stage is automatically completed
- Consultation stage is created (if not exists)
- Queue entry status updated to `vitals_completed`
- Nurse can now assign doctor

#### Assignment Visibility:
- Nurses can see:
  - Patients needing assignment (after vitals)
  - All assignments (front desk + nurse)
  - Which doctor is assigned to which patient
  - Assignment timestamps

## Database Migration

### Migration Created:
- `1067_add_imaging_catalog.py`
- Creates `ImagingCatalog` model
- Run with: `python manage.py migrate hospital`

## Import Process

### Step 1: Run Migration
```bash
python manage.py migrate hospital
```

### Step 2: Run Import Script
```bash
python import_lab_imaging_from_db3.py
```

### Expected Output:
```
=== Importing Lab Tests ===
Found X unique lab tests
Lab Tests: X imported, Y updated, Z skipped

=== Importing Imaging Studies ===
Found X unique imaging studies
Imaging Studies: X imported, Y updated, Z skipped
```

## Usage Guide

### For Doctors:

1. **Prescribing Lab Tests**:
   - Go to consultation view
   - Click "Order Lab" tab
   - Select tests (prices shown)
   - Set priority (routine/urgent/STAT)
   - Add notes if needed
   - Submit

2. **Prescribing Imaging**:
   - Go to consultation view
   - Click "Order Imaging" tab
   - Select imaging studies by modality
   - Prices are displayed
   - Set priority
   - Add clinical indication
   - Submit

### For Nurses:

1. **Assigning Patients After Vitals**:
   - Record vitals for patient
   - Go to `/nurse/assign-patients/`
   - See list of patients needing assignment
   - Select patient and doctor
   - Add notes (optional)
   - Submit assignment

2. **Viewing Assignments**:
   - Go to `/nurse/view-assignments/`
   - See all patient assignments
   - View by doctor
   - See assignment timestamps

## Price Management

### Price Levels Supported:
- `cash`: Cash payment price
- `corp`: Corporate account price
- `ins`: Insurance price
- `gab`: GAB insurance price
- `Cosmo`: Cosmo insurance price
- `Glico`: Glico insurance price
- `nmh`: NMH price
- `nongh`: Non-GH price

### Default Price Selection:
- Import script uses `cash` price as default
- Falls back to `corp` if cash not available
- Falls back to first available price level

## Technical Details

### File Structure:
```
hospital/
├── models_advanced.py          # ImagingCatalog model
├── views_consultation.py       # Enhanced consultation view
├── views_nurse_assignment.py   # Nurse assignment views
└── urls.py                     # URL routes

import_lab_imaging_from_db3.py  # Import script
```

### Key Dependencies:
- `zipfile`: Extract SQL files
- `re`: Parse SQL INSERT statements
- `Decimal`: Handle prices accurately
- Django ORM: Database operations

## Testing Checklist

- [ ] Run migration successfully
- [ ] Import script runs without errors
- [ ] Lab tests appear in consultation view with prices
- [ ] Imaging studies appear grouped by modality with prices
- [ ] Doctors can prescribe lab tests
- [ ] Doctors can prescribe imaging studies
- [ ] Orders are created correctly
- [ ] Nurses can see patients needing assignment
- [ ] Nurses can assign patients to doctors
- [ ] Nurses can view all assignments
- [ ] Queue entries update correctly
- [ ] Workflow stages update correctly

## Next Steps

1. **Run the import**:
   ```bash
   python import_lab_imaging_from_db3.py
   ```

2. **Test doctor prescription**:
   - Create a test encounter
   - Try prescribing lab tests
   - Try prescribing imaging studies

3. **Test nurse assignment**:
   - Record vitals for a patient
   - Assign to a doctor
   - Verify assignment appears in view

4. **Customize prices** (if needed):
   - Update prices in Django admin
   - Or re-run import with updated price mapping

## Notes

- The import script handles duplicate detection (updates existing records)
- Prices are stored as Decimal for accuracy
- Imaging studies are linked to orders via `ImagingStudy` model
- Lab tests are linked to orders via `LabResult` model
- Nurse assignment integrates with existing queue system
- All assignments are visible to nurses for transparency

## Support

If you encounter issues:
1. Check migration status: `python manage.py showmigrations hospital`
2. Check import script output for errors
3. Verify `db_3.zip` is in `import/` directory
4. Check Django logs for errors

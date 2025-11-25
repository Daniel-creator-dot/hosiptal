# Tabular Lab Report Entry System - User Guide

## Overview
The Tabular Lab Report Entry System is a comprehensive, modern solution for entering laboratory test results in a structured, tabular format. It supports multiple test types with pre-defined parameters, reference ranges, and automatic calculations.

## Features

### 1. Supported Test Types

#### Full Blood Count (FBC/CBC)
Complete blood count analysis with differential:
- **Complete Blood Count Parameters:**
  - WBC (White Blood Cells): ×10⁹/L
  - RBC (Red Blood Cells): ×10¹²/L
  - HGB (Hemoglobin): g/dL
  - HCT (Hematocrit): %
  - MCV (Mean Corpuscular Volume): fL
  - MCH (Mean Corpuscular Hemoglobin): pg
  - MCHC (Mean Corpuscular Hemoglobin Concentration): g/dL
  - RDW (Red Cell Distribution Width): %
  - PLT (Platelets): ×10⁹/L

- **Differential Count:**
  - Neutrophils: %
  - Lymphocytes: %
  - Monocytes: %
  - Eosinophils: %
  - Basophils: %

#### Liver Function Tests (LFT)
Comprehensive hepatic panel:
- Total Bilirubin: mg/dL
- Direct Bilirubin: mg/dL
- Indirect Bilirubin: mg/dL (auto-calculated)
- ALT (SGPT): U/L
- AST (SGOT): U/L
- ALP (Alkaline Phosphatase): U/L
- GGT (Gamma-GT): U/L
- Total Protein: g/dL
- Albumin: g/dL
- Globulin: g/dL (auto-calculated)
- A/G Ratio: ratio (auto-calculated)

#### Renal Function Tests (RFT)
Kidney function assessment:
- Urea: mg/dL
- BUN (Blood Urea Nitrogen): mg/dL
- Creatinine: mg/dL
- eGFR (Estimated GFR): mL/min/1.73m²
- Uric Acid: mg/dL
- Sodium (Na⁺): mmol/L
- Potassium (K⁺): mmol/L
- Chloride (Cl⁻): mmol/L
- Bicarbonate (HCO₃⁻): mmol/L

#### Lipid Profile
Complete cholesterol panel:
- Total Cholesterol: mg/dL
- Triglycerides: mg/dL
- HDL Cholesterol (Good): mg/dL
- LDL Cholesterol (Bad): mg/dL
- VLDL Cholesterol: mg/dL (auto-calculated)
- Total Chol/HDL Ratio: ratio (auto-calculated)
- LDL/HDL Ratio: ratio (auto-calculated)
- Non-HDL Cholesterol: mg/dL (auto-calculated)

#### Thyroid Function Tests (TFT)
Thyroid hormone panel:
- TSH (Thyroid Stimulating Hormone): μIU/mL
- Free T4 (Thyroxine): ng/dL
- Total T4: μg/dL
- Free T3 (Triiodothyronine): pg/mL
- Total T3: ng/dL

#### Blood Glucose Tests
Glucose metabolism assessment:
- Fasting Blood Glucose: mg/dL
- Random Blood Glucose: mg/dL
- HbA1c (Glycated Hemoglobin): %
- 2-Hour Post-Prandial Glucose: mg/dL

#### Electrolytes Panel
Serum electrolyte balance:
- Sodium (Na⁺): mmol/L
- Potassium (K⁺): mmol/L
- Chloride (Cl⁻): mmol/L
- Bicarbonate (HCO₃⁻): mmol/L
- Calcium (Ca²⁺): mg/dL
- Magnesium (Mg²⁺): mg/dL
- Phosphorus (PO₄³⁻): mg/dL

### 2. Key Features

#### Smart Auto-Calculations
The system automatically calculates derived values:
- **LFT:** Indirect Bilirubin, Globulin, A/G Ratio
- **Lipid Profile:** VLDL, Cholesterol ratios, Non-HDL
- Reduces errors and saves time

#### Reference Ranges
Each parameter displays standard reference ranges:
- Adult male and female ranges where applicable
- Age-appropriate ranges
- Clear visual presentation

#### Modern User Interface
- Clean, intuitive tabular layout
- Color-coded sections for easy navigation
- Bootstrap 5-based modern design
- Mobile-responsive design

#### Multiple Entry Options
- Quick tabular entry for common tests
- Fallback to traditional entry for other tests
- Easy switching between test types

#### Quality Control
- Status tracking (Pending, In Progress, Completed, Cancelled)
- Verification by lab staff
- Timestamp of verification
- Clinical notes and comments

#### Qualitative Results
Support for non-numeric results:
- Negative/Positive
- Reactive/Non-Reactive
- Normal/Abnormal
- For tests like HBsAg, HIV, RPR, VDRL

## How to Use

### Accessing the System

1. **From Laboratory Dashboard:**
   - Navigate to Laboratory Dashboard
   - View pending or in-progress lab results
   - Click "Enter" button (table icon) to open tabular entry form

2. **Direct URL:**
   - `/laboratory/result/<result_id>/tabular/`

### Entering Lab Results

1. **Select Test Type:**
   - System auto-detects test type from test name/code
   - Click "Change Test Type" button to manually select different test type
   - Choose from: FBC, LFT, RFT, Lipid Profile, TFT, Glucose, Electrolytes

2. **Fill in Parameters:**
   - Enter numeric values in the "Value" column
   - Units and reference ranges are displayed for reference
   - Auto-calculated fields (highlighted in light blue) are read-only

3. **Set Status:**
   - Pending: Test not yet started
   - In Progress: Test is being performed
   - Completed: Results verified and ready
   - Cancelled: Test cancelled

4. **Add Qualitative Result (if applicable):**
   - For tests with qualitative outcomes
   - Select from dropdown: Negative, Positive, Reactive, etc.

5. **Add Clinical Notes:**
   - Enter morphology observations
   - Document any abnormal findings
   - Add interpretations or flags

6. **Save Results:**
   - Click "Save Results" to save as current status
   - Click "Save & Mark Complete" to save and mark as completed
   - Results are verified with your user credentials

### Keyboard Shortcuts

- **Ctrl+S (or Cmd+S):** Save form
- **Esc:** Clear search/Close modal
- **Tab:** Navigate between fields

### Tips for Efficient Entry

1. **Use Tab Navigation:**
   - Press Tab to move between fields quickly
   - Fill top-to-bottom for best workflow

2. **Auto-calculations:**
   - Lipid VLDL auto-calculates from triglycerides ÷ 5
   - Indirect bilirubin = Total - Direct
   - Globulin = Total Protein - Albumin
   - Let the system calculate derived values

3. **Batch Entry:**
   - Keep analyzer printouts handy
   - Enter all parameters at once
   - Review before saving

4. **Quality Checks:**
   - Compare values with reference ranges
   - Check for data entry errors
   - Review auto-calculated values

## Technical Details

### Data Storage
- Results stored in `LabResult.details` JSON field
- Flexible structure allows any test parameters
- Backward compatible with existing data

### Auto-Save
- Form data auto-saves to localStorage
- Prevents data loss on browser refresh
- Cleared after successful submission

### Validation
- Numeric validation on all fields
- Decimal precision: 2 decimal places
- Optional fields - fill only what's available

## Troubleshooting

### Test Type Not Detected
- Manually select test type using "Change Test Type" button
- System uses keywords in test name/code for detection

### Auto-calculations Not Working
- Ensure required fields are filled
- Check JavaScript console for errors
- Refresh page if needed

### Data Not Saving
- Check internet connection
- Ensure you have proper permissions
- Verify lab result exists and is not deleted

## Future Enhancements

Planned features:
- Critical value alerts
- Delta checks (compare with previous results)
- Reference range customization
- Export to PDF
- Print formatted reports
- Integration with lab analyzers
- QC charting
- Result trending graphs

## Support

For technical support or feature requests:
- Contact IT Support
- Report bugs to system administrator
- Submit feature requests through feedback form

## Version History

### Version 1.0 (Current)
- Initial release
- 7 test types supported
- Auto-calculations
- Modern UI
- Reference ranges
- Status tracking
- Qualitative results

---

**Document Version:** 1.0  
**Last Updated:** November 2025  
**System:** Hospital Management System (HMS)































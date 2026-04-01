# 🎓 HOSPITAL MANAGEMENT SYSTEM - TRAINING DOCUMENTATION

## 📚 Table of Contents

1. [Getting Started](#getting-started)
2. [User Roles & Access](#user-roles--access)
3. [Step-by-Step Guides](#step-by-step-guides)
4. [Common Workflows](#common-workflows)
5. [Troubleshooting](#troubleshooting)
6. [Quick Reference](#quick-reference)

---

## 🚀 GETTING STARTED

### First Time Login

1. **Access the System**
   - Open your web browser
   - Navigate to: `http://192.168.2.216:8000/hms/login/`
   - Enter your username and password
   - Click "Login"

2. **Dashboard Overview**
   - After login, you'll see your role-specific dashboard
   - Main dashboard shows: Quick Actions, Statistics, Alerts
   - Use the navigation menu on the left for different modules

3. **Understanding the Interface**
   - **Top Bar:** User info, notifications, logout
   - **Left Sidebar:** Main navigation menu
   - **Center:** Main content area
   - **Right Sidebar:** Quick actions (if available)

---

## 👥 USER ROLES & ACCESS

### Administrator
**Access:** Full system access
**Dashboard:** `/hms/admin-dashboard/`
**Key Features:**
- User management
- System settings
- All reports
- Department management

### Doctor
**Access:** Clinical features
**Dashboard:** `/hms/dashboard/doctor/`
**Key Features:**
- Patient consultations
- Prescribe medications
- Order lab tests
- Order imaging
- Add diagnoses
- Clinical notes

### Nurse
**Access:** Nursing & triage
**Dashboard:** `/hms/dashboard/nurse/`
**Key Features:**
- Triage patients
- Record vital signs
- Medication administration
- Patient monitoring
- Bed management

### Midwife
**Access:** Maternity care
**Dashboard:** `/hms/dashboard/midwife/`
**Key Features:**
- Maternity records
- Antenatal care
- Postnatal care
- Delivery records
- Patient vitals

### Pharmacist
**Access:** Pharmacy operations
**Dashboard:** `/hms/dashboard/pharmacy/`
**Key Features:**
- Dispense medications
- Check stock levels
- Verify payments
- Manage inventory

### Lab Technician
**Access:** Laboratory operations
**Dashboard:** `/hms/dashboard/lab/`
**Key Features:**
- Process lab orders
- Enter results
- Print reports
- Verify payments

### Cashier
**Access:** Billing & payments
**Dashboard:** `/hms/cashier/central/`
**Key Features:**
- Process payments
- Generate receipts
- View patient bills
- Print receipts

### Receptionist
**Access:** Front desk operations
**Dashboard:** `/hms/dashboard/reception/`
**Key Features:**
- Register patients
- Book appointments
- Queue management
- Patient search

### Accountant
**Access:** Financial management
**Dashboard:** `/hms/accountant/comprehensive-dashboard/`
**Key Features:**
- Financial reports
- Revenue tracking
- AR management
- General ledger

---

## 📖 STEP-BY-STEP GUIDES

### 1. REGISTER A NEW PATIENT

**Who Can Do This:** Receptionist, Admin

**Steps:**
1. Click **"New Patient"** button on dashboard (or go to `/hms/patients/new/`)
2. Fill in patient information:
   - **Personal Details:** Name, Date of Birth, Gender, Phone, Email
   - **Address:** Residential address
   - **Emergency Contact:** Name and phone
   - **Insurance:** Select insurance company and plan (if applicable)
3. Click **"Save Patient"**
4. System generates Medical Record Number (MRN)
5. Patient is now registered

**Tips:**
- Always verify phone number (used for SMS)
- Select insurance during registration for automatic coverage
- Emergency contact is important for critical situations

---

### 2. BOOK AN APPOINTMENT

**Who Can Do This:** Receptionist, Admin

**Steps:**
1. Go to **"Appointments"** → **"Book Appointment"** (or `/hms/frontdesk/appointments/`)
2. Click **"New Appointment"** button
3. Select patient (search by name or MRN)
4. Fill in appointment details:
   - **Date & Time**
   - **Provider** (Doctor)
   - **Appointment Type** (Consultation, Follow-up, etc.)
   - **Reason for Visit**
5. Click **"Book Appointment"**
6. System sends SMS confirmation to patient

**Tips:**
- Check provider availability before booking
- SMS reminder sent 24 hours before appointment
- Patient can confirm via SMS link

---

### 3. START A CONSULTATION (DOCTOR)

**Who Can Do This:** Doctor

**Steps:**
1. Go to **"Encounters"** or **"Patients"**
2. Find patient and click **"Start Consultation"**
3. Beautiful consultation interface opens
4. **Record Vital Signs** (if not done):
   - Click **"Record Vitals"** button
   - Enter: BP, Pulse, Temperature, SpO2, etc.
   - Save
5. **Prescribe Medications:**
   - Click **"Prescribe"** tab
   - Search for drug (autocomplete appears)
   - Select drug, enter dose, route, frequency, duration
   - Click **"Add to Prescription"**
6. **Order Lab Tests:**
   - Click **"Lab Tests"** tab
   - Search and select tests
   - Choose priority (STAT/Urgent/Routine)
   - Click **"Order Selected Tests"**
7. **Add Diagnosis:**
   - Click **"Diagnosis"** tab
   - Enter ICD-10 code (optional)
   - Enter diagnosis description
   - Click **"Add to Problem List"**
8. **Write Clinical Notes:**
   - Use SOAP format (Subjective, Objective, Assessment, Plan)
   - Click **"Save Notes"**
9. **Complete Consultation:**
   - Click **"Complete Encounter"** button
   - Confirm completion

**Keyboard Shortcuts:**
- `Alt + 1` = Prescribe tab
- `Alt + 2` = Lab Tests tab
- `Alt + 3` = Diagnosis tab
- `Alt + 4` = History tab

---

### 4. RECORD VITAL SIGNS (NURSE)

**Who Can Do This:** Nurse, Midwife

**Steps:**
1. Go to patient's encounter or profile
2. Click **"Record Vitals"** button
3. Enter vital signs:
   - **Blood Pressure:** Systolic/Diastolic
   - **Pulse:** Beats per minute
   - **Temperature:** Celsius
   - **SpO2:** Oxygen saturation
   - **Respiratory Rate:** Breaths per minute
   - **Weight:** Kilograms
4. Click **"Save Vital Signs"**
5. Vitals appear in patient's record

**Tips:**
- Abnormal values are highlighted in red
- Vitals history is available in timeline
- Can record multiple times per encounter

---

### 5. DISPENSE MEDICATION (PHARMACIST)

**Who Can Do This:** Pharmacist

**Steps:**
1. Go to **"Pharmacy Dashboard"** (`/hms/pharmacy/`)
2. View **"Pending Prescriptions"** list
3. Click on a prescription
4. **Check Stock:**
   - System shows stock status (✅ In Stock, ⚠️ Low Stock, ❌ Out of Stock)
   - Check quantity available
5. **Verify Payment:**
   - Click **"Check Payment"** button
   - System verifies if patient has paid
   - If not paid, redirect to cashier
6. **Dispense Medication:**
   - Enter quantity to dispense
   - Click **"Dispense"** button
   - System updates stock automatically
7. **Print Label** (if needed)

**Tips:**
- Always check stock before dispensing
- Payment must be verified before dispensing
- Stock is automatically deducted

---

### 6. PROCESS LAB ORDER (LAB TECHNICIAN)

**Who Can Do This:** Lab Technician

**Steps:**
1. Go to **"Laboratory Dashboard"** (`/hms/laboratory/`)
2. View **"Pending Orders"** list
3. Click on an order
4. **Verify Payment:**
   - Check if payment is verified
   - If not, send to cashier
5. **Enter Results:**
   - Click **"Enter Results"** button
   - Use tabular entry (for multiple tests)
   - Enter values for each test
   - Mark normal/abnormal
6. **Validate Results:**
   - Review all values
   - Add clinical notes if needed
7. **Release Results:**
   - Click **"Release Results"** button
   - System sends SMS to patient
   - Results available in patient record
8. **Print Report:**
   - Click **"Print Report"** button
   - Professional report with hospital logo

**Tips:**
- Critical values are highlighted
- SMS notification sent automatically
- Reports can be printed anytime

---

### 7. PROCESS PAYMENT (CASHIER)

**Who Can Do This:** Cashier

**Steps:**
1. Go to **"Cashier Dashboard"** (`/hms/cashier/central/`)
2. **Option A - Patient Bills:**
   - Click **"Patient Bills"** tab
   - Search patient by name or MRN
   - View all pending services
   - Select services to pay
   - Enter payment amount
   - Click **"Process Payment"**
3. **Option B - All Pending:**
   - Click **"All Pending"** tab
   - View all unpaid services
   - Filter by department
   - Process individual payments
4. **Generate Receipt:**
   - System generates receipt automatically
   - QR code included
   - Click **"Print Receipt"** button
5. **Payment Methods:**
   - Cash
   - Mobile Money
   - Card
   - Insurance (if applicable)

**Tips:**
- Receipts have QR codes for verification
- All payments sync to accounting automatically
- Can process partial payments

---

### 8. VIEW PATIENT RECORD

**Who Can Do This:** All clinical staff

**Steps:**
1. Go to **"Patients"** (`/hms/patients/`)
2. Search patient by name or MRN
3. Click on patient name
4. **Patient Profile Shows:**
   - Demographics
   - Medical history
   - Allergies
   - Current medications
   - Insurance information
5. **View Encounters:**
   - Click **"Encounters"** tab
   - See all visits
   - Click on encounter for details
6. **View Lab Results:**
   - Click **"Lab Results"** tab
   - See all test results
   - Print reports
7. **View Prescriptions:**
   - Click **"Prescriptions"** tab
   - See medication history
8. **View Vitals:**
   - Click **"Vital Signs"** tab
   - See vital signs history

---

### 9. USE CHAT SYSTEM

**Who Can Do This:** All staff

**Steps:**
1. Go to **"Chat"** (`/hms/chat/`)
2. **View Online Users:**
   - See list of online staff
   - Green indicator shows online status
3. **Start Chat:**
   - Click on a user from online list
   - Or browse by department
   - Select department from dropdown
   - Click on user to chat
4. **Send Message:**
   - Type message in input box
   - Press Enter or click Send
   - Message appears instantly
5. **Receive Messages:**
   - Messages appear automatically
   - Sound notification plays
   - Browser notification shows
6. **View Notifications:**
   - Red badge shows unread count
   - Click to view notifications

**Tips:**
- Messages are real-time (updates every 1 second)
- Can chat with anyone in the system
- Messages are private between users

---

### 10. GENERATE REPORTS

**Who Can Do This:** Admin, Accountant, Managers

**Steps:**
1. Go to **"Reports"** (`/hms/reports/`)
2. **Financial Reports:**
   - Revenue Reports
   - AR Aging Report
   - Payment Reports
   - Select date range
   - Click **"Generate Report"**
3. **Clinical Reports:**
   - Patient Reports
   - Encounter Reports
   - Lab Reports
4. **Operational Reports:**
   - Appointment Reports
   - Bed Occupancy
   - Department Reports
5. **Export Options:**
   - View on screen
   - Export to PDF
   - Export to Excel

---

## 🔄 COMMON WORKFLOWS

### Workflow 1: New Patient Visit

```
1. Receptionist registers patient
   ↓
2. Receptionist books appointment
   ↓
3. Nurse records vital signs
   ↓
4. Doctor starts consultation
   ↓
5. Doctor prescribes medications
   ↓
6. Doctor orders lab tests
   ↓
7. Patient goes to cashier for payment
   ↓
8. Patient goes to pharmacy (if medication prescribed)
   ↓
9. Patient goes to lab (if tests ordered)
   ↓
10. Lab technician processes tests
   ↓
11. Results sent to patient via SMS
   ↓
12. Patient can view results online
```

### Workflow 2: Admission Process

```
1. Doctor decides to admit patient
   ↓
2. Go to "Admissions" → "New Admission"
   ↓
3. Select patient and encounter
   ↓
4. Select ward and bed
   ↓
5. Enter admission details
   ↓
6. System assigns bed automatically
   ↓
7. Bed status changes to "Occupied"
   ↓
8. Daily bed charges start
   ↓
9. Nurse monitors patient
   ↓
10. Doctor updates care plan
   ↓
11. When ready, process discharge
   ↓
12. Bed automatically vacated
```

### Workflow 3: Lab Test Process

```
1. Doctor orders lab test during consultation
   ↓
2. Order appears in lab dashboard
   ↓
3. Patient pays at cashier
   ↓
4. Payment verified in lab system
   ↓
5. Lab technician collects sample
   ↓
6. Lab technician enters results
   ↓
7. Results validated
   ↓
8. Results released
   ↓
9. SMS sent to patient automatically
   ↓
10. Results available in patient record
   ↓
11. Doctor can view results in consultation
```

---

## 🆘 TROUBLESHOOTING

### Problem: Can't Login
**Solution:**
- Check username and password
- Account may be locked (5 failed attempts)
- Contact admin to unlock account
- Clear browser cache and try again

### Problem: Can't See Online Users in Chat
**Solution:**
- Refresh page (Ctrl + Shift + R)
- Check if other users are logged in
- Wait a few seconds (updates every 5 seconds)
- Check browser console for errors

### Problem: Payment Not Showing
**Solution:**
- Wait a few seconds (auto-sync happens)
- Refresh the page
- Check if payment was processed correctly
- Verify in accounting dashboard

### Problem: Stock Not Updating
**Solution:**
- Refresh page
- Check if medication was dispensed
- Verify in inventory dashboard
- Contact admin if issue persists

### Problem: SMS Not Sending
**Solution:**
- Check SMS settings in admin
- Verify phone number format
- Check SMS logs in admin
- Contact IT if issue persists

### Problem: Can't Access Feature
**Solution:**
- Check your role permissions
- Contact admin to grant access
- Verify you're logged in with correct account
- Check if feature is enabled

---

## 📋 QUICK REFERENCE

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| New Patient | `Ctrl + N` (on patients page) |
| Search | `Ctrl + F` (in search boxes) |
| Prescribe Tab | `Alt + 1` |
| Lab Tests Tab | `Alt + 2` |
| Diagnosis Tab | `Alt + 3` |
| History Tab | `Alt + 4` |
| Send Message | `Enter` (in chat) |
| Refresh | `F5` or `Ctrl + R` |
| Hard Refresh | `Ctrl + Shift + R` |

### Important URLs

| Feature | URL |
|---------|-----|
| Login | `/hms/login/` |
| Main Dashboard | `/hms/` |
| Patients | `/hms/patients/` |
| Appointments | `/hms/frontdesk/appointments/` |
| Pharmacy | `/hms/pharmacy/` |
| Laboratory | `/hms/laboratory/` |
| Cashier | `/hms/cashier/central/` |
| Chat | `/hms/chat/` |
| Reports | `/hms/reports/` |

### Status Indicators

| Symbol | Meaning |
|--------|---------|
| ✅ | In Stock / Available / Completed |
| ⚠️ | Low Stock / Warning / Pending |
| ❌ | Out of Stock / Error / Cancelled |
| 🟢 | Online / Active |
| 🔴 | Offline / Inactive |
| 🟡 | Pending / Processing |

### Priority Levels

| Priority | Meaning | Timeframe |
|----------|---------|-----------|
| STAT | Statim (Immediate) | < 1 hour |
| Urgent | Urgent | < 4 hours |
| Routine | Routine | < 24 hours |

---

## 📞 SUPPORT

### Getting Help

1. **Check Documentation:** Review this guide first
2. **Contact IT:** For technical issues
3. **Contact Admin:** For access/permission issues
4. **Check System Health:** `/hms/admin/system-health/`

### Training Resources

- **Video Tutorials:** (Link to be added)
- **User Manual:** This document
- **FAQ:** (Link to be added)
- **System Updates:** Check announcements

---

## ✅ TRAINING CHECKLIST

### For New Users:

- [ ] Login successfully
- [ ] Navigate dashboard
- [ ] Understand role permissions
- [ ] Complete basic task in your role
- [ ] Use search function
- [ ] Generate a report
- [ ] Use chat system
- [ ] Know where to get help

### For Receptionists:

- [ ] Register a new patient
- [ ] Book an appointment
- [ ] Search for patient
- [ ] Update patient information

### For Nurses:

- [ ] Record vital signs
- [ ] View patient record
- [ ] Monitor patients
- [ ] Use triage system

### For Doctors:

- [ ] Start consultation
- [ ] Prescribe medication
- [ ] Order lab tests
- [ ] Add diagnosis
- [ ] Write clinical notes

### For Pharmacists:

- [ ] View pending prescriptions
- [ ] Check stock levels
- [ ] Verify payment
- [ ] Dispense medication

### For Lab Technicians:

- [ ] View lab orders
- [ ] Enter results
- [ ] Release results
- [ ] Print reports

### For Cashiers:

- [ ] Process payment
- [ ] Generate receipt
- [ ] View patient bills
- [ ] Handle refunds

---

**Last Updated:** December 2025  
**Version:** 2.0  
**Status:** Production Ready











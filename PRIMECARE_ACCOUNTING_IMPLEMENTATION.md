# Primecare Medical Centre - Accounting System Implementation

## Overview

This document describes the implementation of the accounting system for Primecare Medical Centre based on the technical and professional guide provided by Francis Bismark Mensah, CA, MCIT.

## ✅ Completed Features

### 1. Chart of Accounts Structure
- **Location**: `hospital/management/commands/setup_primecare_chart_of_accounts.py`
- **Command**: `python manage.py setup_primecare_chart_of_accounts`
- **Structure**:
  - Assets (1000-1999): Current and Non-Current Assets
  - Liabilities (2000-2999): Current and Non-Current Liabilities
  - Equity (3000-3999): Share Capital, Reserves, Retained Earnings
  - Revenue (4000-4999): All revenue categories (Registration, Consultation, Lab, Pharmacy, etc.)
  - Expenses (5000-5999): Cost of Sales and Operating Expenses

### 2. Revenue Recognition Models
- **Location**: `hospital/models_primecare_accounting.py`

#### UndepositedFunds Model
- Tracks cash receipts before bank deposit
- Holds revenue breakdown by category
- After 24 hours, matches to revenue accounts
- Creates journal entries: Debit Revenue, Credit Undeposited Funds

#### InsuranceReceivableEntry Model
- Tracks credit sales (insurance receivables)
- After 48 hours, matches to revenue accounts
- Creates journal entries: Debit AR, Credit Revenue
- Tracks payment status (pending, matched, partially_paid, paid)

#### InsurancePaymentReceived Model
- Records insurance payments with rejections and WHT
- Creates accounting entries:
  - Debit: Bank Account (amount received)
  - Debit: Rejection Account (amount rejected)
  - Debit: WHT Receivable (withholding tax)
  - Credit: Accounts Receivable (total amount)

### 3. User Interfaces

#### Record Deposit Interface
- **URL**: `/hms/primecare/record-deposit/`
- **View**: `views_primecare_accounting.record_deposit`
- **Function**: Moves funds from Undeposited Funds to Bank Account
- **Features**:
  - Select multiple undeposited funds entries
  - Choose bank account
  - Enter deposit reference
  - Automatically creates journal entries

#### Received Payment Interface
- **URL**: `/hms/primecare/received-payment/`
- **View**: `views_primecare_accounting.received_payment`
- **Function**: Records insurance payments with rejections and WHT
- **Features**:
  - Select insurance company (payer)
  - Link to receivable entry (optional)
  - Enter amounts: received, rejected, WHT
  - Automatically calculates and creates accounting entries

## 📋 Setup Instructions

### Step 1: Run Migrations
```bash
# Create migration for new models
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

### Step 2: Setup Chart of Accounts
```bash
python manage.py setup_primecare_chart_of_accounts
```

This will create all accounts according to the Primecare structure.

### Step 3: Create Bank Accounts
Before using the Record Deposit interface, you need to create Bank Account records:
1. Go to Admin panel
2. Navigate to Bank Accounts
3. Create bank accounts (e.g., UMB Bank Account)
4. Link each bank account to the corresponding Account (e.g., 1020 for UMB)

### Step 4: Access Interfaces
- Record Deposit: http://your-domain/hms/primecare/record-deposit/
- Received Payment: http://your-domain/hms/primecare/received-payment/

## 🔄 Revenue Recognition Workflow

### Cash Revenue (24-hour hold)
1. **Cash Receipt**: Patient pays cash for services
2. **Undeposited Funds Entry**: System creates UndepositedFunds entry with revenue breakdown
3. **After 24 Hours**: Accountant matches to revenue accounts
   - Debit: Revenue accounts (Registration, Consultation, etc.)
   - Credit: Undeposited Funds
4. **Bank Deposit**: Accountant records deposit
   - Debit: Bank Account
   - Credit: Undeposited Funds

### Credit Revenue (48-hour hold)
1. **Credit Sale**: Services provided to insurance patient
2. **Receivable Entry**: System creates InsuranceReceivableEntry with revenue breakdown
3. **After 48 Hours**: Accountant matches to revenue accounts
   - Debit: Accounts Receivable (Insurance Company)
   - Credit: Revenue accounts
4. **Payment Received**: Insurance pays (with rejections/WHT)
   - Debit: Bank Account (received)
   - Debit: Rejection Account (rejected)
   - Debit: WHT Receivable (tax)
   - Credit: Accounts Receivable (total)

## 📊 Account Codes Reference

### Revenue Accounts
- 4100: Registration Revenue
- 4110: Consultation Revenue
- 4120: Laboratory Revenue
- 4130: Pharmacy Revenue
- 4140: Surgeries Revenue
- 4150: Admissions & Professional Care Revenue
- 4160: Radiology Revenue
- 4170: Dental Revenue
- 4180: Physiotherapy Revenue

### Key Asset Accounts
- 1010: Cash and Cash Equivalents
- 1015: Undeposited Funds
- 1020: Bank Account - UMB
- 1200: Trade Receivables
- 1300: Withholding Tax Receivable

### Key Expense Accounts
- 5200: Bills Rejections
- 5210: Salaries (Basic + Allowances)
- 5211: 13% Employer's SSF

## 🚧 Pending Tasks

### 1. Templates
Need to create HTML templates:
- `hospital/templates/hospital/primecare/record_deposit.html`
- `hospital/templates/hospital/primecare/received_payment.html`

### 2. Balance Sheet Report
- Implement Balance Sheet matching IAS 1 format
- Include all required sections from document
- Add year comparison functionality

### 3. Profit & Loss Report
- Implement P&L matching document format
- Include all revenue categories
- Add monthly and quarterly views
- Add percentage of revenue calculations

### 4. Revenue Matching Automation
- Create scheduled task to auto-match cash revenue after 24 hours
- Create scheduled task to auto-match credit revenue after 48 hours
- Add notification system for pending matches

### 5. Admin Integration
- Register models in admin panel
- Add admin actions for bulk operations
- Create admin filters and search

## 📝 Notes

- All models use the `BaseModel` which includes `is_deleted` and soft delete functionality
- Journal entries are automatically posted to General Ledger
- All amounts use Decimal precision (15,2)
- System follows double-entry bookkeeping principles
- All transactions are auditable with user tracking

## 🔗 Related Files

- Models: `hospital/models_primecare_accounting.py`
- Views: `hospital/views_primecare_accounting.py`
- URLs: Added to `hospital/urls.py`
- Setup Command: `hospital/management/commands/setup_primecare_chart_of_accounts.py`

## 📞 Support

For questions or issues, refer to the technical guide document or contact the accounting team.















# System Reset - Complete Financial Data Reset

## ✅ **COMPLETED TASKS**

### 1. **Financial Data Reset Command Created**
   - **Location**: `hospital/management/commands/reset_all_financial_data.py`
   - **Purpose**: Comprehensive reset of all financial data to start fresh
   - **Usage**: `python manage.py reset_all_financial_data --confirm`

### 2. **What Gets Reset**

The command clears the following data:

#### **Encounters**
- All patient encounters (marked as deleted)

#### **Payments & Transactions**
- All Payment Receipts
- All Transactions
- All Payment Allocations

#### **Outstanding Balances**
- All Accounts Receivable entries
- All Advanced Accounts Receivable entries
- Invoice balances reset to full amount
- Invoice status reset to 'issued' (except drafts)

#### **Revenues**
- All Revenue records
- All Department Revenue records
- All Revenue Stream data

#### **Accounting Records**
- All General Ledger entries
- All Advanced General Ledger entries
- All Journal Entries
- All Journal Entry Lines
- All Advanced Journal Entry Lines

#### **Other Financial Data**
- Payment Requests
- Bills
- Ambulance Billings
- Patient Deposits (balances reset)
- Telemedicine Payments
- Insurance Payments

### 3. **Receipt Printer Settings Optimized**

**File**: `hospital/templates/hospital/receipt_pos.html`

#### **POS Receipt Dimensions**
- **Width**: 80mm (standard thermal printer width)
- **Page Size**: `80mm auto` (auto height)
- **Margins**: 0mm (no margins for thermal printers)
- **Padding**: 3mm 2mm (minimal padding)

#### **Print Optimizations**
- Proper `@page` CSS rules for thermal printers
- Font size: 11px (optimal for 80mm receipts)
- Monospace font (Courier New) for consistent alignment
- Color adjustment settings for thermal printers
- Page break avoidance for receipt content

#### **Features**
- Auto-print support (via `?auto_print=1` query parameter)
- QR code verification
- Proper formatting for thermal printers
- Print-friendly styling

---

## 🚀 **HOW TO USE**

### **Reset All Financial Data**

```bash
# First, see the warning (no data deleted)
python manage.py reset_all_financial_data

# To actually reset, use --confirm flag
python manage.py reset_all_financial_data --confirm
```

### **What Happens**
1. All encounters are marked as deleted
2. All payments and receipts are deleted
3. All outstanding balances are cleared
4. All revenues are reset
5. All accounting entries are cleared
6. Invoice balances are reset to full amounts
7. System is ready for fresh start

### **Important Notes**
- ⚠️ **This action CANNOT be undone!**
- All financial data will be permanently deleted
- Patient records are NOT deleted (only encounters)
- Account structure is preserved (only balances reset)
- Staff and user accounts are NOT affected

---

## 📋 **RECEIPT PRINTER SETTINGS**

### **POS Receipt Template**
- **File**: `hospital/templates/hospital/receipt_pos.html`
- **Dimensions**: 80mm width (standard thermal printer)
- **Print Settings**: Optimized for thermal receipt printers

### **Access Receipt Print**
- **URL**: `/hms/receipt/pos/{receipt_id}/`
- **Auto-print**: Add `?auto_print=1` to URL
- **Standard Print**: `/hms/receipt/{receipt_id}/print/`

### **Receipt Features**
- Hospital name and contact information
- Receipt number and date/time
- Patient information (name, MRN, phone)
- Payment method and reference
- Amount paid (large, bold)
- QR code for verification
- Footer with thank you message

---

## ✅ **VERIFICATION CHECKLIST**

After running the reset command, verify:

- [ ] All encounters cleared
- [ ] All payments deleted
- [ ] All invoices have balance = total_amount
- [ ] All revenues cleared
- [ ] General Ledger is empty
- [ ] Accounts Receivable is empty
- [ ] Receipt printer settings correct (80mm width)
- [ ] Receipt template displays properly
- [ ] System ready for new transactions

---

## 🔧 **TROUBLESHOOTING**

### **Command Not Found**
```bash
# Make sure you're in the project directory
cd d:\chm
python manage.py reset_all_financial_data --confirm
```

### **Import Errors**
- Check that all models are properly imported
- Verify model names match actual class names
- Check for any missing dependencies

### **Receipt Print Issues**
- Verify browser print settings
- Check printer is set to 80mm thermal paper
- Ensure CSS print media queries are working
- Test with different browsers

---

## 📝 **SUMMARY**

✅ **System Reset Command**: Created and ready to use
✅ **Receipt Printer Settings**: Optimized for 80mm thermal printers
✅ **All Financial Data**: Can be cleared with single command
✅ **Fresh Start**: System ready for new accounting period

**The system is now ready for a fresh start with all previous financial data cleared!**

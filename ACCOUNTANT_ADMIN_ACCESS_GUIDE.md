# 🔍 Accountant Admin Access Guide

## ✅ Permissions Granted!

All accountants now have admin access to accounting models. After **logging out and logging back in**, you can access:

## 📋 Admin URLs for Accounting Models

### **Insurance Receivable Entry** (The imported records from JERRY.xlsx)
```
http://192.168.2.216:8000/admin/hospital/insurancereceivableentry/
```
This shows the 21 imported insurance receivable entries.

### **Insurance Receivable** (Old model - requires patient/invoice)
```
http://192.168.2.216:8000/admin/hospital/insurancereceivable/
```
This shows receivables linked to specific patients/invoices.

### **Insurance Payment Received**
```
http://192.168.2.216:8000/admin/hospital/insurancepaymentreceived/
```

### **Undeposited Funds**
```
http://192.168.2.216:8000/admin/hospital/undepositedfunds/
```

### **Accounts Payable** (The imported creditor records)
```
http://192.168.2.216:8000/admin/hospital/accountspayable/
```
This shows the 52 imported accounts payable entries.

### **Other Accounting Models:**
- Journal Entries: `/admin/hospital/advancedjournalentry/`
- General Ledger: `/admin/hospital/advancedgeneralledger/`
- Payment Vouchers: `/admin/hospital/paymentvoucher/`
- Cashbook: `/admin/hospital/cashbook/`
- And many more...

## 🎯 Quick Access Links

### **View Imported Insurance Receivables:**
Go to: **Insurance Receivable Entry** (NOT Insurance Receivable)
```
http://192.168.2.216:8000/admin/hospital/insurancereceivableentry/
```

### **View Imported Accounts Payable:**
```
http://192.168.2.216:8000/admin/hospital/accountspayable/
```

## ⚠️ Important Notes

1. **Two Different Models:**
   - `InsuranceReceivable` - Requires patient and invoice (shows 0 because we didn't import these)
   - `InsuranceReceivableEntry` - Opening balances from JERRY.xlsx (shows 21 records) ✅

2. **After Logging Back In:**
   - You'll see all accounting models in the admin sidebar
   - You can add, change, delete, and view all accounting records
   - All permissions are active

3. **If You Don't See Records:**
   - Make sure you're looking at `insurancereceivableentry` (not `insurancereceivable`)
   - Check the URL matches exactly
   - Try refreshing the page

## 🔍 Finding Records in Admin

### **Search in Admin:**
- Use the search box to find specific entries
- Filter by status, date, or insurance company
- Use the date hierarchy to browse by date

### **Direct Access:**
To view a specific entry:
```
http://192.168.2.216:8000/admin/hospital/insurancereceivableentry/{entry_id}/change/
```

Replace `{entry_id}` with the actual ID (e.g., `e75999d1-dbcd-446b-b6f9-194998eb32e7`)

---

**Status:** ✅ All permissions granted! Just log out and log back in to activate them.



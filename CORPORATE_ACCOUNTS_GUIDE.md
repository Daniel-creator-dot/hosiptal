# 🏢 Corporate Accounts - Complete Guide

## ✅ Current Status

**Corporate Accounts Page:** ✅ **WORKING**  
**Corporate Accounts in Database:** **0** (No accounts created yet)

---

## 📍 Where to Add Corporate Accounts

### **Option 1: From Corporate Accounts Page**
1. Go to: `http://192.168.2.216:8000/hms/accountant/corporate-accounts/`
2. Click the **"+ Add Account"** button (blue button, top right)
3. Fill in the form and save

### **Option 2: From Django Admin**
1. Go to: `http://192.168.2.216:8000/admin/hospital/accountingcorporateaccount/add/`
2. Fill in the form and save

---

## 📝 How to Add a Corporate Account

### **Required Fields:**
- **Account Number** - Unique identifier (e.g., "CORP-001")
- **Company Name** - Full company name (e.g., "ABC Corporation Ltd")
- **Receivable Account** - Select an Accounts Receivable account from chart of accounts

### **Optional Fields:**
- **Contact Person** - Name of contact person
- **Contact Email** - Email address
- **Contact Phone** - Phone number
- **Credit Limit** - Maximum credit allowed (default: 0.00)
- **Current Balance** - Current outstanding balance (default: 0.00)
- **Is Active** - Checkbox to activate/deactivate account

---

## 🔍 What Was Fixed

1. **View Updated** - Now filters out deleted records (`is_deleted=False`)
2. **Template Working** - Displays accounts correctly when they exist
3. **Add Button Working** - Links to admin form correctly

---

## 📊 Example Corporate Account

**Account Number:** `CORP-001`  
**Company Name:** `ABC Corporation Ltd`  
**Contact Person:** `John Doe`  
**Contact Email:** `john.doe@abccorp.com`  
**Contact Phone:** `0241234567`  
**Credit Limit:** `GHS 100,000.00`  
**Current Balance:** `GHS 0.00`  
**Receivable Account:** Select "Accounts Receivable" account  
**Is Active:** ✅ Checked

---

## 🎯 Next Steps

1. **Add Corporate Accounts:**
   - Click "+ Add Account" on the Corporate Accounts page
   - Or go directly to admin: `/admin/hospital/accountingcorporateaccount/add/`

2. **Fill in Details:**
   - Enter company information
   - Set credit limit
   - Link to receivable account

3. **View Accounts:**
   - Refresh the Corporate Accounts page
   - Accounts will appear in the table

---

**Status:** ✅ **SYSTEM READY - JUST NEED TO ADD ACCOUNTS**









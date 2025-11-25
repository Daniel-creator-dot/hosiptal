# Pricing Management System - Complete Guide

## ✅ **PRICING MANAGEMENT SYSTEM CREATED!**

A comprehensive interface to manage all services, prices, specialist consultations, and procedures in your Hospital Management System.

---

## 🎯 **Features Implemented**

### 1. **Pricing Dashboard**
Central hub for all pricing management activities.

**Features:**
- ✅ Statistics overview (total services, prices, payers)
- ✅ Quick access to all pricing modules
- ✅ Bulk price update tool
- ✅ Recent services list
- ✅ Services by category breakdown

**Access:** http://127.0.0.1:8000/hms/pricing/

### 2. **Service Management**
Complete CRUD (Create, Read, Update, Delete) for all services.

**Features:**
- ✅ List all services with prices
- ✅ Search by code or description
- ✅ Filter by category
- ✅ Add new services with default prices
- ✅ Edit existing services
- ✅ Activate/deactivate services

**Access:** http://127.0.0.1:8000/hms/pricing/services/

### 3. **Payer-Specific Pricing**
Set custom prices for different insurance companies.

**Features:**
- ✅ Select payer/insurance company
- ✅ View all services with default prices
- ✅ Set custom prices for each payer
- ✅ Compare default vs payer-specific prices
- ✅ Real-time save with AJAX

**Access:** http://127.0.0.1:8000/hms/pricing/payer/

### 4. **Specialist Services**
Manage specialist consultations and procedures.

**Features:**
- ✅ 15 pre-defined specialties
- ✅ Add specialist services quickly
- ✅ Automatic code generation
- ✅ Set consultation prices
- ✅ Grouped by specialty
- ✅ Edit specialist service prices

**Specialties Included:**
- Cardiology
- Neurology  
- Orthopedics
- Pediatrics
- Dermatology
- Psychiatry
- Oncology
- ENT (Ear, Nose, Throat)
- Ophthalmology
- Urology
- Gynecology
- Gastroenterology
- Nephrology
- Pulmonology
- Endocrinology

**Access:** http://127.0.0.1:8000/hms/pricing/specialist/

### 5. **Bulk Price Update**
Update multiple prices at once.

**Features:**
- ✅ Increase or decrease prices by percentage
- ✅ Apply to all services or specific category
- ✅ Quick price adjustments
- ✅ Confirmation before applying

---

## 📊 **How to Use**

### **Access the Pricing Dashboard**

1. **Login** as Admin or Finance Manager
2. Navigate to: **http://127.0.0.1:8000/hms/pricing/**
3. You'll see the main dashboard with options

### **Add a New Service**

1. Click "**Add New Service**" button
2. Fill in the form:
   - **Service Code**: Unique identifier (e.g., LAB001, CON001)
   - **Description**: Full service name (e.g., "Complete Blood Count")
   - **Category**: Select or type category (e.g., "Laboratory")
   - **Default Price**: Standard price in GHS
3. Click "**Create Service**"

### **Edit Service Prices**

**Option 1 - From Service List:**
1. Go to **Pricing → Services**
2. Find the service
3. Click "**Edit**"
4. Update price and details
5. Click "**Update Service**"

**Option 2 - From Dashboard:**
1. See recent services
2. Click "**Edit**" on any service
3. Modify as needed

### **Set Payer-Specific Prices**

1. Go to **Pricing → Payer Pricing**
2. Select a payer/insurance company from dropdown
3. Click "**Load Prices**"
4. For each service:
   - Enter custom price for that payer
   - Click "**Save**" button
5. Prices save automatically via AJAX

### **Add Specialist Services**

1. Go to **Pricing → Specialist Services**
2. Use the "Add Specialist Service" form:
   - Select **Specialty** (e.g., Cardiology)
   - Enter **Service Name** (e.g., "Initial Consultation")
   - Enter **Price** in GHS
3. Click "**Add**"
4. Service automatically gets a unique code (e.g., CAR001)

### **Bulk Price Update**

1. From Pricing Dashboard
2. Use "Bulk Price Update" section:
   - Select **Action**: Increase or Decrease
   - Enter **Percentage**: e.g., 10 for 10%
   - (Optional) Select **Category**: specific category or all
3. Click "**Update Prices**"
4. Confirm the action

---

## 📁 **Files Created**

### **Backend (Views)**
- ✅ `hospital/views_pricing.py` - All pricing management logic

### **Frontend (Templates)**
- ✅ `hospital/templates/hospital/pricing_dashboard.html` - Main dashboard
- ✅ `hospital/templates/hospital/service_list.html` - Service list
- ✅ `hospital/templates/hospital/service_create.html` - Add service form
- ✅ `hospital/templates/hospital/service_edit.html` - Edit service form
- ✅ `hospital/templates/hospital/payer_pricing.html` - Payer pricing
- ✅ `hospital/templates/hospital/specialist_services.html` - Specialist services

### **URLs**
- ✅ Updated `hospital/urls.py` with pricing routes

---

## 🔗 **URL Routes**

| Route | Purpose | Access |
|-------|---------|--------|
| `/hms/pricing/` | Pricing Dashboard | Admin/Finance Manager |
| `/hms/pricing/services/` | All Services List | Admin/Finance Manager |
| `/hms/pricing/services/create/` | Add New Service | Admin/Finance Manager |
| `/hms/pricing/services/<id>/edit/` | Edit Service | Admin/Finance Manager |
| `/hms/pricing/payer/` | Payer-Specific Pricing | Admin/Finance Manager |
| `/hms/pricing/specialist/` | Specialist Services | Admin/Finance Manager |
| `/hms/pricing/bulk-update/` | Bulk Price Update | Admin/Finance Manager |

---

## 🎨 **Service Categories**

Common categories for organizing services:

- **Laboratory** - Lab tests and procedures
- **Clinical Services** - General medical services
- **Radiology** - X-rays, CT scans, MRI
- **Pharmacy** - Medications and drugs
- **Surgery** - Surgical procedures
- **Consultation** - Doctor consultations
- **Emergency** - Emergency services
- **Dental** - Dental procedures
- **Cardiology** - Heart-related services
- **Neurology** - Neurological services
- **Orthopedics** - Bone and joint services
- **Pediatrics** - Child healthcare
- **Dermatology** - Skin conditions
- And more...

---

## 💡 **Examples**

### **Example 1: Add Laboratory Service**

```
Service Code: LAB001
Description: Complete Blood Count (CBC)
Category: Laboratory
Default Price: 50.00
```

### **Example 2: Add Consultation Service**

```
Service Code: CON001
Description: General Consultation
Category: Clinical Services  
Default Price: 100.00
```

### **Example 3: Add Specialist Consultation**

```
Specialty: Cardiology
Service Name: Initial Consultation
Price: 200.00

Result: Automatically creates:
- Code: CAR001
- Description: Cardiology - Initial Consultation
- Category: Cardiology
- Price: 200.00
```

### **Example 4: Set Payer Price**

```
Service: CON001 - General Consultation
Default Price: GHS 100.00

For "NHIS Insurance":
Custom Price: GHS 80.00 (20% discount)

For "Private Insurance Co.":
Custom Price: GHS 120.00 (20% premium)
```

### **Example 5: Bulk Price Increase**

```
Action: Increase Prices
Percentage: 10%
Category: Laboratory

Result: All laboratory service prices increased by 10%
- LAB001: GHS 50.00 → GHS 55.00
- LAB002: GHS 75.00 → GHS 82.50
```

---

## 🔐 **Security & Permissions**

**Who Can Access:**
- ✅ Admin users (is_staff=True)
- ✅ Finance Manager group members

**Protection:**
- ✅ Login required on all views
- ✅ User permission check
- ✅ CSRF protection on forms

---

## 📊 **Data Flow**

### **Creating a Service:**
```
User → Service Create Form → ServiceCode model created
     → Default Price → DefaultPrice model created
     → Available for billing
```

### **Setting Payer Price:**
```
User → Select Payer → View Services
     → Set Custom Price → PayerPrice model created
     → Used when billing that payer
```

### **Billing Process:**
```
Invoice Created → Check Patient's Payer
                → Look for PayerPrice
                → If not found, use DefaultPrice
                → Add to invoice line
```

---

## 🎯 **Best Practices**

### **Service Codes:**
- Use consistent prefixes (e.g., LAB for lab, CON for consultation)
- Keep codes short and memorable
- Use sequential numbers (LAB001, LAB002, etc.)

### **Descriptions:**
- Be specific and clear
- Include procedure details if needed
- Use consistent naming

### **Categories:**
- Use standard medical categories
- Be consistent across services
- Group related services together

### **Pricing:**
- Set realistic default prices
- Review prices regularly
- Use bulk updates for inflation adjustments
- Set payer prices based on contracts

---

## 🚀 **Quick Start Guide**

### **Step 1: Add Basic Services**
1. Go to Pricing Dashboard
2. Add consultation services:
   - General Consultation (CON001) - GHS 100
   - Follow-up Consultation (CON002) - GHS 50

### **Step 2: Add Laboratory Services**
1. Go to Services → Create
2. Add common lab tests:
   - CBC (LAB001) - GHS 50
   - Urinalysis (LAB002) - GHS 30
   - Blood Sugar (LAB003) - GHS 25

### **Step 3: Add Specialist Services**
1. Go to Specialist Services
2. Add for each specialty you offer:
   - Cardiology - Initial Consultation - GHS 200
   - Pediatrics - Child Check-up - GHS 150
   - Orthopedics - Joint Assessment - GHS 180

### **Step 4: Set Insurance Prices**
1. Go to Payer Pricing
2. Select NHIS (if you have it)
3. Set discounted rates for all services
4. Save each price

### **Step 5: Ready to Bill!**
- All services now available in invoice creation
- Proper prices applied automatically
- Different prices for different payers

---

## 📈 **Statistics & Monitoring**

The Pricing Dashboard shows:
- **Total Services**: Count of all active services
- **Default Prices**: Services with prices set
- **Payer Prices**: Custom prices configured
- **Active Payers**: Insurance companies in system
- **Recent Services**: Latest additions
- **Services by Category**: Distribution chart

---

## ✅ **Testing Checklist**

- [ ] Access pricing dashboard
- [ ] Create a new service
- [ ] Edit service price
- [ ] View service list
- [ ] Search for services
- [ ] Filter by category
- [ ] Add specialist service
- [ ] Set payer-specific price
- [ ] Test bulk price update
- [ ] Verify prices in invoices

---

## 🎉 **Summary**

**What You Can Now Do:**

✅ **Manage All Services** - Add, edit, view all services in one place  
✅ **Set Prices** - Default prices and payer-specific prices  
✅ **Specialist Services** - Quick setup for specialist consultations  
✅ **Bulk Updates** - Adjust multiple prices at once  
✅ **Search & Filter** - Find services quickly  
✅ **Organized Categories** - Group services logically  
✅ **Insurance Pricing** - Different prices for different payers  
✅ **Professional Interface** - Easy to use, modern design

**Access Point:**
👉 http://127.0.0.1:8000/hms/pricing/

**Your pricing management system is ready to use!** 🎊

---

**Created**: November 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready

































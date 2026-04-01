# 📍 Where to See Your Consultation Prices

## ⚠️ Important: You're Looking at the Wrong Section!

You're currently viewing **"Default Prices"** which only shows:
- Patient Registration
- General Consultation  
- Specialist Consultation
- Vital Signs
- Lab Test
- Imaging
- Pharmacy
- Admission
- Bed Day

**This is NOT where your Excel consultation prices are stored!**

---

## ✅ Correct Location: Service Prices

Your consultation prices from the Excel file are imported into **"Service Prices"**.

### How to View Them:

1. **In Django Admin:**
   - Go to: **Hospital** → **Service Prices**
   - URL: `http://192.168.2.216:8000/admin/hospital/serviceprice/`
   - This shows ALL consultation prices from your Excel

2. **In Pricing Dashboard:**
   - Go to: `http://192.168.2.216:8000/hms/pricing/`
   - Click on any pricing category (Cash, Corporate, Insurance)
   - See all consultation prices

3. **In Price Matrix:**
   - Go to: `http://192.168.2.216:8000/hms/pricing/matrix/`
   - See all services with all price categories side-by-side

---

## 🚀 If Prices Are Not Showing

### Step 1: Run the Import Command

The prices need to be imported first. Run this in Docker:

```bash
docker exec -it <container_name> python manage.py import_consultation_prices --verbose
```

Or use the script:
- Windows: `import_prices_docker.bat`
- Linux/Mac: `./import_prices_docker.sh`

### Step 2: Verify Import

After running the import, you should see:
```
Services processed: 1,549
Prices created: 4,647+
```

### Step 3: Check Service Prices Admin

Go to: `http://192.168.2.216:8000/admin/hospital/serviceprice/`

You should see:
- All consultation services
- Prices for each category (Cash, Corporate, Insurance)
- All insurance company prices

---

## 📊 Admin Sections Explained

### Default Prices
- **Purpose:** Basic service types only
- **Shows:** 9 predefined service types
- **NOT for:** Detailed consultation prices

### Service Prices ✅ (THIS IS WHERE YOUR PRICES ARE)
- **Purpose:** All detailed service prices
- **Shows:** All consultation types from Excel
- **Includes:** Cash, Corporate, Insurance prices
- **URL:** `/admin/hospital/serviceprice/`

### Payer Prices
- **Purpose:** Custom prices for specific payers
- **Shows:** Override prices for specific insurance companies

---

## 🎯 Quick Navigation

### To See All Consultation Prices:

**Option 1: Admin Interface**
```
Hospital → Service Prices
```

**Option 2: Pricing Dashboard**
```
http://192.168.2.216:8000/hms/pricing/
```

**Option 3: Price Matrix**
```
http://192.168.2.216:8000/hms/pricing/matrix/
```

---

## ✅ Summary

- ❌ **Default Prices** = Only 9 basic service types (NOT your consultation prices)
- ✅ **Service Prices** = All consultation prices from Excel (THIS IS WHERE THEY ARE)
- ✅ **Pricing Dashboard** = User-friendly view of all prices
- ✅ **Price Matrix** = Compare all prices side-by-side

---

**Next Steps:**
1. Run the import command if you haven't already
2. Navigate to: **Hospital → Service Prices** in admin
3. Or use the pricing dashboard at `/hms/pricing/`









# 🔍 Fix: Prices Not Showing Due to Date Filter

## ⚠️ Problem Identified

You're on the correct page (**Service Prices**), but a **date filter is hiding your prices**.

The URL shows: `effective_from_gte=2025-12-29&effective_from_lt=2025-12-30`

This filter is looking for prices with effective dates between **December 29-30, 2025** (a future date), but your imported prices have today's date.

---

## ✅ Quick Fix (2 Steps)

### Step 1: Clear the Date Filter

On the right sidebar, you'll see:
- **"↓ By effective from"** filter
- Currently set to a specific date range

**Action:** Click **"X Clear all filters"** at the top of the FILTER section

OR

Set **"↓ By effective from"** to **"Any date"**

### Step 2: Verify Prices Appear

After clearing the filter, you should see all your imported prices!

---

## 🎯 Alternative: Check All Filters

Make sure these filters are set correctly:

1. **"↓ By is active"** → Set to **"All"** (or "Yes" to see only active prices)
2. **"↓ By effective from"** → Set to **"Any date"**
3. Click **"X Clear all filters"** to reset everything

---

## 📊 If Still No Prices

If clearing the filter doesn't show prices, the import may not have run yet.

### Run the Import:

```bash
docker exec -it <container_name> python manage.py import_consultation_prices --verbose
```

Or use the script:
- Windows: `import_prices_docker.bat`
- Linux/Mac: `./import_prices_docker.sh`

---

## ✅ Expected Result

After clearing the filter, you should see:
- All consultation services
- Prices for Cash, Corporate, Insurance categories
- All insurance company prices

---

**Quick Action:** Click **"X Clear all filters"** in the right sidebar now!









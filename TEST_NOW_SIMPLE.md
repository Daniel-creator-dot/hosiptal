# 🧪 Test Duplicate Prevention - Simple Guide

## Step 1: Make Sure Server is Running

Open a new terminal/command prompt and run:
```bash
cd C:\Users\bytz\chm
venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000
```

You should see:
```
Starting development server at http://0.0.0.0:8000/
```

## Step 2: Open Browser

Go to: **http://localhost:8000/hms/patients/new/**

## Step 3: Register First Patient

Fill in:
- **First Name:** `Test`
- **Last Name:** `Duplicate`  
- **Date of Birth:** `1990-01-01`
- **Phone:** `0241234567`
- **Email:** `test@example.com`
- **Gender:** `Male`

Click **"Register Patient"**

✅ **Expected:** Success! Patient created.

## Step 4: Try to Register Same Patient Again

1. Go back to: **http://localhost:8000/hms/patients/new/**
2. Fill in **EXACT SAME** information
3. Click **"Register Patient"** again

❌ **Expected:** Error message "⚠️ Duplicate patient detected!"

## Step 5: Check Patient List

Go to: **http://localhost:8000/hms/patients/**

Search for "Test Duplicate"

✅ **Should find only ONE patient**

---

## ✅ Success = Duplicate Prevention Working!
## ❌ Failure = Still Creating Duplicates


# ⚡ Quick Guide: Add Dr. Kwadwo Ayisi

## 🎯 Easiest Way (Recommended)

### Just Run This:

```bash
ADD_DR_KWADWO_AYISI.bat
```

**That's it!** The script will:
- ✅ Find the user you already created (or create one)
- ✅ Add all staff details automatically
- ✅ Set everything up correctly

---

## 📋 What Gets Added

- **Employee ID:** SPE-DOC-0001
- **Name:** Dr. Kwadwo Ayisi  
- **Department:** Specialist Clinic
- **Profession:** Doctor
- **Phone:** 0246979797
- **Position:** Medical Director and Administrator
- **Age:** 68 years
- **Admin privileges:** Full access

---

## 🔍 If You Need to Specify Username

If the script can't find the user automatically, run:

```bash
docker-compose exec web python manage.py add_medical_director_kwadwo --username YOUR_USERNAME
```

Replace `YOUR_USERNAME` with the actual username you created.

---

## 🌐 Alternative: Use Web Interface

1. Go to: `http://localhost:8000/hms/hr/staff/new/`
2. Select the user you created from dropdown
3. Fill in:
   - Employee ID: `SPE-DOC-0001`
   - Department: Specialist Clinic
   - Profession: Doctor
   - Phone: `0246979797`
   - Specialization: Medical Director and Administrator
4. Save

---

**Ready?** Just run `ADD_DR_KWADWO_AYISI.bat` and you're done! ✅





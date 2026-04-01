# Visit Creation System - Complete Explanation

## Overview
The visit creation tool has been redesigned with a modern UI and doctor-specific pricing system. Here's how it all works:

---

## 🔍 **Why "No Doctors Available" Appears**

The system shows "No doctors available at this time" when the database query finds no doctors matching these criteria:

```python
Staff.objects.filter(
    profession='doctor',        # Must be a doctor
    is_deleted=False,          # Not deleted
    user__isnull=False,         # Has a User account
    user__is_active=True        # User account is active
)
```

### Common Reasons:
1. **No doctors in database** - No Staff records with `profession='doctor'`
2. **Doctors marked as deleted** - `is_deleted=True` on Staff records
3. **No User accounts** - Doctors don't have linked User accounts
4. **Inactive users** - User accounts have `is_active=False`
5. **Wrong profession** - Staff records have different profession values

---

## 💰 **Doctor Pricing System**

### How It Works:

1. **Pricing Configuration** (`utils_doctor_pricing.py`)
   - Each specialist doctor has pricing rules defined
   - Supports first visit vs subsequent visit pricing
   - Controls whether prices are shown in UI

2. **Doctor Matching**
   - System normalizes doctor names (removes "Dr.", spaces, lowercase)
   - Matches by full name, partial name, or last name
   - Example: "Dr. Awah", "Awah", "Dr Awah" all match

3. **Price Display Logic**
   - **Specialists with prices**: Show pricing badges (e.g., "First Visit: GHS 300")
   - **Psychiatrists**: Prices hidden (as requested)
   - **General doctors**: No prices shown (default GHS 150)

4. **First vs Subsequent Visit**
   - System checks patient's previous encounters with the doctor
   - Automatically applies correct pricing:
     - **First visit**: Higher price (if different)
     - **Subsequent visit**: Lower price (if different)

---

## 📋 **Pricing Rules Implemented**

| Doctor | Specialty | First Visit | Subsequent | Show Price? |
|--------|-----------|------------|------------|-------------|
| Dr. Awah | Physician Specialist | GHS 300 | GHS 300 | ✅ Yes |
| Ofosu Sylvester | Dietitian | GHS 150 | GHS 150 | ✅ Yes |
| Dr. Elikem Kumah | Dental Surgeon | GHS 150 | GHS 150 | ✅ Yes |
| Dr. Eugene Owusu-Achaw | ENT Specialist | GHS 260 | GHS 260 | ✅ Yes |
| Dr. Ali Samba | Gynaecology | GHS 260 | GHS 260 | ✅ Yes |
| Dr. Ali Samba | ANC | GHS 235 | GHS 235 | ✅ Yes |
| Titiati Edem | Physiotherapist | GHS 250 | GHS 150 | ✅ Yes |
| Dr. Boakye | Urologist | GHS 250 | GHS 250 | ✅ Yes |
| Dr. Brako Emmanuel | Ophthalmologist | GHS 150 | GHS 150 | ✅ Yes |
| Dr. Adigah Boniface | General Surgeon | GHS 260 | GHS 260 | ✅ Yes |
| Dr. Sheila Appiah-Pippim | Psychiatrist | GHS 350 | GHS 300 | ❌ No |
| Dr. Rebecca Abalo | Psychiatrist | GHS 350 | GHS 300 | ❌ No |
| Dr. Lartey Lorna | Psychiatrist | GHS 350 | GHS 300 | ❌ No |
| Dr. Mustapha Dadzie | Psychiatrist | GHS 350 | GHS 300 | ❌ No |
| Dr. Kojo Ahor-Essel | Paediatrician | GHS 260 | GHS 260 | ✅ Yes |
| Other Doctors | General | GHS 150 | GHS 150 | ❌ No |

---

## 🎨 **UI Features**

### Modern Design Elements:
1. **Card-based Doctor Selection**
   - Doctors grouped by specialty
   - Visual cards with hover effects
   - Click to select

2. **Price Badges**
   - Green badges showing consultation fees
   - Only shown for specialists (except psychiatrists)
   - Shows "First Visit" or "Subsequent" based on patient history

3. **Visit Type Selection**
   - New Visit (charges apply)
   - Review Visit (no charges)

4. **Responsive Layout**
   - Works on desktop and mobile
   - Grid layout for doctor cards
   - Smooth animations

---

## 🔧 **How to Fix "No Doctors Available"**

### Option 1: Check Database
```python
# Run in Django shell
from hospital.models import Staff, User

# Check if doctors exist
doctors = Staff.objects.filter(profession='doctor')
print(f"Total doctors: {doctors.count()}")

# Check active doctors
active = doctors.filter(is_deleted=False, user__is_active=True)
print(f"Active doctors: {active.count()}")

# List doctor names
for doc in active:
    print(f"- {doc.user.get_full_name() if doc.user else 'No user'}")
```

### Option 2: Create/Update Doctor Records
Ensure doctors have:
- `profession='doctor'`
- `is_deleted=False`
- Linked User account with `is_active=True`

### Option 3: Check User Accounts
```python
# Check if doctors have user accounts
doctors_without_users = Staff.objects.filter(
    profession='doctor',
    user__isnull=True
)
print(f"Doctors without users: {doctors_without_users.count()}")
```

---

## 🔄 **Data Flow**

1. **User opens visit creation form**
   - System queries for available doctors
   - Gets pricing info for each doctor
   - Checks if patient visited doctor before

2. **User selects doctor**
   - System shows appropriate price (if applicable)
   - Indicates first vs subsequent visit

3. **User submits form**
   - System creates encounter
   - Applies doctor-specific pricing
   - Creates invoice with correct amount

4. **Billing**
   - Uses `DoctorPricingService.get_consultation_fee()`
   - Checks first vs subsequent visit
   - Applies special rules (e.g., ANC pricing for Dr. Ali)

---

## 📝 **Key Files**

1. **`hospital/utils_doctor_pricing.py`**
   - Pricing configuration
   - Doctor matching logic
   - First visit detection

2. **`hospital/templates/hospital/quick_visit_form.html`**
   - Modern UI template
   - Doctor selection cards
   - Price display logic

3. **`hospital/views.py`** (function: `patient_quick_visit_create`)
   - Fetches doctors
   - Applies pricing
   - Creates encounter

4. **`hospital/utils_billing.py`** (function: `add_consultation_charge`)
   - Uses doctor-specific pricing
   - Creates invoices

---

## 🐛 **Troubleshooting**

### Issue: Doctors not showing
**Solution**: Check database for doctors matching criteria

### Issue: Wrong prices showing
**Solution**: Verify doctor name matches in `DOCTOR_PRICING` dictionary

### Issue: Prices showing for psychiatrists
**Solution**: Check `show_price: False` in pricing config

### Issue: First visit always showing
**Solution**: Check `is_first_visit_to_doctor()` function logic

---

## ✅ **Testing Checklist**

- [ ] Doctors appear in selection
- [ ] Prices show for specialists (except psychiatrists)
- [ ] First visit pricing correct
- [ ] Subsequent visit pricing correct
- [ ] ANC pricing works for Dr. Ali
- [ ] Review visits don't charge
- [ ] Billing uses correct prices
- [ ] UI looks modern and responsive

---

## 📞 **Need Help?**

If doctors still don't appear:
1. Check database for Staff records
2. Verify User accounts are active
3. Check profession field values
4. Review Django logs for errors

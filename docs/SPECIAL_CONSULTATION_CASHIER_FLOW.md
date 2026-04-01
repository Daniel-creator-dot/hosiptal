# Special Consultation → Cashier Flow

This document describes how **Special Consultation** (e.g. urologist) flows from **reception** to **cashier**, and how the cashier sees the patient and the correct amount (GHS 300 for specialist).

---

## 1. Reception: Creating a Special Consultation Visit

### 1.1 Front desk “Create visit” (recommended)

| Step | Location | What happens |
|------|----------|---------------|
| URL | `hospital/urls.py` | `frontdesk/visit/create/<patient_id>/` → `views_frontdesk_visit.frontdesk_visit_create` |
| Form | `frontdesk_visit_create.html` | User selects **Visit Type** = **Special Consultation *sp** (`encounter_type=specialist`) and **New Visit** (charges apply). Optionally assigns a doctor (e.g. urologist). |
| View | `views_frontdesk_visit.py` → `frontdesk_visit_create()` | 1. Create or reuse same-day **Encounter** with `encounter_type=encounter_type` (e.g. `'specialist'`). 2. If `visit_reason == 'new'`: **`consultation_type = 'specialist'`** when `encounter_type == 'specialist'` (or when assigned doctor is a specialist). 3. **`add_consultation_charge(encounter, consultation_type=consultation_type, doctor_staff=...)`** → creates **Invoice** + **InvoiceLine** CON002 (Specialist Consultation), price GHS 300 (cash) or insurance rate. |

So for **Special Consultation** at reception:

- **Encounter** is stored with `encounter_type='specialist'`.
- **Invoice** and **consultation line (CON002)** are created in the same request via **`add_consultation_charge`** with `consultation_type='specialist'`.

### 1.2 Quick visit (patient quick visit form)

| Step | Location | What happens |
|------|----------|---------------|
| View | `views.py` → `patient_quick_visit_create()` | Same idea: user selects **Special Consultation** (`encounter_type=specialist`) and **New Visit**. **`consultation_type = 'specialist'`** when `encounter_type == 'specialist'` (or when assigned doctor is specialist). **`add_consultation_charge(...)`** creates Invoice + CON002 line. |

So both **front desk create visit** and **quick visit** now ensure that when the visit type is **Special Consultation**, the consultation is billed as **specialist** (CON002, GHS 300) so the cashier sees the correct amount even if no doctor is assigned or the doctor is not marked as specialist in pricing.

---

## 2. Why the patient and amount appear at cashier

### 2.1 Data the cashier uses

The cashier dashboard and patient bills are built in **`cashier_patient_bills`** (`views_centralized_cashier.py`). One of the sources is **consultations**:

- **`consultations_query`**: `Encounter.objects.filter(is_deleted=False, status='active')` (optionally filtered by date and search).
- All **active** encounters (including `encounter_type='specialist'`) are included; there is **no filter that excludes Special Consultation**.

So **Special Consultation** encounters are in the same list as Outpatient encounters.

### 2.2 How the consultation amount is shown

For each unpaid consultation encounter, the cashier uses **`get_consultation_price_for_encounter(encounter)`** (`utils_billing.py`):

- If the encounter has a **provider** (assigned doctor), doctor-specific pricing can be used (e.g. urologist fee).
- **Fallback**: if `encounter.encounter_type == 'specialist'` → **GHS 300**; otherwise **GHS 150**.

So **Special Consultation** now shows **GHS 300** at cashier even when no doctor is assigned.

### 2.3 Display label

The cashier shows the visit type label from the encounter:

- **`encounter.get_encounter_type_display()`** → e.g. **“Special Consultation”** for `encounter_type='specialist'`.

So the row appears as **“Special Consultation Consultation”** (or similar) with the correct amount.

---

## 3. End-to-end flow (diagram)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ RECEPTION                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Front desk: Create visit (frontdesk_visit_create)                         │
│    - Visit Type = "Special Consultation *sp"  →  encounter_type = 'specialist'  │
│    - New Visit (charges apply)  →  visit_reason = 'new'                      │
│    - Optional: Assign doctor (e.g. urologist)                                │
│                                                                             │
│  • Quick visit: patient_quick_visit_create                                   │
│    - Same: Special Consultation + New Visit                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ENCOUNTER + BILLING                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Encounter.objects.create(..., encounter_type='specialist', status='active') │
│  2. add_consultation_charge(encounter, consultation_type='specialist', ...)  │
│     → Invoice (get or create for encounter)                                  │
│     → InvoiceLine: CON002 "Specialist Consultation", unit_price = 300 (cash) │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ CASHIER                                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  • cashier_patient_bills() builds list from:                                 │
│    - consultations_query  ←  Encounter (active, not deleted)                │
│      → includes encounter_type='specialist'                                 │
│                                                                             │
│  • For each unpaid consultation encounter:                                  │
│    - get_consultation_price_for_encounter(encounter)                         │
│      → specialist encounter  →  GHS 300                                      │
│      → general encounter    →  GHS 150                                      │
│    - Label: encounter.get_encounter_type_display()  →  "Special Consultation"│
│                                                                             │
│  • Patient appears with "Special Consultation" and correct amount (300).    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. What was fixed (so Special Consultation shows at cashier)

1. **Reception billing (frontdesk + quick visit)**  
   **Consultation type** is now set from **visit type** when it is Special Consultation:
   - If **`encounter_type == 'specialist'`** → **`consultation_type = 'specialist'`** (CON002, GHS 300).
   - So even with **no doctor assigned**, the encounter gets the correct specialist consultation line and the cashier sees the right amount.

2. **Cashier price fallback (`get_consultation_price_for_encounter`)**  
   When there is no doctor or no doctor-specific fee:
   - If **`encounter.encounter_type == 'specialist'`** → return **300**.
   - Otherwise → return **150**.

So:

- **Special Consultation** is created with the correct **encounter_type** and **consultation charge (CON002)** at reception.
- The **cashier** includes these encounters in the consultation list and shows **GHS 300** and the label **“Special Consultation”**.

---

## 5. File reference

| Purpose | File |
|--------|------|
| Front desk create visit | `hospital/views_frontdesk_visit.py` (`frontdesk_visit_create`) |
| Quick visit create | `hospital/views.py` (`patient_quick_visit_create`) |
| Consultation charge + price helper | `hospital/utils_billing.py` (`add_consultation_charge`, `get_consultation_price_for_encounter`) |
| Cashier patient list & consultation row | `hospital/views_centralized_cashier.py` (`cashier_patient_bills`, `consultations_query`) |
| Encounter type choices | `hospital/models.py` (`Encounter.ENCOUNTER_TYPES`: `'specialist'` = "Special Consultation") |
| General patient → cashier trace | `docs/PATIENT_TO_CASHIER_TRACE.md` |

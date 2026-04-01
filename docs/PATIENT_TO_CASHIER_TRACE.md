# Patient creation to cashier – data flow trace

This document traces how a **patient** is created and stored, and how they appear (with name and invoice) at the **cashier** for payment.

---

## 1. Where the patient is created and stored

### 1.1 Main registration (web form)

| Step | Location | What happens |
|------|----------|--------------|
| URL | `hospital/urls.py` | `patients/new/` or `patient-registration/` → `views.patient_create` |
| View | `hospital/views.py` → `patient_create()` | POST: validates with `PatientForm`, duplicate checks (session token, form clean), then **`patient = form.save()`** (i.e. `Patient.save()`). |
| Model | `hospital/models.py` → `Patient` | `Patient.save()`: if new, generates **MRN** (unique), normalizes `national_id`, optional duplicate checks. Stored in DB: `hospital_patient` (or equivalent). |

So the **patient** is stored as soon as the registration form is submitted successfully; the canonical “create” is **`Patient.save()`** in `models.py` (triggered by `form.save()` in `patient_create`).

### 1.2 Other creation paths

- **API**: `hospital/viewsets.py` → `PatientViewSet.create()` – `serializer.save()` creates the patient (same `Patient` model).
- **Walk-in pharmacy**: `hospital/services/pharmacy_walkin_service.py` → `ensure_sale_patient()` – can **`Patient.objects.create(...)`** if no matching patient found.
- **Imports / migrations**: Various management commands create patients via `Patient.objects.create()` or `Patient(...).save()`.

All paths end up creating/updating the same **`Patient`** model; the main user-facing path is **registration** → `patient_create` → `form.save()` → `Patient.save()`.

---

## 2. From patient to visit (encounter)

A **visit** is an **Encounter**. The patient must already exist; then an encounter is created for that patient.

### 2.1 Front desk “Create visit” (recommended path for cashier visibility)

| Step | Location | What happens |
|------|----------|--------------|
| URL | `hospital/urls.py` | `frontdesk/visit/create/<patient_id>/` → `views_frontdesk_visit.frontdesk_visit_create` |
| View | `hospital/views_frontdesk_visit.py` → `frontdesk_visit_create()` | 1. Reuse same-day active encounter if exists (`started_at__date=today`), else **`Encounter.objects.create(patient=..., started_at=timezone.now(), ...)`**. 2. If `visit_reason == 'new'`: calls **`add_consultation_charge(encounter, ...)`** (creates invoice + CON001/CON002 line). 3. Optional: update `PatientInsurance` / notifications. |

So in this path:

- **Encounter** is created (or reused) with **`started_at=timezone.now()`**.
- **Invoice** and **consultation line** are created in the same request via **`add_consultation_charge`**.

No separate “payer sync” view is called here; `add_consultation_charge` gets/creates payer and invoice internally.

### 2.2 Views.py “Start visit” (another full path)

| Step | Location | What happens |
|------|----------|--------------|
| View | `hospital/views.py` (visit/start flow, ~3045–3190) | 1. **`Encounter.objects.create(patient=..., started_at=timezone.now(), ...)`**. 2. **`visit_payer_sync_service.verify_and_set_payer_type(encounter, payer_type)`** → **`_sync_encounter_invoice_payer(encounter, payer)`** which **`Invoice.objects.get_or_create(encounter=encounter, patient=..., defaults={...})`** (creates encounter invoice). 3. If `visit_reason == 'new'`: **`add_consultation_charge(encounter, ...)`** (adds CON001/CON002 line to that invoice). |

So:

- **Encounter** is created with **`started_at=timezone.now()`**.
- **Payer** is set on the patient; **invoice for the encounter** is created in **`visit_payer_sync_service._sync_encounter_invoice_payer`**.
- **Consultation charge** is added by **`add_consultation_charge`** (same as frontdesk path).

### 2.3 Queue “Add to queue” (encounter only, no invoice by default)

| Step | Location | What happens |
|------|----------|--------------|
| View | `hospital/views_queue_frontdesk.py` → `frontdesk_queue_create()` | If no encounter provided: **`Encounter.objects.create(patient=..., started_at=timezone.now(), ...)`**. Then **`queue_service.create_queue_entry(...)`**. **No** call to `add_consultation_charge` or `visit_payer_sync_service`. |

So:

- **Patient** and **Encounter** exist; **Encounter** has **`started_at=timezone.now()`**.
- **No invoice** and **no consultation line** are created in this path. The patient will only appear at cashier once some other flow creates an invoice for this encounter (e.g. doctor starts consultation and billing runs, or someone runs payer sync + consultation charge later).

---

## 3. How invoice and name get on the encounter (for cashier)

Cashier needs:

- **Patient** (for name).
- **Encounter** (for “visit” / consultation row).
- **Invoice** for that encounter with at least one line (e.g. consultation).

### 3.1 Who creates the encounter invoice

- **`visit_payer_sync_service._sync_encounter_invoice_payer(encounter, payer)`**  
  - **`Invoice.objects.get_or_create(encounter=encounter, patient=encounter.patient, ..., defaults={payer, status='draft', ...})`**  
  So the **encounter’s invoice** is created (or updated) here when payer sync runs.

- **`add_consultation_charge(encounter, ...)`** (in `hospital/utils_billing.py`)  
  - Gets or creates **payer** (e.g. Cash).  
  - **`Invoice.objects.filter(encounter=encounter, is_deleted=False).first()`**; if none, **`Invoice.objects.create(patient=..., encounter=encounter, payer=..., ...)`**.  
  - Then adds **InvoiceLine** for CON001/CON002 (consultation).  

So the **same encounter** can get its invoice from either:

1. Payer sync first (`_sync_encounter_invoice_payer`), then **`add_consultation_charge`** adds the line, or  
2. **`add_consultation_charge`** only, which creates the invoice if missing and adds the line.

In both “full” paths (frontdesk visit create and views.py start visit), **consultation charge** runs, so the encounter ends up with an **invoice** and a **consultation line**.  
In the **queue-only** path, neither runs, so there is **no invoice** until another process adds it.

### 3.2 Storage summary

| Entity | Stored in | Key fields |
|--------|-----------|-------------|
| Patient | `hospital.Patient` (e.g. `hospital_patient`) | `id`, `mrn`, `first_name`, `last_name`, `primary_insurance` (FK to Payer) |
| Encounter | `hospital.Encounter` (e.g. `hospital_encounter`) | `id`, `patient_id`, `started_at`, `status='active'` |
| Invoice | `hospital.Invoice` | `id`, `patient_id`, `encounter_id`, `payer_id`, `invoice_number`, `balance`, etc. |
| InvoiceLine | `hospital.InvoiceLine` | `invoice_id`, `service_code_id` (e.g. CON001/CON002), `quantity`, `unit_price`, `line_total` |

---

## 4. How the cashier sees the patient and invoice

### 4.1 Cashier view and data sources

| Location | View / logic |
|----------|------------------|
| `hospital/views_centralized_cashier.py` | **`cashier_patient_bills`** (and “today pending” list) build **`patients_bills`**: one entry per patient with list of services and total. |

**Sources** that feed **`patients_bills`**:

1. **Labs** – `labs_query` (LabResult: verified or has `release_record`).
2. **Prescriptions** – `rx_query`.
3. **Walk-in pharmacy** – `walkin_query`.
4. **Imaging** – `imaging_query` (ImagingStudy in billable statuses).
5. **Consultations** – **`consultations_query`** (Encounter: `status='active'`, optionally date filter).
6. **Unpaid invoices** – **`unpaid_inv`** (Invoice with balance or billable lines, optionally date filter).
7. **Admissions** – `admissions_query`.

So the **patient name** on the cashier list comes from:

- **`patient`** on each of these objects (e.g. `encounter.patient`, `inv.patient`, `lab.order.encounter.patient`).  
The **consultation row** and **invoice** appear when:

- The encounter is in **`consultations_list`** (from **`consultations_query`**), and  
- Either that encounter has an **invoice** (with consultation line) from **`add_consultation_charge`** / payer sync, or the cashier still shows a “consultation” row from the encounter and payment is recorded against the encounter’s invoice.

### 4.2 Consultations query (why a new visit might not show)

**`consultations_query`** (in `cashier_patient_bills`):

- Base: **`Encounter.objects.filter(is_deleted=False, status='active').select_related('patient')`**.
- If **`date_range_start`** is set (e.g. when filtering by “today”):
  - **Default “today”**:  
    **`(started_at in [date_range_start, date_range_end)) OR (started_at >= now - 24h)`**  
    so new visits show even with timezone/date edge cases.
  - **Other dates**:  
    **`started_at in [date_range_start, date_range_end)`** only.

So the **patient + encounter** show up in the cashier list when:

- The encounter is **active** and (if date filter is on) either in the selected day range or in the last 24h for “today”.
- For a **consultation line and invoice** to exist, **`add_consultation_charge`** (or equivalent) must have been run for that encounter (e.g. via frontdesk visit create or views.py start visit). The **queue-only** path does **not** create an invoice, so the patient may appear only under “consultation” from the encounter, and the actual invoice may be created later when consultation billing runs elsewhere.

---

## 5. End-to-end flow (summary)

1. **Patient created**  
   Registration (or API / walk-in) → **`Patient.save()`** or **`Patient.objects.create()`** → patient stored in DB.

2. **Visit created**  
   - **Front desk visit**: **`frontdesk_visit_create`** → create/reuse **Encounter** with **`started_at=timezone.now()`** → **`add_consultation_charge`** → **Invoice** (get or create) + **InvoiceLine** (CON001/CON002).  
   - **Views start visit**: Create **Encounter** → **`visit_payer_sync_service.verify_and_set_payer_type`** → **`_sync_encounter_invoice_payer`** (get/create **Invoice**) → **`add_consultation_charge`** (add consultation line).  
   - **Queue only**: **Encounter** created; **no** invoice/consultation line in this step.

3. **Cashier list**  
   **`cashier_patient_bills`** builds **`patients_bills`** from labs, prescriptions, walk-in, imaging, **consultations_query**, **unpaid_inv**, admissions.  
   Patient name comes from **`patient`** on encounter/invoice/lab/ etc.  
   Consultation row and invoice appear when the encounter is in **`consultations_list`** and an invoice (with consultation line) exists for that encounter.

4. **Why name/invoice might be missing for a “new” visit**  
   - **Encounter not in consultations_query**: e.g. date filter (fixed by “today” + last-24h logic).  
   - **No invoice yet**: e.g. visit created only via queue (no payer sync / no **`add_consultation_charge`**).  
   - **Invoice exists but not linked to encounter** in the way cashier expects (unusual if you only use the flows above).

---

## 6. Files reference

| Purpose | File |
|--------|------|
| Patient model & save (MRN, etc.) | `hospital/models.py` (Patient, Encounter, Invoice, InvoiceLine) |
| Patient registration (web) | `hospital/views.py` (`patient_create`) |
| Front desk create visit | `hospital/views_frontdesk_visit.py` (`frontdesk_visit_create`) |
| Start visit + payer sync + consultation | `hospital/views.py` (visit start flow ~3035–3190) |
| Queue create (encounter only) | `hospital/views_queue_frontdesk.py` (`frontdesk_queue_create`) |
| Payer sync + encounter invoice | `hospital/services/visit_payer_sync_service.py` (`verify_and_set_payer_type`, `_sync_encounter_invoice_payer`) |
| Consultation charge (invoice + line) | `hospital/utils_billing.py` (`add_consultation_charge`) |
| Cashier patient list | `hospital/views_centralized_cashier.py` (`cashier_patient_bills`, consultations_query, unpaid_inv) |

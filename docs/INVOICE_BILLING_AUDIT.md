# Invoice and Billing – Codebase Audit

Audit date: 2025-03-16  
Purpose: Locate all direct `invoice.total_amount` / `invoice.balance` assignments and all `Invoice` creation patterns so Phase 1 (single source of truth) and Phase 5 (one invoice per encounter) can be implemented.

---

## 1. Single source of truth: `update_totals()` / `calculate_totals()`

- **Canonical logic:** `hospital/models.py` – `Invoice.calculate_totals()` (lines 2392–2472) and `Invoice.update_totals()` (2474–2477). These set `total_amount`, `balance`, and `status` from lines + receipts + deposit applications. No other code should set `invoice.total_amount` or `invoice.balance` except inside this flow.

---

## 2. Direct `invoice.total_amount` / `invoice.balance` assignments (must fix)

### 2.1 Core app – replace with `invoice.update_totals()`

| File | Lines | Context | Action |
|------|--------|---------|--------|
| **hospital/services/bed_billing_service.py** | 324–326 | `create_admission_bill`: after adding provisional accommodation line, manual total/balance += | Remove 324–325; after creating line call `invoice.update_totals()` then set status and save. |
| **hospital/services/bed_billing_service.py** | 398–406 | `update_bed_charges_on_discharge`: after _clear and _add accommodation lines, manual total/balance math | Remove 398–400; call `invoice.update_totals()` after _add_accommodation_lines; keep status/issued_at logic and save. |
| **hospital/views_centralized_cashier.py** | 991–998 | `cashier_add_services_to_invoice`: fallback when invoice has no `update_totals` – uses Sum(line_total) and balance = total - amount_paid | Prefer ensuring Invoice always has `update_totals`; replace fallback branch with `invoice.update_totals()` (remove 992–998). |
| **hospital/views.py** | 3313–3316 | Consultation bill: after updating consultation line price, recalc total as sum of `invoice.invoice_lines` and save | Replace with `invoice.update_totals()` after saving the line (and remove direct total_amount assign). |
| **hospital/services/unified_receipt_service.py** | 203–209 | After creating receipt: `invoice.balance -= amount` or `invoice.balance = 0`, then save | Replace with `invoice.update_totals()` so balance comes from receipts. |
| **hospital/services/billing_validation_service.py** | 626–674 | Recalculate totals from lines and payments then set total_amount, balance, status and save | Replace custom recalc with `invoice.calculate_totals()` then `invoice.save(update_fields=['total_amount','balance','status'])` (or call `invoice.update_totals()` and drop the manual field updates). |
| **hospital/viewsets.py** | 554–557 | InvoiceLine viewset `lines` POST: after saving line, set total_amount = sum(line_total), balance = total_amount, save | Replace with `invoice.update_totals()` (so balance reflects payments). |
| **hospital/models_accounting.py** | 221–227 | `PaymentAllocation` allocation loop: `invoice.balance -= amount`, then 0 or status | Per plan §3, allocation should create per-invoice receipts; then call `invoice.update_totals()` here instead of manual balance/status. |
| **hospital/models_patient_deposits.py** | 237–243 | `Deposit.apply_to_invoice`: `invoice.balance -= amount`, then 0 or status | After applying and (if requested) creating receipt, call `invoice.update_totals()` instead of manual balance/status. |

### 2.2 Keep as-is (inside canonical logic or different model)

- **hospital/models.py** 2415–2463: Inside `Invoice.calculate_totals()` – this is the single source of truth; no change.
- **hospital/models_accounting.py** 306, 326; **models_accounting_advanced.py** 318, 340: `balance` on a different model (e.g. ledger entry), not `Invoice`.
- **hospital/models_pharmacy_walkin.py** 136, **models_ambulance.py** 304/307/364, **models_workflow.py** 188, etc.: Other models’ `total_amount`/`balance`; not `Invoice`.

### 2.3 Scripts / management commands (optional or one-off)

- **record_discharge_payment.py** 181, **fix_discharge_payment.py** 146: Direct `invoice.balance` update – consider switching to `invoice.update_totals()` if still in use.
- **hospital/management/commands/reset_all_financial_data.py** 91: Resets to `invoice.balance = invoice.total_amount` – keep or align with recalc policy for reset.
- **hospital/management/commands/backfill_invoice_lines.py** 52: Sets `invoice.balance = 0` – consider `invoice.update_totals()` for consistency.
- **fix_discharged_patient_invoice.py** 44: Read-only check (`if invoice.total_amount == 0 or invoice.balance == 0`); no change needed.

---

## 3. Invoice creation – get_or_create vs create

**Goal:** One consolidated invoice per encounter. All lab, pharmacy, imaging, consultation, and bed billing should use the same encounter invoice (get_or_create by encounter).

### 3.1 Correct pattern (by encounter)

- **hospital/services/auto_billing_service.py**  
  - `_get_or_create_invoice(patient, encounter, payer)` (483–518): Uses `Invoice.all_objects` filter by patient+encounter, then `Invoice.all_objects.create` only when none. Used by lab, pharmacy, imaging, etc. **Good.**
- **hospital/utils_billing.py**  
  - Consultation path (408–422): Filter by `encounter`, then `Invoice.objects.create` if none. Antenatal path (241–261): Same. **Good.**  
  - `get_or_create_encounter_invoice(encounter)` (450–491): Filter by encounter, create if missing. **Good.**
- **hospital/services/bed_billing_service.py** (384–392): Creates invoice only when `Invoice.DoesNotExist` in `update_bed_charges_on_discharge` (get then create). **Good.**
- **hospital/views_centralized_cashier.py** (805–821): When adding lab/pharmacy/imaging to invoice – gets invoice by encounter first, then by patient unpaid, then creates with `encounter=encounter`. **Good** (one per encounter when creating).
- **hospital/views_centralized_cashier.py** (3288–3305): Custom “charge only” flow creates **new** invoice with `encounter=None` and one line – intentional non-encounter invoice; document or keep as-is.
- **hospital/views_pharmacy_dispensing_enforced.py** 272: `get_or_create_encounter_invoice(encounter)`. **Good.**
- **hospital/views_departments.py** 3894–3895: `get_or_create_encounter_invoice(encounter)`. **Good.**
- **hospital/views_specialists.py** 606–609: `get_or_create_encounter_invoice(dental_chart.encounter)`. **Good.**

### 3.2 Create without encounter (or possible duplicate)

- **hospital/views_centralized_cashier.py** (1075–1086): “Add services select” – gets unpaid invoice by patient (no encounter filter); if none, `Invoice.objects.create(..., encounter=None)`. Risk: multiple non-encounter invoices per patient. **Audit:** Prefer get_or_create by encounter when request is encounter-scoped; otherwise document “walk-in / no encounter” policy.
- **hospital/services/unified_receipt_service.py**: When bill has encounter, uses `get_or_create_encounter_invoice(encounter)` so the same encounter invoice is reused; only creates a new invoice when no encounter or get_or_create returns None. **Fixed.**
- **hospital/services/pharmacy_walkin_service.py** (130–144): Filter by patient + line description containing sale number; if none, `Invoice.objects.create(..., encounter=None)`. Walk-in pharmacy sales; not encounter-based. **OK** if design is one invoice per walk-in sale; otherwise consider linking to encounter when applicable.
- **hospital/utils_billing.py** (255): Antenatal – create only when no invoice for encounter (241–244). **Good.**

### 3.3 Scripts / tests

- **record_discharge_payment.py** 84, **fix_discharge_payment.py** 57: Create invoice for testing/fix; no change for production path.
- **hospital/management/commands/generate_test_data.py** 157, **test_accounting_sync.py** 40: Test data; no production impact.

---

## 4. Summary checklist for implementation

### Phase 1 – Totals and balance ✅ (implemented)

- [x] **bed_billing_service.py**: `create_admission_bill` and `update_bed_charges_on_discharge` use `invoice.update_totals()`.
- [x] **views_centralized_cashier.py**: Fallback removed; only `update_totals()` / `calculate_totals()` used.
- [x] **views.py**: Consultation line update uses `invoice.update_totals()`.
- [x] **unified_receipt_service.py**: After receipt creation → `invoice.update_totals()`.
- [x] **billing_validation_service.py**: Uses `invoice.update_totals()`.
- [x] **viewsets.py**: InvoiceLine `lines` POST → `invoice.update_totals()`.
- [x] **models_accounting.py**: PaymentAllocation uses `invoice.update_totals()`; combined payment creates per-invoice receipts (Phase 2).
- [x] **models_patient_deposits.py**: `Deposit.apply_to_invoice` uses `invoice.update_totals()`.

### Phase 5 – One invoice per encounter (audit) ✅

- [x] **unified_receipt_service.py**: When bill has encounter, uses `get_or_create_encounter_invoice(encounter)` so encounter invoice is reused.
- [x] **views_centralized_cashier.py** “Add services select”: Uses patient unpaid invoice or creates with `encounter=None` (walk-in / no encounter); documented as intentional.
- [x] All other `Invoice.objects.create` usages: Confirmed as either encounter get_or_create or intentional non-encounter (walk-in, receipt-only, test).

---

## 5. Key files reference

| Area | Files |
|------|--------|
| Totals/balance | hospital/models.py (Invoice.calculate_totals, update_totals), hospital/services/bed_billing_service.py, hospital/views_centralized_cashier.py, hospital/views.py, hospital/services/unified_receipt_service.py, hospital/services/billing_validation_service.py, hospital/viewsets.py, hospital/models_accounting.py, hospital/models_patient_deposits.py |
| Invoice creation | hospital/utils_billing.py (get_or_create_encounter_invoice), hospital/services/auto_billing_service.py (_get_or_create_invoice), hospital/services/bed_billing_service.py, hospital/views_centralized_cashier.py, hospital/services/unified_receipt_service.py, hospital/services/pharmacy_walkin_service.py |

---

## 6. Single source of truth (documentation)

- **Invoice figures:** The only source of truth for `Invoice.total_amount`, `Invoice.balance`, and `Invoice.status` is `Invoice.calculate_totals()` (and its persistence via `Invoice.update_totals()`). No other code should assign these fields directly.
- **Payments and deposits:** Payments during admission (and combined payments) create one `PaymentReceipt` per allocated invoice so `calculate_totals()` stays correct. Deposit “Apply to bill” creates one receipt per invoice (Phase 2).
- **Outstanding and credit:** `get_patient_outstanding(patient)` returns `total_outstanding` (can be negative = credit), `credit_balance`, and `amount_due_after_deposit`. Use this everywhere for display.
- **Billing cut-off:** After discharge, `Encounter.billing_closed_at` is set; no new invoice lines may be added for that encounter (Phase 3).
- **Credit and refund:** Overpayments show as negative balance (credit). “Refund credit” is available until discharge and creates `refund_issued` transactions so balance is updated via `update_totals()` (Phase 4).

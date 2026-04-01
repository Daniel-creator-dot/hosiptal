# Billing: Single Source of Truth

This document summarizes how invoice totals, balance, and patient outstanding are computed and where to hook in when changing billing behaviour.

## Invoice totals and balance

- **Single source of truth:** `Invoice.calculate_totals()` in `hospital/models.py` computes `total_amount`, `balance`, and `status` from:
  - Invoice lines (excluding waived)
  - Payment receipts (excluding combined summary receipts)
  - Deposit applications (with double-count avoided)
  - Refund-issued transactions (subtracted from effective paid)
- **Persistence:** Call `invoice.update_totals()` after any change to lines, receipts, or refunds. Do **not** set `invoice.total_amount` or `invoice.balance` elsewhere.
- **Credit:** Balance may be negative (overpayment = credit). Status is still `'paid'` when balance ≤ 0.

## One invoice per encounter

- Lab, pharmacy, imaging, consultation, and bed billing all post to the **same** encounter invoice.
- Use `get_or_create_encounter_invoice(encounter)` (in `hospital/utils_billing`) or `AutoBillingService._get_or_create_invoice(patient, encounter, payer)` when creating or attaching to an encounter invoice.
- Receipt-only flows that have an encounter (e.g. bill with `bill.encounter`) should use `get_or_create_encounter_invoice(encounter)` so they do not create a second invoice for the same encounter.

## Payments and deposits

- **Combined payment:** One `PaymentReceipt` per allocated invoice (same transaction, `amount_paid` = allocated amount). A single “summary” receipt for print is excluded from totals.
- **Deposit “Apply to bill”:** Each invoice gets its own receipt when deposit is applied (`create_receipt=True`).
- After creating or changing receipts or allocations, call `invoice.update_totals()` (or rely on the service doing it).

## Patient outstanding and credit

- **Canonical data:** `get_patient_outstanding(patient)` in `hospital/services/patient_outstanding_service.py` returns:
  - `total_billed`, `total_paid`, `deposit_balance`
  - `total_outstanding` (= total_billed − total_paid; can be negative)
  - `credit_balance` (= max(0, total_paid − total_billed))
  - `amount_due_after_deposit`
- Use this (or the `/patients/<id>/outstanding/` API) everywhere for “amount due” and “credit” display.

## Billing cut-off at discharge

- When a patient is discharged, `Encounter.billing_closed_at` is set.
- No new invoice lines may be added for that encounter (guards in auto_billing_service, utils_billing, cashier, bed_billing_service).

## Refund of credit

- Refunds reduce credit by creating `Transaction(transaction_type='refund_issued', invoice=..., amount=...)`. `calculate_totals()` subtracts these from effective paid, so balance increases (credit decreases).
- “Refund credit” is offered only when the patient has an open encounter (not yet discharged). After processing, call `invoice.update_totals()` on affected invoices.

---

See also: `docs/INVOICE_BILLING_AUDIT.md` for the full audit and checklist.

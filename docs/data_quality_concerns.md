# Data Quality Concerns

This document catalogues data quality issues discovered during production investigation of the `sin_categorizar` metric (July 2026). Each issue is classified by root cause, impact, affected sellers, and remediation status.

---

## Issue 1 — Garbage `paymentDate` Years (ETL Bug — Fixed)

**Root cause:** Some MySQL `payment.paymentDate` values contain clearly invalid years (e.g. `1901-01-01`, `0206-04-14`). These appear to be default or corrupt CRM values.

**ETL impact (before fix):**
- `PAYMENT_EXTRACT_QUERY` stored the raw garbage date in `report_payments.payment_date`.
- `PAYMENTS_FOR_CARTS_QUERY` was already sanitizing, so `report_payment_allocations.payment_date` had a correct fallback date (`pay.createdAt`).
- Inconsistency: the payment was excluded from date-range filters on `report_payments` (garbage date outside window) but its allocations were included (correct date inside window).
- Result: `allocated_revenue >> total_revenue` → large **negative** `sin_categorizar`.

**Affected sellers (examples):** Oscar Díaz (−3.5 M MXN), Laura López CDMX, Héctor López (partial).

**Fix:** `PAYMENT_EXTRACT_QUERY` now applies:
```sql
CASE
    WHEN pay.paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
    THEN pay.paymentDate
    ELSE DATE(pay.createdAt)
END AS payment_date
```
Requires a full ETL re-run to backfill `report_payments` rows that were written with garbage dates.

---

## Issue 2 — Wrong Date Fallback: `cart.createdAt` vs `payment.createdAt` (ETL Bug — Fixed)

**Root cause:** When `payment.paymentDate IS NULL` (≈78% of approved payments, exclusively Colombia), `PAYMENT_EXTRACT_QUERY` was using `DATE(c.createdAt)` (the cart's creation date) as the fallback, while `PAYMENTS_FOR_CARTS_QUERY` correctly used `DATE(pay.createdAt)` (the payment record's creation date).

**Why this matters for Colombia:**
In Colombia, contracts are signed when the school signs up (cart created e.g. March 4). The actual payment is processed months later by the finance team (payment record created e.g. September 5). With `paymentDate IS NULL`:
- `report_payments.payment_date` got March 4 (cart creation) → included in March filter
- `report_payment_allocations.payment_date` got September 5 (payment creation) → excluded from March filter

**ETL impact (before fix):**
- Payment counted in `total_revenue` for Period A, but its allocations fall in Period B.
- Result: Period A shows large **positive** `sin_categorizar`; Period B shows large **negative** `sin_categorizar`.

**Affected sellers (examples):**
| Seller | Period | sin_cat | Direction |
|---|---|---|---|
| Laura López CDMX | Jan–Jul 2026 | −1.4 M | Negative |
| Héctor López | Jan–Jul 2026 | −2.0 M | Negative |
| Raúl Andrade | Jan–Jul 2026 | −1.4 M | Negative |
| Aaron Alcalá | Jan–Jul 2026 | −679 k | Negative |
| Liney Rivero | Feb 2024–Aug 2025 | +2.2 M | Positive (majority) |
| Felipe Garzón | Feb 2024–Aug 2025 | Partial | Mixed |

Pattern: exclusively Colombia (all `paymentDate IS NULL`).

**Fix:** `PAYMENT_EXTRACT_QUERY` now uses `DATE(pay.createdAt)` as fallback, matching `PAYMENTS_FOR_CARTS_QUERY`. Requires a full ETL re-run.

---

## Issue 3 — `payment.quantity = 0` with Non-Zero Student Payment Records (Source Data Quality)

**Root cause:** Some Colombia payments were recorded in the CRM with `quantity = 0` — the payment amount field was left empty or not filled in when the payment was created. However, `student_payments` entries for those same payments contain real amounts (e.g. 82,230,000 COP per student).

**ETL behavior:**
- `report_payments.amount_mxn = 0` for these payments (correctly reflects `quantity = 0`).
- Allocation rows are built from `student_payments` amounts and carry real positive MXN values.
- Per-payment contribution to `sin_categorizar`: `0 − allocated_mxn` = large negative.

**Affected sellers (examples):**
- **Liney Rivero:** 4 payments with `quantity = 0`, student amounts totalling approximately 2.2 M MXN in allocations.
- **Felipe Garzón:** 25 payments with `quantity = 0` — systematic pattern suggesting a workflow where the finance team enters student amounts before finalising the payment total in the CRM.

**Remediation:** Cannot be fixed on the backend — the actual collected amount is not recorded in any source table. The payment `quantity` field must be corrected in the source CRM (MySQL) for each affected payment. After correction, ETL re-run will resolve the sin_cat discrepancy.

---

## Issue 4 — Student Payment Entries Exceeding Actual Payment Amount (Source Data Quality)

**Root cause:** `SUM(student_payments.amount for payment P) > P.quantity` — more was recorded through student-level entries than the total payment collected. This is a data entry error: student amounts were entered incorrectly or the payment quantity was not updated after adjustments.

**ETL behavior (by design):**
- The remainder for non-student products = `P.quantity − SUM(student_amounts)` goes **negative**.
- ETL writes negative `allocated_amount` values as-is (module docstring: *"Do not clamp — hiding errors is worse than a negative value"*).
- Result: negative allocation rows → `sin_categorizar` appears negative for those cart_products.

**Affected sellers (examples):**
- **Fernanda Fraga:** 5 payments. JUSTO SIERRA payment had a −149 k MXN remainder; COLEGIO MICHELET −19 k; COLEGIO HEROES −10 k; total sin_cat ≈ −42 k MXN.
- **Oscar Díaz:** small amounts from same pattern.

**Detection:** The `report_payment_allocations` table will contain rows with `allocated_amount_mxn < 0`. The inspect tool surfaces these via `RDB_NEGATIVE_ALLOCATIONS` and `MYSQL_NEGATIVE_REMAINDER` queries.

**Remediation:** Cannot be fixed on the backend. Student payment amounts must be corrected in the source CRM. After correction, ETL re-run will produce correct allocations.

---

## Summary Table

| # | Issue | Root Cause | Direction of Error | Fixed in Code | Needs CRM Fix |
|---|---|---|---|---|---|
| 1 | Garbage `paymentDate` years | ETL stored raw invalid dates | Negative sin_cat | Yes | No |
| 2 | Wrong fallback (`cart.createdAt`) | ETL used cart date instead of payment date | Both directions | Yes | No |
| 3 | `payment.quantity = 0` | Payment amount not entered in CRM | Negative sin_cat | No — amount unknown | Yes |
| 4 | Student amounts > payment quantity | Over-allocation in student_payments | Negative sin_cat | No — by design, surface as-is | Yes |

---

## General Notes

- **Colombia-specific pattern:** Issues 2, 3, and 4 appear predominantly or exclusively in Colombia payments. Colombia uses a workflow where `paymentDate` is systematically NULL, carts are created at contract signing (potentially months before payment), and payment amounts are sometimes finalised after student records are entered.

- **Detection query:** After a full ETL re-run, any remaining `sin_categorizar ≠ 0` indicates either un-processed payments (ETL gap) or active source data quality issues (Issues 3 or 4). Use `tools/inspect_sin_categorizar.py` to drill into specific sellers.

- **Frontend guidance:** When `sin_categorizar < 0` (allocated > collected), the UI should display an amber note: *"El monto categorizado excede lo cobrado. Esto indica un error de calidad en los datos fuente — los pagos registrados por estudiante superan el monto del pago."*

- **ETL re-run required:** Issues 1 and 2 are fixed in `PAYMENT_EXTRACT_QUERY` but existing `report_payments` rows written before the fix contain incorrect dates. A full truncate + ETL backfill is needed for historical data to be consistent.

# Fix Approaches: `sin_categorizar` Bugs

This document describes two proposed approaches to fix both Bug 1 (`payment_day` mismatch) and Bug 2 (`paid_total` overflow) simultaneously. See `bug_payment_day_mismatch.md` and `bug_paid_total_overflow.md` for root cause detail.

---

## Shared Building Block: Remainder Allocation

Both approaches below use the same method to compute how much of a payment belongs to each cart_product. This replaces the two independent allocation paths that cause Bug 2.

**For each approved payment P on a cart:**

1. Query `student_payments` grouped by `(payment_id, cart_product_id)` — gives the exact amount already allocated to any product that has student records (exams, or books with students):

```sql
SELECT
    sp.payment_id,
    st.cartProductId        AS cart_product_id,
    SUM(sp.amount)          AS allocated_amount
FROM student_payments sp
JOIN student st  ON st.id       = sp.student_id
JOIN payment pay ON pay.id      = sp.payment_id
WHERE pay.status = :payment_status
GROUP BY sp.payment_id, st.cartProductId
```

2. `remainder = P.quantity − SUM(allocated_amount for P)`

3. Products with **no** student_payments entry for P receive a proportional share of the remainder, weighted by `cp.total / SUM(cp.total for non-student products in cart)`.

**Guarantee:** `SUM(all paid_totals for cart) = SUM(P.quantity for all approved payments)` always. No overflow is possible.

A negative remainder signals a data quality error in the source (student_payment amounts exceed the payment quantity) and surfaces in reports as a negative paid_total rather than being silently absorbed.

---

## Approach A: Canonical Date + Remainder

### How it works

Assign a single **canonical date** to every payment and line item belonging to the same cart:

```
canonical_date = MAX(paymentDate WHERE paymentDate BETWEEN '2000-01-01' AND '2099-12-31')
                 among all approved payments for the cart
```

Fallback: `cart.createdAt` if all approved payment dates are NULL or out of range.

Apply this date to:
- `report_payments.payment_date` — all payments for the cart are stamped with `canonical_date`
- `report_line_items.payment_day` — all line items for the cart are stamped with `canonical_date`

Combine with the remainder approach for `paid_total`.

### Why it fixes both bugs

**Bug 1:** All line items share `payment_day = canonical_date`. Books and exams in the same cart always fall inside or outside a date filter together.

**Bug 2:** A date filter that includes the cart now includes ALL its payments (all stamped at `canonical_date`), so `total_revenue` = SUM of all historical payments. Combined with the remainder approach, `SUM(paid_total)` = SUM of all historical payments as well. `sin_cat = 0` for any date window.

### Tradeoffs

| | |
|---|---|
| **Simplicity** | No schema changes. Both fixes live entirely in the ETL transform. |
| **Advisor performance use case** | Works correctly. The canonical date represents "when did this deal close." |
| **Cash flow / installment visibility** | Lost. A cart with payments in Jan 2025 and Jun 2026 shows all revenue in Jun 2026. The Jan installment is invisible in January. |
| **Temporal stability** | **Not stable.** When a new payment arrives with a later date, the canonical date shifts and ALL historical entries for that cart re-date in the next ETL run. A cart that appeared in January reports moves to June silently. Period-over-period comparisons can show rows disappearing and reappearing between ETL runs. |
| **Long billing cycles** | Degrades. A 3-year installment plan collapses all revenue to the final payment date. Revenue in the early periods is not visible. |
| **Report query complexity** | No change. Reports continue to filter on `payment_date` and `payment_day` as today. |

---

## Approach B: Payment-Level Allocation Table

### How it works

The already-existing `report_payment_allocations` table (currently populated with incorrect data and never read) is redesigned to store the correct remainder-based allocation at payment grain:

```
report_payment_allocations (
    payment_id       INT,   -- links to report_payments
    cart_product_id  INT,   -- links to report_line_items
    payment_date     DATE,  -- actual date of this payment (for date filtering)
    allocated_amount DECIMAL,
    allocated_amount_mxn DECIMAL,
    allocated_amount_usd DECIMAL
)
```

One row per `(payment, cart_product)` pair, populated using the remainder approach. For a cart with 3 installments and 2 products, this produces 6 rows.

Reports compute allocated revenue by joining through this table rather than summing `report_line_items.paid_total`:

```sql
-- allocated_revenue for a date window
SELECT seller_id, SUM(allocated_amount_mxn) AS allocated_revenue
FROM report_payment_allocations rpa
JOIN report_payments rp ON rp.payment_id = rpa.payment_id
WHERE rp.payment_date BETWEEN :date_from AND :date_to
  AND rp.payment_status = 'Aprobado'
GROUP BY seller_id
```

`report_line_items` is retained for product metadata (quantities, expected amounts, exam types) but is no longer the source of `paid_total`.

`report_payments` keeps actual payment dates — no canonical date override.

### Why it fixes both bugs

**Bug 1:** Date filtering is on `report_payments.payment_date` (actual date), and each allocation row inherits that date. Books and exams on the same cart for the same payment share the same date because they both derive from the same payment row. No `payment_day` fallback is needed.

**Bug 2:** By construction of the remainder approach, allocations for a payment always sum to `payment.quantity`. For any date window: `SUM(payment.quantity)` = `SUM(allocated_amount)`. `sin_cat = 0` always.

### Tradeoffs

| | |
|---|---|
| **Temporal stability** | **Stable.** Each payment's allocation is fixed at its own actual date. A new December payment does not re-date January allocations. |
| **Long billing cycles** | Handles correctly. A 3-year installment plan shows revenue in each payment's actual period. |
| **Cash flow visibility** | Full. Per-payment, per-product revenue is queryable. |
| **Advisor performance use case** | Works correctly — filter by any date window, allocations aggregate properly. |
| **Schema change** | Requires redesigning `report_payment_allocations` (new columns: `payment_date`; current schema lacks it). A migration is needed. |
| **Report query complexity** | Allocated revenue queries must join through the allocations table instead of summing `report_line_items.paid_total`. All three affected reports (`por_asesor`, `por_pais`, `total_sales`) need query updates. |
| **ETL complexity** | Slightly higher — must write allocation rows per payment per product in addition to line item rows. The remainder computation runs per payment rather than per cart_product. |
| **Row volume** | Larger than Approach A. Scales with `payments × cart_products per cart` rather than just `cart_products`. For most carts this is a small multiple; for carts with many installments it grows. |

---

## Comparison Summary

| Criterion | Approach A: Canonical Date + Remainder | Approach B: Allocation Table |
|---|---|---|
| Fixes Bug 1 | ✅ | ✅ |
| Fixes Bug 2 | ✅ | ✅ |
| Temporal stability | ❌ Shifts on new payments | ✅ Fixed per payment |
| Long billing cycles | ❌ Collapses to single date | ✅ Per-installment visibility |
| Cash flow reporting | ❌ Not possible | ✅ Native |
| Schema changes | None | Migration required |
| Report query changes | None | 3 reports updated |
| Implementation effort | Low | Medium |

**Approach A** is appropriate when billing cycles are short and advisor performance (deal-closed semantics) is the primary use case. The temporal instability is acceptable when most carts close within a single reporting period.

**Approach B** is appropriate when billing cycles span multiple periods, cash flow visibility matters, or stable historical comparisons are required. It is the architecturally correct long-term solution.

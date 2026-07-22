# Bug: Negative `sin_categorizar` — `paid_total` Overflow in Mixed Carts

## What is `sin_categorizar`?

In the **por asesor** report:

```
sin_categorizar = total_revenue (report_payments) - allocated_revenue (report_line_items)
```

When this is **negative**, it means `allocated_revenue` exceeds `total_revenue` — the report thinks more money was allocated to products than was actually collected from the school. This signals that the ETL is attributing payments to line items incorrectly.

---

## Root Cause

### Two independent allocation paths with no date filter

The ETL computes `paid_total` for line items through two separate queries, neither of which has a date filter:

**For exams** (`PAID_TOTAL_BY_DATE_QUERY`, `app/etl/upsert.py`):
```sql
SELECT
    st.cartProductId AS cart_product_id,
    pay.paymentDate  AS payment_date,
    SUM(sp.amount)   AS paid_total
FROM student_payments sp
JOIN student st ON sp.student_id = st.id
JOIN payment pay ON sp.payment_id = pay.id
WHERE pay.status = :payment_status
  AND st.cartProductId IN :cart_product_ids
GROUP BY st.cartProductId, pay.paymentDate, l.site
-- NO date filter: accumulates ALL historical student_payments
```

**For books and courses** (`ALLOCATION_PAID_TOTAL_BY_DATE_QUERY`):
```sql
SELECT
    cp.id AS cart_product_id,
    ROUND(pay.quantity * cp.total / NULLIF(ct.cart_total, 0), 2) AS allocated_amount
FROM payment pay
JOIN cart c ON c.id = pay.cartId
JOIN cart_product cp ON cp.cartId = c.id
-- NO date filter: accumulates ALL historical approved payments proportionally
```

The results of these two queries are summed independently, then stored in `report_line_items.paid_total`. The key problem: **these two totals are computed from overlapping payment data and can add up to more than the actual payment amount**.

### How the overflow happens in mixed carts

Consider a cart (e.g. cart 3575, Elvis Gómez) that contains both exams and books, paid in multiple installments:

**Total approved payments for the cart (all time):** 875,111 MXN

The ETL computes:
- Exam line items via `PAID_TOTAL_BY_DATE_QUERY`: allocates 733,425 + 14,500 = **747,925 MXN** to exam items (from student_payments)
- Book line items via `ALLOCATION_PAID_TOTAL_BY_DATE_QUERY`: proportional share = **127,186 MXN** (from all approved cart payments)

Combined `paid_total` across all line items: 747,925 + 127,186 = **875,111 MXN**

This equals the total payments — so far so good for a full-history view.

### Why it goes negative when a date filter is applied

The problem surfaces because the exam items and book items end up with **different `payment_day` values**:

- Exam items: `payment_day = MAX(student_payment.paymentDate)` — e.g. a 2026 date
- Book items: `payment_day = cart.createdAt` — e.g. a 2025 date (due to Bug 1, `bug_payment_day_mismatch.md`)

When filtering for **2026-01-01 to 2026-07-19**:

| Source | Included? | Amount |
|---|---|---|
| `total_revenue` (report_payments) | Only 2026 payments | 765,250 MXN |
| `allocated_revenue` — exam items (dated 2026) | ✅ Yes | 747,925 MXN |
| `allocated_revenue` — book items (dated 2025) | ❌ No | 127,186 MXN |

`sin_cat` = 765,250 − 747,925 = **+17,325** (looks okay so far)

But this is actually hiding the problem. After Bug 1 is fixed and book items get a 2026 `payment_day`:

| Source | Included? | Amount |
|---|---|---|
| `total_revenue` | Only 2026 payments | 765,250 MXN |
| `allocated_revenue` — exam items (2026) | ✅ | 747,925 MXN |
| `allocated_revenue` — book items (2026, fixed) | ✅ | 127,186 MXN |
| **Total allocated** | | **875,111 MXN** |

`sin_cat` = 765,250 − 875,111 = **−109,861 MXN**

The allocated total (875,111) now exceeds the actual 2026 payments (765,250) because the full historical paid_total for ALL items (exams + books) was attributed to the same 2026 date window, but the 2026 payments only represent a portion of the cart's total payment history.

### Confirmed impact — cart 3575, Elvis Gómez

```
Cart 3575 — CENTRO UNIVERSITARIO ANGLO MEXICANO
2026 approved payments:   765,250 MXN
ETL paid_total (all items): 875,111 MXN
  ├── Exam group 1 (student_payments): 733,425 MXN
  ├── Exam group 2 (student_payments):  14,500 MXN
  └── Books (proportional allocation): 127,186 MXN
Net sin_cat from this cart: −109,861 MXN
```

---

## Why the No-Date-Filter Design Exists

The queries intentionally accumulate all historical payments to ensure incremental ETL re-runs don't overwrite a previously correct `paid_total` with a partial value. If the ETL ran a second time covering only the last 30 days, a date-filtered query would lose earlier student_payments and produce a lower `paid_total`. The design trades correctness-under-incremental-runs for correctness-under-date-filtering.

---

## Fix Status

**Not yet implemented.** The fix requires one of:

1. **Remainder allocation**: After computing exam `paid_total` via student_payments, allocate the remaining cart payment proportionally to books/courses — ensuring the sum never exceeds the actual payment.

2. **Payment→line-item allocation table**: Introduce a `report_payment_allocations` table that explicitly links each payment to the line items it covers with the allocated amount per payment date. This is the architecturally clean solution and also resolves the date attribution problem fundamentally, but requires a schema migration and ETL redesign.

3. **Cap `paid_total` to the cart's actual payment total**: After computing both exam and book allocations independently, rescale them so their sum equals the cart's total approved payments.

---

## Relationship to Bug 1

Bug 1 (`bug_payment_day_mismatch.md`) masks Bug 2 for many advisors. When Bug 1 inflates sin_cat (e.g. +1,442,447 MXN for Kena Orozco), it hides the negative contribution from Bug 2 underneath. Fixing Bug 1 alone will expose Bug 2 and may push some advisors' sin_cat negative. **Both bugs must be fixed together.**

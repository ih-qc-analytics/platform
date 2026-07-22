# Bug: Inflated `sin_categorizar` — `payment_day` Mismatch

## What is `sin_categorizar`?

In the **por asesor** report, each advisor's revenue is split into:

- `total_revenue` — sum of all approved payments in `report_payments` for the date range
- `allocated_revenue` — sum of `paid_total` across `report_line_items` where `include_in_product_breakdown = TRUE` for the same date range

```
sin_categorizar = total_revenue - allocated_revenue
```

Ideally this is zero or a small rounding difference. When it is large and positive, it means payments exist that have no matching allocated line items in the date window — the revenue is "uncategorized."

---

## Root Cause

### The `payment_day` fallback in the ETL

`report_line_items.payment_day` controls which date window a line item falls into. It is set in `_transform_line_item` (`app/etl/upsert.py`):

```python
payment_date = dims["payment_date"]  # MAX(paymentDate) from student_payments; NULL for books/courses
"payment_day": payment_date or dims["created_at"].date(),
```

`payment_date` comes from the `pa` subquery in `LINE_ITEM_EXTRACT_QUERY`, which joins `student_payments`. **Books and courses have no rows in `student_payments`**, so `payment_date` is always `NULL` for them. The fallback is `cart.createdAt`.

### Why this inflates sin_cat

Consider a cart created in November 2025 for which the school pays in January 2026:

| Item | `payment_date` | `payment_day` |
|---|---|---|
| Exam (has student_payments) | `2026-01-15` | `2026-01-15` ✅ |
| Book (no student_payments) | `NULL` | `2025-11-28` ❌ |

When a user filters the report for **2026-01-01 to 2026-07-19**:

- `total_revenue`: includes the full Jan 2026 payment → e.g. 500,000 MXN
- `allocated_revenue`: includes the exam (dated 2026) but **excludes the book** (dated 2025)
- `sin_cat` = 500,000 − (exam portion only) → inflated by the book's value

The book's revenue is real and was paid in 2026, but the ETL dated it to 2025 because the cart was created then.

### Confirmed impact — Kena Orozco (2026-01-01 to 2026-07-19)

7 carts were identified where the MAX approved payment date falls in 2026 but their book/course line items have `payment_day` in 2024–2025:

| Cart | `payment_day` (current) | Correct date |
|---|---|---|
| 3258 | 2025-11-28 | 2026-01-xx |
| 3199 | 2025-11-26 | 2026-01-xx |
| 3378 | 2025-12-18 | 2026-03-xx |
| 3379 | 2025-12-18 | 2026-03-xx |
| 2033 | 2024-xx-xx | 2026-xx-xx |
| 3355 | 2025-xx-xx | 2026-xx-xx |
| 2857 | 2024-xx-xx | 2026-xx-xx |

Total wrongly excluded from `allocated_revenue`: **+2,818,113 MXN**  
Reported sin_cat: **+1,442,447 MXN** (should be much closer to zero)

---

## Data Quality Issues in MySQL

`payment.paymentDate` has garbage values that must be sanitized:
- `NULL` — 78.3% of approved payments have no paymentDate
- Garbage years — e.g. `0206-01-03` (year 206), `1901-01-01` — ~1% of records

`cart_product.examsCloseDate` has a sentinel: `1899-12-03` (≈ 14 records) that must be treated as NULL.

Any fix must filter dates to `BETWEEN '2000-01-01' AND '2099-12-31'` before using them.

---

## Planned Fix

Extend `payment_day` to a 4-level fallback chain in `LINE_ITEM_EXTRACT_QUERY` and `_transform_line_item`:

1. **`pa.payment_date`** — MAX date from `student_payments` (exams only, unchanged)
2. **`cp.examsCloseDate`** — sanitized (NULL if `YEAR < 2000`); by the time exams close, the product has been paid
3. **`cap.max_clean_pay_date`** — MAX sanitized `payment.paymentDate` for the cart among approved payments (catches books/courses)
4. **`cart.createdAt`** — last resort (unchanged)

SQL addition to `LINE_ITEM_EXTRACT_QUERY`:

```sql
-- New columns in SELECT:
CASE
    WHEN cp.examsCloseDate IS NOT NULL AND YEAR(cp.examsCloseDate) >= 2000
    THEN cp.examsCloseDate
    ELSE NULL
END AS exams_close_date,
cap.max_clean_pay_date AS max_clean_pay_date

-- New LEFT JOIN (after the `pa` subquery):
LEFT JOIN (
    SELECT
        cartId,
        MAX(
            CASE
                WHEN paymentDate BETWEEN '2000-01-01' AND '2099-12-31'
                THEN paymentDate
                ELSE NULL
            END
        ) AS max_clean_pay_date
    FROM payment
    WHERE status = :payment_status
    GROUP BY cartId
) cap ON cap.cartId = c.id
```

Python change in `_transform_line_item`:

```python
payment_date = dims["payment_date"]
exams_close_date = coerce_to_date(row.get("exams_close_date"), None)
max_clean_pay_date = coerce_to_date(row.get("max_clean_pay_date"), None)
payment_day = payment_date or exams_close_date or max_clean_pay_date or dims["created_at"].date()
```

---

## Warning: Bug 2 Underneath

After this fix alone, `sin_cat` for some advisors will go **negative** because Bug 2 (paid_total overflow in mixed exam+book carts) was previously masked by Bug 1's inflation. See `bug_paid_total_overflow.md`. Both bugs must be fixed together for accurate results.

**Estimated post-fix sin_cat for Kena Orozco**: ~−1,375,665 MXN (from +1,442,447 today), driven entirely by Bug 2.

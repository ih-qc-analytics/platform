# Report 3 — Detalle por Asesor: Backend Instructions

## Overview
A paginated, searchable report showing exam sales broken down by seller, school, and exam date. One row per seller + school + exam date combination. Columns represent specific exam types from `exam_cat.name`.

---

## Reference Files
- `app/services/total_sales/total_sales.py` — service pattern to follow
- `app/schemas/reports.py` — add new schemas here
- `schema_snapshot.json` — full DB schema
- `tools/exam_classifier.py` — use `canonical_exam_category()` for category grouping in Report 2. For Report 3, use `exam_cat.name` directly as column keys.

---

## DB Notes
- `lead` is a reserved word — always backtick it: `` `lead` ``
- Never join `lead_address` directly — always use this deduplication subquery:
```sql
LEFT JOIN (SELECT DISTINCT leadId, stateName, city FROM lead_address) la ON la.leadId = l.id
```
- `product.productType = 'exam'` to filter only exam products
- `cart.deletedAt IS NULL` to exclude deleted carts

---

## 1. Schemas (`app/schemas/reports.py`)

```python
class DetalleFilters(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    countries: list[str] = []
    zones: list[str] = []
    states: list[str] = []
    cities: list[str] = []
    search: Optional[str] = None   # matches seller name OR school name
    cursor: Optional[int] = None   # last row id for cursor pagination
    page_size: int = 20

class DetalleRow(BaseModel):
    id: int                        # cart_product.id, used as cursor
    seller_name: str
    school_name: str
    exam_date: str                 # YYYY-MM-DD from cart_product.testDate
    exam_counts: dict[str, int]    # { "KET": 12, "FCE": 8, ... } keyed by exam_cat.name
    total: int                     # sum of all exam_counts values

class DetalleReportResponse(BaseModel):
    rows: list[DetalleRow]
    next_cursor: Optional[int]     # None if no more pages
    has_more: bool
```

---

## 2. Service (`app/services/detalle_asesor/detalle_asesor.py`)

### Query Structure
Group by `cart_product.id`, seller, school, and exam date. Use conditional aggregation per exam type.

```sql
SELECT
    cp.id,
    CONCAT(s.name, ' ', s.lastName) as seller_name,
    l.name as school_name,
    cp.testDate as exam_date,
    SUM(CASE WHEN ec.name = :exam_name THEN cp.quantity ELSE 0 END) as exam_count,
    SUM(cp.quantity) as total
FROM cart c
JOIN seller_lead sl ON c.sellerLeadId = sl.id
JOIN seller s ON sl.sellerId = s.id
JOIN `lead` l ON sl.leadId = l.id
LEFT JOIN zone z ON l.zoneId = z.id
LEFT JOIN (SELECT DISTINCT leadId, stateName, city FROM lead_address) la ON la.leadId = l.id
JOIN cart_product cp ON cp.cartId = c.id
JOIN product p ON cp.productId = p.id
LEFT JOIN exam_cat ec ON p.examId = ec.id
WHERE c.deletedAt IS NULL
AND p.productType = 'exam'
{where_clause}
GROUP BY cp.id, seller_name, school_name, exam_date
ORDER BY cp.id ASC
LIMIT :page_size
```

### Approach
Since exam columns are dynamic (keyed by `exam_cat.name`), do NOT use one CASE per column in SQL. Instead:

1. Run a simpler query that returns one row per `cp.id + exam_cat.name + quantity`
2. In Python, pivot the results into `exam_counts: dict[str, int]` per `cp.id`
3. Return the pivoted rows

### Cursor Pagination
- When `cursor` is provided, add `AND cp.id > :cursor` to WHERE clause
- Order by `cp.id ASC`
- Fetch `page_size + 1` rows — if you get `page_size + 1` results, set `has_more = True` and return only `page_size` rows, with `next_cursor` = last row's id
- If fewer than `page_size + 1` results, `has_more = False`, `next_cursor = None`

### Search
When `search` is provided add:
```sql
AND (
    CONCAT(s.name, ' ', s.lastName) LIKE :search
    OR l.name LIKE :search
)
```
where `:search = f"%{filters.search}%"`

### Where Clause
Support the same filters as Report 1:
- `date_from` → `c.createdAt >= :date_from`
- `date_to` → `c.createdAt <= :date_to`
- `countries` → `` `lead`.site IN :countries ``
- `zones` → `z.name IN :zones`
- `states` → `la.stateName IN :states`
- `cities` → `la.city IN :cities`

---

## 3. Router (`app/routers/detalle_asesor.py`)

```python
from fastapi import APIRouter
from app.services.detalle_asesor.detalle_asesor import getDetalleData
from app.schemas.reports import DetalleReportResponse, DetalleFilters

router = APIRouter()

@router.post("/detalle-asesor", response_model=DetalleReportResponse)
async def get_detalle_asesor(filters: DetalleFilters):
    return await getDetalleData(filters)
```

Register in `app/main.py`:
```python
from app.routers import detalle_asesor
app.include_router(detalle_asesor.router, prefix="/reports", tags=["reports"])
```

---

## 4. Tests (`tests/test_detalle_asesor.py`)

Create seed file `tests/seeds/detalle_asesor.sql` with:
- 2 sellers, 3 schools each
- Multiple exam types per school
- Data spanning 2 years for date filter testing

Test coverage:
- No filters returns all rows
- Date range filter reduces results
- Country filter works
- Search by seller name returns correct rows
- Search by school name returns correct rows
- Cursor pagination returns correct next page
- `has_more` is False on last page
- `exam_counts` values are correct
- `total` equals sum of all `exam_counts` values
# Architecture

This document explains how the system is designed, how data flows through it, and the key decisions behind that design.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              BROWSER                                     │
│                     React SPA (Vite + TypeScript)                        │
│   Ventas Totales │ Por Asesor │ Detalle Asesor │ Por País                │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ HTTP (JSON) + JWT
                             │
┌────────────────────────────▼────────────────────────────────────────────┐
│                         FastAPI (port 8000)                              │
│   /reports/ventas-totales                                                │
│   /reports/por-asesor          ◄── Supabase Auth (JWT verification)     │
│   /reports/detalle-asesor                                                │
│   /reports/por-pais                                                      │
│   /filters/*                                                             │
└──────────────┬──────────────────────────────────────────────────────────┘
               │ async SQL (asyncpg)
               │
┌──────────────▼──────────────┐        ┌───────────────────────────────┐
│  PostgreSQL (Supabase)       │        │  Source DB (MySQL)            │
│  Reporting DB                │◄───────│  payments, leads, products,   │
│  report_payments             │  ETL   │  sellers, exams, carts        │
│  report_line_items           │ (every │                               │
│  report_payment_allocations  │  3h)   └───────────────────────────────┘
│  exchange_rates              │
│  etl_meta                    │        ┌───────────────────────────────┐
└──────────────────────────────┘◄───────│  Frankfurter API              │
                                  FX    │  api.frankfurter.dev          │
                                 rates  │  (daily, 2 AM)                │
                                        └───────────────────────────────┘
```

**One sentence:** Source DB data is extracted every 3 hours, transformed into a reporting schema, and served by FastAPI to a React dashboard.

---

## Data Flow: From Payment to Dashboard

Here is what happens between a payment being entered in the Source DB and a revenue number appearing on screen.

**1. Payment created in the Source DB**
A seller records a payment for a student's exam registration. The Source DB stores this across `payment`, `cart`, `cart_product`, and `lead` tables.

**2. ETL upsert runs (every 3 hours)**
The scheduler triggers `run_upsert()` in `backend/app/etl/upsert.py`. It:
- Queries the Source DB for payments updated since the last run (`etl_meta.last_run`)
- Extracts related line items (products, exam types, quantities)
- Resolves dimensions: seller name/zone, lead country, exam category
- Looks up the exchange rate for the payment date from the `exchange_rates` table
- Allocates payments proportionally across line items in the same cart
- Upserts all records into `report_payments`, `report_line_items`, and `report_payment_allocations`
- Deletes any records that were soft-deleted in the Source DB

**3. User opens a report in the browser**
React Query fires a fetch to the FastAPI `/reports/*` endpoint with the active filters (date range, country, agent, comparison mode).

**4. FastAPI builds and runs a query**
The service layer constructs a parameterized SQL query against the Reporting DB, applying all filters as WHERE conditions. Results are aggregated (SUM, COUNT) and returned as JSON.

**5. React renders the result**
The component receives typed data and renders tables, KPI cards, and charts. If comparison mode is active, the response includes both the current and comparison period data in a single payload and deltas are computed on the frontend.

---

## ETL Jobs

| Job | File | Schedule | Manual Trigger | What It Does |
|-----|------|----------|----------------|--------------|
| **Payment Upsert** | `etl/upsert.py` | Every 3h (configurable via `PAYMENT_UPSERT_LOOKBACK_HOURS`) | `POST /admin/etl/payment-upsert` | Syncs payments from the Source DB into the Reporting DB |
| **Dimensional Refresh** | `etl/dimensional_refresh.py` | Daily at 3 AM | `POST /admin/etl/dimensional-refresh` | Updates seller names, lead data, and zone info from the Source DB |
| **FX Rate Fetch** | `etl/exchange_rates.py` | Daily at 2 AM | `POST /admin/etl/exchange-rates` | Fetches today's MXN↔USD rate from Frankfurter API |
| **FX Rate Backfill** | `etl/exchange_rate_backfill.py` | Manual only | `make exchange-rate-backfill` | Imports historical rates for all dates present in the Reporting DB |
| **Startup Backfill** | `etl/startup_backfill.py` | On app startup | — | If the Reporting DB is empty, runs a full historical upsert |

Admin endpoints require the `X-Admin-Key` header (see `ADMIN_API_KEY` in `.env`).

---

## Reporting Database Schema

All tables live in the PostgreSQL Reporting DB. Migrations are managed by Alembic (`backend/alembic/versions/`).

### `report_payments`
One row per payment in the Source DB. Stores the resolved dimensions at upsert time (seller name, zone, country/site) so report queries don't need to join back to the Source DB.

Key columns: `payment_id`, `seller_id`, `seller_name`, `zone_name`, `site` (country), `payment_day`, `payment_status`, `payment_mxn`, `payment_usd`, `is_active`

### `report_line_items`
One row per cart product (exam seat, book, course). Links to the payment that funded it.

Key columns: `cart_product_id`, `payment_id`, `product_type` (`exam`/`book`/`course`), `exam_canonical_name`, `quantity`, `allocated_revenue_mxn`, `allocated_revenue_usd`, `include_in_product_breakdown`

### `report_payment_allocations`
Bridge table that records how much of each payment was allocated to each product. Used to calculate `paid_total` per product when a cart contains multiple items.

Key columns: `allocation_id`, `payment_id`, `cart_product_id`, `allocated_amount_mxn`, `allocated_amount_usd`

### `exchange_rates`
Historical FX rates fetched from Frankfurter API.

Key columns: `date`, `base_currency`, `quote_currency`, `rate`

### `etl_meta`
Tracks when each ETL job last ran successfully.

Key columns: `job_name`, `last_run` (timestamp)

---

## Currency Handling

All monetary values are stored in both MXN and USD at upsert time, using the exchange rate for the payment date.

- If no rate exists for a date, the ETL falls back to the nearest available rate and logs a warning.
- The user selects a display currency (MXN or USD) in the top bar. This preference is stored in localStorage and sent as the `X-Currency: MXN|USD` request header.
- Report queries switch between `*_mxn` and `*_usd` columns based on this header.
- Payments from countries with unknown exchange rates (`site IS NULL`) are excluded from country-level reports (Por País) but included in the total (Ventas Totales) — their amounts are still stored correctly.

---

## Comparison Mode

Most reports support comparing the current period against a previous period. The comparison runs as a **second independent query** with a shifted date range, not as a SQL join.

**Three modes:**
- `PREVIOUS_YEAR` — same date range, one year back
- `PREVIOUS_PERIOD` — a period of equal length immediately before the current one
- `CUSTOM` — user-specified date range

**Single request:** When `show_comparison=true` is included in the request params, the backend runs both the current and comparison queries within the same endpoint call and returns them together — a `current` field and a nullable `comparison` field in one JSON response. No second HTTP request is made.

**Backend:** The service runs the same SQL query twice with different date ranges and packages both results into the response schema. Deltas (% change) are then computed on the frontend using `getPercentChange()` from `src/lib/utils.ts`.

---

## Deployment

The production build is a **single Docker image** built from `Dockerfile` at the repo root:

1. **Stage 1 (Node 20):** `npm run build` produces the React SPA into `frontend/dist/`
2. **Stage 2 (Python 3.12):** Copies the built frontend into `backend/app/static/` and installs Python dependencies (including WeasyPrint system deps)
3. **Runtime:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. FastAPI detects `app/static/` exists and mounts it as a SPA fallback — all non-API routes serve `index.html`

**Production environment variables required:**
| Variable | Where | Purpose |
|----------|-------|---------|
| `ENVIRONMENT` | backend `.env` | Set to `production` to use prod DB credentials |
| `PROD_DB_HOST/PORT/USER/PASSWORD/NAME` | backend `.env` | Source DB connection |
| `PROD_REPORTING_DB_HOST/PORT/USER/PASSWORD/NAME` | backend `.env` | Reporting DB connection |
| `SUPABASE_URL` | backend `.env` | For JWT verification |
| `SUPABASE_ANON_KEY` | backend `.env` | For JWT verification |
| `ADMIN_API_KEY` | backend `.env` | Protects ETL admin endpoints |
| `CORS_ORIGINS` | backend `.env` | Comma-separated allowed origins |
| `VITE_SUPABASE_URL` | frontend `.env` (build arg) | Supabase client |
| `VITE_SUPABASE_ANON_KEY` | frontend `.env` (build arg) | Supabase client |
| `VITE_API_URL` | frontend `.env` (build arg) | Backend API base URL |

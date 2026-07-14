# Backend

FastAPI application that serves the reporting API and runs the ETL pipeline.

**Entry point:** `backend/app/main.py`
**Start command (dev):** `make dev` or `make run`

---

## Startup Sequence

When the app starts, the lifespan hook in `main.py` runs these steps in order:

1. **Startup backfill** (`etl/startup_backfill.py`) — if the Reporting DB is empty (first deploy or wiped), runs a full historical payment upsert before accepting traffic.
2. **Scheduler start** (`etl/scheduler.py`) — starts APScheduler with the three recurring ETL jobs.
3. **Static file mount** — if `app/static/` exists (production build), mounts the React SPA as a fallback for all non-API routes.

---

## Routers

| Router file | Path prefix | What it returns | Auth |
|-------------|-------------|-----------------|------|
| `routers/filters.py` | `/filters` | Available filter options (countries, zones, states, cities, sellers) | JWT |
| `routers/total_sales.py` | `/reports/ventas-totales` | Revenue summary, KPIs, trend points, geo breakdown | JWT |
| `routers/por_asesor.py` | `/reports/por-asesor` | Per-seller metrics, paginated, sortable | JWT |
| `routers/detalle_asesor.py` | `/reports/detalle-asesor` | Per-seller line-item detail, paginated, sortable | JWT |
| `routers/por_pais.py` | `/reports/por-pais` | Per-country metrics + per-country detail | JWT |

Each router also exposes `/export/excel` and `/export/pdf` variants (where applicable) that return file downloads.

Admin endpoints (`POST /admin/etl/*`) require `X-Admin-Key: <ADMIN_API_KEY>` instead of a JWT.

---

## Service Layer Pattern

Every report follows the same layered structure:

```
Router (routers/*.py)
  └── Service function (services/<report>/<report>.py)
        └── Repository functions (services/<report>/repository.py)
              └── Raw SQL against ReportingSessionLocal (PostgreSQL)
```

**Routers** parse and validate request params (via Pydantic schemas in `schemas/reports.py`), call the service function, and return the response.

**Services** orchestrate the work: build filter objects, call one or more repository functions, aggregate results, and return a typed response object.

**Repositories** contain the actual SQL. They accept a filter object, build a parameterized query (using a `_build_where()` helper), and return raw SQLAlchemy row objects.

**Schemas** (`schemas/reports.py`) define the Pydantic models for both request filters and JSON responses. The frontend `types/index.ts` mirrors these exactly.

---

## Report Anatomy

Every paginated report (Por Asesor, Detalle Asesor) follows this flow:

1. **Filter object** — incoming query params are parsed into a `*Filters` Pydantic model
2. **WHERE clause builder** — `_build_where(filters)` returns a SQL fragment + param dict. All user input goes into params (never interpolated directly into SQL).
3. **Cursor-based pagination** — the cursor is a base64-encoded JSON payload containing the sort column, sort direction, sort value, and row ID of the last seen row. This avoids offset-based pagination drift.
4. **Sort whitelist** — `SORTABLE_COLUMNS: dict[str, str]` maps frontend column names to safe SQL column names. Only whitelisted columns reach the SQL.
5. **Response** — rows are mapped to Pydantic response models and returned with `next_cursor` and `has_more` for the frontend to page through.

---

## Authentication

**User auth (JWT):**
- Every request to a report or filter endpoint must include `Authorization: Bearer <token>`
- `app/auth.py::verify_token()` calls `GET {SUPABASE_URL}/auth/v1/user` with the token and the anon key
- If Supabase returns a user object, the request proceeds. If not, `401` is returned.
- The frontend catches `401` responses in `src/api/client.ts` and redirects to `/login`

**Admin auth (API key):**
- ETL trigger endpoints (`/admin/etl/*`) check for `X-Admin-Key: <ADMIN_API_KEY>` in the request header
- If missing or wrong, `403` is returned

---

## Exports

### Excel
- **Library:** openpyxl (wrapped by `services/exports/excel.py`)
- **Pattern:** define an `ExcelWorksheetSpec(name, columns, rows)` where `columns` is a list of `ExcelColumn(field, header)`. Call `build_excel_workbook(specs)` to get a `BytesIO` object.
- **Charts:** `build_chart_worksheet(series, title, x_label, y_label)` adds a line chart sheet.
- Reports that need "export all" (ignoring pagination) call a separate `get_all_*_rows()` function that pages through the cursor internally.

### PDF
- **Library:** WeasyPrint (HTML → PDF) + Jinja2 templates
- **Templates:** `services/exports/templates/*.html.j2`
- **Pattern:** build a `*PDFPayload` Pydantic object containing header info, tables, and KPIs, pass it to `render_pdf(template_name, payload)` in `services/exports/pdf_renderer.py`, which renders the Jinja template and runs it through WeasyPrint.
- PDF generation requires WeasyPrint system dependencies (Cairo, Pango) — these are installed in the Dockerfile.

---

## Adding a New Report

1. **Schema** — add `NewReportFilters` and `NewReportResponse` Pydantic models to `schemas/reports.py`
2. **Repository** — create `services/new_report/repository.py` with `fetch_*` functions that run SQL against `ReportingSessionLocal`
3. **Service** — create `services/new_report/new_report.py` with the main service function, filter builder, and cursor logic
4. **Router** — create `routers/new_report.py`, define the endpoint, inject `verify_token`, mount at a path, call the service
5. **Mount** — add `app.include_router(new_report.router)` in `main.py`
6. **Tests** — add `tests/test_new_report_reporting.py` following the pattern in existing test files (seed data in conftest → call service → assert aggregates)

---

## Makefile Reference

Run these from the `backend/` directory.

| Target | What it does |
|--------|-------------|
| `make run` | Start uvicorn in dev mode with auto-reload |
| `make run-prod` | Start uvicorn without auto-reload |
| `make dev` | Start Supabase local + Source DB docker + uvicorn |
| `make db-up` | Start Docker databases only |
| `make migrate` | Run `alembic upgrade head` |
| `make test` | Run all pytest tests with `-v` |
| `make lint` | Run `ruff check .` |
| `make format` | Run `ruff format .` |
| `make format-check` | Check formatting without writing files |
| `make ci` | lint + format-check + test (what CI runs) |
| `make seed-ui` | Truncate reporting tables and load test seed data |
| `make exchange-rate-backfill` | Run the historical FX rate importer |

---

## Testing

**Framework:** pytest + pytest-asyncio

**Test DB setup:** `tests/conftest.py` spins up an in-memory async Source DB engine and a PostgreSQL Reporting DB engine using the credentials in `.env.test`. Alembic migrations run against the test reporting DB before each session. Seed data is loaded per-test using fixtures.

**Run a single file:**
```bash
cd backend
pytest tests/test_por_asesor_reporting.py -v
```

**Run a single test:**
```bash
pytest tests/test_por_asesor_reporting.py::test_revenue_totals_match -v
```

**Key test files:**
| File | What it tests |
|------|--------------|
| `test_etl.py` | Payment upsert and dimensional refresh jobs end-to-end |
| `test_ventas_totales_reporting.py` | Ventas Totales aggregation accuracy |
| `test_por_asesor_reporting.py` | Por Asesor aggregation accuracy |
| `test_por_pais_reporting.py` | Por País aggregation accuracy |
| `test_excel_exports.py` | Excel file generation (column names, row count) |
| `test_other_reports_pdf.py` | PDF payload construction |
| `test_admin_endpoints.py` | ETL trigger endpoints return 200 |
| `test_api.py` | Full HTTP integration tests through the FastAPI test client |

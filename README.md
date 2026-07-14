# QC Analytics

Business intelligence and reporting layer for the Quality Circle platform. Ingests sales and payment data from the Source DB, transforms it into a reporting schema (PostgreSQL), and serves it through a React dashboard.

> **Source DB** refers to the Quality Circle MySQL database — the operational system where sellers, students, payments, and exam registrations are recorded day-to-day.

**Four reports:**
- **Ventas Totales** — Revenue summary by product type, trend over time, and geography
- **Por Asesor** — Per-seller breakdown of revenue, expected cost, profit margin, and product mix
- **Detalle Asesor** — Deep dive into a single seller's exam registrations, schools, and students
- **Por País** — Revenue and exam volume broken down by country

All reports support date filtering, geographic filtering (country, zone, state, city), and a **comparison mode** that shows the same period from a prior year or a custom range side-by-side.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic |
| Reporting DB | PostgreSQL 16 (hosted on Supabase) |
| Source DB | MySQL 8 (Quality Circle) |
| Auth | Supabase Auth (JWT) |
| ETL Scheduler | APScheduler |
| PDF export | WeasyPrint + Jinja2 |
| Excel export | openpyxl |
| FX rates | Frankfurter API |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node 20+
- Docker (for local Source DB and Reporting DB)

### 1. Clone the repo

```bash
git clone <repo-url>
cd platform
```

### 2. Backend setup

```bash
cd backend

# Create virtualenv and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy environment variables and fill in values (see table below)
cp .env.example .env   

# Start local databases (Source DB + Reporting DB via Docker)
make db-up

# Run database migrations
make migrate

# (Optional) Load seed data for local testing
make seed-ui

# Start the dev server (http://localhost:8000)
make dev
```

### 3. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env   

# Start the dev server (http://localhost:5173)
npm run dev
```

The frontend dev server proxies API requests to `http://localhost:8000` via `VITE_API_URL`.

---

## Environment Variables

### `backend/.env`

| Variable | Purpose |
|----------|---------|
| `ENVIRONMENT` | `development` or `production` — controls which DB credentials are used |
| `DEV_DB_HOST/PORT/USER/PASSWORD/NAME` | Source DB connection (development) |
| `PROD_DB_HOST/PORT/USER/PASSWORD/NAME` | Source DB connection (production) |
| `DEV_REPORTING_DB_HOST/PORT/USER/PASSWORD/NAME` | Reporting DB connection (development) |
| `PROD_REPORTING_DB_HOST/PORT/USER/PASSWORD/NAME` | Reporting DB connection (production) |
| `SUPABASE_URL` | Supabase project URL (for JWT verification) |
| `SUPABASE_ANON_KEY` | Supabase anon key (for JWT verification) |
| `ADMIN_API_KEY` | Secret key for ETL admin endpoints (`X-Admin-Key` header) |
| `CORS_ORIGINS` | Comma-separated allowed origins (e.g. `http://localhost:5173`) |
| `PAYMENT_UPSERT_LOOKBACK_HOURS` | How far back the ETL looks for updated payments (default: `3`) |

### `frontend/.env`

| Variable | Purpose |
|----------|---------|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon key |
| `VITE_API_URL` | Backend API base URL (e.g. `http://localhost:8000`) |

---

## Documentation

| Doc | What it covers |
|-----|---------------|
| [docs/architecture.md](docs/architecture.md) | System design, data flow, ETL pipeline, DB schema, currency handling, deployment |
| [docs/backend.md](docs/backend.md) | Routers, service layer, auth, exports, adding a new report, Makefile reference, testing |
| [docs/frontend.md](docs/frontend.md) | Routes, components, data fetching, filters, comparison mode, API client, adding a new report |

Interactive API reference (auto-generated): [`http://localhost:8000/docs`](http://localhost:8000/docs) when the backend is running.

---

Developed by [Manuel Torres](https://github.com/manueltorres0)

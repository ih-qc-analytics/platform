from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.etl.dimensional_refresh import run_dimensional_refresh
from app.etl.exchange_rates import fetch_and_store_rates
from app.etl.scheduler import start_scheduler
from app.etl.startup_backfill import run_startup_backfill_if_needed
from app.etl.upsert import run_upsert
from app.routers import detalle_asesor, filters, por_asesor, por_pais, total_sales
from app.validator import validate_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.source_db_url or settings.host:
        print(f"--- Starting app in {settings.env_mode} mode ---")
        await validate_schema()

    if settings.reporting_db_url:
        await run_startup_backfill_if_needed()
        start_scheduler()

    yield

app = FastAPI(
    title="IH-QC Analytics",
    version="0.1.0",
    docs_url="/docs" if settings.env_mode == "dev" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.env_mode}

# Admin ETL triggers — protect with API key before production
@app.post("/admin/etl/payment-upsert")
async def trigger_payment_upsert():
    await run_upsert()
    return {"status": "ok"}

@app.post("/admin/etl/dimensional-refresh")
async def trigger_dimensional_refresh():
    await run_dimensional_refresh()
    return {"status": "ok"}

@app.post("/admin/etl/fetch-rates")
async def trigger_fetch_rates():
    await fetch_and_store_rates()
    return {"status": "ok"}

app.include_router(filters.router, prefix="/filters", tags=["filters"])
app.include_router(total_sales.router, prefix="/reports", tags=["reports"])
app.include_router(por_asesor.router, prefix="/reports", tags=["reports"])
app.include_router(detalle_asesor.router, prefix="/reports", tags=["reports"])
app.include_router(por_pais.router, prefix="/reports", tags=["reports"])

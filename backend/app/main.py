import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import logging

from sqlalchemy.exc import SQLAlchemyError

from app.auth import verify_token
from app.config import settings
from app.etl.dimensional_refresh import run_dimensional_refresh
from app.etl.exchange_rates import fetch_and_store_rates
from app.etl.scheduler import start_scheduler
from app.etl.startup_backfill import run_startup_backfill_if_needed
from app.etl.upsert import run_upsert
from app.routers import auth, detalle_asesor, filters, por_asesor, por_pais, total_sales


def verify_admin_key(x_admin_key: str = Header()) -> None:
    if not settings.admin_api_key:
        raise HTTPException(status_code=503, detail="Admin key not configured")
    if not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=403, detail="Forbidden")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.reporting_db_url:
        try:
            await run_startup_backfill_if_needed()
        except Exception:
            logger.exception(
                "Startup backfill failed — app will start with existing reporting data"
            )
        start_scheduler()

    yield


app = FastAPI(
    title="IH-QC Analytics",
    version="0.1.0",
    docs_url="/docs" if settings.env_mode == "dev" else None,
    lifespan=lifespan,
)


@app.exception_handler(SQLAlchemyError)
async def db_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("DB error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=503, content={"detail": "Database error"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.env_mode}


@app.post("/admin/etl/payment-upsert", dependencies=[Depends(verify_admin_key)])
async def trigger_payment_upsert():
    result = await run_upsert()
    return {"status": "ok", **result}


@app.post("/admin/etl/dimensional-refresh", dependencies=[Depends(verify_admin_key)])
async def trigger_dimensional_refresh():
    result = await run_dimensional_refresh()
    return {"status": "ok", **result}


@app.post("/admin/etl/fetch-rates", dependencies=[Depends(verify_admin_key)])
async def trigger_fetch_rates():
    result = await fetch_and_store_rates()
    return {"status": "ok", **result}


app.include_router(auth.router, prefix="/auth", tags=["auth"])

_auth = [Depends(verify_token)]
app.include_router(filters.router, prefix="/filters", tags=["filters"], dependencies=_auth)
app.include_router(total_sales.router, prefix="/reports", tags=["reports"], dependencies=_auth)
app.include_router(por_asesor.router, prefix="/reports", tags=["reports"], dependencies=_auth)
app.include_router(detalle_asesor.router, prefix="/reports", tags=["reports"], dependencies=_auth)
app.include_router(por_pais.router, prefix="/reports", tags=["reports"], dependencies=_auth)

# ── Static file serving (production monolithic build) ────────────────────────
# The Dockerfile copies the Vite build output to ./static relative to /app.
# In local dev this directory won't exist, so we skip mounting gracefully.
_static_dir = Path(__file__).parent.parent / "static"
if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(_static_dir / "index.html")

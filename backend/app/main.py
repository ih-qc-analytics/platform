from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.validator import validate_schema
from app.routers import detalle_asesor, filters, por_asesor, por_pais, total_sales
import logging 
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)


async def refresh_rates(app: FastAPI):
    url = "https://api.frankfurter.dev/v2/rates?base=MXN&quotes=COP,PEN"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            app.state.rates = {item['quote']: item['rate'] for item in data}
            print(f"Rates refreshed successfully at {data[0]['date']}")
        except Exception as e:
            print(f"Failed to refresh rates: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.host:
        print(f"--- Starting app in {settings.env_mode} mode ---")
        await validate_schema()

    await refresh_rates(app)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        refresh_rates, 
        'cron', 
        hour=8, 
        minute=0, 
        args=[app]
    )
    scheduler.start()
    yield
    scheduler.shutdown()

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
    return {"status": "ok", "environment": settings.environment}

app.include_router(filters.router, prefix="/filters", tags=["filters"])
app.include_router(total_sales.router, prefix="/reports", tags=["reports"])
app.include_router(por_asesor.router, prefix="/reports", tags=["reports"])
app.include_router(detalle_asesor.router, prefix="/reports", tags=["reports"])
app.include_router(por_pais.router, prefix="/reports", tags=["reports"])

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.validator import validate_schema
from app.routers import filters, total_sales
import logging 

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.source_db_url:
        await validate_schema()
    yield

app = FastAPI(
    title="IH-QC Analytics",
    version="0.1.0",
    docs_url="/docs" if settings.environment == "development" else None,
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

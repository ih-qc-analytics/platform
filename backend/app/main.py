from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.validator import validate_schema

app = FastAPI(
    title="IH-QC Analytics",
    version="0.1.0",
    docs_url="/docs" if settings.environment == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    if settings.source_db_url:
        await validate_schema()

@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}

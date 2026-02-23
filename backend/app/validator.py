from sqlalchemy import text
from app.database import SessionLocal
import logging

logger = logging.getLogger(__name__)

# tables and columns your reports depend on
REQUIRED_SCHEMA = {
    "cart": ["id", "total", "cost", "sub_total", "created_at", "sale_type", "billing_status"],
    "payment": ["id", "quantity", "status", "payment_date", "method"],
    "seller": ["id", "name", "last_name"],
    "lead": ["id", "name", "site", "type"],
    "product": ["id", "name", "product_type", "sale_price", "purchase_price"],
    "seller_lead": ["id", "seller_id", "lead_id", "business_status", "promotional_status"],
    "cart_product": ["id", "cart_id", "product_id", "quantity", "total", "test_date"],
}

async def validate_schema():
    if not SessionLocal:
        logger.warning("⚠️  No DB configured, skipping schema validation")
        return
    async with SessionLocal() as session:
        missing = []
        for table, columns in REQUIRED_SCHEMA.items():
            for col in columns:
                result = await session.execute(text("""
                    SELECT COUNT(*) FROM information_schema.columns
                    WHERE table_name = :table AND column_name = :col
                """), {"table": table, "col": col})
                count = result.scalar()
                if count == 0:
                    missing.append(f"{table}.{col}")

        if missing:
            logger.warning(f"⚠️  Schema drift detected — missing: {missing}")
        else:
            logger.info("✅ Schema validation passed")
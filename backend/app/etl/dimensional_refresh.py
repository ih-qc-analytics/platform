from datetime import datetime
from sqlalchemy import text
from app.database import SessionLocal
from app.reporting.database import ReportingSessionLocal
from app.etl.payment_upsert import _log
import logging

logger = logging.getLogger(__name__)

DIMENSIONAL_QUERY = """
    SELECT DISTINCT
        l.id                                as lead_id,
        l.name                              as school_name,
        l.site                              as site,
        z.name                              as zone_name,
        la.stateName                        as state_name,
        la.city                             as city,
        s.id                                as seller_id,
        CONCAT(s.name, ' ', s.lastName)     as seller_name
    FROM `lead` l
    LEFT JOIN zone z ON l.zoneId = z.id
    LEFT JOIN (
        SELECT la1.leadId, la1.stateName, la1.city
        FROM lead_address la1
        WHERE la1.id = (
            SELECT MIN(id) FROM lead_address la2
            WHERE la2.leadId = la1.leadId
            AND la2.deletedAt IS NULL
        )
    ) la ON la.leadId = l.id
    JOIN seller_lead sl ON sl.leadId = l.id
    JOIN seller s ON sl.sellerId = s.id
"""


async def run_dimensional_refresh() -> None:
    start = datetime.now()
    logger.info("Job 2 started")

    try:
        async with SessionLocal() as source:
            result = await source.execute(text(DIMENSIONAL_QUERY))
            rows = result.mappings().fetchall()

        async with ReportingSessionLocal() as reporting:
            async with reporting.begin():
                for row in rows:
                    await reporting.execute(text("""
                        UPDATE report_line_items
                        SET
                            school_name = :school_name,
                            site        = :site,
                            zone_name   = :zone_name,
                            state_name  = :state_name,
                            city        = :city,
                            seller_name = :seller_name
                        WHERE lead_id   = :lead_id
                        AND seller_id   = :seller_id
                    """), dict(row))

        logger.info(f"Job 2 complete — {len(rows)} leads refreshed")
        await _log(start, "dimensional_refresh", len(rows), "success")

    except Exception as e:
        logger.error(f"Job 2 failed: {e}")
        await _log(start, "dimensional_refresh", 0, "failed", error=str(e))
        raise

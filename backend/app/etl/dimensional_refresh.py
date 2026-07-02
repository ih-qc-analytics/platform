from datetime import datetime

from sqlalchemy import text

from app.database import SessionLocal
from app.enums import ETLJobName
from app.etl.shared import LEAD_ADDRESS_SUBQUERY, log_etl_run, split_multi_value
from app.reporting.database import ReportingSessionLocal


DIMENSIONAL_QUERY = """
    SELECT DISTINCT
        l.id                            AS lead_id,
        l.name                          AS school_name,
        l.site                          AS site,
        z.name                          AS zone_name,
        la.stateName                    AS state_name,
        la.city                         AS city,
        la.state_names                  AS all_states,
        la.city_names                   AS all_cities,
        s.id                            AS seller_id,
        CONCAT(s.name, ' ', s.lastName) AS seller_name
    FROM `lead` l
    LEFT JOIN zone z ON l.zoneId = z.id
    {LEAD_ADDRESS_SUBQUERY}
    JOIN seller_lead sl ON sl.leadId = l.id
    JOIN seller s ON sl.sellerId = s.id
"""

DIMENSION_UPDATE = """
    UPDATE {table}
    SET
        school_name = :school_name,
        site        = :site,
        zone_name   = :zone_name,
        state_name  = :state_name,
        city        = :city,
        all_states  = :all_states,
        all_cities  = :all_cities,
        state_names = :all_states,
        city_names  = :all_cities,
        seller_name = :seller_name
    WHERE lead_id = :lead_id
    AND seller_id = :seller_id
"""


async def run_dimensional_refresh() -> dict:
    start = datetime.now()
    try:
        async with SessionLocal() as source:
            result = await source.execute(
                text(DIMENSIONAL_QUERY.format(LEAD_ADDRESS_SUBQUERY=LEAD_ADDRESS_SUBQUERY))
            )
            rows = result.mappings().fetchall()

        async with ReportingSessionLocal() as reporting:
            async with reporting.begin():
                for raw_row in rows:
                    row = dict(raw_row)
                    row["all_states"] = split_multi_value(row.get("all_states"))
                    row["all_cities"] = split_multi_value(row.get("all_cities"))
                    for table in ("report_payments", "report_line_items"):
                        await reporting.execute(text(DIMENSION_UPDATE.format(table=table)), row)

        await log_etl_run(ETLJobName.DIMENSIONAL_REFRESH, len(rows), "success", start)
        return {"leads_refreshed": len(rows)}
    except Exception as error:
        await log_etl_run(ETLJobName.DIMENSIONAL_REFRESH, 0, "failed", start, error=str(error))
        raise

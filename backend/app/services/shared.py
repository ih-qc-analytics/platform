from datetime import date, datetime

from app.enums import PaymentStatus


def coerce_iso_date_param(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def report_date_expr(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return f"COALESCE({prefix}payment_day, {prefix}payment_date, DATE({prefix}created_at))"


def build_geo_where_clause(filters) -> tuple[str, dict]:
    """
    Build a WHERE clause for report_line_items (single-table, no joins).
    Always filters: is_active = TRUE AND payment_status = 'Aprobado'.
    All list params use PostgreSQL's = ANY(:param) — no expanding bindparams needed.
    """
    conditions = [
        "is_active = TRUE",
        "payment_status = :payment_status",
    ]
    params: dict = {
        "payment_status": PaymentStatus.APROBADO.value,
    }

    if getattr(filters, "countries", None):
        conditions.append("site = ANY(:countries)")
        params["countries"] = list(filters.countries)
    if getattr(filters, "zones", None):
        conditions.append("zone_name = ANY(:zones)")
        params["zones"] = list(filters.zones)
    if getattr(filters, "states", None):
        conditions.append(
            "COALESCE(state_names, ARRAY[]::text[]) && CAST(:states AS text[])"
        )
        params["states"] = list(filters.states)
    if getattr(filters, "cities", None):
        conditions.append(
            "COALESCE(city_names, ARRAY[]::text[]) && CAST(:cities AS text[])"
        )
        params["cities"] = list(filters.cities)
    if getattr(filters, "date_from", None):
        conditions.append(f"{report_date_expr()} >= :date_from")
        params["date_from"] = coerce_iso_date_param(filters.date_from)
    if getattr(filters, "date_to", None):
        conditions.append(f"{report_date_expr()} <= :date_to")
        params["date_to"] = coerce_iso_date_param(filters.date_to)
    if getattr(filters, "year", None):
        conditions.append("year = :year")
        params["year"] = filters.year

    return " AND ".join(conditions), params

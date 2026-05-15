from app.enums import PaymentStatus


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
        conditions.append("state_name = ANY(:states)")
        params["states"] = list(filters.states)
    if getattr(filters, "cities", None):
        conditions.append("city = ANY(:cities)")
        params["cities"] = list(filters.cities)
    if getattr(filters, "date_from", None):
        conditions.append("created_at >= :date_from")
        params["date_from"] = filters.date_from
    if getattr(filters, "date_to", None):
        conditions.append("created_at <= :date_to")
        params["date_to"] = filters.date_to
    if getattr(filters, "year", None):
        conditions.append("year = :year")
        params["year"] = filters.year

    return " AND ".join(conditions), params

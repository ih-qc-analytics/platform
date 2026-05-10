from collections.abc import Sequence


def build_geo_where_clause(filters) -> tuple[list[str], dict[str, object], list[str]]:
    conditions = ["c.deletedAt IS NULL"]
    params: dict[str, object] = {}
    expanding_keys: list[str] = []
    countries = getattr(filters, "countries", [])
    zones = getattr(filters, "zones", [])
    states = getattr(filters, "states", [])
    cities = getattr(filters, "cities", [])

    def add_expanding_condition(field: str, values: Sequence[str], sql: str) -> None:
        if values:
            conditions.append(sql)
            params[field] = list(values)
            expanding_keys.append(field)

    add_expanding_condition("countries", countries, "l.site IN :countries")
    add_expanding_condition("zones", zones, "z.name IN :zones")
    add_expanding_condition(
        "states",
        states,
        """
        EXISTS (
            SELECT 1
            FROM lead_address addr
            WHERE addr.leadId = l.id
              AND addr.deletedAt IS NULL
              AND addr.stateName IN :states
        )
        """.strip(),
    )
    add_expanding_condition(
        "cities",
        cities,
        """
        EXISTS (
            SELECT 1
            FROM lead_address addr
            WHERE addr.leadId = l.id
              AND addr.deletedAt IS NULL
              AND addr.city IN :cities
        )
        """.strip(),
    )

    return conditions, params, expanding_keys

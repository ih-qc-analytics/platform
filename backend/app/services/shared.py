from collections.abc import Sequence


def build_geo_where_clause(filters) -> tuple[list[str], dict[str, object], list[str]]:
    conditions = ["c.deletedAt IS NULL"]
    params: dict[str, object] = {}
    expanding_keys: list[str] = []

    def add_expanding_condition(field: str, values: Sequence[str], sql: str) -> None:
        if values:
            conditions.append(sql)
            params[field] = list(values)
            expanding_keys.append(field)

    add_expanding_condition("countries", filters.countries, "l.site IN :countries")
    add_expanding_condition("zones", filters.zones, "z.name IN :zones")
    add_expanding_condition("states", filters.states, "la.stateName IN :states")
    add_expanding_condition("cities", filters.cities, "la.city IN :cities")

    return conditions, params, expanding_keys

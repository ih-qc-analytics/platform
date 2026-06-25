from pathlib import Path

from db import get_engine
from sqlalchemy import inspect
import json

## tablas necesarias para realizar los reportes
REPORT_TABLES = [
    "cart",
    "cart_product",
    "payment",
    "seller",
    "seller_lead",
    "lead",
    "lead_address",
    "product",
    "exam_cat",
    "auth",
    "zone",
]


## analyza el esquema de la base de datos y produce un snapshot en el
# archivo schema_snapshot.json
def main():
    inspector = inspect(get_engine())
    existing_tables = inspector.get_table_names()
    snapshot = {}
    for table in REPORT_TABLES:
        if table not in existing_tables:
            print(f"Table '{table}' not found in DB")
        else:
            columns = inspector.get_columns(table)
            snapshot[table] = {
                "columns": [
                    {"name": col["name"], "type": str(col["type"]), "nullable": col["nullable"]}
                    for col in columns
                ]
            }
            snapshot[table]["foreign_keys"] = inspector.get_foreign_keys(table)
            snapshot[table]["primary_key"] = inspector.get_pk_constraint(table)[
                "constrained_columns"
            ]

    output_path = Path(__file__).parent.parent / "schema_snapshot.json"
    with open(output_path, "w") as file:
        json.dump(snapshot, file, indent=2)


if __name__ == "__main__":
    main()

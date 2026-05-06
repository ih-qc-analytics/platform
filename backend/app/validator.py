import json
import logging
from pathlib import Path
from sqlalchemy import text
from app.database import SessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

## carga los esquemas snapshot de la base de datos
def load_schema() -> dict:
    path = Path(__file__).parent.parent / "schema_snapshot.json"
    with open(path) as f:
        return json.load(f)


def get_db_name() -> str:
    return settings.dbname

## verifica que las columnas de la base de datos live tienen el mismo nombre, tipo, y null
## constraint que las columnas del snapshot que se usan para la fabricacion de reportes
def check_columns(table: str, table_data: dict, live_cols: dict) -> list[str]:
    issues = []
    for col in table_data["columns"]:
        name = col["name"]
        if name not in live_cols:
            issues.append(f"{table}.{name} column missing from live DB")
        else:
            live_type = live_cols[name]["data_type"].lower()
            snapshot_type = col["type"].lower()
            if live_type not in snapshot_type:
                issues.append(f"{table}.{name} type changed: snapshot={col['type']} live={live_cols[name]['data_type']}")
            live_nullable = live_cols[name]["is_nullable"] == "YES"
            if live_nullable != col["nullable"]:
                issues.append(f"{table}.{name} nullable changed: snapshot={col['nullable']} live={live_nullable}")
    return issues

## verifica que los primary keys de la base de datos son las mismas que 
# las del snapshot que se usa para la fabricacion de reportes
def check_primary_keys(table: str, table_data: dict, live_pks: list) -> list[str]:
    issues = []
    snapshot_pk = set(table_data["primary_key"])
    live_pk = set(live_pks)
    if snapshot_pk != live_pk:
        issues.append(f"{table} PK changed: snapshot={snapshot_pk} live={live_pk}")
    return issues

## verifica que los foreign keys de la base de datos son los mismos que 
# las del snapshot que se usa para la fabricacion de reportes
def check_foreign_keys(table: str, table_data: dict, live_fks: dict) -> list[str]:
    issues = []
    for fk in table_data["foreign_keys"]:
        col = fk["constrained_columns"][0]
        if col not in live_fks:
            issues.append(f"{table}.{col} FK missing from live DB")
        else:
            live = live_fks[col]
            if live["referenced_table_name"] != fk["referred_table"]:
                issues.append(f"{table}.{col} FK referred_table changed: snapshot={fk['referred_table']} live={live['referenced_table_name']}")
            if live["referenced_column_name"] != fk["referred_columns"][0]:
                issues.append(f"{table}.{col} FK referred_column changed: snapshot={fk['referred_columns'][0]} live={live['referenced_column_name']}")
    return issues

## obtiene las columnas y sus tipos de las tablas en la base de datos live
async def fetch_live_columns(session, db_name: str, tables: tuple) -> dict:
    result = await session.execute(text("""
        SELECT
            TABLE_NAME  AS table_name,
            COLUMN_NAME AS column_name,
            DATA_TYPE   AS data_type,
            IS_NULLABLE AS is_nullable
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = :db_name
        AND TABLE_NAME IN :tables
    """), {"db_name": db_name, "tables": tables})
    per_table = {}
    for r in result.mappings().fetchall():
        t = r["table_name"]
        if t not in per_table:
            per_table[r.table_name] = {}
        per_table[r.table_name][r.column_name] = {
            "data_type": r.data_type,
            "is_nullable": r.is_nullable
        }
    return per_table

## obtiene las primary keys de las tablas en la base de datos live
async def fetch_live_primary_keys(session, db_name: str, tables: tuple) -> dict:
    result = await session.execute(text("""
        SELECT
            TABLE_NAME  AS table_name,
            COLUMN_NAME AS column_name
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE table_schema = :db_name
        AND table_name IN :tables
        AND constraint_name = 'PRIMARY'
    """), {"db_name": db_name, "tables": tables})
    per_table = {}
    for r in result.mappings().fetchall():
        t = r["table_name"]
        if t not in per_table:
            per_table[t] = []
        per_table[t].append(r["column_name"])
    return per_table

# Obtiene las foreign keys de las tablas en la base de datos live
async def fetch_live_foreign_keys(session, db_name: str, tables: tuple) -> dict:
    result = await session.execute(text("""
        SELECT
            TABLE_NAME              AS table_name,
            COLUMN_NAME             AS column_name,
            REFERENCED_TABLE_NAME   AS referenced_table_name,
            REFERENCED_COLUMN_NAME  AS referenced_column_name
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE table_schema = :db_name
        AND table_name IN :tables
        AND referenced_table_name IS NOT NULL
    """), {"db_name": db_name, "tables": tables})
    per_table = {}
    for r in result.mappings().fetchall():
        t = r["table_name"]
        if t not in per_table:
            per_table[r.table_name] = {}
        per_table[r.table_name][r.column_name] = {
            "referenced_table_name": r.referenced_table_name,
            "referenced_column_name": r.referenced_column_name
        }
    return per_table

# valida que el esquema de la base de datos en vivo coincida con el snapshot guardado
async def validate_schema():
    snapshot = load_schema()
    tables = tuple(snapshot.keys())
    db_name = get_db_name()
    issues = []

    async with SessionLocal() as session:
        per_table_cols = await fetch_live_columns(session, db_name, tables)
        per_table_pk = await fetch_live_primary_keys(session, db_name, tables)
        per_table_fk = await fetch_live_foreign_keys(session, db_name, tables)

    for table, table_data in snapshot.items():
        issues += check_columns(table, table_data, per_table_cols.get(table, {}))
        issues += check_primary_keys(table, table_data, per_table_pk.get(table, []))
        issues += check_foreign_keys(table, table_data, per_table_fk.get(table, {}))

    if issues:
        logger.error(f"Schema drift detected — {len(issues)} issue(s):")
        for issue in issues:
            logger.error(f"  {issue}")
    else:
        logger.info("Schema validation passed")
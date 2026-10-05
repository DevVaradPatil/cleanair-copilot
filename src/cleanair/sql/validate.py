"""🧠 SQL validator (SPEC §8.1 step 3) -- Varad implements `validate`. tests/test_sql_validate.py is the spec.

Layer 1 of SQL safety. execute.py adds layer 2 (read-only connection, no external access, timeout, row cap),
so a validator bug is not a data-loss bug -- but the validator is what makes the guarantees *explainable*:
"only a single SELECT over allow-listed tables/columns can reach the database".

Suggested approach: sqlglot.parse(sql, read="duckdb") -> exactly one statement -> it must be a SELECT (or a
UNION / WITH ... SELECT); walk the AST: every exp.Table must be in ALLOWED (CTE names are fine), every
exp.Column must exist in one of the referenced tables (or be a CTE / alias column), and no exp.Anonymous /
exp.Func whose name is in FORBIDDEN_FUNCTIONS (file and network readers, settings, environment). Then append
LIMIT max_rows when the outermost query has none and cap a larger one.
"""

from sqlglot import exp  # noqa: F401  (you'll want it)

# table -> allowed columns. Kept in sync with src/cleanair/data/schema.sql by tests/test_sql_validate.py.
ALLOWED: dict[str, set[str]] = {
    "city_aqi_daily": {
        "city",
        "date",
        "aqi",
        "aqi_category",
        "prominent_pollutant",
        "stations_reporting",
        "stations_total",
    },
    "aqi_categories": {"aqi_category", "severity_rank", "aqi_min", "aqi_max"},
    "stations": {"station_id", "name", "city", "state", "latitude", "longitude", "agency"},
    "readings_daily": {
        "station_id",
        "date",
        "pm25",
        "pm10",
        "no2",
        "so2",
        "co",
        "o3",
        "aqi",
        "aqi_category",
        "coverage_pct",
    },
    "city_daily": {"city", "date", "pm25", "pm10", "max_station_aqi", "n_stations"},
}

# DuckDB functions that touch files, the network, settings or the environment.
FORBIDDEN_FUNCTIONS = {
    "read_csv",
    "read_csv_auto",
    "read_parquet",
    "parquet_scan",
    "read_json",
    "read_json_auto",
    "read_ndjson",
    "read_text",
    "read_blob",
    "glob",
    "sniff_csv",
    "getenv",
    "current_setting",
    "duckdb_settings",
    "duckdb_extensions",
    "duckdb_secrets",
    "query",
    "query_table",
    "iceberg_scan",
    "delta_scan",
    "postgres_scan",
    "sqlite_scan",
    "mysql_scan",
}


class SQLValidationError(ValueError):
    """Raised with a human-readable reason; the text-to-SQL repair loop feeds it back to the LLM."""


def validate(sql: str, allowed: dict[str, set[str]] = ALLOWED, max_rows: int = 1000) -> str:
    """🧠 Return a safe version of `sql` (with LIMIT <= max_rows), or raise SQLValidationError explaining why not."""
    raise NotImplementedError("🧠 validate is Varad's to implement (plan step 3.4)")

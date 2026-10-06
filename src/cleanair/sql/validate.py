"""🧠 SQL validator (SPEC §8.1 step 3). Explained in docs/BRAIN_NOTES.md; tests/test_sql_validate.py is the spec.

Layer 1 of SQL safety. execute.py adds layer 2 (read-only connection, no external access, timeout, row cap),
so a validator bug is not a data-loss bug -- but the validator is what makes the guarantee *explainable*:
"only a single SELECT over allow-listed tables and columns can reach the database".

Allow-list, not deny-list: parse the SQL into a syntax tree (sqlglot, DuckDB dialect) and accept it only if every
part is something we explicitly allow. A deny-list ("block DROP, DELETE, ...") always misses a variant.
"""

import logging

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

logging.getLogger("sqlglot").setLevel(logging.ERROR)  # "falling back to Command" noise; such input is rejected anyway

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


def _parse_single(sql: str) -> exp.Expression:
    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except ParseError as e:
        raise SQLValidationError(f"could not parse the SQL: {str(e).splitlines()[0]}") from e
    if len(statements) != 1:
        raise SQLValidationError(f"exactly one statement is allowed, got {len(statements)}")
    return statements[0]


def _check_tables(tree: exp.Expression, allowed: dict[str, set[str]]) -> set[str]:
    """Every table is allow-listed or a CTE defined in this query; returns the real tables referenced."""
    ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    real: set[str] = set()
    for t in tree.find_all(exp.Table):
        if t.args.get("db") or t.args.get("catalog"):  # information_schema.tables, other.db.t, ...
            raise SQLValidationError(f"schema-qualified table '{t.sql(dialect='duckdb')}' is not allowed")
        if not isinstance(t.this, exp.Identifier):  # FROM 'file.csv' or FROM some_function(...)
            raise SQLValidationError(f"'{t.sql(dialect='duckdb')}' is not allowed in FROM; use an allowed table")
        name = t.name.lower()
        if name in ctes:
            continue
        if name not in allowed:
            raise SQLValidationError(f"table '{name}' is not allowed; allowed tables: {', '.join(sorted(allowed))}")
        real.add(name)
    return real


def _check_functions(tree: exp.Expression) -> None:
    for f in tree.find_all(exp.Func):
        name = (f.name if isinstance(f, exp.Anonymous) else f.sql_name()).lower()
        if name in FORBIDDEN_FUNCTIONS:
            raise SQLValidationError(f"function '{name}' is not allowed (file, network or environment access)")


def _check_columns(tree: exp.Expression, tables: set[str], allowed: dict[str, set[str]]) -> None:
    """Columns must exist in a referenced table, or be an alias defined in the query (SELECT x AS a ... ORDER BY a).

    ponytail: checks against the union of the referenced tables' columns, not per table qualifier; enough to stop
    invented columns, and the read-only executor rejects anything that is truly ambiguous.
    """
    known = set().union(*(allowed[t] for t in tables)) if tables else set()
    known |= {a.alias.lower() for a in tree.find_all(exp.Alias) if a.alias}
    known |= {c.alias_or_name.lower() for cte in tree.find_all(exp.CTE) for c in cte.find_all(exp.Alias)}
    known |= {
        col.name.lower() for t in tree.find_all(exp.TableAlias) for col in (t.args.get("columns") or [])
    }  # WITH w(a, b) AS ...
    for col in tree.find_all(exp.Column):
        name = col.name.lower()
        if name and name not in known:
            raise SQLValidationError(
                f"column '{name}' does not exist in {', '.join(sorted(tables)) or 'the referenced tables'}"
            )


def _apply_limit(tree: exp.Expression, max_rows: int) -> exp.Expression:
    limit = tree.args.get("limit")
    if limit is None:
        return tree.limit(max_rows)
    value = limit.expression
    if not (isinstance(value, exp.Literal) and value.is_int):
        raise SQLValidationError("LIMIT must be a plain integer")
    if int(value.this) > max_rows:
        limit.set("expression", exp.Literal.number(max_rows))
    return tree


def validate(sql: str, allowed: dict[str, set[str]] = ALLOWED, max_rows: int = 1000) -> str:
    """Return a safe version of `sql` (with LIMIT <= max_rows), or raise SQLValidationError explaining why not."""
    tree = _parse_single(sql)
    if not isinstance(tree, exp.Query):  # Select, Union/Except/Intersect (WITH ... SELECT is a Select)
        raise SQLValidationError(f"only SELECT queries are allowed, got {type(tree).__name__.upper()}")
    tables = _check_tables(tree, allowed)
    _check_functions(tree)
    _check_columns(tree, tables, allowed)
    return _apply_limit(tree, max_rows).sql(dialect="duckdb")

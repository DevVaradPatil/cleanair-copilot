"""🧠 SQL validator (SPEC §8.1-8.2: 100% of malicious SQL rejected, legitimate SQL passes with a LIMIT)."""

import re
from pathlib import Path

import pytest

from cleanair.sql.validate import ALLOWED, SQLValidationError, validate

MALICIOUS = [
    # not a single SELECT
    "DROP TABLE city_aqi_daily",
    "DELETE FROM city_aqi_daily",
    "UPDATE city_aqi_daily SET aqi = 0",
    "INSERT INTO aqi_categories VALUES ('Fake', 7, 501, 999)",
    "CREATE TABLE t AS SELECT * FROM city_aqi_daily",
    "SELECT 1; DROP TABLE city_aqi_daily",
    "SELECT city FROM city_aqi_daily; SELECT 2",
    "SELECT 1 -- harmless\n; DROP TABLE city_aqi_daily",
    "ATTACH 'other.db' AS o",
    "DETACH o",
    "COPY city_aqi_daily TO 'out.csv'",
    "EXPORT DATABASE 'dump'",
    "PRAGMA database_list",
    "INSTALL httpfs",
    "LOAD httpfs",
    "SET threads = 1",
    "CALL pragma_version()",
    # file / network / environment access inside a SELECT
    "SELECT * FROM read_csv('C:/Users/User/secrets.csv')",
    "SELECT * FROM read_parquet('s3://bucket/x.parquet')",
    "SELECT * FROM read_text('C:/Windows/win.ini')",
    "SELECT * FROM 'data/raw/manifest.csv'",
    "SELECT * FROM glob('*')",
    "SELECT getenv('GEMINI_API_KEY')",
    "SELECT * FROM duckdb_settings()",
    "SELECT city FROM city_aqi_daily WHERE city IN (SELECT * FROM read_csv('x.csv'))",
    # outside the allow-list
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM users",
    "SELECT secret FROM city_aqi_daily",
]

ALLOWED_QUERIES = [
    "SELECT avg(aqi) FROM city_aqi_daily WHERE city = 'Kanpur'",
    "SELECT city, count(*) AS severe_days FROM city_aqi_daily WHERE aqi_category = 'Severe' GROUP BY city",
    "WITH w AS (SELECT * FROM city_aqi_daily WHERE date BETWEEN DATE '2024-11-01' AND DATE '2025-02-28') "
    "SELECT city, max(aqi) FROM w GROUP BY city",
    "SELECT d.city, d.date FROM city_aqi_daily d JOIN aqi_categories c USING (aqi_category) WHERE c.severity_rank >= 5",
    "SELECT city, date_trunc('month', date) AS m, avg(aqi) FROM city_aqi_daily GROUP BY ALL ORDER BY m",
    "SELECT city, aqi, rank() OVER (PARTITION BY city ORDER BY aqi DESC) AS r FROM city_aqi_daily",
    "SELECT CASE WHEN aqi > 300 THEN 'bad' ELSE 'ok' END AS label FROM city_aqi_daily",
    "SELECT city FROM city_aqi_daily WHERE strftime(date, '%m') IN ('11', '12')",
    "SELECT city FROM city_aqi_daily WHERE city = 'Delhi' UNION SELECT city FROM city_aqi_daily WHERE city = 'Kanpur'",
]


@pytest.mark.parametrize("sql", MALICIOUS)
def test_malicious_sql_rejected(sql):
    with pytest.raises(SQLValidationError):
        validate(sql)


@pytest.mark.parametrize("sql", ALLOWED_QUERIES)
def test_legitimate_sql_passes_and_gets_a_limit(sql):
    out = validate(sql)
    assert re.search(r"\bLIMIT\s+\d+", out, re.IGNORECASE)


def test_existing_limit_kept_and_large_limit_capped():
    assert re.search(r"LIMIT\s+10\b", validate("SELECT city FROM city_aqi_daily LIMIT 10"), re.I)
    assert re.search(r"LIMIT\s+1000\b", validate("SELECT city FROM city_aqi_daily LIMIT 50000"), re.I)


def test_error_message_explains_the_problem():
    with pytest.raises(SQLValidationError, match=r"(?i)users|not allowed|unknown"):
        validate("SELECT * FROM users")


def test_allow_list_matches_schema_sql():
    """Not 🧠: guards the allow-list against schema drift (a renamed column would silently break text-to-SQL)."""
    schema = (Path(__file__).parent.parent / "src/cleanair/data/schema.sql").read_text(encoding="utf-8")
    for table in ("city_aqi_daily", "aqi_categories", "stations", "readings_daily"):
        body = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", schema, re.S).group(1)
        cols = {m.group(1) for m in re.finditer(r"^\s+(\w+)\s+[A-Z]", body, re.M)} - {"PRIMARY"}
        assert cols == ALLOWED[table], table


def test_every_golden_reference_query_is_accepted():
    """Realistic legitimate SQL: the validator must not be so strict that correct answers get blocked."""
    import json

    gold = Path(__file__).parent.parent / "eval/golden/questions.jsonl"
    queries = [
        q["reference_sql"]
        for q in map(json.loads, gold.read_text(encoding="utf-8").splitlines())
        if q.get("reference_sql")
    ]
    assert queries
    for sql in queries:
        validate(sql)

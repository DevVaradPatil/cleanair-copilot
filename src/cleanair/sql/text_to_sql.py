"""Text-to-SQL (SPEC §8.1): plan -> 🧠 validate -> execute (read-only) -> repair (<= N retries) -> coverage.

The LLM writes reasoning BEFORE the SQL (SQLPlan field order), and may declare a question unanswerable from
the tables (empty sql) -- e.g. pollutant concentrations, which v1 does not have.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
from pydantic import BaseModel

from cleanair.config import PipelineConfig
from cleanair.generation.synthesize import complete_json
from cleanair.routing.router import RouterOutput
from cleanair.sql.execute import QueryResult, connect_readonly, execute
from cleanair.sql.schema_context import build_context
from cleanair.sql.validate import SQLValidationError, validate


class SQLPlan(BaseModel):
    reasoning: str  # brief; generated BEFORE the SQL
    sql: str
    assumptions: list[str] = []  # e.g. "winter = Nov–Feb", "city AQI as published by CPCB"
    expected_columns: list[str] = []


SQL_SYSTEM = """You translate questions about Indian air-quality data into ONE DuckDB SELECT statement.
Use only the tables and columns documented below and follow its conventions exactly.
- Filter cities with exact names; filter dates with DATE 'YYYY-MM-DD' literals and BETWEEN.
- Always return the count of days behind any average or count, so coverage can be reported.
- If the question needs data that is not in the tables (e.g. pollutant concentrations in µg/m³, stations,
  forecasts), return "sql": "" and say why in reasoning. Never substitute a different measure.
Return JSON with keys in this order: {"reasoning": str, "sql": str, "assumptions": [str], "expected_columns": [str]}"""


@dataclass
class DataResult:
    question: str
    plan: SQLPlan | None = None
    sql: str | None = None  # the validated SQL actually executed
    result: QueryResult | None = None
    error: str | None = None
    unanswerable: bool = False
    attempts: int = 0
    coverage: list[dict] = field(default_factory=list)
    usage: list[dict] = field(default_factory=list)

    @property
    def low_coverage(self) -> bool:
        return any(c["pct_days_reported"] < 70 for c in self.coverage)


def coverage(db_path: Path, cities: list[str], time_range: str | None) -> list[dict]:
    """Days reported vs days in range, and mean station coverage, per city (SPEC §8.1 step 6)."""
    if not cities or not time_range:
        return []
    d0, d1 = time_range.split("/")
    con = connect_readonly(db_path)
    try:
        rows = con.execute(
            """
            SELECT c.city,
                   date_diff('day', ?::DATE, ?::DATE) + 1 AS days_in_range,
                   count(a.date) AS days_reported,
                   round(avg(a.stations_reporting::DOUBLE / nullif(a.stations_total, 0)) * 100, 1)
            FROM (SELECT unnest(?::VARCHAR[]) AS city) c
            LEFT JOIN city_aqi_daily a ON a.city = c.city AND a.date BETWEEN ?::DATE AND ?::DATE
            GROUP BY c.city ORDER BY c.city
            """,
            [d0, d1, cities, d0, d1],
        ).fetchall()
    finally:
        con.close()
    return [
        {
            "city": c,
            "days_in_range": n,
            "days_reported": r,
            "pct_days_reported": round(100 * r / n, 1) if n else 0,
            "station_coverage_pct": s,
        }
        for c, n, r, s in rows
    ]


def answer_data(question: str, cfg: PipelineConfig, route: RouterOutput | None = None) -> DataResult:
    d = cfg.data
    db_path = Path(d.db_path)
    out = DataResult(question=question)
    asked = route.data_subquery if route and route.data_subquery else question
    base = f"{build_context(question, db_path)}\n\nQuestion: {asked}"
    feedback = ""
    for attempt in range(1, d.sql_max_repairs + 2):
        out.attempts = attempt
        raw, usage = complete_json(
            cfg.generation.model, SQL_SYSTEM, base + feedback, max_tokens=4096, fallback=cfg.generation.fallback_model
        )
        out.usage.append(usage)
        try:
            plan = SQLPlan.model_validate(raw)
        except Exception as e:
            feedback = f"\n\nYour previous reply was not a valid plan ({e}). Return the JSON plan."
            continue
        out.plan = plan
        if not plan.sql.strip() or plan.sql.lstrip().startswith("--"):
            out.unanswerable = True
            break
        try:
            out.sql = validate(plan.sql, max_rows=d.max_rows)
            out.result = execute(out.sql, db_path, d.sql_timeout_s, d.max_rows)
            out.error = None
            break
        except (SQLValidationError, duckdb.Error, TimeoutError) as e:  # repair loop: show the model its error
            out.error = f"{type(e).__name__}: {e}"
            feedback = f"\n\nPrevious SQL:\n{plan.sql}\nfailed with: {out.error}\nReturn a corrected plan."
    if route:
        out.coverage = coverage(db_path, route.cities, sql_period(out.sql) or route.time_range)
    return out


def sql_period(sql: str | None) -> str | None:
    """The period the executed SQL actually covers: min..max of its DATE literals. Coverage must describe what was
    computed, not what the router guessed (rules routing reads "October 2023 to September 2026" as Oct 2023)."""
    dates = sorted(re.findall(r"DATE\s+'(\d{4}-\d{2}-\d{2})'", sql or "", re.IGNORECASE))
    return f"{dates[0]}/{dates[-1]}" if dates else None

"""Text-to-SQL control flow with a fake LLM. The 🧠 validator is replaced by a passthrough HERE ONLY,
so these tests cover the repair loop / unanswerable / coverage logic, not SQL safety."""

import pytest

from cleanair.config import DataConfig, PipelineConfig
from cleanair.routing.router import RouterOutput
from cleanair.sql import text_to_sql as t2s


@pytest.fixture
def cfg(aq_db, monkeypatch):
    monkeypatch.setattr(t2s, "validate", lambda sql, max_rows=1000: sql)  # test-only stand-in for 🧠
    monkeypatch.setattr(t2s, "build_context", lambda q, db: "schema")
    return PipelineConfig(name="t", data=DataConfig(db_path=str(aq_db)))


def scripted(*plans):
    calls = iter(plans)

    def fake(model, system, user, **kw):
        return next(calls), {"model": "fake"}

    return fake


def plan(sql):
    return {"reasoning": "r", "sql": sql, "assumptions": ["winter = Nov-Feb"], "expected_columns": []}


ROUTE = RouterOutput(route="data", language="en", cities=["Kanpur"], time_range="2024-11-01/2024-11-10")


def test_good_sql_runs_first_time(cfg, monkeypatch):
    monkeypatch.setattr(
        t2s,
        "complete_json",
        scripted(plan("SELECT count(*) FROM city_aqi_daily WHERE city = 'Kanpur' AND aqi_category = 'Severe'")),
    )
    out = t2s.answer_data("How many Severe days?", cfg, ROUTE)
    assert out.result.rows == [(2,)] and out.attempts == 1 and out.error is None  # AQI 420 and 450


def test_error_is_fed_back_and_repaired(cfg, monkeypatch):
    seen = []

    def fake(model, system, user, **kw):
        seen.append(user)
        return (
            plan("SELECT nonexistent FROM city_aqi_daily")
            if len(seen) == 1
            else plan("SELECT max(aqi) FROM city_aqi_daily WHERE city = 'Kanpur'")
        ), {"model": "fake"}

    monkeypatch.setattr(t2s, "complete_json", fake)
    out = t2s.answer_data("Max AQI?", cfg, ROUTE)
    assert out.attempts == 2 and out.result.rows == [(450,)]
    assert "nonexistent" in seen[1] and "failed with" in seen[1]


def test_gives_up_after_max_repairs(cfg, monkeypatch):
    monkeypatch.setattr(t2s, "complete_json", scripted(*[plan("SELECT bad FROM nowhere")] * 3))
    out = t2s.answer_data("?", cfg, ROUTE)
    assert out.attempts == 3 and out.result is None and out.error  # 1 try + sql_max_repairs (2)


def test_unanswerable_question_is_declared_not_queried(cfg, monkeypatch):
    monkeypatch.setattr(t2s, "complete_json", scripted(plan("")))
    out = t2s.answer_data("Average PM2.5 in µg/m3?", cfg, ROUTE)
    assert out.unanswerable and out.result is None


def test_coverage_period_comes_from_the_executed_sql(cfg, monkeypatch):
    sql = (
        "SELECT count(*) FROM city_aqi_daily WHERE city = 'Kanpur' "
        "AND date BETWEEN DATE '2024-11-01' AND DATE '2024-11-05'"
    )
    monkeypatch.setattr(t2s, "complete_json", scripted(plan(sql)))
    wrong_guess = RouterOutput(route="data", language="en", cities=["Kanpur"], time_range="2023-10-01/2023-10-31")
    out = t2s.answer_data("?", cfg, wrong_guess)
    assert out.coverage[0]["days_in_range"] == 5 and out.coverage[0]["days_reported"] == 4  # Nov 5 is missing
    assert t2s.sql_period("SELECT 1") is None


def test_coverage_counts_missing_days_and_stations(aq_db):
    cov = t2s.coverage(aq_db, ["Kanpur", "Lucknow"], "2024-11-01/2024-11-10")
    kanpur, lucknow = cov[0], cov[1]
    assert (kanpur["days_reported"], kanpur["days_in_range"], kanpur["pct_days_reported"]) == (9, 10, 90.0)
    assert kanpur["station_coverage_pct"] == 75.0
    assert lucknow["days_reported"] == 0 and lucknow["pct_days_reported"] == 0

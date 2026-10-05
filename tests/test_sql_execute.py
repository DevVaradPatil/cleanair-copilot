"""Layer-2 SQL safety holds on its own, even if the validator lets something through."""

import duckdb
import pytest

from cleanair.sql.execute import execute


def test_select_works_and_reports_columns(aq_db):
    r = execute("SELECT city, aqi FROM city_aqi_daily ORDER BY aqi DESC LIMIT 1", aq_db)
    assert r.columns == ["city", "aqi"] and r.rows[0] == ("Kanpur", 450) and not r.truncated


def test_writes_fail_on_read_only_connection(aq_db):
    with pytest.raises(duckdb.Error):
        execute("DELETE FROM city_aqi_daily", aq_db)
    assert execute("SELECT count(*) FROM city_aqi_daily", aq_db).rows == [(10,)]


def test_external_file_access_is_blocked(aq_db, tmp_path):
    secret = tmp_path / "secret.csv"
    secret.write_text("key\nhunter2\n")
    with pytest.raises(duckdb.Error):
        execute(f"SELECT * FROM read_csv('{secret.as_posix()}')", aq_db)


def test_row_cap_and_truncation_flag(aq_db):
    r = execute("SELECT * FROM range(5000)", aq_db, max_rows=100)
    assert len(r.rows) == 100 and r.truncated


def test_runaway_query_times_out(aq_db):
    with pytest.raises(TimeoutError):
        execute("SELECT count(*) FROM range(100000000) a, range(100000000) b", aq_db, timeout_s=0.5)

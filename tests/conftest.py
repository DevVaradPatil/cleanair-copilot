import duckdb
import pytest

from cleanair.data.load import SCHEMA


@pytest.fixture
def aq_db(tmp_path):
    """Tiny aq.duckdb: Kanpur 2024-11-01..10 with two Severe days and one missing day; one Delhi day."""
    path = tmp_path / "aq.duckdb"
    con = duckdb.connect(str(path))
    con.execute(SCHEMA.read_text(encoding="utf-8"))
    rows = [("Kanpur", f"2024-11-{d:02d}", 150 + 30 * d, None, "PM2.5", 3, 4) for d in range(1, 11) if d != 5]
    rows = [(c, d, aqi, None, p, n, t) for c, d, aqi, _, p, n, t in rows]
    con.executemany(
        "INSERT INTO city_aqi_daily SELECT ?, ?::DATE, ?, "
        "(SELECT aqi_category FROM aqi_categories WHERE ? BETWEEN aqi_min AND aqi_max), ?, ?, ?",
        [(c, d, aqi, min(aqi, 500), p, n, t) for c, d, aqi, _, p, n, t in rows],
    )
    con.execute("INSERT INTO city_aqi_daily VALUES ('Delhi', DATE '2024-11-15', 396, 'Very Poor', 'PM2.5', 38, 39)")
    con.close()
    return path

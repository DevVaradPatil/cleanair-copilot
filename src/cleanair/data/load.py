"""Build data/aq.duckdb from scratch: schema.sql + the parsed bulletin CSV. Idempotent (always rebuilds).

Run: uv run python -m cleanair.data.load
"""

import argparse
from pathlib import Path

import duckdb

SCHEMA = Path(__file__).with_name("schema.sql")


def build(db_path: Path, bulletins_csv: Path) -> dict:
    tmp = db_path.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    try:
        con.execute(SCHEMA.read_text(encoding="utf-8"))
        con.execute(
            "CREATE TEMP TABLE raw AS SELECT * FROM read_csv(?, header = true, "
            "types = {'aqi': 'INTEGER', 'stations_reporting': 'INTEGER', 'stations_total': 'INTEGER'})",
            [str(bulletins_csv)],
        )
        # CPCB's spelling drifts (1-9 Jul 2026 bulletins are all lowercase; 'Navi mumbai' from 10 Jul 2026).
        # Exact-match SQL (city = 'Kanpur') would silently drop those days, so map every case-variant to the
        # spelling used most often.
        con.execute(
            """
            CREATE TEMP TABLE canon AS
            SELECT lower(city) AS k, arg_max(city, n) AS city
            FROM (SELECT city, count(*) AS n FROM raw GROUP BY city) GROUP BY lower(city)
            """
        )
        # A city can appear twice in one bulletin (e.g. a re-listed row): keep the row with a value.
        con.execute(
            """
            INSERT INTO city_aqi_daily
            SELECT c.city, CAST(r.date AS DATE), r.aqi, r.aqi_category, r.prominent_pollutant,
                   r.stations_reporting, r.stations_total
            FROM raw r JOIN canon c ON lower(r.city) = c.k
            QUALIFY row_number() OVER (PARTITION BY c.city, r.date ORDER BY r.aqi DESC NULLS LAST) = 1
            """
        )
        stats = dict(
            zip(
                ["rows", "cities", "first", "last", "null_aqi"],
                con.execute(
                    "SELECT count(*), count(DISTINCT city), min(date), max(date), count(*) FILTER (aqi IS NULL) "
                    "FROM city_aqi_daily"
                ).fetchone(),
                strict=True,
            )
        )
    finally:
        con.close()
    tmp.replace(db_path)  # swap in only a fully built database
    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rebuild data/aq.duckdb.")
    p.add_argument("--db", type=Path, default=Path("data/aq.duckdb"))
    p.add_argument("--bulletins", type=Path, default=Path("data/processed/aqi_bulletins.csv"))
    args = p.parse_args(argv)
    print(build(args.db, args.bulletins))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

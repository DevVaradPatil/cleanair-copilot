"""CPCB daily AQI bulletins -> one row per (date, city).

The bulletin (cpcb.nic.in/upload/Downloads/AQI_Bulletin_YYYYMMDD.pdf, ~4 PM, 24-hour average) lists for every
monitored city: AQI category, AQI value, prominent pollutant(s), and stations participating / total.
Official, no login, back to 2015 -- the v1 monitoring dataset until station-level data arrives (TODO T3.1).

Run: uv run python -m cleanair.data.bulletins --start 2023-10-01 --end 2026-10-04
"""

import argparse
import csv
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import pymupdf

from cleanair.ingest.download import clean_pdf, fetch

URL = "https://cpcb.nic.in/upload/Downloads/AQI_Bulletin_{:%Y%m%d}.pdf"
CATEGORIES = ("Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe")
# CPCB AQI bands (naqi-2014): upper bound of each category
BANDS = {"Good": 50, "Satisfactory": 100, "Moderate": 200, "Poor": 300, "Very Poor": 400, "Severe": 500}
# AQI value and station counts are optional: on some days (e.g. Delhi, Severe, 2023-11-15) those cells have no
# text layer. Dropping such rows would under-count exactly the worst days, so keep the category and store NULLs.
ROW = re.compile(
    r"^\d+\n(?P<city>[^\n]+)\n(?P<category>" + "|".join(CATEGORIES) + r")\n(?:(?P<aqi>\d+)\n)?"
    r"(?P<pollutant>[^\n\d][^\n]*)(?:\n(?P<n>\d+)\s*/\s*(?P<total>\d+))?$",
    re.MULTILINE,
)
HEADER_DATE = re.compile(r"Air Quality Index on (\w{3} \d{1,2}, \d{4})")
FIELDS = ["date", "city", "aqi", "aqi_category", "prominent_pollutant", "stations_reporting", "stations_total"]


def category_for(aqi: int) -> str:
    return next(c for c, upper in BANDS.items() if aqi <= upper) if aqi <= 500 else "Severe"


def parse_bulletin(pdf_bytes: bytes) -> tuple[date, list[dict]]:
    with pymupdf.open(stream=pdf_bytes) as doc:
        text = "\n".join(page.get_text() for page in doc)
    text = re.sub(r"[ \t]+\n", "\n", text)  # trailing spaces after header cells
    m = HEADER_DATE.search(text)
    if not m:
        raise ValueError("no 'Air Quality Index on <date>' header")
    day = datetime.strptime(m.group(1), "%b %d, %Y").date()
    rows = []
    for r in ROW.finditer(text):
        rows.append(
            {
                "date": day.isoformat(),
                "city": r["city"].strip(),
                "aqi": int(r["aqi"]) if r["aqi"] else None,
                "aqi_category": r["category"],
                "prominent_pollutant": r["pollutant"].strip(),
                "stations_reporting": int(r["n"]) if r["n"] else None,
                "stations_total": int(r["total"]) if r["total"] else None,
            }
        )
    return day, rows


def download_range(start: date, end: date, raw_dir: Path, workers: int = 6) -> list[Path]:
    """Fetch missing bulletins (skips files already on disk). Missing days (holidays, outages) are just absent."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    days = [start + timedelta(d) for d in range((end - start).days + 1)]

    def get(day: date) -> Path | None:
        path = raw_dir / f"{day:%Y%m%d}.pdf"
        if path.exists():
            return path
        try:
            path.write_bytes(clean_pdf(fetch(URL.format(day), retries=2, timeout=60)))
            return path
        except Exception as e:  # a missing bulletin is a data gap, not a failure
            print(f"  no bulletin {day}: {type(e).__name__}", flush=True)
            return None

    with ThreadPoolExecutor(workers) as ex:
        return [p for p in ex.map(get, days) if p]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Download + parse CPCB daily AQI bulletins into a CSV.")
    p.add_argument("--start", type=date.fromisoformat, default=date(2023, 10, 1))
    p.add_argument("--end", type=date.fromisoformat, default=date.today())
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw/aqi_bulletins"))
    p.add_argument("--out", type=Path, default=Path("data/processed/aqi_bulletins.csv"))
    args = p.parse_args(argv)

    files = download_range(args.start, args.end, args.raw_dir)
    rows, problems = [], 0
    for f in sorted(files):
        try:
            day, day_rows = parse_bulletin(f.read_bytes())
        except Exception as e:
            print(f"  unparseable {f.name}: {e}")
            problems += 1
            continue
        if day.strftime("%Y%m%d") != f.stem:  # CPCB occasionally re-uploads an old bulletin under a new name
            print(f"  {f.name} is dated {day}; skipped")
            problems += 1
            continue
        rows += day_rows
    mismatched = sum(r["aqi"] is not None and category_for(r["aqi"]) != r["aqi_category"] for r in rows)
    no_value = sum(r["aqi"] is None for r in rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(
        f"{len(files)} bulletins, {len(rows)} city-days, {len({r['city'] for r in rows})} cities, "
        f"{problems} skipped files, {no_value} rows without an AQI value, "
        f"{mismatched} rows whose category disagrees with the AQI band -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

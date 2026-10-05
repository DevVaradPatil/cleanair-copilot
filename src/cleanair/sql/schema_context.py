"""What the text-to-SQL model sees (SPEC §8.1 step 1): data dictionary + live schema facts + few-shot examples.

Few-shot examples are picked by word overlap with the question. They deliberately use cities that the golden
set's data questions do not (Agra, Patna, Navi Mumbai, ...), so the eval measures SQL skill, not copying.
"""

import re
from pathlib import Path

from cleanair.sql.execute import connect_readonly

DICTIONARY = Path("docs/DATA_DICTIONARY.md")

EXAMPLES = [
    (
        "Average AQI in Agra in March 2025?",
        "SELECT round(avg(aqi), 1) AS avg_aqi, count(aqi) AS days_with_value FROM city_aqi_daily "
        "WHERE city = 'Agra' AND date BETWEEN DATE '2025-03-01' AND DATE '2025-03-31'",
    ),
    (
        "How many days was Patna's AQI Severe in winter 2023-24?",
        "SELECT count(*) AS severe_days FROM city_aqi_daily WHERE city = 'Patna' AND aqi_category = 'Severe' "
        "AND date BETWEEN DATE '2023-11-01' AND DATE '2024-02-29'",
    ),
    (
        "How many days was Navi Mumbai Poor or worse in 2024?",
        "SELECT count(*) AS days FROM city_aqi_daily d JOIN aqi_categories c USING (aqi_category) "
        "WHERE d.city = 'Navi Mumbai' AND c.severity_rank >= 4 AND d.date BETWEEN DATE '2024-01-01' AND DATE '2024-12-31'",
    ),
    (
        "Which day had the highest AQI in Gurugram in 2025, and what was the main pollutant?",
        "SELECT date, aqi, prominent_pollutant FROM city_aqi_daily WHERE city = 'Gurugram' "
        "AND date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31' AND aqi IS NOT NULL ORDER BY aqi DESC LIMIT 1",
    ),
    (
        "Monthly average AQI in Varanasi during 2024",
        "SELECT strftime(date, '%Y-%m') AS month, round(avg(aqi), 1) AS avg_aqi, count(aqi) AS days "
        "FROM city_aqi_daily WHERE city = 'Varanasi' AND date BETWEEN DATE '2024-01-01' AND DATE '2024-12-31' "
        "GROUP BY month ORDER BY month",
    ),
    (
        "Compare the average winter 2024-25 AQI of Patna and Agra",
        "SELECT city, round(avg(aqi), 1) AS avg_aqi, count(aqi) AS days FROM city_aqi_daily "
        "WHERE city IN ('Patna', 'Agra') AND date BETWEEN DATE '2024-11-01' AND DATE '2025-02-28' GROUP BY city",
    ),
    (
        "What share of days in 2025 was PM10 the prominent pollutant in Jaipur?",
        "SELECT round(100.0 * count(*) FILTER (prominent_pollutant LIKE '%PM10%') / count(*), 1) AS pct_days_pm10 "
        "FROM city_aqi_daily WHERE city = 'Jaipur' AND date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'",
    ),
    (
        "Average PM2.5 concentration in Agra last month?",
        "-- not answerable: pollutant concentrations (readings_daily) are not loaded; only AQI is available",
    ),
]


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def pick_examples(question: str, k: int = 4) -> list[tuple[str, str]]:
    q = _words(question)
    return sorted(EXAMPLES, key=lambda ex: len(q & _words(ex[0])), reverse=True)[:k]


def live_facts(db_path: Path) -> str:
    con = connect_readonly(db_path)
    try:
        n, d0, d1, cities = con.execute(
            "SELECT count(*), min(date), max(date), count(DISTINCT city) FROM city_aqi_daily"
        ).fetchone()
        sample = con.execute("SELECT * FROM city_aqi_daily WHERE city = 'Kanpur' ORDER BY date DESC LIMIT 3").fetchall()
    finally:
        con.close()
    rows = "\n".join(str(r) for r in sample)
    return f"city_aqi_daily: {n} rows, {cities} cities, dates {d0} .. {d1}.\nSample rows:\n{rows}"


def build_context(question: str, db_path: Path) -> str:
    examples = "\n\n".join(f"Q: {q}\nSQL: {sql}" for q, sql in pick_examples(question))
    return (
        f"{DICTIONARY.read_text(encoding='utf-8')}\n\n## Live facts\n{live_facts(db_path)}\n\n## Examples\n{examples}"
    )

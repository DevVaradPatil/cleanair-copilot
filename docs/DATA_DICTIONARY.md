# Data dictionary — `data/aq.duckdb`

This file is also fed verbatim to the text-to-SQL model (`cleanair.sql.schema_context`), so it states
conventions as rules. Coverage numbers: `docs/DATA_QUALITY.md`.

## city_aqi_daily — the v1 dataset

One row per city per day, from the **CPCB daily AQI bulletin** (official; the AQI is the 24-hour average
reported at 4 PM that day). Source URL: `https://cpcb.nic.in/upload/Downloads/AQI_Bulletin_YYYYMMDD.pdf`.
Covers ~250 Indian cities from 2023-10-01.

| column | type | meaning |
|---|---|---|
| city | VARCHAR | City name exactly as CPCB prints it: 'Delhi', 'Kanpur', 'Lucknow', 'Mumbai', 'Navi Mumbai', ... Case-sensitive. |
| date | DATE | Bulletin date. |
| aqi | INTEGER | City AQI (0–500) **as published by CPCB** (CPCB's city aggregate; we do not recompute it). **NULL** on a few days when the bulletin cell had no text — the category is still known. |
| aqi_category | VARCHAR | 'Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor', 'Severe'. Never NULL. |
| prominent_pollutant | VARCHAR | Pollutant(s) driving the AQI that day, e.g. 'PM2.5', 'PM10, PM2.5', 'O3'. |
| stations_reporting | INTEGER | Monitoring stations that contributed that day. |
| stations_total | INTEGER | Stations installed in the city. |

## aqi_categories — lookup

| aqi_category | severity_rank | aqi_min | aqi_max |
|---|---|---|---|
| Good | 1 | 0 | 50 |
| Satisfactory | 2 | 51 | 100 |
| Moderate | 3 | 101 | 200 |
| Poor | 4 | 201 | 300 |
| Very Poor | 5 | 301 | 400 |
| Severe | 6 | 401 | 500 |

Use `severity_rank` for "X or worse" (`JOIN aqi_categories USING (aqi_category) WHERE severity_rank >= 5`).

## stations, readings_daily, city_daily — EMPTY in v1

Station-level pollutant concentrations (PM2.5, PM10, NO2, SO2, CO, O3 in µg/m³) are **not loaded yet**.
Questions about pollutant concentrations (e.g. "average PM2.5 in µg/m³") cannot be answered from this database:
say so instead of querying these tables or substituting AQI.

## Conventions (state them as assumptions in every answer)

- **Winter** = 1 November to the last day of February. "Winter 2024-25" = 2024-11-01 .. 2025-02-28.
- "**Days with AQI Severe**" counts rows where `aqi_category = 'Severe'` (not `aqi > 400`, so NULL-AQI days count).
- "**Average AQI**" = `avg(aqi)` over days with a value; also report how many days that average is over.
- **Coverage**: report days reported vs days in the period, and stations_reporting/stations_total. Missing
  bulletins are not imputed. Below 70% of days reported, the answer must warn.
- Dates in the data end at the last bulletin downloaded; "yesterday"/"today" may not be present.
- Comparisons between cities use the same date range for each city.

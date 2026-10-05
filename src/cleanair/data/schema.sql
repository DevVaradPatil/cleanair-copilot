-- DuckDB schema for data/aq.duckdb. Rebuilt from scratch by `python -m cleanair.data.load`.
-- Column meanings, units and caveats: docs/DATA_DICTIONARY.md (also fed to the text-to-SQL prompt).

-- v1 data: city-level daily AQI from CPCB daily AQI bulletins (official, 24-hour average reported at 4 PM).
CREATE TABLE city_aqi_daily (
  city                VARCHAR NOT NULL,
  date                DATE    NOT NULL,
  aqi                 INTEGER,          -- NULL when the bulletin cell had no text layer; category is still known
  aqi_category        VARCHAR NOT NULL, -- Good / Satisfactory / Moderate / Poor / Very Poor / Severe
  prominent_pollutant VARCHAR,          -- e.g. 'PM2.5', 'PM10, PM2.5'
  stations_reporting  INTEGER,          -- stations that contributed that day
  stations_total      INTEGER,          -- stations installed in the city
  PRIMARY KEY (city, date)
);

-- AQI bands (CPCB National AQI, 2014): lets SQL compare categories by rank instead of string matching.
CREATE TABLE aqi_categories (
  aqi_category VARCHAR PRIMARY KEY,
  severity_rank INTEGER NOT NULL,  -- 1 = Good ... 6 = Severe
  aqi_min INTEGER NOT NULL,
  aqi_max INTEGER NOT NULL
);
INSERT INTO aqi_categories VALUES
  ('Good', 1, 0, 50), ('Satisfactory', 2, 51, 100), ('Moderate', 3, 101, 200),
  ('Poor', 4, 201, 300), ('Very Poor', 5, 301, 400), ('Severe', 6, 401, 500);

-- SPEC §5.3 station-level tables: empty until station data arrives (TODO T3.1).
CREATE TABLE stations (
  station_id VARCHAR PRIMARY KEY,
  name       VARCHAR,
  city       VARCHAR,
  state      VARCHAR,
  latitude   DOUBLE,
  longitude  DOUBLE,
  agency     VARCHAR
);

CREATE TABLE readings_daily (
  station_id   VARCHAR REFERENCES stations(station_id),
  date         DATE,
  pm25         DOUBLE,   -- µg/m³, 24-h mean
  pm10         DOUBLE,
  no2          DOUBLE,
  so2          DOUBLE,
  co           DOUBLE,   -- unit as in source; document it
  o3           DOUBLE,
  aqi          INTEGER,
  aqi_category VARCHAR,
  coverage_pct DOUBLE,   -- % of hourly values present that day
  PRIMARY KEY (station_id, date)
);

CREATE VIEW city_daily AS
SELECT s.city, r.date,
       avg(r.pm25) AS pm25, avg(r.pm10) AS pm10, max(r.aqi) AS max_station_aqi,
       count(*) AS n_stations
FROM readings_daily r JOIN stations s USING (station_id)
GROUP BY s.city, r.date;

-- =============================================================================
-- 02_views_analytics.sql
-- Gold Layer Analytical Views untuk Tim ML & BI Dashboard
-- Proyek: Jabodetabek Compound Flood BI & Early Warning System (2022–2024)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. VIEW: vw_ml_coastal_dataset
-- Dataset siap latih untuk tim Machine Learning pada wilayah elevasi <= 15.0 m.
-- Menggabungkan tabel fakta dengan atribut lokasi dan waktu.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_ml_coastal_dataset AS
SELECT
    f.observation_id,
    f.location_id,
    f.time_id,
    l.kabupaten_kota,
    l.kecamatan,
    l.NAME_3_clean,
    l.lat,
    l.long,
    l.elevation,
    l.slope,
    l.landcover_class,
    l.is_coastal_zone,
    t.year,
    t.month,
    t.month_name,
    t.quarter,
    t.season,
    f.avg_rainfall,
    f.max_rainfall,
    f.avg_temperature,
    f.ndvi,
    f.soil_moisture,
    f.weather_rain_sum,
    f.weather_rain_max,
    f.weather_precip_sum,
    f.weather_humidity_mean,
    f.weather_temp_mean,
    f.weather_wind_max,
    f.weather_pressure_mean,
    f.sea_level_max,
    f.sea_level_mean,
    f.sea_level_min,
    f.rain_index,
    f.sea_index,
    f.compound_risk_score,
    f.banjir,
    f.trigger_label,
    f.trigger_desc,
    CASE WHEN f.trigger_label > 0 THEN 1 ELSE 0 END AS is_flood
FROM fact_compound_flood_observations AS f
INNER JOIN dim_location AS l
    ON f.location_id = l.location_id
INNER JOIN dim_time AS t
    ON f.time_id = t.time_id
WHERE l.elevation <= 15.0;

-- -----------------------------------------------------------------------------
-- 2. VIEW: vw_dashboard_risk_summary
-- Ringkasan risiko banjir & Compound Flood per kabupaten/kota, kecamatan,
-- tahun, dan musim untuk kebutuhan peta serta KPI BI Dashboard.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_dashboard_risk_summary AS
SELECT
    l.kabupaten_kota,
    l.kecamatan,
    t.year,
    t.season,
    l.lat,
    l.long,
    l.is_coastal_zone,
    COUNT(*) AS total_observations,
    SUM(f.banjir) AS total_banjir,
    SUM(CASE WHEN f.trigger_label = 3 THEN 1 ELSE 0 END) AS total_compound_flood,
    ROUND(AVG(f.compound_risk_score), 4) AS avg_compound_risk_score
FROM fact_compound_flood_observations AS f
INNER JOIN dim_location AS l
    ON f.location_id = l.location_id
INNER JOIN dim_time AS t
    ON f.time_id = t.time_id
GROUP BY
    l.kabupaten_kota,
    l.kecamatan,
    t.year,
    t.season,
    l.lat,
    l.long,
    l.is_coastal_zone
ORDER BY
    t.year,
    l.kabupaten_kota,
    l.kecamatan,
    t.season;

-- -----------------------------------------------------------------------------
-- 3. VIEW: vw_monthly_trend
-- Tren bulanan rata-rata curah hujan, puncak pasang laut, dan jumlah kecamatan
-- yang terdampak banjir sepanjang periode 2022–2024.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_monthly_trend AS
SELECT
    t.time_id,
    t.year,
    t.month,
    t.month_name,
    t.quarter,
    t.season,
    ROUND(AVG(f.avg_rainfall), 4) AS avg_rainfall,
    ROUND(AVG(f.max_rainfall), 4) AS avg_max_rainfall,
    ROUND(AVG(f.weather_rain_sum), 4) AS avg_weather_rain_sum,
    ROUND(MAX(f.sea_level_max), 4) AS peak_sea_level_max,
    ROUND(AVG(f.sea_level_mean), 4) AS avg_sea_level_mean,
    COUNT(DISTINCT CASE WHEN f.banjir = 1 THEN f.location_id END) AS jumlah_kecamatan_terdampak_banjir,
    SUM(CASE WHEN f.trigger_label = 3 THEN 1 ELSE 0 END) AS total_compound_flood,
    ROUND(AVG(f.compound_risk_score), 4) AS avg_compound_risk_score
FROM fact_compound_flood_observations AS f
INNER JOIN dim_time AS t
    ON f.time_id = t.time_id
GROUP BY
    t.time_id,
    t.year,
    t.month,
    t.month_name,
    t.quarter,
    t.season
ORDER BY
    t.year,
    t.month;

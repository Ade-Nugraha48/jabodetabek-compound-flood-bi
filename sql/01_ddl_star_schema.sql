-- =============================================================================
-- 01_ddl_star_schema.sql
-- Gold Layer Data Warehouse DDL (DuckDB Compatible + PostgreSQL Reference)
-- Proyek: Jabodetabek Compound Flood BI & Early Warning System (2022–2024)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. DIMENSION TABLE: dim_location
-- Atribut geografis unik per (kabupaten_kota, kecamatan) — 58 kecamatan.
-- is_coastal_zone = TRUE jika elevation <= 15.0 ATAU kabupaten_kota = 'jakarta utara'.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_location (
    location_id      INTEGER PRIMARY KEY,
    kabupaten_kota   VARCHAR NOT NULL,
    kecamatan        VARCHAR NOT NULL,
    NAME_3_clean     VARCHAR NOT NULL,
    lat              DOUBLE NOT NULL,
    long             DOUBLE NOT NULL,
    elevation        DOUBLE NOT NULL,
    slope            DOUBLE NOT NULL,
    landcover_class  VARCHAR NOT NULL,
    is_coastal_zone  BOOLEAN NOT NULL,
    UNIQUE (kabupaten_kota, kecamatan)
);

-- -----------------------------------------------------------------------------
-- 2. DIMENSION TABLE: dim_time
-- Atribut kalender bulanan unik per (year, month) — 36 periode (2022–2024).
-- time_id berformat YYYYMM (contoh: 202201).
-- season: 'Musim Hujan' (bulan 10–3), 'Musim Kemarau' (bulan 4–9).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_time (
    time_id     INTEGER PRIMARY KEY,
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    month_name  VARCHAR NOT NULL,
    quarter     INTEGER NOT NULL,
    season      VARCHAR NOT NULL,
    UNIQUE (year, month)
);

-- -----------------------------------------------------------------------------
-- 3. FACT TABLE: fact_compound_flood_observations
-- Granularitas: 1 baris per (kecamatan, bulan) — 2.088 baris (58 x 36).
-- Seluruh kolom metrik cocok 100% dengan data/staging/dataset_compound_flood_ready.csv.
-- Catatan DuckDB: Partisi fisik per tahun diekspor ke Parquet (fact_partitioned/year=YYYY/).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_compound_flood_observations (
    observation_id         INTEGER PRIMARY KEY,
    location_id            INTEGER NOT NULL REFERENCES dim_location(location_id),
    time_id                INTEGER NOT NULL REFERENCES dim_time(time_id),
    year                   INTEGER NOT NULL,

    -- Metrik Citra Satelit & Kondisi Permukaan Lahan
    avg_rainfall           DOUBLE NOT NULL,
    max_rainfall           DOUBLE NOT NULL,
    avg_temperature        DOUBLE NOT NULL,
    ndvi                   DOUBLE NOT NULL,
    soil_moisture          DOUBLE NOT NULL,

    -- Metrik Cuaca Per Jam (Agregasi Bulanan)
    weather_rain_sum       DOUBLE NOT NULL,
    weather_rain_max       DOUBLE NOT NULL,
    weather_precip_sum     DOUBLE NOT NULL,
    weather_humidity_mean  DOUBLE NOT NULL,
    weather_temp_mean      DOUBLE NOT NULL,
    weather_wind_max       DOUBLE NOT NULL,
    weather_pressure_mean  DOUBLE NOT NULL,

    -- Metrik Tinggi Muka Air Laut
    sea_level_max          DOUBLE NOT NULL,
    sea_level_mean         DOUBLE NOT NULL,
    sea_level_min          DOUBLE NOT NULL,

    -- Indeks Risiko, Target Banjir, & Label Pemicu
    rain_index             DOUBLE NOT NULL,
    sea_index              DOUBLE NOT NULL,
    compound_risk_score    DOUBLE NOT NULL,
    banjir                 INTEGER NOT NULL,
    trigger_label          INTEGER NOT NULL,
    trigger_desc           VARCHAR NOT NULL,
    alasan_kategori        VARCHAR NOT NULL,
    map_image              VARCHAR NOT NULL,

    UNIQUE (location_id, time_id)
);

-- -----------------------------------------------------------------------------
-- 4. ANALYTICS TABLE: analytics_ml_predictions
-- Output prediksi probabilitas & skenario banjir dari model Two-Stage.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics_ml_predictions (
    prediction_id            INTEGER PRIMARY KEY,
    observation_id           INTEGER REFERENCES fact_compound_flood_observations(observation_id),
    location_id              INTEGER NOT NULL REFERENCES dim_location(location_id),
    time_id                  INTEGER NOT NULL REFERENCES dim_time(time_id),
    actual_banjir            INTEGER,
    predicted_banjir         INTEGER NOT NULL,
    risk_probability         DOUBLE NOT NULL,
    predicted_trigger_label  INTEGER NOT NULL,
    predicted_scenario       VARCHAR NOT NULL,
    decision_threshold       DOUBLE NOT NULL,
    model_version            VARCHAR NOT NULL,
    run_date                 DATE NOT NULL
);

-- -----------------------------------------------------------------------------
-- 5. ANALYTICS TABLE: analytics_vulnerability_clusters
-- Output hasil clustering zonasi kerentanan wilayah (per kecamatan).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics_vulnerability_clusters (
    cluster_record_id         INTEGER PRIMARY KEY,
    location_id               INTEGER NOT NULL REFERENCES dim_location(location_id),
    elevation                 DOUBLE NOT NULL,
    slope                     DOUBLE NOT NULL,
    ndvi                      DOUBLE NOT NULL,
    avg_rainfall_mean         DOUBLE NOT NULL,
    max_rainfall_mean         DOUBLE NOT NULL,
    compound_risk_score_mean  DOUBLE NOT NULL,
    total_banjir              INTEGER NOT NULL,
    cluster_id                INTEGER NOT NULL,
    vulnerability_tier        VARCHAR NOT NULL,
    centroid_distance         DOUBLE NOT NULL,
    clustering_algorithm      VARCHAR NOT NULL,
    silhouette_score          DOUBLE,
    run_date                  DATE NOT NULL
);

-- -----------------------------------------------------------------------------
-- 6. ANALYTICS TABLE: analytics_anomaly_logs
-- Log deteksi anomali cuaca maupun pasang laut ekstrem per observasi.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics_anomaly_logs (
    anomaly_id        INTEGER PRIMARY KEY,
    observation_id    INTEGER REFERENCES fact_compound_flood_observations(observation_id),
    location_id       INTEGER NOT NULL REFERENCES dim_location(location_id),
    time_id           INTEGER NOT NULL REFERENCES dim_time(time_id),
    anomaly_score     DOUBLE NOT NULL,
    is_anomaly        BOOLEAN NOT NULL,
    anomaly_feature   VARCHAR NOT NULL,
    detection_method  VARCHAR NOT NULL,
    detected_at       TIMESTAMP NOT NULL
);

-- =============================================================================
-- REFERENSI PRODUKSI POSTGRESQL: PARTITIONING PER TAHUN & INDEXING STANDAR
-- Catatan: Blok di bawah ini merupakan referensi DDL untuk deployment
-- PostgreSQL (>= 14) menggunakan Declarative Range Partitioning pada kolom `year`.
-- =============================================================================
/*
-- 1. Tabel Fakta Terpartisi (Declarative Range Partitioning by year)
CREATE TABLE IF NOT EXISTS fact_compound_flood_observations (
    observation_id         INTEGER GENERATED BY DEFAULT AS IDENTITY,
    location_id            INTEGER NOT NULL REFERENCES dim_location(location_id),
    time_id                INTEGER NOT NULL REFERENCES dim_time(time_id),
    year                   INTEGER NOT NULL,
    avg_rainfall           DOUBLE PRECISION NOT NULL,
    max_rainfall           DOUBLE PRECISION NOT NULL,
    avg_temperature        DOUBLE PRECISION NOT NULL,
    ndvi                   DOUBLE PRECISION NOT NULL,
    soil_moisture          DOUBLE PRECISION NOT NULL,
    weather_rain_sum       DOUBLE PRECISION NOT NULL,
    weather_rain_max       DOUBLE PRECISION NOT NULL,
    weather_precip_sum     DOUBLE PRECISION NOT NULL,
    weather_humidity_mean  DOUBLE PRECISION NOT NULL,
    weather_temp_mean      DOUBLE PRECISION NOT NULL,
    weather_wind_max       DOUBLE PRECISION NOT NULL,
    weather_pressure_mean  DOUBLE PRECISION NOT NULL,
    sea_level_max          DOUBLE PRECISION NOT NULL,
    sea_level_mean         DOUBLE PRECISION NOT NULL,
    sea_level_min          DOUBLE PRECISION NOT NULL,
    rain_index             DOUBLE PRECISION NOT NULL,
    sea_index              DOUBLE PRECISION NOT NULL,
    compound_risk_score    DOUBLE PRECISION NOT NULL,
    banjir                 INTEGER NOT NULL CHECK (banjir IN (0, 1)),
    trigger_label          INTEGER NOT NULL CHECK (trigger_label IN (0, 1, 2, 3)),
    trigger_desc           VARCHAR(50) NOT NULL,
    alasan_kategori        TEXT NOT NULL,
    map_image              VARCHAR(255) NOT NULL,
    PRIMARY KEY (observation_id, year),
    UNIQUE (location_id, time_id, year)
) PARTITION BY RANGE (year);

-- 2. Partisi Tahunan (2022, 2023, 2024, dan Default)
CREATE TABLE IF NOT EXISTS fact_compound_flood_observations_2022
    PARTITION OF fact_compound_flood_observations
    FOR VALUES FROM (2022) TO (2023);

CREATE TABLE IF NOT EXISTS fact_compound_flood_observations_2023
    PARTITION OF fact_compound_flood_observations
    FOR VALUES FROM (2023) TO (2024);

CREATE TABLE IF NOT EXISTS fact_compound_flood_observations_2024
    PARTITION OF fact_compound_flood_observations
    FOR VALUES FROM (2024) TO (2025);

CREATE TABLE IF NOT EXISTS fact_compound_flood_observations_default
    PARTITION OF fact_compound_flood_observations
    DEFAULT;

-- 3. Indexing Standar PostgreSQL (B-Tree Indexes untuk Kueri BI & Filter Dashboard)
CREATE INDEX IF NOT EXISTS idx_dim_location_kab_kec
    ON dim_location (kabupaten_kota, kecamatan);

CREATE INDEX IF NOT EXISTS idx_dim_location_coastal
    ON dim_location (is_coastal_zone);

CREATE INDEX IF NOT EXISTS idx_dim_time_year_month
    ON dim_time (year, month);

CREATE INDEX IF NOT EXISTS idx_dim_time_season
    ON dim_time (season);

CREATE INDEX IF NOT EXISTS idx_fact_location_id
    ON fact_compound_flood_observations (location_id);

CREATE INDEX IF NOT EXISTS idx_fact_time_id
    ON fact_compound_flood_observations (time_id);

CREATE INDEX IF NOT EXISTS idx_fact_trigger_banjir
    ON fact_compound_flood_observations (year, trigger_label, banjir);

CREATE INDEX IF NOT EXISTS idx_fact_compound_risk
    ON fact_compound_flood_observations (compound_risk_score DESC);

CREATE INDEX IF NOT EXISTS idx_ml_pred_loc_time
    ON analytics_ml_predictions (location_id, time_id);

CREATE INDEX IF NOT EXISTS idx_ml_pred_banjir_prob
    ON analytics_ml_predictions (predicted_banjir, risk_probability DESC);

CREATE INDEX IF NOT EXISTS idx_vuln_cluster_loc
    ON analytics_vulnerability_clusters (location_id, cluster_id);

CREATE INDEX IF NOT EXISTS idx_anomaly_loc_time_flag
    ON analytics_anomaly_logs (location_id, time_id, is_anomaly);
*/

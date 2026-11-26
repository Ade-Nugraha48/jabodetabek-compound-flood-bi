# Jabodetabek Compound Flood BI & Early Warning System

Sistem Business Intelligence, Data Warehouse, dan Machine Learning terpusat untuk analisis serta **Early Warning Dashboard Banjir Majemuk (*Compound Flood*)** di wilayah pesisir Jabodetabek (**Jakarta Utara, Tangerang, dan Bekasi**) untuk periode **2022–2024**.

---

## Ringkasan Proyek & Arsitektur Data (Medallion Architecture)

Proyek ini mengadopsi **Medallion Architecture** agar tim *Data Engineering*, *Data Science/ML*, dan *BI Dashboard* bekerja di atas satu *Single Source of Truth*:

1. **Bronze Layer (`data/raw/`):** Dokumentasi 3 dataset mentah publik dari Kaggle (`Cuaca Per Jam Indonesia`, `Tinggi Muka Air Laut Indonesia`, dan `Kejadian Banjir Jabodetabek`).
2. **Silver Layer (`data/staging/`):** Dataset bulanan terintegrasi [`dataset_compound_flood_ready.csv`](data/staging/dataset_compound_flood_ready.csv) (**2.088 baris × 33 kolom**; 58 kecamatan × 36 bulan) lengkap dengan `rain_index`, `sea_index`, `compound_risk_score`, dan label multi-kelas `trigger_label` (`0 = Aman`, `1 = Hujan Lokal`, `2 = Banjir Rob`, `3 = Compound Flood`).
3. **Gold Layer (`data/warehouse/`):** Data Warehouse berbasis **DuckDB** (`compound_flood_dw.duckdb`) dengan pemodelan **Star Schema**, *analytical SQL views*, tabel output ML/analitik, serta ekspor **Parquet terpartisi per tahun** (`fact_partitioned/year=YYYY/`).

---

## Diagram ERD Star Schema

```mermaid
erDiagram
    dim_location {
        INTEGER location_id PK
        VARCHAR kabupaten_kota
        VARCHAR kecamatan
        VARCHAR NAME_3_clean
        DOUBLE lat
        DOUBLE long
        DOUBLE elevation
        DOUBLE slope
        VARCHAR landcover_class
        BOOLEAN is_coastal_zone
    }

    dim_time {
        INTEGER time_id PK
        INTEGER year
        INTEGER month
        VARCHAR month_name
        INTEGER quarter
        VARCHAR season
    }

    fact_compound_flood_observations {
        INTEGER observation_id PK
        INTEGER location_id FK
        INTEGER time_id FK
        INTEGER year
        DOUBLE avg_rainfall
        DOUBLE max_rainfall
        DOUBLE avg_temperature
        DOUBLE ndvi
        DOUBLE soil_moisture
        DOUBLE weather_rain_sum
        DOUBLE weather_rain_max
        DOUBLE weather_precip_sum
        DOUBLE weather_humidity_mean
        DOUBLE weather_temp_mean
        DOUBLE weather_wind_max
        DOUBLE weather_pressure_mean
        DOUBLE sea_level_max
        DOUBLE sea_level_mean
        DOUBLE sea_level_min
        DOUBLE rain_index
        DOUBLE sea_index
        DOUBLE compound_risk_score
        INTEGER banjir
        INTEGER trigger_label
        VARCHAR trigger_desc
        VARCHAR alasan_kategori
        VARCHAR map_image
    }

    analytics_ml_predictions {
        INTEGER prediction_id PK
        INTEGER observation_id FK
        INTEGER location_id FK
        INTEGER time_id FK
        INTEGER actual_banjir
        INTEGER predicted_banjir
        DOUBLE risk_probability
        INTEGER predicted_trigger_label
        VARCHAR predicted_scenario
        DOUBLE decision_threshold
        VARCHAR model_version
        DATE run_date
    }

    analytics_vulnerability_clusters {
        INTEGER cluster_record_id PK
        INTEGER location_id FK
        DOUBLE elevation
        DOUBLE slope
        DOUBLE ndvi
        DOUBLE avg_rainfall_mean
        DOUBLE max_rainfall_mean
        DOUBLE compound_risk_score_mean
        INTEGER total_banjir
        INTEGER cluster_id
        VARCHAR vulnerability_tier
        DOUBLE centroid_distance
        VARCHAR clustering_algorithm
        DOUBLE silhouette_score
        DATE run_date
    }

    analytics_anomaly_logs {
        INTEGER anomaly_id PK
        INTEGER observation_id FK
        INTEGER location_id FK
        INTEGER time_id FK
        VARCHAR anomaly_type
        DOUBLE anomaly_score
        BOOLEAN is_anomaly
        VARCHAR detection_method
        VARCHAR severity_level
        TIMESTAMP detected_at
    }

    dim_location ||--o{ fact_compound_flood_observations : "has observations"
    dim_time ||--o{ fact_compound_flood_observations : "recorded in"
    fact_compound_flood_observations ||--o{ analytics_ml_predictions : "evaluated by"
    dim_location ||--o{ analytics_ml_predictions : "location ref"
    dim_time ||--o{ analytics_ml_predictions : "time ref"
    dim_location ||--o{ analytics_vulnerability_clusters : "clustered as"
    fact_compound_flood_observations ||--o{ analytics_anomaly_logs : "flagged in"
    dim_location ||--o{ analytics_anomaly_logs : "location ref"
    dim_time ||--o{ analytics_anomaly_logs : "time ref"
```

---

## Struktur Repositori

```text
jabodetabek-compound-flood-bi/
├── data/
│   ├── raw/                  # Dokumentasi 3 dataset mentah Kaggle (Bronze)
│   ├── staging/              # dataset_compound_flood_ready.csv (Silver)
│   └── warehouse/            # compound_flood_dw.duckdb & fact_partitioned/ (Gold)
├── notebooks/                # Eksplorasi & prototipe ETL/ML awal
├── sql/
│   ├── 01_ddl_star_schema.sql
│   └── 02_views_analytics.sql
├── scripts/
│   └── load_warehouse.py     # Loader Star Schema, SQL Views, & ekspor Parquet
├── ml/
│   └── train_and_predict.py  # Pipeline Two-Stage Random Forest + Rule-Based
├── dashboard/                # Aset & implementasi BI Dashboard
├── tests/
│   └── test_warehouse.py     # Validasi integritas DW dengan pytest
├── ARCHITECTURE.md
├── CONTRIBUTING.md
└── requirements.txt
```

---

## Panduan Instalasi & Menjalankan Pipeline

### 1. Instalasi Dependensi

Disarankan menggunakan virtual environment (`.venv`), lalu instal seluruh dependensi Python:

```bash
pip install -r requirements.txt
```

### 2. Membangun Data Warehouse & Ekspor Parquet

Memuat dimensi (`dim_location`, `dim_time`), tabel fakta (`fact_compound_flood_observations`), *analytical views*, dan partisi Parquet tahunan ke `data/warehouse/`:

```bash
python scripts/load_warehouse.py
```

### 3. Menjalankan Pipeline Machine Learning (Two-Stage)

Mengambil data latih pesisir (`elevation <= 15.0`) dari view `vw_ml_coastal_dataset`, melatih model Two-Stage, dan menyimpan hasil prediksi ke tabel `analytics_ml_predictions`:

```bash
python ml/train_and_predict.py
```

### 4. Menjalankan Pengujian Data (`pytest`)

Memverifikasi integritas jumlah baris, *foreign key*, partisi Parquet, SQL views, dan tabel prediksi:

```bash
pytest -v
```

---

## Dokumentasi Lanjutan

- [ARCHITECTURE.md](ARCHITECTURE.md) — Gambaran arsitektur sistem, Medallion layer, dan struktur tim.
- [CONTRIBUTING.md](CONTRIBUTING.md) — Standar engineering, pemodelan data, validasi, serta konvensi commit Git.

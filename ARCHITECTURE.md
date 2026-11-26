# System Architecture & Project Overview

## 1. Latar Belakang Proyek
Repositori ini merupakan *workspace* terpusat untuk sistem analisis dan **Early Warning Dashboard Banjir Majemuk (Compound Flood)** di wilayah pesisir Jabodetabek (**Jakarta Utara, Tangerang, dan Bekasi**) untuk periode pengamatan **2022–2024**.

## 2. Alur Data (Medallion Architecture)
Proyek ini menerapkan pemisahan lapisan data agar setiap divisi (Data Engineering, Data Science/ML, dan BI Dashboard) bekerja di atas *Single Source of Truth*:

1. **Bronze Layer (`data/raw/`):** Dokumentasi dan referensi 3 dataset mentah publik dari Kaggle (Cuaca Per Jam, Tinggi Muka Air Laut Indonesia, dan Kejadian Banjir Jabodetabek). File mentah tidak disimpan langsung di Git untuk menjaga ukuran repositori.
2. **Silver Layer (`data/staging/`):** Dataset hasil integrasi ETL tingkat bulanan (`dataset_compound_flood_ready.csv`) berukuran 2.088 baris × 33 kolom yang telah dilengkapi indeks risiko (`rain_index`, `sea_index`, `compound_risk_score`) dan label target multi-kelas (`trigger_label`: 0 = Aman, 1 = Hujan Lokal, 2 = Banjir Rob, 3 = Compound Flood).
3. **Gold Layer (`data/warehouse/`):** Data Warehouse terpusat berbasis **DuckDB** (`compound_flood_dw.duckdb`) dengan pemodelan **Star Schema**, dilengkapi ekspor **Parquet terpartisi per tahun** (`fact_partitioned/year=YYYY/`) untuk performa kueri analitik yang optimal.

## 3. Struktur Monorepo Tim
- `data/` — Penyimpanan data lintas layer (`raw/`, `staging/`, `warehouse/`).
- `notebooks/` — Notebook eksplorasi, ETL, dan prototipe awal (`Project_Business_Intelligence_SI.ipynb`).
- `sql/` — Skrip DDL Star Schema (`01_ddl_star_schema.sql`) dan SQL Views (`02_views_analytics.sql`).
- `scripts/` — Skrip otomasi *data pipeline* (`load_warehouse.py`).
- `ml/` — Modul *Machine Learning* (Two-Stage Classification, Clustering, Anomaly Detection) yang membaca dari Data Warehouse dan menyimpan hasil prediksi kembali ke tabel analitik.
- `dashboard/` — Kode aplikasi atau dokumentasi BI Dashboard.
- `tests/` — Pengujian integritas data otomatis menggunakan `pytest`.
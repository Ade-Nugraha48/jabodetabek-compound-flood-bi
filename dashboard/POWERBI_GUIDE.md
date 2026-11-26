# Panduan Integrasi Power BI — Jabodetabek Compound Flood BI

Panduan ini membantu tim Business Intelligence menghubungkan hasil Data Warehouse DuckDB dan output Machine Learning ke **Power BI Desktop**.

---

## 1. Memuat Data (`Get Data`) dari `data/exports/powerbi/`

Sebelum membuka Power BI, pastikan seluruh pipeline sudah dijalankan untuk memperbarui file CSV:

```bash
python scripts/load_warehouse.py
python ml/train_and_predict.py
python ml/run_clustering.py
python ml/run_anomaly_detection.py
python scripts/export_for_powerbi.py
```

Di **Power BI Desktop**:
1. Pilih **Home → Get Data → Text/CSV** (atau gunakan **Get Data → Folder** jika ingin memuat seluruh folder `data/exports/powerbi/` lalu memfilter per file).
2. Arahkan ke folder `data/exports/powerbi/` dan muat ke-8 file berikut:
   - **Dimensi:** `dim_location.csv`, `dim_time.csv`
   - **Fakta:** `fact_compound_flood_observations.csv`
   - **Analitik ML:** `analytics_ml_predictions.csv`, `analytics_vulnerability_clusters.csv`, `analytics_anomaly_logs.csv`
   - **Views Teragregasi:** `vw_dashboard_risk_summary.csv`, `vw_monthly_trend.csv`
3. Pastikan di **Power Query Editor** baris pertama sudah terdeteksi sebagai header (*Use First Row as Headers*) dan tipe data numerik/desimal (`lat`, `long`, `risk_probability`, `anomaly_score`) serta tanggal (`run_date`, `detected_at`) sudah sesuai.

---

## 2. Pengaturan Relasi Star Schema (Model View)

Masuk ke **Model View** di Power BI Desktop dan atur relasi **One-to-Many (`1:*`)** dengan *Cross filter direction* = **Single** (dari tabel dimensi ke tabel fakta/analitik):

### Relasi `dim_location`
- `dim_location[location_id]` (`1`) → `fact_compound_flood_observations[location_id]` (`*`)
- `dim_location[location_id]` (`1`) → `analytics_ml_predictions[location_id]` (`*`)
- `dim_location[location_id]` (`1`) → `analytics_vulnerability_clusters[location_id]` (`*`)
- `dim_location[location_id]` (`1`) → `analytics_anomaly_logs[location_id]` (`*`)

### Relasi `dim_time`
- `dim_time[time_id]` (`1`) → `fact_compound_flood_observations[time_id]` (`*`)
- `dim_time[time_id]` (`1`) → `analytics_ml_predictions[time_id]` (`*`)
- `dim_time[time_id]` (`1`) → `analytics_anomaly_logs[time_id]` (`*`)

> **Catatan:** Tabel `vw_dashboard_risk_summary` dan `vw_monthly_trend` merupakan *pre-aggregated views* siap pakai yang dapat digunakan langsung sebagai sumber visual independen tanpa perlu dihubungkan ke relasi `1:*` agar terhindar dari *ambiguous paths*.

---

## 3. Rekomendasi 4 Visual Utama Dashboard

1. **Peta Kerentanan Wilayah (Map / Azure Map)**
   - **Latitude / Longitude:** `dim_location[lat]`, `dim_location[long]`
   - **Legend:** `analytics_vulnerability_clusters[vulnerability_tier]` (`Rendah`, `Sedang`, `Tinggi`, `Sangat Tinggi`)
   - **Size / Tooltips:** `dim_location[kabupaten_kota]`, `dim_location[kecamatan]`, `analytics_vulnerability_clusters[total_banjir]`, `analytics_vulnerability_clusters[compound_risk_score_mean]`

2. **Tren Bulanan Curah Hujan, Pasang Laut, & Dampak Banjir (Line and Clustered Column Chart)**
   - **Sumber Data:** `vw_monthly_trend`
   - **X-Axis:** `vw_monthly_trend[time_id]` (atau hierarki `year` → `month_name`)
   - **Column Y-Axis:** `vw_monthly_trend[avg_rainfall]` dan `vw_monthly_trend[jumlah_kecamatan_terdampak_banjir]`
   - **Line Y-Axis:** `vw_monthly_trend[peak_sea_level_max]`

3. **KPI Card Early Warning (Card & Donut/Bar Chart)**
   - **Sumber Data:** `analytics_ml_predictions` (terfilter oleh slicer `dim_location` & `dim_time`)
   - **Metrik KPI:**
     - Total Prediksi Peringatan Banjir: `COUNTROWS(FILTER(analytics_ml_predictions, analytics_ml_predictions[predicted_banjir] = 1))`
     - Rata-rata / Maksimum Probabilitas Risiko: `AVERAGE(analytics_ml_predictions[risk_probability])` / `MAX(...)`
     - Breakdown Skenario Pemicu: `analytics_ml_predictions[predicted_scenario]` (`0 - Aman`, `1 - Hujan Lokal`, `2 - Banjir Rob`, `3 - Compound Flood`)

4. **Tabel Log Anomali Ekstrem (Table Visual)**
   - **Sumber Data:** `analytics_anomaly_logs` + `dim_location` + `dim_time`
   - **Filter Visual:** `analytics_anomaly_logs[is_anomaly] = TRUE`
   - **Kolom:** `dim_location[kabupaten_kota]`, `dim_location[kecamatan]`, `dim_time[year]`, `dim_time[month_name]`, `analytics_anomaly_logs[anomaly_feature]`, `analytics_anomaly_logs[anomaly_score]` (urutkan *Ascending* karena skor lebih negatif menunjukkan anomali paling ekstrem), dan `analytics_anomaly_logs[detected_at]`.

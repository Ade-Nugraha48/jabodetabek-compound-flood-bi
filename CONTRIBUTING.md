# Team Guidelines & Engineering Standards

Dokumen ini mengatur standar teknis, pemodelan data, dan alur kerja Git untuk seluruh kontributor proyek.

## 1. Integritas Data Staging
- File dataset hasil ETL di `data/staging/` bersifat **read-only**. Dilarang memodifikasi nilai mentah di dalam CSV secara manual.
- Seluruh transformasi lanjutan, pemetaan *Foreign Key*, dan agregasi wajib dilakukan melalui skrip di `scripts/` atau `sql/`.

## 2. Standar Data Modeling (Star Schema)
Data Warehouse wajib mematuhi struktur tabel berikut:
- **`dim_location`:** Atribut geografis unik per (`kabupaten_kota`, `kecamatan`) dilengkapi `location_id` (PK), `lat`, `long`, `elevation`, `slope`, `landcover_class`, serta penanda boolean `is_coastal_zone` (`elevation <= 15.0` ATAU `kabupaten_kota == 'jakarta utara'`).
- **`dim_time`:** Atribut kalender bulanan unik per (`year`, `month`) dilengkapi `time_id` (PK format `YYYYMM`), `month_name` (Bahasa Indonesia), `quarter`, dan `season` (`Musim Hujan` untuk bulan 10–3, `Musim Kemarau` untuk bulan 4–9).
- **`fact_compound_flood_observations`:** Menyimpan `observation_id`, `location_id` (FK), `time_id` (FK), `year`, serta seluruh metrik cuaca, pasang laut, indeks risiko, `banjir`, `trigger_label`, `trigger_desc`, `alasan_kategori`, dan `map_image`.
- **Tabel Output Analitik (Data Science):**
  - `analytics_ml_predictions`: Menampung hasil prediksi probabilitas & skenario banjir dari model *Two-Stage*.
  - `analytics_vulnerability_clusters`: Menampung hasil *clustering* zonasi kerentanan wilayah.
  - `analytics_anomaly_logs`: Menampung log deteksi anomali cuaca/pasang laut ekstrem.

## 3. Standar Validasi & Pengujian
- Setiap perubahan pada skrip *loader* atau skema SQL wajib lolos seluruh pengujian di `tests/test_warehouse.py` menggunakan `pytest`.
- Jumlah baris pada `fact_compound_flood_observations` harus konsisten (2.088 baris) tanpa nilai `NULL` pada `location_id` maupun `time_id`.

## 4. Konvensi Commit Git
Gunakan format *Conventional Commits* agar riwayat repositori mudah dibaca:
- `chore:` — Setup repositori, konfigurasi, atau dependensi.
- `feat(dw):` — Penambahan skema, loader, atau view Data Warehouse.
- `feat(ml):` — Penambahan atau pembaruan skrip Machine Learning.
- `test:` — Penambahan atau pembaruan unit/data test.
- `docs:` — Pembaruan dokumentasi (`README.md`, diagram ERD, dll.).
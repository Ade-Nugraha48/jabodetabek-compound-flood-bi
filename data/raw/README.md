# Bronze Layer — Raw Datasets (Kaggle)

Folder ini merupakan dokumentasi dan tempat referensi **Bronze Layer** sesuai `ARCHITECTURE.md`. File dataset mentah tidak disimpan langsung di Git untuk menjaga ukuran repositori agar tetap ringan.

Seluruh data mentah diambil dari Kaggle melalui notebook eksplorasi (`notebooks/Project_Business_Intelligence_SI.ipynb`) menggunakan `kagglehub`:

1. **Indonesia Hourly Weather for Rain Prediction** (Cuaca Per Jam & Prediksi Hujan)
   - **Sumber Kaggle:** [`karanroyka/indonesia-hourly-weather-for-rain-prediction`](https://www.kaggle.com/datasets/karanroyka/indonesia-hourly-weather-for-rain-prediction)
   - **File utama:** `ml_dataset.csv`
   - **Variabel di notebook:** `df_weather`

2. **Sea Water Level in Indonesia** (Tinggi Muka Air Laut Indonesia)
   - **Sumber Kaggle:** [`jalaludinmuflih/dataset-sea-water-level-in-indonesia`](https://www.kaggle.com/datasets/jalaludinmuflih/dataset-sea-water-level-in-indonesia)
   - **File utama:** `Dataset Sea Watel level in indonesia.xlsx`
   - **Variabel di notebook:** `df_sea`

3. **Banjir Jabodetabek** (Data Kejadian Banjir Jabodetabek)
   - **Sumber Kaggle:** [`yusufginanjar7/banjir-jabodetabek`](https://www.kaggle.com/datasets/yusufginanjar7/banjir-jabodetabek)
   - **File utama:** `data_banjir_combine_final.csv`
   - **Variabel di notebook:** `df_banjir`

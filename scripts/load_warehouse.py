"""ETL loader untuk membangun Data Warehouse DuckDB dan ekspor Parquet terpartisi."""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
STAGING_CSV = BASE_DIR / "data" / "staging" / "dataset_compound_flood_ready.csv"
DDL_PATH = BASE_DIR / "sql" / "01_ddl_star_schema.sql"
WAREHOUSE_DIR = BASE_DIR / "data" / "warehouse"
DB_PATH = WAREHOUSE_DIR / "compound_flood_dw.duckdb"
PARQUET_DIR = WAREHOUSE_DIR / "fact_partitioned"

MONTH_NAMES_ID = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}

FACT_COLUMNS = [
    "observation_id",
    "location_id",
    "time_id",
    "year",
    "avg_rainfall",
    "max_rainfall",
    "avg_temperature",
    "ndvi",
    "soil_moisture",
    "weather_rain_sum",
    "weather_rain_max",
    "weather_precip_sum",
    "weather_humidity_mean",
    "weather_temp_mean",
    "weather_wind_max",
    "weather_pressure_mean",
    "sea_level_max",
    "sea_level_mean",
    "sea_level_min",
    "rain_index",
    "sea_index",
    "compound_risk_score",
    "banjir",
    "trigger_label",
    "trigger_desc",
    "alasan_kategori",
    "map_image",
]


def build_dim_location(df: pd.DataFrame) -> pd.DataFrame:
    """Membentuk tabel dimensi lokasi unik per (kabupaten_kota, kecamatan)."""
    dim_loc = (
        df.sort_values(["kabupaten_kota", "kecamatan"])
        .groupby(["kabupaten_kota", "kecamatan"], as_index=False)
        .agg(
            NAME_3_clean=("NAME_3_clean", "first"),
            lat=("lat", "first"),
            long=("long", "first"),
            elevation=("elevation", "first"),
            slope=("slope", "first"),
            landcover_class=("landcover_class", "first"),
        )
        .sort_values(["kabupaten_kota", "kecamatan"])
        .reset_index(drop=True)
    )
    dim_loc.insert(0, "location_id", range(1, len(dim_loc) + 1))
    dim_loc["is_coastal_zone"] = (dim_loc["elevation"] <= 15.0) | (
        dim_loc["kabupaten_kota"].str.lower() == "jakarta utara"
    )
    return dim_loc[
        [
            "location_id",
            "kabupaten_kota",
            "kecamatan",
            "NAME_3_clean",
            "lat",
            "long",
            "elevation",
            "slope",
            "landcover_class",
            "is_coastal_zone",
        ]
    ]


def build_dim_time(df: pd.DataFrame) -> pd.DataFrame:
    """Membentuk tabel dimensi waktu bulanan unik per (year, month)."""
    dim_time = (
        df[["year", "month"]]
        .drop_duplicates()
        .sort_values(["year", "month"])
        .reset_index(drop=True)
    )
    dim_time["time_id"] = dim_time["year"] * 100 + dim_time["month"]
    dim_time["month_name"] = dim_time["month"].map(MONTH_NAMES_ID)
    dim_time["quarter"] = (dim_time["month"] - 1) // 3 + 1
    dim_time["season"] = dim_time["month"].apply(
        lambda m: "Musim Hujan" if m in {10, 11, 12, 1, 2, 3} else "Musim Kemarau"
    )
    return dim_time[["time_id", "year", "month", "month_name", "quarter", "season"]]


def build_fact_observations(
    df: pd.DataFrame, dim_location: pd.DataFrame, dim_time: pd.DataFrame
) -> pd.DataFrame:
    """Memetakan FK location_id dan time_id untuk membentuk tabel fakta."""
    fact_df = df.merge(
        dim_location[["location_id", "kabupaten_kota", "kecamatan"]],
        on=["kabupaten_kota", "kecamatan"],
        how="left",
    ).merge(
        dim_time[["time_id", "year", "month"]],
        on=["year", "month"],
        how="left",
    )

    if fact_df["location_id"].isna().any() or fact_df["time_id"].isna().any():
        raise ValueError("Ditemukan nilai NULL pada foreign key location_id atau time_id.")

    fact_df["location_id"] = fact_df["location_id"].astype("int64")
    fact_df["time_id"] = fact_df["time_id"].astype("int64")
    fact_df = fact_df.sort_values(["time_id", "location_id"]).reset_index(drop=True)
    fact_df.insert(0, "observation_id", range(1, len(fact_df) + 1))
    return fact_df[FACT_COLUMNS]


def load_warehouse(
    staging_csv: Path = STAGING_CSV,
    ddl_path: Path = DDL_PATH,
    db_path: Path = DB_PATH,
    parquet_dir: Path = PARQUET_DIR,
) -> dict[str, int]:
    """Memuat Star Schema ke DuckDB dan mengekspor Parquet terpartisi per tahun."""
    df = pd.read_csv(staging_csv)
    df["kabupaten_kota"] = df["kabupaten_kota"].astype(str).str.strip().str.lower()
    df["kecamatan"] = df["kecamatan"].astype(str).str.strip().str.lower()
    df["NAME_3_clean"] = df["NAME_3_clean"].astype(str).str.strip().str.lower()

    dim_location = build_dim_location(df)
    dim_time = build_dim_time(df)
    fact_df = build_fact_observations(df, dim_location, dim_time)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    ddl_sql = ddl_path.read_text(encoding="utf-8")

    con = duckdb.connect(str(db_path))
    try:
        # Rebuild schema secara idempoten dengan urutan DROP terbalik (child -> parent)
        for table in [
            "analytics_anomaly_logs",
            "analytics_vulnerability_clusters",
            "analytics_ml_predictions",
            "fact_compound_flood_observations",
            "dim_time",
            "dim_location",
        ]:
            con.execute(f"DROP TABLE IF EXISTS {table};")

        con.execute(ddl_sql)

        con.register("tmp_dim_location", dim_location)
        con.execute("INSERT INTO dim_location SELECT * FROM tmp_dim_location;")

        con.register("tmp_dim_time", dim_time)
        con.execute("INSERT INTO dim_time SELECT * FROM tmp_dim_time;")

        con.register("tmp_fact_obs", fact_df)
        con.execute(
            "INSERT INTO fact_compound_flood_observations SELECT * FROM tmp_fact_obs;"
        )

        if parquet_dir.exists():
            shutil.rmtree(parquet_dir)
        parquet_dir.mkdir(parents=True, exist_ok=True)

        parquet_posix = parquet_dir.as_posix()
        con.execute(
            f"""
            COPY fact_compound_flood_observations
            TO '{parquet_posix}'
            (FORMAT PARQUET, PARTITION_BY (year), OVERWRITE_OR_IGNORE 1);
            """
        )

        tables = [
            "dim_location",
            "dim_time",
            "fact_compound_flood_observations",
            "analytics_ml_predictions",
            "analytics_vulnerability_clusters",
            "analytics_anomaly_logs",
        ]
        counts = {
            t: con.execute(f"SELECT COUNT(*) FROM {t};").fetchone()[0] for t in tables
        }
    finally:
        con.close()

    return counts


def main() -> None:
    counts = load_warehouse()
    print(f"Data Warehouse berhasil dimuat ke: {DB_PATH}")
    print("Ringkasan jumlah baris per tabel:")
    for table, count in counts.items():
        print(f"  - {table}: {count:,} baris")
    print(f"Parquet terpartisi diekspor ke: {PARQUET_DIR}")


if __name__ == "__main__":
    main()

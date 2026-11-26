"""Pipeline Isolation Forest untuk deteksi anomali cuaca dan pasang laut ekstrem."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "warehouse" / "compound_flood_dw.duckdb"

ANOMALY_FEATURES = [
    "weather_rain_sum",
    "max_rainfall",
    "sea_level_max",
    "rain_index",
    "sea_index",
    "compound_risk_score",
]


def load_fact_observations(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Mengambil data observasi bulanan dari fact_compound_flood_observations."""
    query = """
        SELECT
            f.observation_id,
            f.location_id,
            f.time_id,
            l.kabupaten_kota,
            l.kecamatan,
            f.weather_rain_sum,
            f.max_rainfall,
            f.sea_level_max,
            f.rain_index,
            f.sea_index,
            f.compound_risk_score
        FROM fact_compound_flood_observations AS f
        INNER JOIN dim_location AS l
            ON f.location_id = l.location_id
        ORDER BY f.time_id, f.location_id;
    """
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        df = con.execute(query).fetchdf()
    finally:
        con.close()
    return df


def detect_anomalies(
    df_obs: pd.DataFrame,
    contamination: float = 0.05,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Melatih Isolation Forest dan menandai fitur pemicu anomali via Z-Score absolut."""
    x_df = df_obs[ANOMALY_FEATURES].copy()

    model = IsolationForest(
        contamination=contamination,
        random_state=random_state,
    )
    preds = model.fit_predict(x_df)
    scores = model.decision_function(x_df)
    is_anomaly = preds == -1

    # Hitung Z-Score absolut untuk menentukan fitur paling ekstrem pada tiap baris anomali
    means = x_df.mean()
    stds = x_df.std(ddof=0).replace(0.0, 1.0)
    abs_z = ((x_df - means) / stds).abs()
    dominant_feature = abs_z.idxmax(axis=1)
    anomaly_feature = np.where(is_anomaly, dominant_feature, "Normal")

    detected_at = datetime.now().replace(microsecond=0)

    enriched = df_obs.copy()
    enriched["anomaly_score"] = np.round(scores, 6)
    enriched["is_anomaly"] = is_anomaly
    enriched["anomaly_feature"] = anomaly_feature
    enriched["detection_method"] = f"IsolationForest (contamination={contamination})"
    enriched["detected_at"] = detected_at
    enriched = enriched.sort_values(["time_id", "location_id"]).reset_index(drop=True)
    enriched.insert(0, "anomaly_id", range(1, len(enriched) + 1))

    logs_df = enriched[
        [
            "anomaly_id",
            "observation_id",
            "location_id",
            "time_id",
            "anomaly_score",
            "is_anomaly",
            "anomaly_feature",
            "detection_method",
            "detected_at",
        ]
    ]
    return logs_df, enriched


def save_anomaly_logs(logs_df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """Menyimpan seluruh log deteksi anomali ke analytics_anomaly_logs secara idempoten."""
    con = duckdb.connect(str(db_path))
    try:
        con.register("tmp_anomaly_logs", logs_df)
        con.execute("DELETE FROM analytics_anomaly_logs;")
        con.execute(
            "INSERT INTO analytics_anomaly_logs SELECT * FROM tmp_anomaly_logs;"
        )
        row_count = con.execute(
            "SELECT COUNT(*) FROM analytics_anomaly_logs;"
        ).fetchone()[0]
    finally:
        con.close()
    return int(row_count)


def main() -> None:
    df_obs = load_fact_observations()
    logs_df, enriched = detect_anomalies(df_obs)
    saved_count = save_anomaly_logs(logs_df)

    anomalies = enriched[enriched["is_anomaly"]].sort_values(
        "anomaly_score", ascending=True
    )
    print(f"Total observasi dianalisis: {saved_count:,} baris")
    print(f"Total anomali terdeteksi (is_anomaly=True): {len(anomalies):,} baris")

    print("\nDistribusi fitur pemicu anomali:")
    print(
        anomalies["anomaly_feature"]
        .value_counts()
        .rename_axis("anomaly_feature")
        .reset_index(name="jumlah")
        .to_string(index=False)
    )

    print("\n5 contoh baris anomali tertinggi (anomaly_score paling ekstrem):")
    cols = [
        "anomaly_id",
        "location_id",
        "kabupaten_kota",
        "kecamatan",
        "time_id",
        "anomaly_score",
        "anomaly_feature",
        "weather_rain_sum",
        "max_rainfall",
        "sea_level_max",
        "compound_risk_score",
    ]
    print(anomalies[cols].head(5).to_string(index=False))


if __name__ == "__main__":
    main()

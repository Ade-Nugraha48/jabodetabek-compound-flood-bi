"""Pipeline Two-Stage Flood Prediction yang terintegrasi dengan DuckDB Warehouse."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, classification_report
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "warehouse" / "compound_flood_dw.duckdb"
MODEL_VERSION = "rf_two_stage_v1"
DECISION_THRESHOLD = 0.35

CANDIDATE_FEATURES = [
    "avg_rainfall",
    "max_rainfall",
    "elevation",
    "slope",
    "ndvi",
    "soil_moisture",
    "landcover_class",
    "weather_rain_sum",
    "weather_rain_max",
    "weather_temp_max",
    "sea_level_max",
    "sea_level_mean",
    "month",
]


def load_coastal_dataset(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Mengambil dataset wilayah pesisir langsung dari view vw_ml_coastal_dataset."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        df = con.execute(
            "SELECT * FROM vw_ml_coastal_dataset ORDER BY time_id, location_id;"
        ).fetchdf()
    finally:
        con.close()
    return df


def prepare_features(df_coastal: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Menyiapkan matriks fitur bebas leakage dan target biner is_flood."""
    avail_cols = [col for col in CANDIDATE_FEATURES if col in df_coastal.columns]
    x_raw = df_coastal[avail_cols].copy()

    num_cols = x_raw.select_dtypes(include=[np.number]).columns
    cat_cols = x_raw.select_dtypes(exclude=[np.number]).columns

    x_raw[num_cols] = x_raw[num_cols].fillna(x_raw[num_cols].median())
    if len(cat_cols) > 0:
        x_raw[cat_cols] = x_raw[cat_cols].fillna("Unknown")
        x_encoded = pd.get_dummies(x_raw, columns=list(cat_cols), drop_first=False, dtype=int)
    else:
        x_encoded = x_raw

    y = df_coastal["is_flood"].astype(int)
    return x_encoded, y


def classify_trigger(pred_banjir: int, rain_index: float, sea_index: float) -> tuple[int, str]:
    """Stage 2: Klasifikasi pemicu banjir berbasis aturan pada rain_index & sea_index."""
    if pred_banjir == 0:
        return 0, "0 - Aman"
    if rain_index > 0.5 and sea_index > 0.5:
        return 3, "3 - Compound Flood"
    if sea_index > 0.5:
        return 2, "2 - Banjir Rob"
    return 1, "1 - Hujan Lokal"


def train_and_evaluate(
    df_coastal: pd.DataFrame,
    threshold: float = DECISION_THRESHOLD,
    model_version: str = MODEL_VERSION,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Melatih Stage 1 Random Forest, mengevaluasi metrik, dan memprediksi Stage 2."""
    x_features, y = prepare_features(df_coastal)
    x_train, x_test, y_train, y_test = train_test_split(
        x_features, y, test_size=0.20, random_state=42, stratify=y
    )

    model_stage1 = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        class_weight="balanced",
        random_state=42,
    )
    model_stage1.fit(x_train, y_train)

    y_prob = model_stage1.predict_proba(x_test)[:, 1]
    y_pred = (y_prob >= threshold).astype(int)
    pr_auc = float(average_precision_score(y_test, y_prob))

    print("=== EVALUASI STAGE 1: DETEKSI KEJADIAN BANJIR (DATA UJI) ===")
    print(classification_report(y_test, y_pred, target_names=["Aman (0)", "Banjir (1)"]))
    print(f"PR-AUC Score: {pr_auc:.4f}")

    test_meta = df_coastal.loc[
        x_test.index,
        ["observation_id", "location_id", "time_id", "rain_index", "sea_index"],
    ].copy()
    test_meta["actual_banjir"] = y_test.to_numpy()
    test_meta["predicted_banjir"] = y_pred
    test_meta["risk_probability"] = np.round(y_prob, 4)

    triggers = [
        classify_trigger(pred, r_idx, s_idx)
        for pred, r_idx, s_idx in zip(
            test_meta["predicted_banjir"],
            test_meta["rain_index"],
            test_meta["sea_index"],
        )
    ]
    test_meta["predicted_trigger_label"] = [t[0] for t in triggers]
    test_meta["predicted_scenario"] = [t[1] for t in triggers]
    test_meta["decision_threshold"] = threshold
    test_meta["model_version"] = model_version
    test_meta["run_date"] = date.today()

    test_meta = test_meta.sort_values(["time_id", "location_id"]).reset_index(drop=True)
    test_meta.insert(0, "prediction_id", range(1, len(test_meta) + 1))

    predictions_df = test_meta[
        [
            "prediction_id",
            "observation_id",
            "location_id",
            "time_id",
            "actual_banjir",
            "predicted_banjir",
            "risk_probability",
            "predicted_trigger_label",
            "predicted_scenario",
            "decision_threshold",
            "model_version",
            "run_date",
        ]
    ]
    metrics = {"pr_auc": pr_auc, "test_rows": float(len(predictions_df))}
    return predictions_df, metrics


def save_predictions(predictions_df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """Menyimpan hasil prediksi data uji ke tabel analytics_ml_predictions di DuckDB."""
    con = duckdb.connect(str(db_path))
    try:
        con.register("tmp_ml_predictions", predictions_df)
        con.execute("DELETE FROM analytics_ml_predictions;")
        con.execute("INSERT INTO analytics_ml_predictions SELECT * FROM tmp_ml_predictions;")
        row_count = con.execute("SELECT COUNT(*) FROM analytics_ml_predictions;").fetchone()[0]
    finally:
        con.close()
    return int(row_count)


def main() -> None:
    df_coastal = load_coastal_dataset()
    print(f"Dataset pesisir dimuat dari vw_ml_coastal_dataset: {len(df_coastal):,} baris")
    predictions_df, _ = train_and_evaluate(df_coastal)
    saved_count = save_predictions(predictions_df)
    print(f"Berhasil menyimpan {saved_count:,} baris ke analytics_ml_predictions.")


if __name__ == "__main__":
    main()

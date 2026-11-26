"""Pipeline K-Means Clustering untuk zonasi 4 tier kerentanan wilayah (58 kecamatan)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "warehouse" / "compound_flood_dw.duckdb"

FEATURE_COLS = [
    "elevation",
    "slope",
    "ndvi",
    "avg_rainfall_mean",
    "max_rainfall_mean",
    "compound_risk_score_mean",
    "total_banjir",
]

TIER_LABELS = {
    1: "Rendah",
    2: "Sedang",
    3: "Tinggi",
    4: "Sangat Tinggi",
}


def load_location_features(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Mengambil fitur kerentanan teragregasi per location_id dari DuckDB."""
    query = """
        SELECT
            l.location_id,
            l.kabupaten_kota,
            l.kecamatan,
            l.elevation,
            l.slope,
            AVG(f.ndvi) AS ndvi,
            AVG(f.avg_rainfall) AS avg_rainfall_mean,
            AVG(f.max_rainfall) AS max_rainfall_mean,
            AVG(f.compound_risk_score) AS compound_risk_score_mean,
            CAST(SUM(f.banjir) AS INTEGER) AS total_banjir
        FROM dim_location AS l
        INNER JOIN fact_compound_flood_observations AS f
            ON l.location_id = f.location_id
        GROUP BY
            l.location_id,
            l.kabupaten_kota,
            l.kecamatan,
            l.elevation,
            l.slope
        ORDER BY l.location_id;
    """
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        df = con.execute(query).fetchdf()
    finally:
        con.close()
    return df


def _minmax_norm(series: pd.Series) -> pd.Series:
    """Normalisasi min-max aman terhadap pembagian nol."""
    span = float(series.max() - series.min())
    if span == 0.0:
        return pd.Series(0.0, index=series.index)
    return (series - series.min()) / span


def run_kmeans_clustering(
    df_loc: pd.DataFrame,
    n_clusters: int = 4,
    random_state: int = 42,
) -> tuple[pd.DataFrame, float]:
    """Menjalankan K-Means, mengurutkan 4 tier risiko, dan menghitung jarak centroid."""
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(df_loc[FEATURE_COLS])

    kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    raw_labels = kmeans.fit_predict(x_scaled)
    sil_score = float(silhouette_score(x_scaled, raw_labels))

    df_out = df_loc.copy()
    df_out["raw_cluster"] = raw_labels

    # Jarak Euclidean tiap kecamatan terhadap pusat clusternya di ruang terstandardisasi
    assigned_centroids = kmeans.cluster_centers_[raw_labels]
    df_out["centroid_distance"] = np.round(
        np.linalg.norm(x_scaled - assigned_centroids, axis=1), 6
    )

    # Urutkan cluster: kombinasi compound_risk_score tertinggi & elevation terendah
    cluster_stats = df_out.groupby("raw_cluster").agg(
        risk_mean=("compound_risk_score_mean", "mean"),
        elev_mean=("elevation", "mean"),
    )
    cluster_stats["risk_norm"] = _minmax_norm(cluster_stats["risk_mean"])
    cluster_stats["low_elev_norm"] = 1.0 - _minmax_norm(cluster_stats["elev_mean"])
    cluster_stats["composite_risk_order"] = (
        cluster_stats["risk_norm"] + cluster_stats["low_elev_norm"]
    )
    ordered_raw_ids = (
        cluster_stats.sort_values(
            ["composite_risk_order", "risk_mean"], ascending=[True, True]
        )
        .index.tolist()
    )

    tier_id_map = {raw_id: rank for rank, raw_id in enumerate(ordered_raw_ids, start=1)}
    df_out["cluster_id"] = df_out["raw_cluster"].map(tier_id_map)
    df_out["vulnerability_tier"] = df_out["cluster_id"].map(TIER_LABELS)
    df_out["clustering_algorithm"] = f"KMeans (k={n_clusters})"
    df_out["silhouette_score"] = round(sil_score, 4)
    df_out["run_date"] = date.today()

    df_out = df_out.sort_values("location_id").reset_index(drop=True)
    df_out.insert(0, "cluster_record_id", range(1, len(df_out) + 1))

    result_df = df_out[
        [
            "cluster_record_id",
            "location_id",
            "elevation",
            "slope",
            "ndvi",
            "avg_rainfall_mean",
            "max_rainfall_mean",
            "compound_risk_score_mean",
            "total_banjir",
            "cluster_id",
            "vulnerability_tier",
            "centroid_distance",
            "clustering_algorithm",
            "silhouette_score",
            "run_date",
        ]
    ]
    return result_df, sil_score


def save_clusters(clusters_df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """Menyimpan hasil clustering ke analytics_vulnerability_clusters secara idempoten."""
    con = duckdb.connect(str(db_path))
    try:
        con.register("tmp_vulnerability_clusters", clusters_df)
        con.execute("DELETE FROM analytics_vulnerability_clusters;")
        con.execute(
            "INSERT INTO analytics_vulnerability_clusters SELECT * FROM tmp_vulnerability_clusters;"
        )
        row_count = con.execute(
            "SELECT COUNT(*) FROM analytics_vulnerability_clusters;"
        ).fetchone()[0]
    finally:
        con.close()
    return int(row_count)


def main() -> None:
    df_loc = load_location_features()
    clusters_df, sil_score = run_kmeans_clustering(df_loc)
    saved_count = save_clusters(clusters_df)

    print(f"Silhouette Score (k=4): {sil_score:.4f}")
    print(f"Berhasil menyimpan {saved_count} baris ke analytics_vulnerability_clusters.")
    print("\nDistribusi jumlah kecamatan per vulnerability_tier:")
    dist = (
        clusters_df.groupby(["cluster_id", "vulnerability_tier"], as_index=False)
        .agg(
            jumlah_kecamatan=("location_id", "count"),
            avg_elevation=("elevation", "mean"),
            avg_compound_risk=("compound_risk_score_mean", "mean"),
            total_banjir=("total_banjir", "sum"),
            avg_centroid_dist=("centroid_distance", "mean"),
        )
        .sort_values("cluster_id")
    )
    print(dist.round(4).to_string(index=False))


if __name__ == "__main__":
    main()

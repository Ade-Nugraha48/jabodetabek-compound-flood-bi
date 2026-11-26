"""Suite pengujian integritas Data Warehouse DuckDB, Parquet, dan SQL Views."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
WAREHOUSE_DIR = BASE_DIR / "data" / "warehouse"
DB_PATH = WAREHOUSE_DIR / "compound_flood_dw.duckdb"
PARQUET_DIR = WAREHOUSE_DIR / "fact_partitioned"
POWERBI_EXPORT_DIR = BASE_DIR / "data" / "exports" / "powerbi"

VALID_VULNERABILITY_TIERS = {"Rendah", "Sedang", "Tinggi", "Sangat Tinggi"}
POWERBI_CSV_FILES = [
    "dim_location.csv",
    "dim_time.csv",
    "fact_compound_flood_observations.csv",
    "analytics_ml_predictions.csv",
    "analytics_vulnerability_clusters.csv",
    "analytics_anomaly_logs.csv",
    "vw_dashboard_risk_summary.csv",
    "vw_monthly_trend.csv",
]


@pytest.fixture(scope="module")
def dw_conn() -> duckdb.DuckDBPyConnection:
    """Membuka koneksi read-only ke DuckDB warehouse untuk pengujian."""
    assert DB_PATH.exists(), f"Database tidak ditemukan: {DB_PATH}"
    con = duckdb.connect(str(DB_PATH), read_only=True)
    yield con
    con.close()


def test_database_exists_and_opens(dw_conn: duckdb.DuckDBPyConnection) -> None:
    """Memastikan file compound_flood_dw.duckdb ada dan dapat dieksekusi kuerinya."""
    assert DB_PATH.is_file()
    result = dw_conn.execute("SELECT 1;").fetchone()
    assert result == (1,)


def test_fact_row_count(dw_conn: duckdb.DuckDBPyConnection) -> None:
    """Memastikan fact_compound_flood_observations memuat tepat 2.088 baris."""
    count = dw_conn.execute(
        "SELECT COUNT(*) FROM fact_compound_flood_observations;"
    ).fetchone()[0]
    assert count == 2088


def test_fact_foreign_keys_not_null(dw_conn: duckdb.DuckDBPyConnection) -> None:
    """Memastikan tidak ada NULL pada foreign key location_id maupun time_id."""
    null_count = dw_conn.execute(
        """
        SELECT COUNT(*)
        FROM fact_compound_flood_observations
        WHERE location_id IS NULL OR time_id IS NULL;
        """
    ).fetchone()[0]
    assert null_count == 0


def test_dim_time_row_count_and_years(dw_conn: duckdb.DuckDBPyConnection) -> None:
    """Memastikan dim_time memiliki tepat 36 baris untuk periode 2022–2024."""
    count = dw_conn.execute("SELECT COUNT(*) FROM dim_time;").fetchone()[0]
    years = [
        row[0]
        for row in dw_conn.execute(
            "SELECT DISTINCT year FROM dim_time ORDER BY year;"
        ).fetchall()
    ]
    assert count == 36
    assert years == [2022, 2023, 2024]


def test_yearly_parquet_partitions_exist(dw_conn: duckdb.DuckDBPyConnection) -> None:
    """Memastikan partisi Parquet year=2022, 2023, 2024 terbentuk dan terbaca utuh."""
    for year in (2022, 2023, 2024):
        part_dir = PARQUET_DIR / f"year={year}"
        assert part_dir.is_dir(), f"Folder partisi tidak ditemukan: {part_dir}"
        parquet_files = list(part_dir.glob("*.parquet"))
        assert len(parquet_files) > 0, f"Tidak ada file Parquet di {part_dir}"

    parquet_glob = (PARQUET_DIR / "**" / "*.parquet").as_posix()
    total_rows = dw_conn.execute(
        f"SELECT COUNT(*) FROM read_parquet('{parquet_glob}', hive_partitioning=true);"
    ).fetchone()[0]
    assert total_rows == 2088


@pytest.mark.parametrize(
    "relation_name",
    [
        "vw_ml_coastal_dataset",
        "vw_dashboard_risk_summary",
        "vw_monthly_trend",
        "analytics_ml_predictions",
    ],
)
def test_views_and_ml_predictions_queryable(
    dw_conn: duckdb.DuckDBPyConnection, relation_name: str
) -> None:
    """Memastikan seluruh SQL Views dan analytics_ml_predictions dapat di-query."""
    rows = dw_conn.execute(f"SELECT * FROM {relation_name} LIMIT 5;").fetchall()
    total = dw_conn.execute(f"SELECT COUNT(*) FROM {relation_name};").fetchone()[0]
    assert len(rows) > 0
    assert total > 0


def test_vulnerability_clusters_valid(dw_conn: duckdb.DuckDBPyConnection) -> None:
    """Memastikan analytics_vulnerability_clusters memiliki 58 baris & tier valid."""
    total = dw_conn.execute(
        "SELECT COUNT(*) FROM analytics_vulnerability_clusters;"
    ).fetchone()[0]
    dim_loc_count = dw_conn.execute("SELECT COUNT(*) FROM dim_location;").fetchone()[0]
    tiers = {
        row[0]
        for row in dw_conn.execute(
            "SELECT DISTINCT vulnerability_tier FROM analytics_vulnerability_clusters;"
        ).fetchall()
    }
    assert total == 58
    assert total == dim_loc_count
    assert tiers.issubset(VALID_VULNERABILITY_TIERS)
    assert tiers == VALID_VULNERABILITY_TIERS


def test_anomaly_logs_valid(dw_conn: duckdb.DuckDBPyConnection) -> None:
    """Memastikan analytics_anomaly_logs memiliki 2.088 baris dan >= 1 anomali."""
    total = dw_conn.execute(
        "SELECT COUNT(*) FROM analytics_anomaly_logs;"
    ).fetchone()[0]
    anomaly_count = dw_conn.execute(
        "SELECT COUNT(*) FROM analytics_anomaly_logs WHERE is_anomaly = TRUE;"
    ).fetchone()[0]
    assert total == 2088
    assert anomaly_count >= 1


@pytest.mark.parametrize("csv_name", POWERBI_CSV_FILES)
def test_powerbi_exports_exist_and_nonempty(csv_name: str) -> None:
    """Memastikan seluruh 8 file CSV ekspor Power BI tersedia dan tidak kosong."""
    csv_path = POWERBI_EXPORT_DIR / csv_name
    assert csv_path.is_file(), f"File ekspor Power BI tidak ditemukan: {csv_path}"
    assert csv_path.stat().st_size > 0, f"File ekspor Power BI kosong: {csv_path}"
    with csv_path.open("r", encoding="utf-8") as fh:
        lines = [next(fh, None) for _ in range(2)]
    assert lines[0] is not None and lines[1] is not None, (
        f"File ekspor Power BI tidak memiliki baris data: {csv_path}"
    )

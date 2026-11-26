"""Suite pengujian integritas Data Warehouse DuckDB, Parquet, dan SQL Views."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
WAREHOUSE_DIR = BASE_DIR / "data" / "warehouse"
DB_PATH = WAREHOUSE_DIR / "compound_flood_dw.duckdb"
PARQUET_DIR = WAREHOUSE_DIR / "fact_partitioned"


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

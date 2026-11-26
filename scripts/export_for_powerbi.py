"""Ekspor tabel Star Schema, SQL Views, dan tabel ML ke CSV siap Power BI."""

from __future__ import annotations

from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "warehouse" / "compound_flood_dw.duckdb"
EXPORT_DIR = BASE_DIR / "data" / "exports" / "powerbi"

EXPORT_OBJECTS = [
    "dim_location",
    "dim_time",
    "fact_compound_flood_observations",
    "analytics_ml_predictions",
    "analytics_vulnerability_clusters",
    "analytics_anomaly_logs",
    "vw_dashboard_risk_summary",
    "vw_monthly_trend",
]


def export_for_powerbi(
    db_path: Path = DB_PATH,
    export_dir: Path = EXPORT_DIR,
    objects: list[str] | None = None,
) -> dict[str, int]:
    """Mengekspor seluruh tabel/view DuckDB ke CSV UTF-8 tanpa index."""
    targets = objects or EXPORT_OBJECTS
    export_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db_path), read_only=True)
    exported_counts: dict[str, int] = {}
    try:
        for name in targets:
            df = con.execute(f"SELECT * FROM {name};").fetchdf()
            out_path = export_dir / f"{name}.csv"
            df.to_csv(out_path, index=False, encoding="utf-8")
            exported_counts[name] = len(df)
    finally:
        con.close()

    return exported_counts


def main() -> None:
    counts = export_for_powerbi()
    print(f"Ekspor Power BI selesai ke: {EXPORT_DIR}")
    for name, count in counts.items():
        print(f"  - {name}.csv: {count:,} baris")


if __name__ == "__main__":
    main()

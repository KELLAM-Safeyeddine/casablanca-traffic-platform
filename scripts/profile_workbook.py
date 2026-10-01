"""Profiler le classeur source en lecture seule pour la phase 2."""

import json
import sys
from pathlib import Path

# Le lancement direct depuis scripts/ garde les imports du dépôt explicites.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.extract.workbook_profile import profile_workbook  # noqa: E402

SOURCE = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"


def main() -> None:
    """Produire des diagnostics auditables sans toucher au classeur ni aux bases."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic avec Python 3.11")
    report, _tables, measures = profile_workbook(SOURCE)
    destination = ROOT / "docs/profiling"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "workbook_profile.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8",
    )
    measures.to_parquet(destination / "measurement_diagnostics.parquet", index=False)
    daily = measures.groupby(["day_of_week", "day"]).agg(
        measurements=("hour", "size"), scaled_times=("time_scaled_candidate", "sum"),
        scaled_distances=("distance_scaled_candidate", "sum"),
        source_formula_matches=("source_tti_formula_matches", "sum"),
        provided_tti_below_one=("source_tti_missing_or_below_one", "sum"),
        provided_tti_above_five=("source_tti_above_five", "sum"),
        gap_above_0_1=("tti_absolute_gap_above_0_1", "sum"),
    )
    daily.to_csv(destination / "daily_diagnostics.csv")
    hourly = measures.groupby("hour").agg(
        max_tti_provided=("tti_provided", "max"),
        max_tti_recalculated=("tti_recalculated_candidate", "max"),
        mean_absolute_delta=("tti_delta_candidate", lambda s: s.abs().mean()),
    )
    hourly.to_csv(destination / "hourly_tti_diagnostics.csv")
    columns = ["sheet", "_excel_row", "hour", "travel_time_raw", "travel_time_min_candidate",
               "distance_raw", "distance_km_candidate", "tti_provided",
               "tti_recalculated_candidate"]
    examples = measures.loc[
        measures["time_scaled_candidate"] | measures["source_tti_missing_or_below_one"] |
        measures["source_tti_above_five"], columns,
    ].groupby("sheet", sort=False).head(8)
    examples.to_csv(destination / "anomaly_examples.csv", index=False)
    print(daily.to_string())
    print(json.dumps(report["measurements"], indent=2, ensure_ascii=False))
    print(json.dumps(report["dimensions"], indent=2, ensure_ascii=False))
    print(f"Source SHA-256 intact : {report['source_sha256']}")


if __name__ == "__main__":
    main()

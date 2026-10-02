"""Vérifier le fichier réellement téléchargé depuis l'interface, sans écrire en base."""

import json
import sys
from pathlib import Path

import pandas as pd


def main() -> None:
    """Contrôler le CSV français complet et enregistrer une preuve compacte."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    root = Path(__file__).resolve().parents[1]
    source = root / "data/raw/dashboard_validation_export.csv"
    frame = pd.read_csv(source, sep=";", decimal=",", encoding="utf-8-sig")
    assert len(frame) == 73920
    assert not frame.duplicated(["trajectory_id", "day_of_week", "hour"]).any()
    assert frame.day_of_week.nunique() == 7 and frame.hour.nunique() == 24
    assert frame.point_id.nunique() == 110 and frame.trajectory_id.nunique() == 440
    assert frame.tti.ge(1).all() and frame.speed_kmh.gt(0).all()
    result = {
        "downloaded_rows": len(frame),
        "duplicate_keys": 0,
        "points": int(frame.point_id.nunique()),
        "routes": int(frame.trajectory_id.nunique()),
        "days": 7,
        "hours": 24,
        "csv_format": "UTF-8 BOM; separator ; decimal comma",
    }
    proof = json.dumps(result, ensure_ascii=False, indent=2)
    (root / "docs/dashboard_export_validation.json").write_text(proof + "\n", encoding="utf-8")
    print(proof)


if __name__ == "__main__":
    main()

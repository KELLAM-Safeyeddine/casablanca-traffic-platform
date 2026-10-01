"""Extraire localement le classeur vers RAW avec le venv CasaTraffic."""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.extract.excel_reader import extract_workbook  # noqa: E402


def main() -> None:
    """Publier les treize Parquets sans modifier la source ni une partition existante."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic avec Python 3.11")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    source = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
    paths = extract_workbook(source, ROOT / "data/raw")
    print(f"OK {len(paths)} feuilles extraites dans RAW")


if __name__ == "__main__":
    main()

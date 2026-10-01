"""Vérifier le cadrage, l'interpréteur, les dépendances et la source immuable."""

import hashlib
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
SOURCE_SHA256 = "4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d"


def main() -> None:
    """Échouer explicitement si un prérequis de la phase 0 manque."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser exclusivement CasaTraffic avec Python 3.11")
    required_paths = (
        "README.md", "docs/business_scope.md", "docs/data_dictionary.md",
        "docs/decisions.md", "docs/project_plan.md", "dags", "src/extract",
        "src/transform", "src/validate", "src/load", "sql/ddl", "sql/marts",
        "tests", "notebooks", "data/source", "data/raw", "data/quarantine",
        ".github/workflows",
    )
    for relative in required_paths:
        if not (ROOT / relative).exists():
            raise FileNotFoundError(relative)
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("Le SHA-256 du classeur source a changé")
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        package, expected = line.split("==")
        name = package.split("[")[0]
        actual = version(name)
        if actual != expected:
            raise RuntimeError(f"{name}: {actual}, attendu {expected}")
        print(f"OK {name}=={actual}")
    try:
        version("apache-airflow")
    except PackageNotFoundError:
        pass
    else:
        raise RuntimeError("Airflow ne doit pas être installé dans le venv")
    print(f"OK Python {sys.version.split()[0]} / CasaTraffic")
    print(f"OK source SHA-256 {SOURCE_SHA256}")
    print("OK cadrage et arborescence — phase 0 validée")


if __name__ == "__main__":
    main()

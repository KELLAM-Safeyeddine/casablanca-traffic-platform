"""Exécuter le notebook dans CasaTraffic et contrôler les preuves de profilage."""

import hashlib
import json
import sys
from pathlib import Path

import nbformat
import pandas as pd
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"


def main() -> None:
    """Échouer si le notebook, les cardinalités ou la source ne sont pas conformes."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic avec Python 3.11")
    before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    specs = KernelSpecManager(kernel_dirs=[str(Path(sys.prefix) / "share/jupyter/kernels")])
    manager = KernelManager(kernel_name="casatraffic", kernel_spec_manager=specs)
    if Path(manager.kernel_spec.argv[0]).resolve() != Path(sys.executable).resolve():
        raise RuntimeError("Le kernel du notebook n'est pas celui de CasaTraffic")
    path = ROOT / "notebooks/02_source_profiling.ipynb"
    notebook = nbformat.read(path, as_version=4)
    try:
        NotebookClient(notebook, km=manager, timeout=180,
                       resources={"metadata": {"path": str(ROOT)}}).execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    nbformat.validate(notebook)
    nbformat.write(notebook, path)
    codes = [cell for cell in notebook.cells if cell.cell_type == "code"]
    if not all(cell.execution_count is not None for cell in codes):
        raise RuntimeError("Certaines cellules du notebook n'ont pas été exécutées")
    report = json.loads((ROOT / "docs/profiling/workbook_profile.json").read_text(encoding="utf-8"))
    frame = pd.read_parquet(ROOT / "docs/profiling/measurement_diagnostics.parquet")
    if len(frame) != 73920 or report["measurement_count"] != len(frame):
        raise RuntimeError("Cardinalité des diagnostics non conforme")
    keys = ["day_of_week", "origin_point_candidate", "dest_point_candidate", "hour"]
    if frame.duplicated(keys).any() or frame[keys].isna().any().any():
        raise RuntimeError("Clés candidates manquantes ou dupliquées")
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != before:
        raise RuntimeError("La source a changé")
    if before != report["source_sha256"]:
        raise RuntimeError("Le rapport ne décrit pas cette source")
    print(f"OK notebook : {len(codes)} cellules exécutées, kernel CasaTraffic Python 3.11")
    print("OK 13 feuilles profilées, 22 communes, 110 points, 440 trajets, 73 920 mesures")
    print("OK 73 920 clés candidates uniques et complètes")
    print(f"OK source SHA-256 intact : {before}")
    print("Phase 2 validée ; corrections candidates conservées séparément des données brutes.")


if __name__ == "__main__":
    main()

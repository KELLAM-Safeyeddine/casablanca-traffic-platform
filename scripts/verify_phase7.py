"""Prouver les quatre DAGs, les Datasets et l'idempotence sur le scheduler réel."""

import json
import sys
import time
import uuid
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_phase3 import api, fingerprint, run_dag  # noqa: E402
from scripts.verify_phase5 import snapshot  # noqa: E402
from scripts.verify_phase6 import mart_snapshot  # noqa: E402
from src.extract.excel_reader import source_digest  # noqa: E402
from src.extract.workbook_profile import SOURCE_SHA256  # noqa: E402


def wait_run(dag_id: str, run_id: str) -> dict:
    """Attendre une exécution et vérifier toutes les instances de tâches."""
    deadline = time.monotonic() + 480
    previous = None
    while time.monotonic() < deadline:
        run = api(f"dags/{dag_id}/dagRuns/{run_id}")
        if run["state"] != previous:
            print(f"{dag_id}/{run_id}: {run['state']}", flush=True)
            previous = run["state"]
        if run["state"] in {"success", "failed"}:
            tasks = api(f"dags/{dag_id}/dagRuns/{run_id}/taskInstances")["task_instances"]
            if run["state"] != "success" or any(t["state"] != "success" for t in tasks):
                raise RuntimeError(f"Run échoué : {dag_id}/{run_id}, tâches={tasks}")
            return {"dag_id": dag_id, "run_id": run_id, "state": run["state"],
                    "run_type": run["run_type"], "start_date": run["start_date"],
                    "end_date": run["end_date"], "task_count": len(tasks)}
        time.sleep(3)
    raise TimeoutError(f"{dag_id}/{run_id}")


def latest_ids(dag_id: str) -> set[str]:
    """Lister les runs connus avant une nouvelle publication de Dataset."""
    return {r["dag_run_id"] for r in api(
        f"dags/{dag_id}/dagRuns?limit=100&order_by=-execution_date")["dag_runs"]}


def wait_dataset_run(dag_id: str, before: set[str]) -> dict:
    """Attendre un nouveau run déclenché automatiquement, jamais le lancer à la main."""
    deadline = time.monotonic() + 480
    while time.monotonic() < deadline:
        runs = api(f"dags/{dag_id}/dagRuns?limit=100&order_by=-execution_date")["dag_runs"]
        new = [r for r in runs if r["dag_run_id"] not in before
               and r["run_type"] == "dataset_triggered"]
        if new:
            return wait_run(dag_id, new[0]["dag_run_id"])
        time.sleep(3)
    raise TimeoutError(f"Dataset sans déclenchement : {dag_id}")


def verify_dataset_links(chains: list[dict]) -> list[dict]:
    """Relier chaque run producteur au run consommateur créé par son événement."""
    events = api("datasets/events?limit=100&order_by=-timestamp")["dataset_events"]
    verified = []
    for chain in chains:
        for producer, consumer in [("ingestion", "quality"), ("quality", "marts")]:
            source_id = chain[producer]["run_id"]
            target_id = chain[consumer]["run_id"]
            matches = [e for e in events if e["source_run_id"] == source_id
                       and any(r["dag_run_id"] == target_id for r in e["created_dagruns"])]
            assert len(matches) == 1, (source_id, target_id, matches)
            verified.append(matches[0])
    return verified


def main() -> None:
    """Bootstrap manuel puis deux chaînes automatiques ; comparer contenu complet."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    expected = {"bootstrap_dimensions", "ingest_traffic", "data_quality", "build_marts"}
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        present = {d["dag_id"] for d in api("dags")["dags"]}
        if present == expected:
            break
        time.sleep(3)
    assert present == expected, present
    assert not api("importErrors")["import_errors"]
    for dag_id in expected:
        api(f"dags/{dag_id}", "PATCH", {"is_paused": False})
    config = dotenv_values(ROOT / ".env")
    database = psycopg2.connect(
        host="127.0.0.1", port=config["POSTGRES_PORT"], dbname="traffic", user="traffic",
        password=config["TRAFFIC_DB_PASSWORD"],
    )
    try:
        before_core, before_marts = snapshot(database), mart_snapshot(database)
        database.commit()
        paths = list((ROOT / "data/raw").rglob("*.parquet"))
        raw_before = fingerprint(paths)
        bootstrap_id = "phase7_bootstrap_" + uuid.uuid4().hex
        api("dags/bootstrap_dimensions/dagRuns", "POST", {"dag_run_id": bootstrap_id})
        bootstrap = wait_run("bootstrap_dimensions", bootstrap_id)
        chains = []
        for _ in range(2):
            quality_before = latest_ids("data_quality")
            marts_before = latest_ids("build_marts")
            ingestion = run_dag({"mode": "full"}, phase="phase7")
            quality = wait_dataset_run("data_quality", quality_before)
            marts = wait_dataset_run("build_marts", marts_before)
            assert snapshot(database) == before_core
            assert mart_snapshot(database) == before_marts
            database.commit()
            chains.append({"ingestion": ingestion, "quality": quality, "marts": marts})
            print("OK chaîne Dataset et empreintes CORE/marts identiques", flush=True)
        assert fingerprint(paths) == raw_before
        source = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
        assert source_digest(source) == SOURCE_SHA256
        result = {"bootstrap": bootstrap, "chains": chains, "core": before_core,
                  "marts": before_marts, "immutable_raw": True,
                  "source_sha256": SOURCE_SHA256, "import_errors": [],
                  "dataset_events": verify_dataset_links(chains)}
        (ROOT / "docs/phase7_runs.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("OK quatre DAGs réussis, deux chaînes automatiques, idempotence prouvée", flush=True)
    finally:
        database.close()


if __name__ == "__main__":
    main()

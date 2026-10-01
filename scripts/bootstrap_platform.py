"""Initialiser la semaine complète avant le rejeu, puis prouver deux chaînes Dataset."""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import verify_phase3  # noqa: E402
from scripts.verify_phase5 import snapshot  # noqa: E402
from scripts.verify_phase6 import mart_snapshot  # noqa: E402
from scripts.verify_phase7 import (  # noqa: E402
    latest_ids,
    verify_dataset_links,
    wait_dataset_run,
)


def wait_api() -> None:
    """Attendre webserver et sérialisation des quatre DAGs, sans afficher les secrets."""
    deadline = time.monotonic() + 420
    while time.monotonic() < deadline:
        try:
            ids = {d["dag_id"] for d in verify_phase3.api("dags")["dags"]}
            if ids == {"bootstrap_dimensions", "ingest_traffic", "data_quality", "build_marts"}:
                assert not verify_phase3.api("importErrors")["import_errors"]
                return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(3)
    raise TimeoutError("Airflow indisponible ou quatre DAGs non enregistrés après 420 s")


def main() -> None:
    """Sur un volume neuf, charger avant d'activer les Datasets et l'horaire."""
    import subprocess

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    arguments = parser.parse_args()
    workspace = arguments.workspace.resolve()
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    verify_phase3.ROOT = workspace
    settings = dotenv_values(workspace / ".env")
    wait_api()
    database = psycopg2.connect(host="127.0.0.1", port=settings["POSTGRES_PORT"],
                               dbname="traffic", user="traffic",
                               password=settings["TRAFFIC_DB_PASSWORD"])
    try:
        with database.cursor() as query:
            query.execute("SELECT to_regclass('public.fact_travel_time')")
            present = query.fetchone()[0] is not None
            rows = 0
            if present:
                query.execute("SELECT count(*) FROM fact_travel_time")
                rows = query.fetchone()[0]
        database.commit()
        if rows != 73920:
            for dag_id in ("ingest_traffic", "data_quality", "build_marts"):
                verify_phase3.api(f"dags/{dag_id}", "PATCH", {"is_paused": True})
            logical_date = datetime.now(UTC).isoformat()
            # Les commandes test exécutent réellement les tâches sur le volume neuf.
            # DAGs encore pausés : aucun audit incomplet ne précède le premier full.
            for dag_id in ("bootstrap_dimensions", "ingest_traffic"):
                command = ["docker", "compose", "exec", "-T", "airflow-scheduler",
                           "airflow", "dags", "test", dag_id, logical_date]
                if dag_id == "ingest_traffic":
                    command += ["--conf", json.dumps({"mode": "full"})]
                subprocess.run(command, cwd=workspace, check=True, stdout=subprocess.DEVNULL)
                print(f"OK amorçage réel {dag_id}", flush=True)
        before_core = snapshot(database)
        assert before_core["fact_travel_time"]["rows"] == 73920
        database.commit()
        for dag_id in ("bootstrap_dimensions", "data_quality", "build_marts", "ingest_traffic"):
            verify_phase3.api(f"dags/{dag_id}", "PATCH", {"is_paused": False})
        chains = []
        before_marts = None
        for _ in range(2):
            quality_before, marts_before = latest_ids("data_quality"), latest_ids("build_marts")
            ingestion = verify_phase3.run_dag({"mode": "full"}, phase="bootstrap")
            quality = wait_dataset_run("data_quality", quality_before)
            marts = wait_dataset_run("build_marts", marts_before)
            assert snapshot(database) == before_core
            current_marts = mart_snapshot(database)
            database.commit()
            if before_marts is not None:
                assert current_marts == before_marts
            before_marts = current_marts
            chains.append({"ingestion": ingestion, "quality": quality, "marts": marts})
        report = {"core": before_core, "marts": before_marts, "chains": chains,
                  "dataset_events": verify_dataset_links(chains), "idempotent": True}
        destination = workspace / "data/quarantine/bootstrap_verification.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("OK semaine complète, quatre DAGs et deux chaînes idempotentes", flush=True)
    finally:
        database.close()


if __name__ == "__main__":
    main()

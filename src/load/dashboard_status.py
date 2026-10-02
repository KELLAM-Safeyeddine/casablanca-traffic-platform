"""Collecteur Docker séparé : métadonnées opérationnelles vers un JSON public local."""

import base64
import json
import logging
import os
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2

from src.validate.pipeline import safe_run_name

LOGGER = logging.getLogger(__name__)
DAGS = ("bootstrap_dimensions", "ingest_traffic", "data_quality", "build_marts")


def latest_run(dag_id: str) -> dict[str, Any]:
    """Lire seulement le dernier run via l'API Airflow du réseau interne."""
    credentials = f"{os.environ['STATUS_AIRFLOW_USER']}:{os.environ['STATUS_AIRFLOW_PASSWORD']}"
    path = f"/dags/{dag_id}/dagRuns?limit=1&order_by=-execution_date"
    request = urllib.request.Request(
        os.environ["STATUS_AIRFLOW_URL"] + path,
        headers={"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        runs = json.load(response)["dag_runs"]
    if not runs:
        return {"dag_id": dag_id, "state": "unavailable", "run_id": None, "end_date": None}
    run = runs[0]
    return {
        "dag_id": dag_id,
        "state": run["state"],
        "run_id": run["dag_run_id"],
        "start_date": run["start_date"],
        "end_date": run["end_date"],
    }


def collect() -> dict[str, Any]:
    """Séparer l'accès opérationnel du compte dashboard qui ne lit que CORE/marts."""
    dags = [latest_run(dag_id) for dag_id in DAGS]
    database = psycopg2.connect(
        host=os.environ["STATUS_DB_HOST"],
        dbname="traffic",
        user="traffic",
        password=os.environ["STATUS_DB_PASSWORD"],
        connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=5000",
    )
    try:
        with database, database.cursor() as query:
            query.execute("SELECT severity, count(*) FROM public.quarantine GROUP BY severity")
            quarantine = dict(query.fetchall())
            query.execute(
                "SELECT count(*), count(*) FILTER (WHERE tti_gap_flag) FROM public.fact_travel_time"
            )
            facts, gaps = query.fetchone()
    finally:
        database.close()
    quality = next(run for run in dags if run["dag_id"] == "data_quality")
    ingestion = next(run for run in dags if run["dag_id"] == "ingest_traffic")
    path = Path("/opt/airflow/reports") / safe_run_name(quality["run_id"] or "absent")
    try:
        report = json.loads((path / "warehouse_quality.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = {}
    checked = (
        quality["state"] == "success"
        and report.get("status") == "passed"
        and report.get("run_id") == quality["run_id"]
        and report.get("counts", {}).get("fact_travel_time") == facts
        and report.get("tti_gap_count") == gaps
        and ingestion["state"] == "success"
        and quality["end_date"]
        and ingestion["end_date"]
        and quality["end_date"] >= ingestion["end_date"]
    )
    return {
        "available": True,
        "collected_at": datetime.now(UTC).isoformat(),
        "dags": dags,
        "quarantine": {"total": sum(quarantine.values()), **quarantine},
        "quality": {
            "status": "passed" if checked else "needs_verification",
            "run_id": quality["run_id"],
            "checked_at": quality["end_date"],
            "facts_checked": report.get("counts", {}).get("fact_travel_time"),
            "latest_ingestion_end": ingestion["end_date"],
        },
    }


def publish(result: dict[str, Any], root: Path) -> None:
    """Remplacer atomiquement un JSON sans secret ; conserver un état d'échec explicite."""
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / "dashboard_status.tmp"
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(root / "dashboard_status.json")


def main() -> None:
    """Collecter périodiquement ; aucun appel ni credential de ce service dans le dashboard."""
    logging.basicConfig(level=logging.INFO)
    interval = max(10, int(os.environ.get("DASHBOARD_STATUS_INTERVAL", "60")))
    while True:
        try:
            result = collect()
            LOGGER.info("Metadata collected: quality=%s", result["quality"]["status"])
        except Exception:
            # Ne pas exposer corps HTTP, requêtes ou credentials dans les messages utilisateur.
            LOGGER.warning("Operational collection unavailable; retry scheduled")
            result = {"available": False, "collected_at": datetime.now(UTC).isoformat(), "dags": []}
        publish(result, Path("/opt/airflow/monitoring"))
        time.sleep(interval)


if __name__ == "__main__":
    main()

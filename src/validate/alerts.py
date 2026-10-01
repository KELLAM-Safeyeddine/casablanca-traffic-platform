"""Alertes locales durables ; aucune transmission externe ni secret."""

import json
import logging
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)


def failure_alert(context: dict[str, Any]) -> None:
    """Journaliser l'identité de la tâche échouée, sans sérialiser son exception."""
    from airflow.models import Variable

    root = Path(Variable.get(
        "traffic_alert_root", default_var="/opt/airflow/data/quarantine/alerts"
    ))
    instance = context["task_instance"]
    write_alert(root, instance.dag_id, context["run_id"], instance.task_id, instance.map_index)


def write_alert(root: Path, dag_id: str, run_id: str, task_id: str, map_index: int) -> Path:
    """Écrire une alerte idempotente par tâche/run, consultable sur l'hôte."""
    from src.validate.pipeline import safe_run_name

    root.mkdir(parents=True, exist_ok=True)
    name = safe_run_name(f"{dag_id}_{run_id}_{task_id}_{map_index}")
    target = root / f"{name}.json"
    payload = {"dag_id": dag_id, "run_id": run_id, "task_id": task_id,
               "map_index": map_index, "state": "failed"}
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    LOG.error("Échec Airflow : %s ; alerte=%s", payload, target)
    return target

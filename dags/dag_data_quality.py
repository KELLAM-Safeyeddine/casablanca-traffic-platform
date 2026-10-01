"""Après ingestion : contrôle pandera RAW/CORE et rapport bloquant."""

from datetime import timedelta

import pendulum
from airflow import Dataset
from airflow.decorators import dag, task
from airflow.operators.python import get_current_context

from src.validate.alerts import failure_alert


@dag(
    dag_id="data_quality", schedule=[Dataset("casatraffic://warehouse/core")],
    start_date=pendulum.datetime(2026, 1, 5, tz="Africa/Casablanca"),
    catchup=False, max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(seconds=15),
                  "retry_exponential_backoff": True, "on_failure_callback": failure_alert},
    tags=["casablanca", "quality"], doc_md=__doc__,
)
def data_quality() -> None:
    """Publier uniquement les données ayant passé tous les contrôles."""
    @task(outlets=[Dataset("casatraffic://warehouse/quality_passed")])
    def audit() -> dict:
        """Contrôler la semaine entière avec la Connection casatraffic."""
        from pathlib import Path

        from src.load.airflow_runtime import settings, traffic_database
        from src.validate.warehouse_quality import warehouse_quality

        config = settings()
        with traffic_database() as database:
            return warehouse_quality(database, config["source"], config["raw_root"],
                                     get_current_context()["run_id"], config["threshold"],
                                     Path("/opt/airflow/data/quarantine/reports"))

    audit()


data_quality()

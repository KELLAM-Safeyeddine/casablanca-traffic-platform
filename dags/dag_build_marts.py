"""Reconstruction transactionnelle après ingestion et validation réussies."""

from datetime import timedelta

import pendulum
from airflow import Dataset
from airflow.decorators import dag, task

from src.validate.alerts import failure_alert


@dag(
    dag_id="build_marts", schedule=[Dataset("casatraffic://warehouse/quality_passed")],
    start_date=pendulum.datetime(2026, 1, 5, tz="Africa/Casablanca"),
    catchup=False, max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(seconds=15),
                  "retry_exponential_backoff": True, "on_failure_callback": failure_alert},
    tags=["casablanca", "marts"], doc_md=__doc__,
)
def build_marts() -> None:
    """Exécuter les quatre marts SQL avec la même connexion que l'ingestion."""
    @task
    def refresh() -> dict[str, int]:
        """Conserver les anciens marts si une instruction SQL échoue."""
        from src.load.airflow_runtime import traffic_database
        from src.load.marts import build_marts as refresh_tables

        with traffic_database() as database:
            return refresh_tables(database)

    refresh()


build_marts()

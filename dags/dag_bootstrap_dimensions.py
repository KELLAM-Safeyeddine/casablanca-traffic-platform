"""Initialisation manuelle des dimensions et de la référence TTI figée."""

from datetime import timedelta

import pendulum
from airflow.decorators import dag, task
from airflow.operators.python import get_current_context

from src.validate.alerts import failure_alert


@dag(
    dag_id="bootstrap_dimensions", schedule=None,
    start_date=pendulum.datetime(2026, 1, 5, tz="Africa/Casablanca"),
    catchup=False, max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(seconds=15),
                  "retry_exponential_backoff": True, "on_failure_callback": failure_alert},
    tags=["casablanca", "dimensions"], doc_md=__doc__,
)
def bootstrap_dimensions() -> None:
    """Créer les dimensions ; les faits ne sont pas modifiés."""
    @task
    def initialize() -> dict[str, int]:
        """Lire les paramètres runtime et charger les références idempotentes."""
        from src.load.airflow_runtime import settings, traffic_database
        from src.load.warehouse import bootstrap_warehouse

        config = settings()
        with traffic_database() as database:
            return bootstrap_warehouse(config["source"], config["raw_root"], database,
                                       get_current_context()["run_id"], config["threshold"])

    initialize()


bootstrap_dimensions()

"""Ingestion RAW : sept jours mappés en mode complet, une tranche par tick en mode rejeu.

La validation et quarantine précèdent le chargement des faits, ajouté en phase 5.
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pendulum
from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.operators.python import get_current_context


@dag(
    dag_id="ingest_traffic",
    schedule="@hourly",
    start_date=pendulum.datetime(2026, 1, 5, tz="Africa/Casablanca"),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=4,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(seconds=15),
        "retry_exponential_backoff": True,
    },
    tags=["casablanca", "raw", "replay"],
    doc_md=__doc__,
)
def ingest_traffic() -> None:
    """Publier des partitions immuables puis réconcilier les cardinalités RAW."""

    @task
    def prepare_source() -> dict[str, Any]:
        """Lire la configuration à l'exécution et extraire les cinq tables de référence."""
        from src.extract.excel_reader import extract_sheet, inventory_source

        source = Variable.get(
            "traffic_source_file",
            default_var=(
                "/opt/airflow/data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
            ),
        )
        raw_root = Variable.get("traffic_raw_root", default_var="/opt/airflow/data/raw")
        inventory = inventory_source(Path(source))
        static = [
            str(extract_sheet(Path(source), Path(raw_root), number)) for number in [None, *range(5)]
        ]
        context = get_current_context()
        conf = context["dag_run"].conf or {}
        mode = conf.get("mode", "replay")
        if mode not in {"full", "replay"}:
            raise ValueError("mode doit être full ou replay")
        if mode == "full":
            jobs = [{"table_number": number} for number in range(5, 12)]
        else:
            # L'ancre UTC est une horloge de simulation, pas une date d'observation.
            anchor = pendulum.parse(
                Variable.get("traffic_replay_anchor", default_var=("2026-01-05T00:00:00Z"))
            )
            tick = conf.get(
                "tick",
                int((context["data_interval_start"].timestamp() - anchor.timestamp()) // 3600),
            )
            jobs = [{"tick": tick}]
        return {
            "source": source,
            "raw_root": raw_root,
            "static_paths": static,
            "jobs": jobs,
            "mode": mode,
            "source_sha256": inventory["source_sha256"],
        }

    @task
    def plan_jobs(settings: dict[str, Any]) -> list[dict[str, Any]]:
        """Produire la liste utilisée par le dynamic task mapping."""
        return settings["jobs"]

    @task
    def extract_partition(settings: dict[str, Any], job: dict[str, Any]) -> str:
        """Extraire un jour complet ou une tranche horaire, sans charger l'entrepôt."""
        from src.extract.excel_reader import extract_sheet
        from src.extract.flow_simulator import replay_hour

        source, raw_root = Path(settings["source"]), Path(settings["raw_root"])
        if settings["mode"] == "full":
            return str(extract_sheet(source, raw_root, job["table_number"]))
        return str(replay_hour(source, raw_root, job["tick"]))

    @task
    def validate_static(settings: dict[str, Any]) -> dict[str, Any]:
        """Valider les références et persister leurs rejets avant tout trafic."""
        import psycopg2
        from airflow.hooks.base import BaseHook

        from src.extract.excel_reader import verify_raw
        from src.load.quarantine import initialize_quarantine
        from src.validate.pipeline import safe_run_name, validate_partition

        connection = BaseHook.get_connection("casatraffic")
        database = psycopg2.connect(
            host=connection.host,
            port=connection.port,
            dbname=connection.schema,
            user=connection.login,
            password=connection.password,
        )
        try:
            initialize_quarantine(database)
            points = verify_raw(Path(settings["static_paths"][1]))
            threshold = float(Variable.get("traffic_max_error_rate", default_var="0.01"))
            run_id = get_current_context()["run_id"]
            reports = Path("/opt/airflow/data/quarantine/reports") / safe_run_name(run_id)
            summaries = [
                validate_partition(Path(path), points, database, run_id, threshold, reports)
                for path in settings["static_paths"]
            ]
            return {
                "points_path": settings["static_paths"][1],
                "summaries": summaries,
                "threshold": threshold,
                "run_id": run_id,
                "report_root": str(reports),
            }
        finally:
            database.close()

    @task
    def validate_traffic(path: str, static: dict[str, Any]) -> dict[str, Any]:
        """Valider chaque jour/tranche mappé, journaliser puis contrôler le seuil."""
        import psycopg2
        from airflow.hooks.base import BaseHook

        from src.extract.excel_reader import verify_raw
        from src.validate.pipeline import validate_partition

        connection = BaseHook.get_connection("casatraffic")
        database = psycopg2.connect(
            host=connection.host,
            port=connection.port,
            dbname=connection.schema,
            user=connection.login,
            password=connection.password,
        )
        try:
            return validate_partition(
                Path(path),
                verify_raw(Path(static["points_path"])),
                database,
                static["run_id"],
                static["threshold"],
                Path(static["report_root"]),
            )
        finally:
            database.close()

    @task
    def reconcile_raw(settings: dict[str, Any], paths: list[str]) -> dict[str, Any]:
        """Contrôler les fichiers mappés et confirmer le nombre de mesures représentées."""
        from src.extract.excel_reader import verify_raw

        materialized = list(paths)
        for path in [*settings["static_paths"], *materialized]:
            frame = verify_raw(Path(path))
            if frame["_source_sha256"].iloc[0] != settings["source_sha256"]:
                raise ValueError("Partitions de sources différentes")
        counts = [len(verify_raw(Path(path))) for path in materialized]
        expected = 7 if settings["mode"] == "full" else 1
        if len(counts) != expected or any(count != 440 for count in counts):
            raise ValueError(f"Cardinalités RAW inattendues : {counts}")
        represented = sum(counts) * (24 if settings["mode"] == "full" else 1)
        return {
            "mode": settings["mode"],
            "partitions": len(counts),
            "represented_measurements": represented,
            "paths": materialized,
        }

    settings = prepare_source()
    paths = extract_partition.partial(settings=settings).expand(job=plan_jobs(settings))
    static = validate_static(settings)
    validated = validate_traffic.partial(static=static).expand(path=paths)
    reconciliation = reconcile_raw(settings, paths)
    validated >> reconciliation


ingest_traffic()

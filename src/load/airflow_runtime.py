"""Configuration tardive et connexion partagée par les tâches Airflow."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from psycopg2.extensions import connection


def settings() -> dict[str, Any]:
    """Lire les Variables uniquement pendant une tâche, jamais au parsing."""
    from airflow.models import Variable

    return {
        "source": Path(Variable.get(
            "traffic_source_file",
            default_var="/opt/airflow/data/source/"
            "Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx",
        )),
        "raw_root": Path(Variable.get("traffic_raw_root", default_var="/opt/airflow/data/raw")),
        "threshold": float(Variable.get("traffic_max_error_rate", default_var="0.01")),
    }


@contextmanager
def traffic_database() -> Iterator[connection]:
    """Ouvrir et fermer une connexion issue de la Connection casatraffic."""
    import psycopg2
    from airflow.hooks.base import BaseHook

    configured = BaseHook.get_connection("casatraffic")
    database = psycopg2.connect(
        host=configured.host, port=configured.port, dbname=configured.schema,
        user=configured.login, password=configured.password,
    )
    try:
        yield database
    finally:
        database.close()

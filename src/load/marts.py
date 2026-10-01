"""Reconstruire les quatre marts atomiquement à partir d'un CORE complet."""

import logging
from pathlib import Path

from psycopg2 import sql
from psycopg2.extensions import connection

ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger(__name__)
MART_TABLES = (
    "mart_commune_hourly_congestion",
    "mart_peak_hours",
    "mart_weekday_vs_weekend",
    "mart_commune_features",
)
SQL_FILES = (
    "00_tables.sql",
    "01_commune_hourly_congestion.sql",
    "02_peak_hours.sql",
    "03_weekday_vs_weekend.sql",
    "04_commune_features.sql",
)


def build_marts(database: connection) -> dict[str, int]:
    """Verrouiller la lecture CORE, rafraîchir les marts et réconcilier avant commit."""
    counts = {}
    with database:
        with database.cursor() as query:
            query.execute("SELECT pg_advisory_xact_lock(20261003, 0)")
            query.execute(
                "LOCK TABLE public.fact_travel_time, public.dim_commune, "
                "public.dim_point, public.dim_time, public.dim_trajectory IN SHARE MODE"
            )
            query.execute("SELECT count(*) FROM public.fact_travel_time")
            if query.fetchone()[0] != 73920:
                raise ValueError("CORE incomplet : charger la semaine type avant les marts")
            for filename in SQL_FILES:
                query.execute((ROOT / "sql/marts" / filename).read_text(encoding="utf-8"))
                LOGGER.info("SQL mart exécuté : %s", filename)
            for table in MART_TABLES:
                query.execute(
                    sql.SQL("SELECT count(*) FROM public.{}").format(sql.Identifier(table))
                )
                counts[table] = query.fetchone()[0]
            query.execute(
                "SELECT sum(measurement_count) FROM public.mart_commune_hourly_congestion"
            )
            if query.fetchone()[0] != 73920:
                raise ValueError("Mesures perdues ou multipliées dans les agrégats : rollback")
            if (counts[MART_TABLES[0]], counts[MART_TABLES[2]], counts[MART_TABLES[3]]) != (
                3696,
                44,
                22,
            ):
                raise ValueError(f"Cardinalités marts inattendues : {counts}")
            query.execute(
                "SELECT count(DISTINCT (commune_id, day_of_week)) FROM public.mart_peak_hours"
            )
            if query.fetchone()[0] != 154:
                raise ValueError("Les pointes doivent couvrir les 22 communes et les 7 jours")
    LOGGER.info("Marts reconstruits et réconciliés : %s", counts)
    return counts

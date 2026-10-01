"""Charger les dimensions et remplacer les partitions STAGING/CORE atomiquement."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from psycopg2 import sql
from psycopg2.extensions import connection, cursor
from psycopg2.extras import execute_values

from src.extract.excel_reader import extract_sheet, verify_raw
from src.load.quarantine import initialize_quarantine, persist_events
from src.transform.dimensions import dimension_frames
from src.transform.normalize import normalize_traffic, with_reference
from src.validate.normalized import admissible_rows, normalized_events
from src.validate.quality import enforce_threshold, validate_table

ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger(__name__)
STAGE_COLUMNS = [
    "source_sha256",
    "trajectory_id",
    "day_of_week",
    "hour",
    "travel_time_min",
    "distance_km",
    "travel_time_raw",
    "distance_raw",
    "tti_provided",
    "time_scaled",
    "distance_scaled",
    "index_repaired",
    "origin_index_raw",
    "dest_index_raw",
    "source_file",
    "sheet",
    "excel_row",
]
AUDIT_RENAME = {
    "_source_sha256": "source_sha256",
    "_source_file": "source_file",
    "_sheet": "sheet",
    "_excel_row": "excel_row",
    "origin_index": "origin_index_raw",
    "dest_index": "dest_index_raw",
}


def initialize_warehouse(database: connection) -> None:
    """Appliquer les DDL sur volume existant, sous verrou transactionnel."""
    initialize_quarantine(database)
    with database:
        with database.cursor() as query:
            query.execute("SELECT pg_advisory_xact_lock(20261001, 0)")
            query.execute((ROOT / "sql/ddl/02_warehouse.sql").read_text(encoding="utf-8"))


def insert_frame(query: cursor, table: str, frame: pd.DataFrame) -> None:
    """Insérer des tuples paramétrés sans concaténer de valeur source au SQL."""
    if frame.empty:
        return
    schema, name = table.split(".")
    statement = sql.SQL("INSERT INTO {} ({}) VALUES %s ON CONFLICT DO NOTHING").format(
        sql.Identifier(schema, name), sql.SQL(", ").join(sql.Identifier(column) for column in frame)
    )
    execute_values(query, statement, list(frame.itertuples(index=False, name=None)), page_size=1000)


def prepare_measures(
    raw: pd.DataFrame,
    points: pd.DataFrame,
    database: connection,
    run_id: str,
    threshold: float,
    references: dict[int, float] | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Journaliser puis séparer toutes les mesures admissibles des rejets explicites."""
    original = validate_table(raw, points)
    normalized = normalize_traffic(raw, points)
    if references is not None:
        normalized = with_reference(normalized, references)
    events = [*original.events, *normalized_events(normalized)]
    persist_events(database, events, run_id)
    accepted = admissible_rows(normalized, events)
    summary = {
        "total": len(normalized),
        "loaded": len(accepted),
        "rejected": len(normalized) - len(accepted),
    }
    enforce_threshold(summary, threshold)
    LOGGER.info("Normalisation et réconciliation : %s", summary)
    return accepted, summary


def reference_trajectories(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Figer le minimum indépendant du TTI fourni et la distance du lundi."""
    week = pd.concat(frames, ignore_index=True)
    reference = week.groupby("trajectory_id")["travel_time_min"].min()
    monday = (
        frames[0]
        .loc[
            frames[0]["hour"] == 0,
            ["trajectory_id", "origin_point_id", "dest_point_id", "distance_km"],
        ]
        .copy()
    )
    if monday["trajectory_id"].duplicated().any():
        raise ValueError("Trajets du lundi dupliqués")
    monday["free_flow_reference_min"] = monday["trajectory_id"].map(reference)
    monday["reference_source_sha256"] = frames[0]["_source_sha256"].iloc[0]
    if len(monday) != 440 or monday.isna().any().any():
        raise ValueError("Les 440 trajets doivent avoir une référence valide")
    for column in ("trajectory_id", "origin_point_id", "dest_point_id"):
        monday[column] = monday[column].astype(int)
    return monday


def bootstrap_warehouse(
    source: Path,
    raw_root: Path,
    database: connection,
    run_id: str,
    threshold: float,
) -> dict[str, int]:
    """Charger les références validées, sans insérer de faits lors du bootstrap."""
    initialize_warehouse(database)
    tables = {number: verify_raw(extract_sheet(source, raw_root, number)) for number in range(5)}
    for frame in tables.values():
        result = validate_table(frame, tables[0])
        persist_events(database, result.events, run_id)
        if result.summary["rejected"]:
            raise ValueError("Bootstrap bloqué : références invalides journalisées")
    dimensions = dimension_frames(tables)
    week = [
        prepare_measures(
            verify_raw(extract_sheet(source, raw_root, number)),
            tables[0],
            database,
            run_id,
            threshold,
        )[0]
        for number in range(5, 12)
    ]
    trajectories = reference_trajectories(week)
    with database:
        with database.cursor() as query:
            query.execute("SELECT pg_advisory_xact_lock(20261001, 1)")
            insert_frame(query, "staging.commune", dimensions["dim_commune"])
            insert_frame(query, "staging.point", dimensions["dim_point"])
            insert_frame(query, "staging.trajectory", trajectories)
            query.execute((ROOT / "sql/ddl/03_dimensions_to_core.sql").read_text(encoding="utf-8"))
            query.execute(
                "SELECT trajectory_id, free_flow_reference_min, reference_source_sha256 "
                "FROM public.dim_trajectory ORDER BY trajectory_id"
            )
            actual = query.fetchall()
            expected = list(
                trajectories.sort_values("trajectory_id")[
                    ["trajectory_id", "free_flow_reference_min", "reference_source_sha256"]
                ].itertuples(index=False, name=None)
            )
            if actual != expected:
                raise ValueError(
                    "Référence TTI figée incompatible : migration explicite nécessaire"
                )
    counts = {
        "dim_commune": 22,
        "dim_point": 110,
        "dim_time": 168,
        "dim_trajectory": len(trajectories),
    }
    LOGGER.info("Dimensions chargées : %s", counts)
    return counts


def load_partition(
    path: Path,
    points: pd.DataFrame,
    database: connection,
    run_id: str,
    threshold: float,
) -> dict[str, Any]:
    """Remplacer exactement les heures demandées ; rollback STAGING et CORE ensemble."""
    raw = verify_raw(path)
    with database.cursor() as query:
        query.execute("SELECT trajectory_id, free_flow_reference_min FROM public.dim_trajectory")
        references = dict(query.fetchall())
    frame, summary = prepare_measures(raw, points, database, run_id, threshold, references)
    all_rows = normalize_traffic(raw, points)
    day = int(all_rows["day_of_week"].iloc[0])
    hours = sorted(int(hour) for hour in all_rows["hour"].unique())
    source_hash = str(raw["_source_sha256"].iloc[0])
    stage = frame.rename(columns=AUDIT_RENAME)[STAGE_COLUMNS].copy()
    for column in (
        "trajectory_id",
        "day_of_week",
        "hour",
        "origin_index_raw",
        "dest_index_raw",
        "excel_row",
    ):
        stage[column] = stage[column].astype(int)
    with database:
        with database.cursor() as query:
            # Verrous des heures : un full et un replay concurrents ne se chevauchent pas.
            for hour in hours:
                query.execute(
                    "SELECT pg_advisory_xact_lock(20261002, %s)", ((day - 1) * 24 + hour,)
                )
            query.execute(
                "DELETE FROM staging.travel_time WHERE source_sha256=%s "
                "AND day_of_week=%s AND hour=ANY(%s)",
                (source_hash, day, hours),
            )
            insert_frame(query, "staging.travel_time", stage)
            query.execute(
                (ROOT / "sql/ddl/04_partition_to_core.sql").read_text(encoding="utf-8"),
                {"day": day, "hours": hours, "source_sha256": source_hash},
            )
            query.execute(
                "SELECT count(*) FROM public.fact_travel_time "
                "WHERE day_of_week=%s AND hour=ANY(%s)",
                (day, hours),
            )
            loaded = query.fetchone()[0]
            if loaded != summary["loaded"]:
                raise ValueError("Chargement non réconcilié : rollback de la partition")
    LOGGER.info("Partition jour=%d heures=%s chargée : %s", day, hours, summary)
    return summary | {"day_of_week": day, "hours": hours, "source_sha256": source_hash}

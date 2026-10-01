"""Persister les événements qualité sans doublon dans PostgreSQL."""

import logging
from pathlib import Path
from typing import Any

from psycopg2.extensions import connection
from psycopg2.extras import Json, execute_values

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]


def initialize_quarantine(database: connection) -> None:
    """Appliquer le DDL idempotent ; aucune suppression ni troncature."""
    with database:
        with database.cursor() as cursor:
            cursor.execute((ROOT / "sql/ddl/01_quarantine.sql").read_text(encoding="utf-8"))


def persist_events(database: connection, events: list[dict[str, Any]], run_id: str) -> int:
    """Upsert atomique : préserver la première observation et le payload brut."""
    if not events:
        return 0
    values = [
        (
            event["event_id"],
            event["source_sha256"],
            event["source_file"],
            event["sheet"],
            event["excel_row"],
            event["hour"],
            event["column_name"],
            event["reason"],
            event["severity"],
            Json(event["raw_payload"]),
            run_id,
        )
        for event in events
    ]
    with database:
        with database.cursor() as cursor:
            execute_values(
                cursor,
                """
                INSERT INTO public.quarantine
                (event_id, source_sha256, source_file, sheet, excel_row, hour, column_name,
                 reason, severity, raw_payload, last_run_id) VALUES %s
                ON CONFLICT (event_id) DO UPDATE SET
                    last_seen_at = now(), last_run_id = EXCLUDED.last_run_id
                """,
                values,
                page_size=500,
            )
    LOGGER.info("Quarantine : %d événements vérifiés/persistés, run=%s", len(events), run_id)
    return len(events)

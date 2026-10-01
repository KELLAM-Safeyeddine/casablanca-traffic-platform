"""Validation RAW, journal PostgreSQL et gate qualité dans cet ordre."""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
from psycopg2.extensions import connection

from src.extract.excel_reader import verify_raw
from src.load.quarantine import persist_events
from src.validate.quality import enforce_threshold, validate_table

LOGGER = logging.getLogger(__name__)


def safe_run_name(run_id: str) -> str:
    """Conserver un nom de dossier portable pour les runs Airflow horodatés."""
    readable = re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)[:100]
    digest = hashlib.sha256(run_id.encode()).hexdigest()[:12]
    return f"{readable}_{digest}"


def validate_partition(
    path: Path,
    points: pd.DataFrame,
    database: connection,
    run_id: str,
    max_error_rate: float,
    report_root: Path,
) -> dict[str, Any]:
    """Persister tous les événements avant d'appliquer le seuil de rejet."""
    raw = verify_raw(path)
    result = validate_table(raw, points)
    persist_events(database, result.events, run_id)
    summary = result.summary | {"raw_path": str(path), "run_id": run_id}
    report_root.mkdir(parents=True, exist_ok=True)
    name = f"{path.stem}_{raw['_sheet'].iloc[0].replace(' ', '_').replace('.', '_')}.json"
    (report_root / name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    LOGGER.info("Réconciliation qualité : %s", summary)
    enforce_threshold(summary, max_error_rate)
    return summary

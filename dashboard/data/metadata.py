"""Lecture de rapports d'exploitation externes, jamais de bases Airflow/quarantine."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import streamlit as st


@st.cache_data(ttl=30, show_spinner=False)
def read_metadata() -> dict[str, Any]:
    """Signaler absence, invalidité ou vieillissement sans inventer de fraîcheur."""
    path = (
        Path(os.environ.get("DASHBOARD_METADATA_ROOT", "/app/metadata")) / "dashboard_status.json"
    )
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(result["collected_at"])
        if timestamp.tzinfo is None or not isinstance(result.get("dags"), list):
            raise ValueError("Invalid metadata contract")
        result["stale"] = (datetime.now(UTC) - timestamp).total_seconds() > 3600
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return {"available": False, "stale": True}

"""Le collecteur publie atomiquement un contrat lisible sans état partiel."""

import json
from pathlib import Path

from src.load.dashboard_status import publish


def test_status_atomic_replace_and_explicit_unavailable(tmp_path: Path) -> None:
    first = {"available": True, "collected_at": "2026-10-02T00:00:00+00:00", "dags": []}
    publish(first, tmp_path)
    assert json.loads((tmp_path / "dashboard_status.json").read_text()) == first
    second = {"available": False, "collected_at": "2026-10-02T00:01:00+00:00", "dags": []}
    publish(second, tmp_path)
    assert json.loads((tmp_path / "dashboard_status.json").read_text()) == second
    assert not (tmp_path / "dashboard_status.tmp").exists()

"""Régression du gate CORE et des alertes locales, sans dépendance Airflow locale."""

import json
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

from src.validate.alerts import write_alert
from src.validate.warehouse_quality import EXPECTED, check_core_frame


def measure() -> pd.DataFrame:
    """Construire une mesure cohérente pour isoler les contrôles de formule."""
    return pd.DataFrame({
        "trajectory_id": [1], "origin_point_id": [0], "dest_point_id": [1],
        "day_of_week": [1], "hour": [0], "distance_km": [2.0],
        "travel_time_min": [4.0], "free_flow_reference_min": [2.0],
        "reference_min": [2.0], "tti": [2.0], "tti_provided": [1.5],
        "tti_delta": [0.5], "speed_kmh": [30.0],
    })


def test_incomplete_week_blocks_publication() -> None:
    with pytest.raises(ValueError, match="CORE incomplet"):
        check_core_frame(measure())


@pytest.mark.parametrize("column", ["tti", "speed_kmh", "free_flow_reference_min", "tti_delta"])
def test_inconsistent_formula_blocks_publication(monkeypatch, column: str) -> None:
    monkeypatch.setitem(EXPECTED, "fact_travel_time", 1)
    frame = measure()
    check_core_frame(frame)
    frame.loc[0, column] += 1
    with pytest.raises(ValueError, match=column):
        check_core_frame(frame)


def test_duplicate_grain_blocks_publication() -> None:
    with pytest.raises(pa.errors.SchemaErrors):
        check_core_frame(pd.concat([measure(), measure()], ignore_index=True))


def test_alert_is_idempotent_and_portable(tmp_path: Path) -> None:
    target = write_alert(tmp_path, "data_quality", "scheduled__2026-10-01T12:00:00+00:00",
                         "audit", -1)
    assert write_alert(tmp_path, "data_quality", "scheduled__2026-10-01T12:00:00+00:00",
                       "audit", -1) == target
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert json.loads(target.read_text())["state"] == "failed"
    assert ":" not in target.name


def test_alerts_keep_distinct_microsecond_run_ids(tmp_path: Path) -> None:
    first = write_alert(tmp_path, "data_quality", "manual__2026-10-01T12:00:00.111+00:00",
                        "audit", -1)
    second = write_alert(tmp_path, "data_quality", "manual__2026-10-01T12:00:00.222+00:00",
                         "audit", -1)
    assert first != second
    assert len(list(tmp_path.glob("*.json"))) == 2

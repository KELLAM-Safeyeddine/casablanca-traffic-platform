"""Contrats URL, formats et résumés métier, y compris sélections vides et égalités."""

import json
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from dashboard.components.formatting import number, summary, timestamp
from dashboard.components.kpis import period_gap
from dashboard.data import metadata, queries
from dashboard.data.filters import Filters, decode, encode


@pytest.mark.parametrize(
    "value,expected",
    [(12345.678, "12 345,68"), (None, "—"), (float("inf"), "—"), (float("nan"), "—")],
)
def test_french_number(value: object, expected: str) -> None:
    assert number(value) == expected
    assert number(12345.678, language="en") == "12,345.68"


def test_timestamp_uses_explicit_utc_and_preserves_missing_values() -> None:
    assert timestamp("2026-10-02T01:10:00+01:00") == "02/10/2026 00:10 UTC"
    assert timestamp("2026-10-02T00:10:00+00:00", "en") == "2026-10-02 00:10 UTC"
    assert timestamp(None) == "—"
    assert timestamp("2026-10-02T00:10:00") == "—"


@pytest.mark.parametrize("communes", [(), (1,), (1, 2)])
def test_url_roundtrip_and_empty_intersection(communes: tuple[int, ...]) -> None:
    filters = Filters(communes, (1, 6), (7, 19), "weekday")
    assert decode(encode(filters, (1, 2)), (1, 2)) == filters
    assert filters.effective_days == (1,)
    assert Filters(communes, (1,), period="weekend").effective_days == ()
    assert Filters((), ()).parameters()["communes"] == []


@pytest.mark.parametrize(
    "parameters",
    [
        {"hours": "23,0"},
        {"hours": "0,24"},
        {"days": "8"},
        {"communes": "999"},
        {"period": "invalid"},
    ],
)
def test_invalid_shared_link(parameters: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        decode(parameters, (1, 2))


def test_summary_uses_actual_pair_and_stable_ties() -> None:
    frame = pd.DataFrame(
        {"commune": ["B", "A", "A"], "hour": [18, 9, 8], "tti_mean": [2.0, 2.0, 2.0]}
    )
    assert summary(frame) == "A atteint le TTI moyen maximal de cette sélection à 08 h : 2,00."
    assert "08:00" in summary(frame, "en")
    assert "Aucune donnée" in summary(frame.iloc[:0])
    dangerous = frame.iloc[:1].assign(commune="<script>")
    assert "<script>" not in summary(dangerous)


def test_gap_does_not_invent_missing_period() -> None:
    frame = pd.DataFrame({"is_weekend": [False, True], "tti_mean": [2.0, 1.0]})
    assert period_gap(frame) == -50
    assert period_gap(frame.iloc[:1]) is None


def test_sql_is_whitelisted_and_values_are_bound() -> None:
    sql = queries.statement("points")
    assert "ST_X" in sql and "percentile_cont(0.95)" in sql
    assert "%(communes)s" in sql and "GROUP BY" in sql
    assert "quarantine" not in sql and "staging" not in sql
    with pytest.raises(KeyError):
        queries.statement("DROP TABLE")
    with pytest.raises(ValueError):
        queries.correlation_statement("primary_roads); DELETE FROM fact_travel_time")


def test_metadata_absence_and_staleness(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_METADATA_ROOT", str(tmp_path))
    metadata.read_metadata.clear()
    assert metadata.read_metadata()["available"] is False
    content = {"collected_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat(), "dags": []}
    (tmp_path / "dashboard_status.json").write_text(json.dumps(content))
    metadata.read_metadata.clear()
    assert metadata.read_metadata()["stale"] is True
    metadata.read_metadata.clear()

"""Prouver les rejets précis, les cas réparables et la conservation de la source."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.extract.excel_reader import METADATA_COLUMNS, extract_sheet, write_immutable_parquet
from src.extract.workbook_profile import SOURCE_SHA256, TRAFFIC_BASE_COLUMNS
from src.validate.pipeline import safe_run_name, validate_partition
from src.validate.quality import enforce_threshold, raw_payload, validate_table

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def raw_directory(tmp_path_factory):
    root = tmp_path_factory.mktemp("quality_raw")
    source = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
    for number in (0, 2, 5):
        extract_sheet(source, root, number)
    return root / f"source_sha256={SOURCE_SHA256}"


@pytest.fixture
def points(raw_directory):
    return pd.read_parquet(raw_directory / "table_00.parquet")


@pytest.fixture
def monday(raw_directory):
    return pd.read_parquet(raw_directory / "table_05.parquet")


@pytest.mark.parametrize("value", [0, -1, np.nan, np.inf, "invalid", True])
def test_bad_time_is_quarantined_for_its_hour_only(monday, points, value):
    monday["time_00"] = monday["time_00"].astype(object)
    monday.loc[0, "time_00"] = value
    original = monday.copy(deep=True)
    result = validate_table(monday, points)
    assert result.summary["rejected"] == 1
    assert result.summary["total"] == 10560
    matching = [
        event
        for event in result.events
        if event["excel_row"] == 11 and event["column_name"] == "time_00"
    ]
    assert matching and all(event["hour"] == 0 for event in matching)
    assert all(event["severity"] == "rejected" for event in matching)
    pd.testing.assert_frame_equal(monday, original)


def test_known_repairs_remain_traceable_and_unknown_index_rejected(monday, points):
    result = validate_table(monday, points)
    assert result.summary["rejected"] == 0
    assert result.summary["repairable"] == 480
    assert (
        sum(event["reason"] == "point_index_coordinate_mismatch" for event in result.events) == 40
    )  # origine et destination
    monday.loc[0, "origin_index"] = 999
    result = validate_table(monday, points)
    assert result.summary["rejected"] == 24


def test_tti_below_one_is_repairable_but_nonpositive_rejected(monday, points):
    monday.loc[0, "tti_00"] = 0.5
    result = validate_table(monday, points)
    assert any(
        event["column_name"] == "tti_00"
        and event["severity"] == "repairable"
        and event["excel_row"] == 11
        for event in result.events
    )
    monday.loc[0, "tti_00"] = 0
    assert validate_table(monday, points).summary["rejected"] == 1


def test_missing_column_and_duplicate_routes_are_not_dropped(monday, points):
    result = validate_table(monday.drop(columns="time_00"), points)
    assert result.summary["rejected"] == 440
    monday.loc[1, ["origin_index", "dest_index"]] = monday.loc[0, ["origin_index", "dest_index"]]
    assert validate_table(monday, points).summary["rejected"] >= 48


def test_invalid_coordinate_and_unknown_commune(monday, points):
    monday.loc[0, "origin_lat"] = 48.8
    monday.loc[1, "commune"] = "Unknown"
    result = validate_table(monday, points)
    assert result.summary["rejected"] == 48
    assert any(event["reason"] == "commune_zip_unknown" for event in result.events)


def test_point_duplicates_and_fractional_counts(points, raw_directory):
    duplicate = points.copy()
    duplicate.loc[1, ["Latitude", "Longitude"]] = duplicate.loc[0, ["Latitude", "Longitude"]]
    assert validate_table(duplicate, duplicate).summary["rejected"] == 2
    stations = pd.read_parquet(raw_directory / "table_02.parquet")
    stations["Tram-Station"] = stations["Tram-Station"].astype(float)
    stations.loc[0, "Tram-Station"] = 0.5
    assert validate_table(stations, points).summary["rejected"] == 1


def test_gate_and_json_payload():
    with pytest.raises(ValueError, match="Taux de rejet"):
        enforce_threshold({"total": 100, "rejected": 2}, 0.01)
    enforce_threshold({"total": 100, "rejected": 1}, 0.01)
    with pytest.raises(ValueError, match="seuil qualité"):
        enforce_threshold({"total": 100, "rejected": 0}, np.nan)
    assert raw_payload(pd.Series({"value": np.inf, "missing": np.nan})) == {
        "value": "inf",
        "missing": "nan",
    }


def test_persistence_precedes_failure_gate(monday, points, tmp_path, monkeypatch):
    monday.loc[0, "distance_raw"] = 0
    path = tmp_path / "synthetic.parquet"
    write_immutable_parquet(monday.drop(columns=list(METADATA_COLUMNS)), path,
                            "synthetic.xlsx", "Table 5. Monday", "b" * 64)
    captured = []
    monkeypatch.setattr("src.validate.pipeline.persist_events",
                        lambda database, events, run_id: captured.extend(events))
    with pytest.raises(ValueError, match="Taux de rejet"):
        validate_partition(path, points, None, "synthetic_gate", 0, tmp_path / "reports")
    assert any(event["column_name"] == "distance_raw"
               and event["raw_payload"]["distance_raw"] == 0 for event in captured)
    assert list((tmp_path / "reports").glob("*.json"))


def test_scheduled_run_report_name_is_portable():
    run_id = "scheduled__2026-10-01T22:00:00+00:00"
    name = safe_run_name(run_id)
    assert ":" not in name and "+" not in name
    assert name == safe_run_name(run_id)
    assert name != safe_run_name(run_id.replace(":", "_"))


def test_missing_replay_hour_is_fully_quarantined(monday, points):
    replay = monday[[*TRAFFIC_BASE_COLUMNS, "_excel_row", *METADATA_COLUMNS]].copy()
    replay["day_of_week"] = 1
    replay["travel_time_raw"] = monday["time_00"]
    replay["tti_provided"] = monday["tti_00"]
    result = validate_table(replay, points)
    assert result.summary["total"] == result.summary["rejected"] == 440
    assert any(event["column_name"] == "hour" for event in result.events)

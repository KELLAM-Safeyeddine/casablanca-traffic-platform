"""Tester les seuils d'unités, le crosswalk et les garanties avant CORE."""

import numpy as np
import pandas as pd
import pytest

from src.extract.workbook_profile import SOURCE_SHA256
from src.transform.normalize import (
    commune_key,
    normalize_distance,
    normalize_time,
    resolve_point,
    unpivot_traffic,
    with_reference,
)
from src.validate.normalized import admissible_rows, normalized_events


def test_unit_boundaries_and_source_scope():
    values = pd.Series([100, 101, 9954, 1.27, np.nan])
    distances, changed = normalize_distance(values)
    assert distances.iloc[:4].tolist() == [100, 0.101, 9.954, 1.27]
    assert changed.tolist() == [False, True, True, False, False]
    times, scaled = normalize_time(pd.Series([999, 1000, 10283, 1000.5, -1]), SOURCE_SHA256)
    assert times.tolist() == [999, 1, 10.283, 1000.5, -1]
    assert scaled.tolist() == [False, True, True, False, False]
    unscaled, flags = normalize_time(pd.Series([10283]), "unknown_version")
    assert unscaled.iloc[0] == 10283 and not flags.any()


def test_unicode_and_coordinate_resolution():
    assert commune_key("  ＣＡＳＡ   Blanca  ") == "casa blanca"
    assert commune_key(None) == ""
    assert resolve_point(110, 33.5, -7.6, {(33.5, -7.6): [105]}) == 105
    assert np.isnan(resolve_point(999, 33.5, -7.6, {(33.5, -7.6): [105]}))
    assert np.isnan(resolve_point(105, 33.5, -7.6, {(33.5, -7.6): [105, 106]}))


def test_long_format_preserves_missing_hour():
    raw = pd.DataFrame(
        {
            "commune": ["Casa"],
            "zip": [20000],
            "origin_index": [0],
            "origin_coordinates": ["raw"],
            "origin_lat": [33.5],
            "origin_lon": [-7.6],
            "dest_index": [1],
            "dest_coordinates": ["raw"],
            "dest_lat": [33.51],
            "dest_lon": [-7.61],
            "distance_raw": [9954],
            "_excel_row": [11],
            "_sheet": ["Table 5. Monday"],
            "time_00": [12.583],
            "tti_00": [1.26],
        }
    )
    long = unpivot_traffic(raw)
    assert len(long) == 24 and long["hour"].tolist() == list(range(24))
    assert long.loc[0, "travel_time_raw"] == 12.583
    assert long["travel_time_raw"].isna().sum() == 23
    assert long["distance_raw"].eq(9954).all()


@pytest.mark.parametrize("reference", [2.0, np.nan])
def test_invalid_frozen_reference_is_quarantined(reference):
    frame = pd.DataFrame(
        {
            "trajectory_id": [2],
            "origin_point_id": [0],
            "dest_point_id": [1],
            "day_of_week": [1],
            "hour": [0],
            "distance_km": [1.0],
            "travel_time_min": [1.0],
            "travel_time_raw": [1.0],
            "_excel_row": [11],
            "_sheet": ["Table 5. Monday"],
            "_source_sha256": [SOURCE_SHA256],
            "_source_file": ["synthetic.xlsx"],
        }
    )
    calculated = with_reference(frame, {2: reference})
    events = normalized_events(calculated)
    assert events and all(event["severity"] == "rejected" for event in events)
    assert admissible_rows(calculated, events).empty


def test_reference_and_speed_are_independent_of_source_tti():
    frame = pd.DataFrame(
        {
            "trajectory_id": [1, 1],
            "distance_km": [3.0, 4.0],
            "travel_time_min": [6.0, 8.0],
            "tti_provided": [99.0, 0.5],
        }
    )
    original = frame.copy()
    calculated = with_reference(frame, {1: 2.0})
    assert calculated["tti"].tolist() == [3.0, 4.0]
    assert calculated["speed_kmh"].tolist() == [30.0, 30.0]
    pd.testing.assert_frame_equal(frame, original)

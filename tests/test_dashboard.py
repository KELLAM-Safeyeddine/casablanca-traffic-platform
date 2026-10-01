"""Tester filtres, KPI et rendu Streamlit sans dépendre du warehouse local."""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.load.dashboard_data import aggregate, point_summary, select_measures


@pytest.fixture
def measures() -> pd.DataFrame:
    """Deux communes, deux jours et deux heures, avec deux observations par groupe."""
    rows = []
    for point, commune in [(0, "Commune A"), (1, "Commune B")]:
        for day in (1, 6):
            for hour in (0, 8):
                for tti in (1.0, 2.0 + point):
                    rows.append({"point_id": point, "commune": commune,
                                 "day_of_week": day, "hour": hour, "tti": tti,
                                 "latitude": 33.5 + point / 100, "longitude": -7.6,
                                 "speed_kmh": 30.0})
    return pd.DataFrame(rows)


def test_filters_are_inclusive_and_nonmutating(measures: pd.DataFrame) -> None:
    original = measures.copy(deep=True)
    selected = select_measures(measures, ["Commune A"], [1], (0, 8))
    assert len(selected) == 4 and set(selected.hour) == {0, 8}
    assert select_measures(measures, [], [1], (0, 23)).empty
    pd.testing.assert_frame_equal(measures, original)


def test_p95_is_computed_from_observations(measures: pd.DataFrame) -> None:
    result = aggregate(measures, ["commune"]).set_index("commune")
    assert result.loc["Commune A", "tti_mean"] == 1.5
    assert result.loc["Commune B", "tti_p95"] == 3
    assert result.measurement_count.sum() == len(measures)
    unequal = measures.iloc[[0, 1, 2, 3, 8]]
    assert aggregate(unequal.assign(group="all"), ["group"]).tti_mean.iloc[0] == 1.4


def test_map_keeps_points_and_stable_color_scale(measures: pd.DataFrame) -> None:
    points = point_summary(measures)
    assert len(points) == 2 and points.point_id.is_unique
    assert points.measurement_count.sum() == len(measures)
    assert all(len(color) == 4 for color in points.color)
    assert all(0 <= channel <= 255 for color in points.color for channel in color)


def test_streamlit_filters_and_empty_selection(monkeypatch, measures: pd.DataFrame) -> None:
    monkeypatch.setattr("src.load.dashboard_data.read_measures", lambda: measures)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "src/dashboard.py"))
    app.run(timeout=30)
    assert not app.exception
    assert [metric.value for metric in app.metric] == ["16", "1.750", "3.000", "2"]
    app.sidebar.multiselect[1].set_value([1]).run(timeout=30)
    assert not app.exception and app.metric[0].value == "8"
    app.sidebar.multiselect[0].set_value([]).run(timeout=30)
    assert not app.exception and len(app.info) == 1 and len(app.metric) == 0

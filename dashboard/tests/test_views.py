"""Exécuter chaque onglet avec AppTest ; données de test explicitement synthétiques."""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from dashboard.data import queries
from dashboard.pages_or_tabs import communes, map, quality

APP = Path(__file__).parents[1] / "app.py"


def fake_query(sql: str, parameters: dict[str, object]) -> pd.DataFrame:
    """Simuler les résultats SQL pour tester l'UI indépendamment des droits de production."""
    if "SELECT commune_id, nom commune" in sql:
        return pd.DataFrame({"commune_id": [1, 2], "commune": ["A", "B"]})
    if "SELECT (SELECT count(*)" in sql:
        return pd.DataFrame({"facts": [16], "points": [2], "communes": [2], "trajectories": [4]})
    rows = []
    for district in parameters["communes"]:
        for day in parameters["days"]:
            for hour in range(parameters["start"], parameters["end"] + 1):
                rows.append(
                    {
                        "commune_id": district,
                        "commune": "A" if district == 1 else "B",
                        "hour": hour,
                        "is_weekend": day >= 6,
                        "point_id": district,
                        "latitude": 33.55,
                        "longitude": -7.6,
                        "population_density_per_km2": district * 100,
                        "tram_stations": district,
                        "primary_roads": district * 2,
                    }
                )
    fields = queries.GROUPS
    ordered = sorted(fields, key=lambda key: -len(fields[key]))
    kind = next((kind for kind in ordered if "SELECT " + fields[kind] + "," in sql), "summary")
    if "corr(" in sql:
        kind = "features"
    if not rows or kind == "summary":
        return pd.DataFrame(
            {
                "measurement_count": [len(rows)],
                "tti_mean": [1.4],
                "tti_p95": [1.8],
                "speed_mean_kmh": [30.0],
                "travel_mean_min": [10.0],
                "tti_gap_count": [0],
            }
        )
    keys = fields[kind].replace("(day_of_week >= 6) ", "").split(", ")
    frame = pd.DataFrame(rows)[keys].drop_duplicates()
    frame = frame.assign(
        measurement_count=4,
        tti_mean=1.4,
        tti_p95=1.8,
        speed_mean_kmh=30.0,
        travel_mean_min=10.0,
        tti_gap_count=0,
    )
    if "corr(" in sql:
        frame = frame.assign(correlation=0.8, slope=0.001, intercept=1.1, pair_count=2)
    return frame


@pytest.fixture(autouse=True)
def mocked_results(monkeypatch):
    queries.fetch.clear()
    queries.correlations.clear()
    monkeypatch.setattr(queries, "execute", fake_query)
    yield
    queries.fetch.clear()
    queries.correlations.clear()


@pytest.mark.parametrize("tab", range(6))
@pytest.mark.parametrize("language", ["fr", "en"])
def test_each_tab_renders_without_raw_error(tab: int, language: str) -> None:
    app = AppTest.from_file(str(APP))
    app.query_params["tab"] = str(tab)
    app.query_params["lang"] = language
    app.run(timeout=30)
    assert not app.exception
    assert not app.error
    assert len(app.tabs) == 6


def test_empty_selection_url_language_and_reset() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.sidebar.multiselect[0].set_value([]).run(timeout=30)
    assert not app.exception and "Aucune donnée" in app.info[0].value
    assert app.query_params["days"] == ["none"]
    reset_button = next(b for b in app.button if b.label == "Réinitialiser les filtres")
    reset_button.click().run(timeout=30)
    assert not app.error and len(app.tabs) == 6
    app.sidebar.selectbox[0].select("en").run(timeout=30)
    assert not app.exception and app.tabs[0].label == "Overview"
    assert app.query_params["lang"] == ["en"]


def test_database_failure_is_readable(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("sensitive database traceback")

    monkeypatch.setattr(queries, "execute", fail)
    app = AppTest.from_file(str(APP)).run(timeout=30)
    assert not app.exception and len(app.error) == 1
    assert "sensitive" not in app.error[0].value


def test_navigation_keeps_selection_across_url_updates() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=30)
    for name, index in [("Heures de pointe", 2), ("Communes", 4), ("Semaine vs Week-end", 3)]:
        app.session_state["navigation"] = name
        app.run(timeout=30)
        assert not app.exception and not app.error
        assert app.query_params["tab"] == [str(index)]


def test_language_change_translates_options_without_losing_filters() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.sidebar.multiselect[0].set_value([1]).run(timeout=30)
    app.sidebar.slider[0].set_value((7, 19)).run(timeout=30)
    app.sidebar.selectbox[0].select("en").run(timeout=30)
    assert not app.exception and not app.error
    assert app.sidebar.selectbox[1].options == ["Traffic", "Cividis · accessible"]
    assert app.sidebar.multiselect[0].options[0] == "Monday"
    assert app.query_params["days"] == ["1"]
    assert app.query_params["hours"] == ["7,19"]
    app.sidebar.selectbox[0].select("fr").run(timeout=30)
    assert app.sidebar.selectbox[1].options == ["Trafic", "Cividis · accessible"]
    assert app.query_params["days"] == ["1"]


def test_language_change_preserves_latest_local_selection(monkeypatch) -> None:
    # AppTest sérialise les labels hors du contexte Streamlit utilisé par tr().
    # La traduction des filtres globaux est couverte séparément ; ici, tester l'état.
    monkeypatch.setattr(communes, "tr", lambda french, english: french)
    app = AppTest.from_file(str(APP))
    app.query_params["tab"] = "4"
    app.run(timeout=30)
    app.sidebar.selectbox[0].select("en").run(timeout=30)
    app.selectbox(key="ranking_order_en").select("bottom").run(timeout=30)
    app.sidebar.selectbox[0].select("fr").run(timeout=30)
    assert not app.exception and not app.error
    assert app.selectbox(key="ranking_order_fr").value == "bottom"
    assert app.query_params["ranking_order"] == ["bottom"]


def test_map_frame_failure_is_readable(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("private connection details")

    monkeypatch.setattr(map, "draw", fail)
    app = AppTest.from_file(str(APP))
    app.query_params["tab"] = "1"
    app.run(timeout=30)
    assert not app.exception and len(app.error) == 1
    assert "Carte indisponible" in app.error[0].value
    assert "private" not in app.error[0].value


def test_stale_metadata_never_displays_quality_success(monkeypatch) -> None:
    monkeypatch.setattr(
        quality,
        "read_metadata",
        lambda: {
            "available": True,
            "stale": True,
            "collected_at": "2026-10-02T00:00:00+00:00",
            "dags": [],
            "quarantine": {"total": 485, "repairable": 314, "warning": 171},
            "quality": {"status": "passed", "facts_checked": 73920},
        },
    )
    app = AppTest.from_file(str(APP))
    app.query_params["tab"] = "5"
    app.run(timeout=30)
    assert not app.exception and not app.success
    assert any("Statut qualité" in warning.value for warning in app.warning)

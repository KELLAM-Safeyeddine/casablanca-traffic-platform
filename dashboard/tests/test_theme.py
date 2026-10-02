"""Empêcher les recolorations partielles et les régressions de contraste."""

import re
import tomllib
from pathlib import Path

import pytest

from dashboard.components.contrast import contrast_ratio

ROOT = Path(__file__).parents[1]
CSS = (ROOT / "assets/style.css").read_text(encoding="utf-8")
CONFIG = tomllib.loads((ROOT / ".streamlit/config.toml").read_text(encoding="utf-8"))
PAIRS = {
    name: (light, dark)
    for name, light, dark in re.findall(
        r"--ct-(\w+):\s*light-dark\((#[\da-fA-F]+),\s*(#[\da-fA-F]+)\)", CSS
    )
}


def test_colors_only_declared_in_theme_variables() -> None:
    """Interdire les littéraux couleur dans les règles des composants."""
    without_comments = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    without_variables = re.sub(r"--[\w-]+\s*:[^;]+;", "", without_comments)
    assert not re.search(r"#[\da-fA-F]{3,8}\b|rgba?\(|hsla?\(", without_variables)
    assert len(PAIRS) == 6
    assert "base" not in CONFIG["theme"]


@pytest.mark.parametrize("index,theme", [(0, "light"), (1, "dark")])
def test_theme_contrast_and_native_palette(index: int, theme: str) -> None:
    """Texte principal/secondaire ≥4,5 ; accent UI ≥3 sur les deux surfaces."""
    palette = {key: values[index] for key, values in PAIRS.items()}
    native = CONFIG["theme"][theme]
    assert native["textColor"] == palette["text"]
    assert native["backgroundColor"] == palette["bg"]
    assert native["secondaryBackgroundColor"] == palette["surface"]
    assert native["primaryColor"] == palette["accent"]
    for background in (palette["bg"], palette["surface"]):
        assert contrast_ratio(palette["text"], background) >= 4.5
        assert contrast_ratio(palette["muted"], background) >= 4.5
        assert contrast_ratio(palette["accent"], background) >= 4.5


def test_dark_palette_is_unchanged() -> None:
    assert {key: value[1] for key, value in PAIRS.items()} == {
        "bg": "#0B1220", "surface": "#162033", "text": "#F1F5F9",
        "muted": "#B5C1D1", "accent": "#58CCD4", "border": "#334155",
    }


def test_native_charts_and_map_follow_frontend_theme() -> None:
    charts = (ROOT / "components/charts.py").read_text(encoding="utf-8")
    map_code = (ROOT / "pages_or_tabs/map.py").read_text(encoding="utf-8")
    assert 'theme="streamlit"' in charts and "appearance" not in charts
    assert "map_style=None" in map_code and "appearance" not in map_code
    assert '#MainMenu' not in CSS


def test_contrast_known_reference_values() -> None:
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21)
    assert contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1)
    assert contrast_ratio("#123456", "#FFFFFF") == contrast_ratio("#FFFFFF", "#123456")
    with pytest.raises(ValueError):
        contrast_ratio("transparent", "#FFFFFF")


@pytest.mark.parametrize("index", [0, 1])
def test_native_faded_text_still_meets_aa(index: int) -> None:
    """Les en-têtes canvas utilisent 60 % d'opacité : tester la couleur composée."""
    for key in ("bg", "surface"):
        foreground, background = PAIRS["text"][index], PAIRS[key][index]
        blended = "#" + "".join(
            f"{round(0.6 * int(foreground[n:n+2], 16) + 0.4 * int(background[n:n+2], 16)):02X}"
            for n in (1, 3, 5)
        )
        assert contrast_ratio(blended, background) >= 4.5


def test_plotly_labels_meet_aa_and_preserve_native_dark() -> None:
    match = re.search(r"--ct-chart-label:\s*light-dark\((#[\da-fA-F]+),\s*(#[\da-fA-F]+)\)", CSS)
    assert match and match[2] == "#E6EAF1"
    for index in (0, 1):
        assert contrast_ratio(match[index + 1], PAIRS["bg"][index]) >= 4.5


def test_map_tooltip_contrast_and_dark_preservation() -> None:
    colors = {}
    for name in ("bg", "text"):
        match = re.search(
            rf"--ct-map-tooltip-{name}:\s*light-dark\((#[\da-fA-F]+),\s*(#[\da-fA-F]+)\)", CSS
        )
        assert match
        colors[name] = match.groups()
    assert colors["bg"][1] == "#29323C"
    assert colors["text"][1] == "#A0A7B4"
    for index in (0, 1):
        assert contrast_ratio(colors["text"][index], colors["bg"][index]) >= 4.5


def test_plotly_toolbar_light_contrast() -> None:
    for name in ("icon", "active"):
        match = re.search(rf"--ct-chart-toolbar-{name}:\s*light-dark\((#[\da-fA-F]+),", CSS)
        assert match
        assert contrast_ratio(match[1], PAIRS["surface"][0]) >= 3

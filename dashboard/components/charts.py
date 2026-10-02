"""Palette partagée, thème Plotly, tooltips localisés et export PNG."""

from collections.abc import Iterable
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from plotly.colors import sample_colorscale

from dashboard.components.formatting import number

TRAFFIC = [[0, "#1B9E77"], [0.33, "#E6C84F"], [0.66, "#E77932"], [1, "#C52F40"]]
SERIES = ["#087F8C", "#B35B1D", "#725CC8", "#3B78BD"]


def scale() -> str | list[list[float | str]]:
    """La même échelle TTI sur la carte, heatmap et classements."""
    return "Cividis" if st.session_state.get("palette") == "cividis" else TRAFFIC


def rgba(tti: float) -> list[int]:
    """Échantillonner TTI 1–2 pour l'affichage, sans modifier la mesure exacte."""
    rgb = sample_colorscale(scale(), [max(0, min(1, tti - 1))])[0]
    channels = [int(float(v.strip())) for v in rgb[4:-1].split(",")]
    return [*channels, 220]


def skin() -> None:
    """Appliquer les variables et la CSS légère de l'application."""
    dark = st.session_state.get("appearance") == "dark"
    colors = (
        ("#0B1220", "#162033", "#F1F5F9", "#B5C1D1", "#58CCD4", "#334155")
        if dark
        else ("#F5F7FA", "#FFFFFF", "#172538", "#526174", "#087F8C", "#D8E1EA")
    )
    variables = ";".join(
        f"--ct-{key}:{value}"
        for key, value in zip(
            ["bg", "surface", "text", "muted", "accent", "border"], colors, strict=True
        )
    )
    css = (Path(__file__).parents[1] / "assets/style.css").read_text(encoding="utf-8")
    st.html(f"<style>:root{{{variables}}}{css}</style>")


def show(figure: go.Figure, name: str, title: str, y_title: str = "TTI") -> None:
    """Normaliser la présentation et conserver un bouton PNG natif côté navigateur."""
    dark = st.session_state.get("appearance") == "dark"
    figure.update_layout(
        title={"text": title, "font": {"size": 17}},
        template="plotly_dark" if dark else "plotly_white",
        font={"family": "Inter, Arial, sans-serif", "color": "#F1F5F9" if dark else "#172538"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 10, "r": 10, "t": 55, "b": 85},
        yaxis_title=y_title,
        separators=", " if st.session_state.get("language") == "fr" else ".,",
        legend={"orientation": "h", "y": -0.22, "x": 0},
    )
    figure.update_xaxes(tickformat=".2f" if figure.layout.xaxis.title.text == "TTI" else ",.0f")
    if y_title == "TTI":
        figure.update_yaxes(tickformat=".2f")
    st.plotly_chart(
        figure,
        width="stretch",
        key=name,
        config={
            "displaylogo": False,
            "toImageButtonOptions": {"format": "png", "filename": "casablanca_" + name, "scale": 2},
        },
    )


def labels(values: Iterable[float], digits: int = 2) -> list[str]:
    """Préformater les tooltips : format français même si Plotly n'est pas localisé."""
    return [number(v, digits, st.session_state.get("language", "fr")) for v in values]

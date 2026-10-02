"""Courbes horaires, périodes de référence et matrice commune × heure."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.components.charts import SERIES, labels, scale, show
from dashboard.components.filters import local_choice
from dashboard.components.i18n import tr
from dashboard.data.filters import Filters
from dashboard.data.queries import fetch


def hourly_chart(frame: pd.DataFrame, key: str) -> None:
    """Tracer les moyennes SQL et les p95 exacts, sans réagréger le résultat."""
    ordered = frame.sort_values("hour")
    figure = go.Figure()
    for column, name, dash in [
        ("tti_mean", tr("TTI moyen", "Mean TTI"), "solid"),
        ("tti_p95", "TTI p95", "dot"),
    ]:
        figure.add_trace(
            go.Scatter(
                x=ordered.hour,
                y=ordered[column],
                name=name,
                mode="lines+markers",
                line={"color": SERIES[0], "dash": dash},
                customdata=labels(ordered[column]),
                hovertemplate="%{x}:00 · %{customdata}<extra>%{fullData.name}</extra>",
            )
        )
    for start, end in [(6.5, 9.5), (16.5, 19.5)]:
        figure.add_vrect(x0=start, x1=end, fillcolor="#D6A32A", opacity=0.12, line_width=0)
    figure.add_hline(y=1, line_dash="dot", annotation_text=tr("Référence", "Reference"))
    figure.update_layout(xaxis_title=tr("Heure de la semaine type", "Typical-week hour"))
    show(figure, key, tr("Profil horaire · moyenne et p95", "Hourly profile · mean and p95"))


def render(filters: Filters, catalog: tuple[int, ...]) -> None:
    """Compléter les courbes par une heatmap filtrable et un tableau numérique."""
    hourly_chart(fetch("hourly", filters), "peak_hourly")
    st.caption(
        tr(
            "Bandes de référence : 07–09 h et 17–19 h. Le maximum réel peut être ailleurs.",
            "Reference bands: 07–09 and 17–19. The actual maximum may be elsewhere.",
        )
    )
    frame = fetch("heatmap", filters)
    choices = [tr("Toutes", "All"), *sorted(frame.commune.unique())]
    choice = local_choice(
        "heatmap_commune",
        tr("Commune de la heatmap", "Heatmap district"),
        choices,
        tr("Filtre local à la matrice.", "Local matrix filter."),
    )
    if choice != choices[0]:
        frame = frame.loc[frame.commune == choice]
    matrix = frame.pivot(index="commune", columns="hour", values="tti_mean")
    cells = {
        (row.commune, row.hour): labels([row.tti_mean, row.tti_p95, row.measurement_count])
        for row in frame.itertuples()
    }
    formatted = [
        [cells.get((name, hour), ["—", "—", "—"]) for hour in matrix.columns]
        for name in matrix.index
    ]
    figure = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=matrix.columns,
            y=matrix.index,
            colorscale=scale(),
            zmin=1,
            zmax=2,
            customdata=formatted,
            colorbar={"title": "TTI · 1–≥2"},
            hovertemplate="%{y} · %{x}:00<br>TTI %{customdata[0]}"
            "<br>p95 %{customdata[1]} · n=%{customdata[2]}<extra></extra>",
        )
    )
    figure.update_layout(height=max(380, len(matrix) * 25 + 100), xaxis_title=tr("Heure", "Hour"))
    show(
        figure,
        "peak_heatmap",
        tr("Congestion par commune et heure", "District/hour congestion"),
        tr("Commune", "District"),
    )
    st.dataframe(frame, hide_index=True, width="stretch")

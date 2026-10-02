"""Classement réglable et associations descriptives avec les variables urbaines."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.components.charts import SERIES, labels, scale, show
from dashboard.components.filters import local_choice
from dashboard.components.formatting import number
from dashboard.components.i18n import tr
from dashboard.components.tables import show as show_table
from dashboard.data.filters import Filters
from dashboard.data.queries import correlations, fetch


def ranking(filters: Filters) -> None:
    """Présenter les N communes choisies, tri stable et valeurs numériques visibles."""
    frame = fetch("communes", filters)
    direction = local_choice(
        "ranking_order",
        tr("Classement", "Ranking"),
        ["top", "bottom"],
        tr("Plus ou moins congestionnées.", "Most or least congested."),
        lambda value: tr("Plus congestionnées", "Most congested")
        if value == "top"
        else tr("Moins congestionnées", "Least congested"),
    )
    count = local_choice(
        "ranking_n",
        tr("Nombre de communes", "Number of districts"),
        list(range(1, len(frame) + 1)),
        tr("Borné à la sélection disponible.", "Limited to available districts."),
        default=min(10, len(frame)),
    )
    displayed = frame.sort_values(
        ["tti_mean", "commune"], ascending=[direction == "bottom", True]
    ).head(count)
    figure = go.Figure(
        go.Bar(
            x=displayed.tti_mean,
            y=displayed.commune,
            orientation="h",
            marker={"color": displayed.tti_mean, "colorscale": scale(), "cmin": 1, "cmax": 2},
            text=labels(displayed.tti_mean),
            textposition="outside",
            hovertemplate="%{y}<br>TTI %{text}<extra></extra>",
        )
    )
    figure.update_layout(
        yaxis={"autorange": "reversed"}, height=max(340, count * 28 + 100), xaxis_title="TTI"
    )
    show(figure, "commune_ranking", tr("Classement des communes", "District ranking"), "")
    show_table(displayed)


def association(filters: Filters) -> None:
    """Afficher corrélation et droite SQL ; exclure les cas statistiquement indéfinis."""
    options = {
        "population_density_per_km2": tr("Densité · habitants/km²", "Density · people/km²"),
        "tram_stations": tr("Stations de tram", "Tram stations"),
        "primary_roads": tr("Routes primaires", "Primary roads"),
    }
    variable = local_choice(
        "urban_variable",
        tr("Variable urbaine", "Urban variable"),
        list(options),
        tr(
            "Une observation par commune ; association descriptive.",
            "One observation per district; descriptive association.",
        ),
        options.get,
    )
    frame = correlations(variable, filters)
    if frame.empty:
        st.info(tr("Aucune paire disponible.", "No available pairs."))
        return
    row = frame.iloc[0]
    figure = go.Figure(
        go.Scatter(
            x=frame[variable],
            y=frame.tti_mean,
            mode="markers",
            name=tr("Communes", "Districts"),
            marker={"color": SERIES[0], "size": 12},
            customdata=list(
                zip(frame.commune, labels(frame.tti_mean), labels(frame[variable]), strict=True)
            ),
            hovertemplate="%{customdata[0]}<br>X %{customdata[2]}"
            "<br>TTI %{customdata[1]}<extra></extra>",
        )
    )
    valid = row.pair_count >= 3 and pd.notna(row.correlation) and pd.notna(row.slope)
    if valid:
        figure.add_trace(
            go.Scatter(
                x=frame[variable],
                y=frame[variable] * row.slope + row.intercept,
                mode="lines",
                line={"dash": "dash", "color": SERIES[1]},
                name=tr("Tendance linéaire", "Linear trend"),
            )
        )
        coefficient = float(row.correlation)
        strength = (
            tr("faible", "weak")
            if abs(coefficient) < 0.3
            else tr("modérée", "moderate")
            if abs(coefficient) < 0.7
            else tr("forte", "strong")
        )
        st.caption(
            tr("Association", "Association")
            + f" {strength} · r="
            + number(coefficient, 3, st.session_state.language)
            + f" · n={int(row.pair_count)}"
        )
    else:
        st.info(
            tr(
                "Pas de tendance estimable : moins de trois paires ou variable constante.",
                "No estimable trend: fewer than three pairs or constant variable.",
            )
        )
    figure.update_layout(xaxis_title=options[variable])
    show(
        figure,
        "urban_correlation",
        tr("Congestion et contexte urbain", "Congestion and urban context"),
    )
    st.caption(
        tr(
            "Association observée, pas preuve de causalité. Échantillon limité à 22 communes.",
            "Observed association, not evidence of causality. At most 22 districts.",
        )
    )


def render(filters: Filters, catalog: tuple[int, ...]) -> None:
    """Rassembler classement et contexte, avec séparation des objectifs."""
    ranking(filters)
    st.divider()
    association(filters)

"""Comparaisons explicites des périodes et de deux communes."""

import plotly.graph_objects as go
import streamlit as st

from dashboard.components.charts import SERIES, labels, show
from dashboard.components.filters import local_choice
from dashboard.components.formatting import number
from dashboard.components.i18n import tr
from dashboard.components.tables import show as show_table
from dashboard.data.filters import Filters
from dashboard.data.queries import fetch


def period_chart(filters: Filters) -> None:
    """Garder les deux périodes sur les communes/heures choisies, avec avertissement visible."""
    comparative = Filters(filters.communes, hours=filters.hours)
    periods = fetch("periods", comparative).sort_values("is_weekend")
    names = [
        tr("Semaine", "Weekdays") if not v else tr("Week-end", "Weekend")
        for v in periods.is_weekend
    ]
    figure = go.Figure(
        go.Bar(
            x=names,
            y=periods.tti_mean,
            marker_color=SERIES[:2],
            text=labels(periods.tti_mean),
            textposition="outside",
            customdata=labels(periods.measurement_count, 0),
            hovertemplate="%{x}<br>TTI %{text}<br>n=%{customdata}<extra></extra>",
        )
    )
    show(figure, "weekend_bars", tr("TTI moyen par période", "Mean TTI by period"))
    hourly = fetch("period_hourly", comparative)
    figure = go.Figure()
    for index, weekend in enumerate([False, True]):
        part = hourly.loc[hourly.is_weekend == weekend].sort_values("hour")
        figure.add_trace(
            go.Scatter(
                x=part.hour,
                y=part.tti_mean,
                mode="lines+markers",
                name=names[index] if len(names) == 2 else str(weekend),
                line={"color": SERIES[index], "dash": "dash" if weekend else "solid"},
                customdata=labels(part.tti_mean),
                hovertemplate="%{x}:00 · %{customdata}<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_layout(xaxis_title=tr("Heure", "Hour"))
    show(
        figure, "weekend_hourly", tr("Profils semaine et week-end", "Weekday and weekend profiles")
    )
    st.caption(
        tr(
            "Deux périodes conservées : mêmes communes/heures, filtre jours/période ignoré.",
            "Both periods retained: same districts/hours, day/period filters ignored.",
        )
    )
    show_table(periods)


def compare_districts(filters: Filters, catalog: tuple[int, ...]) -> None:
    """Comparer deux communes sans laisser le filtre global exclure le second choix."""
    names = fetch("catalog").set_index("commune_id").commune.to_dict()
    if len(catalog) < 2:
        st.info(tr("Deux communes sont nécessaires.", "Two districts are required."))
        return
    left, right = st.columns(2)
    with left:
        first = local_choice(
            "compare_a",
            tr("Commune A", "District A"),
            list(catalog),
            tr(
                "Choix local indépendant du filtre communes.",
                "Local selection independent of district filters.",
            ),
            names.get,
        )
    with right:
        second = local_choice(
            "compare_b",
            tr("Commune B", "District B"),
            [v for v in catalog if v != first],
            tr("Même plage horaire et mêmes jours que A.", "Same hours and days as A."),
            names.get,
        )
    figure = go.Figure()
    profiles = []
    for index, district in enumerate([first, second]):
        selected = Filters((district,), filters.days, filters.hours, filters.period)
        frame = fetch("hourly", selected).sort_values("hour")
        profiles.append(frame)
        figure.add_trace(
            go.Scatter(
                x=frame.hour,
                y=frame.tti_mean,
                name=names[district],
                mode="lines+markers",
                line={"color": SERIES[index], "dash": "solid" if index == 0 else "dash"},
                customdata=labels(frame.tti_mean),
                hovertemplate="%{x}:00 · %{customdata}<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_layout(xaxis_title=tr("Heure", "Hour"))
    show(
        figure,
        "district_comparison",
        tr("Deux communes · mêmes axes", "Two districts · shared axes"),
    )
    # Bornes d'affichage communes ; aucune métrique métier n'est réagrégée ici.
    ceiling = max(float(profile.tti_mean.max()) for profile in profiles) * 1.1
    for column, district, profile in zip(st.columns(2), [first, second], profiles, strict=True):
        with column:
            scope = Filters((district,), filters.days, filters.hours, filters.period)
            mean = fetch("summary", scope).iloc[0].tti_mean
            st.metric(
                names[district],
                number(mean, language=st.session_state.language),
                help=tr(
                    "TTI moyen de cette commune sur les jours/heures sélectionnés.",
                    "District mean TTI over selected days/hours.",
                ),
            )
            small = go.Figure(
                go.Scatter(
                    x=profile.hour,
                    y=profile.tti_mean,
                    mode="lines+markers",
                    line={"color": SERIES[0]},
                    customdata=labels(profile.tti_mean),
                    hovertemplate="%{x}:00 · %{customdata}<extra></extra>",
                )
            )
            small.update_layout(yaxis_range=[1, ceiling], xaxis_title=tr("Heure", "Hour"))
            show(small, f"side_by_side_{district}", names[district])
    st.caption(
        tr(
            "Cette comparaison remplace le filtre communes ; jours/heures restent appliqués.",
            "This comparison overrides district filters; days/hours still apply.",
        )
    )


def render(filters: Filters, catalog: tuple[int, ...]) -> None:
    """Afficher les deux échelles de comparaison, avec leur périmètre explicite."""
    period_chart(filters)
    st.divider()
    compare_districts(filters, catalog)

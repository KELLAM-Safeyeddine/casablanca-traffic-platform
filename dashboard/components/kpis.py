"""Six cartes de synthèse avec définitions et références comparables."""

from html import escape

import pandas as pd
import streamlit as st

from dashboard.components.formatting import number
from dashboard.components.i18n import tr


def period_gap(periods: pd.DataFrame) -> float | None:
    """Lire deux moyennes SQL ; pas de moyenne de groupes en Python."""
    indexed = periods.set_index("is_weekend")
    if True not in indexed.index or False not in indexed.index:
        return None
    return (float(indexed.loc[True, "tti_mean"]) / float(indexed.loc[False, "tti_mean"]) - 1) * 100


def cards(
    selected: pd.DataFrame,
    baseline: pd.DataFrame,
    districts: pd.DataFrame,
    hourly: pd.DataFrame,
    periods: pd.DataFrame,
    global_periods: pd.DataFrame,
) -> None:
    """Comparer chaque KPI à une référence explicite, avec unités dans le delta."""
    language = st.session_state.language
    metric, global_metric = selected.iloc[0], baseline.iloc[0]
    top = districts.sort_values(["tti_mean", "commune"], ascending=[False, True]).iloc[0]
    peak = hourly.sort_values(["tti_mean", "hour"], ascending=[False, True]).iloc[0]
    gap, global_gap = period_gap(periods), period_gap(global_periods)

    def value(v: object, digits: int = 2) -> str:
        return number(v, digits, language)

    comparison = tr("écart au TTI moyen global", "difference vs global mean TTI")
    specifications = [
        (
            tr("TTI moyen", "Mean TTI"),
            value(metric.tti_mean),
            value(metric.tti_mean - global_metric.tti_mean),
            comparison,
            tr(
                "Moyenne par observation, référence empirique du trajet.",
                "Observation mean, relative to the route's empirical reference.",
            ),
        ),
        (
            "TTI p95",
            value(metric.tti_p95),
            value(metric.tti_p95 - global_metric.tti_mean),
            comparison,
            tr(
                "95 % des observations ont un TTI inférieur ou égal à cette valeur.",
                "95% of observations have a TTI at or below this value.",
            ),
        ),
        (
            tr("Commune la plus congestionnée", "Most congested district"),
            f"{escape(str(top.commune))} · {value(top.tti_mean)}",
            value(top.tti_mean - global_metric.tti_mean),
            comparison,
            tr(
                "Maximum du TTI moyen par commune ; ordre alphabétique en cas d'égalité.",
                "Highest district mean TTI; alphabetical tie break.",
            ),
        ),
        (
            tr("Heure de pointe", "Peak hour"),
            f"{int(peak.hour):02d} h · {value(peak.tti_mean)}",
            value(peak.tti_mean - global_metric.tti_mean),
            comparison,
            tr(
                "Maximum horaire dans cette sélection ; première heure en cas d'égalité.",
                "Highest hourly mean in the selection; earliest hour on a tie.",
            ),
        ),
        (
            tr("Vitesse moyenne", "Mean speed"),
            value(metric.speed_mean_kmh) + " km/h",
            value(metric.speed_mean_kmh - global_metric.speed_mean_kmh) + " km/h",
            tr("écart à la vitesse globale", "difference vs global mean speed"),
            tr(
                "Moyenne arithmétique des vitesses de chaque observation.",
                "Arithmetic mean of each observation's speed.",
            ),
        ),
        (
            tr("Écart week-end / semaine", "Weekend / weekday gap"),
            value(gap) + " %",
            value(None if gap is None or global_gap is None else gap - global_gap) + " pp",
            tr("écart au différentiel global", "difference vs global gap"),
            tr(
                "100 × (TTI week-end / semaine −1), mêmes communes/heures ; "
                "deux périodes conservées.",
                "100 × (weekend / weekday TTI −1), same districts/hours; both periods retained.",
            ),
        ),
    ]
    html = "".join(
        f'<article class="ct-card"><div class="label">'
        f'<abbr tabindex="0" title="{escape(help_text)}">{escape(label)}</abbr></div>'
        f'<div class="value">{display}</div><div class="delta">'
        f"{delta} · {escape(reference)}</div></article>"
        for label, display, delta, reference, help_text in specifications
    )
    st.html(f'<div class="ct-grid">{html}</div>')

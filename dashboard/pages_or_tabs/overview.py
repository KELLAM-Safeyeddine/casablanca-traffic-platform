"""Synthèse des six indicateurs et résumé déterministe de la sélection."""

import streamlit as st

from dashboard.components.formatting import summary
from dashboard.components.i18n import tr
from dashboard.components.kpis import cards
from dashboard.data.filters import Filters
from dashboard.data.queries import fetch
from dashboard.pages_or_tabs.peak_hours import hourly_chart


def render(filters: Filters, catalog: tuple[int, ...]) -> None:
    """Lire les agrégats SQL nécessaires à la synthèse, jamais tous les faits."""
    global_filters = Filters(catalog)
    comparative = Filters(filters.communes, hours=filters.hours)
    cards(
        fetch("summary", filters),
        fetch("summary", global_filters),
        fetch("communes", filters),
        fetch("hourly", filters),
        fetch("periods", comparative),
        fetch("periods", global_filters),
    )
    st.info(summary(fetch("heatmap", filters), st.session_state.language))
    st.caption(
        tr(
            "Référence globale : toutes communes, sept jours et 24 heures.",
            "Global reference: all districts, seven days and 24 hours.",
        )
    )
    hourly_chart(fetch("hourly", filters), "overview_hourly")

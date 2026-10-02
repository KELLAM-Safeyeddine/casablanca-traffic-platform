"""Entrée du dashboard moderne : navigation différée et lectures contrôlées."""

import logging
from html import escape

import streamlit as st

from dashboard.components.charts import skin
from dashboard.components.filters import sidebar
from dashboard.components.formatting import number
from dashboard.components.i18n import TABS, tr
from dashboard.data.queries import fetch
from dashboard.pages_or_tabs import communes, map, overview, peak_hours, quality, weekend

LOGGER = logging.getLogger(__name__)
RENDERERS = [
    overview.render,
    map.render,
    peak_hours.render,
    weekend.render,
    communes.render,
    quality.render,
]


def guide() -> None:
    """Définir le TTI et les limites métier dans les deux langues."""
    with st.expander(tr("Comment lire ce dashboard", "How to read this dashboard")):
        st.markdown(
            tr(
                "**TTI >1 = trajet plus lent que sa référence.** Un TTI de 1,5 correspond à +50 %. "
                "La référence est ici le minimum hebdomadaire corrigé du trajet, et non une "
                "mesure indépendante en circulation fluide. Chaque observation a le même poids. "
                "Les communes sont celles de l'origine. "
                "Il s'agit d'une semaine type sans dates réelles. "
                "Le bouton appareil photo des graphiques télécharge un PNG.",
                "**TTI >1 means slower than the reference.** TTI 1.5 means +50%. "
                "The reference is the route's corrected weekly minimum, not an independent "
                "free-flow measurement. Observations have equal weight. "
                "Districts refer to origins. This is a typical week without actual dates. "
                "Use the chart camera button to export PNG.",
            )
        )


def content() -> None:
    """Rendre uniquement l'onglet actif et afficher explicitement les sélections vides."""
    catalog = fetch("catalog")
    if catalog.empty:
        st.info(tr("Marts absents : terminer le chargement.", "No marts: finish ingestion."))
        return
    filters = sidebar(catalog)
    skin()
    subtitle = tr("Comprendre la congestion d'une semaine type", "Explore a typical traffic week")
    st.html(
        '<header class="ct-hero"><div class="ct-eyebrow">MOBILITY / CASABLANCA</div>'
        f"<h1>Casablanca Traffic</h1><p>{escape(subtitle)}</p></header>"
    )
    if st.session_state.pop("invalid_url", False):
        st.warning(tr("Lien invalide : filtres réinitialisés.", "Invalid link: filters reset."))
    counts = fetch("summary", filters)
    count = int(counts.iloc[0].measurement_count)
    st.caption(
        f"{number(count, 0, st.session_state.language)} "
        + tr("mesures sélectionnées", "selected observations")
        + f" · {filters.hours[0]:02d}–{filters.hours[1]:02d} h"
    )
    if count == 0:
        st.info(
            tr(
                "Aucune donnée pour ces filtres. Réinitialisez ou élargissez la sélection.",
                "No matching data. Reset or broaden your filters.",
            )
        )
        guide()
        return
    names = TABS[st.session_state.language]
    default_id = st.query_params.get("tab", "0")
    default_index = int(default_id) if default_id in {str(i) for i in range(6)} else 0
    # Le default participe à l'identité du widget : le figer évite de perdre
    # le clic suivant lorsque l'URL vient d'être synchronisée.
    if st.session_state.get("navigation_language") != st.session_state.language:
        st.session_state.navigation_default = default_index
        st.session_state.navigation_language = st.session_state.language
    tabs = st.tabs(
        names,
        default=names[st.session_state.navigation_default],
        key="navigation",
        on_change="rerun",
    )
    ids = tuple(sorted(int(v) for v in catalog.commune_id))
    for index, tab in enumerate(tabs):
        if tab.open:
            if index != 1:
                st.session_state.playing = False
            if st.query_params.get("tab") != str(index):
                st.query_params["tab"] = str(index)
            with tab, st.spinner(tr("Préparation de la vue…", "Preparing view…")):
                RENDERERS[index](filters, ids)
    guide()


def main() -> None:
    """Intercepter les erreurs côté serveur, sans traceback ni secret dans l'UI."""
    st.set_page_config(page_title="Casablanca Traffic", page_icon="🚦", layout="wide")
    try:
        content()
    except Exception:
        LOGGER.exception("Dashboard view unavailable")
        st.error(
            tr(
                "Cette vue est indisponible. Vérifiez la connexion puis réessayez.",
                "This view is unavailable. Check the connection and retry.",
            )
        )
        if st.button(tr("Réessayer", "Retry")):
            st.cache_data.clear()
            st.rerun()


if __name__ == "__main__":
    main()

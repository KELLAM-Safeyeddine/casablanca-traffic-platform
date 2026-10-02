"""Couverture, rapports qualité et exports complets de la sélection."""

import streamlit as st

from dashboard.components.i18n import tr
from dashboard.data.filters import Filters
from dashboard.data.metadata import read_metadata
from dashboard.data.queries import fetch


def render(filters: Filters, catalog: tuple[int, ...]) -> None:
    """Séparer données métier, métadonnées collectées et date d'observation inconnue."""
    st.subheader(tr("Couverture du warehouse", "Warehouse coverage"))
    st.dataframe(fetch("coverage"), hide_index=True, width="stretch")
    metadata = read_metadata()
    if not metadata.get("available", True):
        st.warning(
            tr(
                "Métadonnées d'exploitation indisponibles. Statut qualité à vérifier.",
                "Operational metadata unavailable. Quality status needs verification.",
            )
        )
    else:
        st.caption(
            tr("Métadonnées collectées à", "Metadata collected at") + " " + metadata["collected_at"]
        )
        if metadata["stale"]:
            st.warning(
                tr(
                    "Rapport de plus d'une heure : fraîcheur à vérifier.",
                    "Report older than one hour: freshness needs verification.",
                )
            )
        st.dataframe(metadata["dags"], hide_index=True, width="stretch")
        st.write(
            tr(
                "Journal quarantine (événements, pas lignes supprimées)",
                "Quarantine journal (events, not deleted rows)",
            ),
            metadata.get("quarantine"),
        )
        st.write(tr("Dernier audit observé", "Last observed audit"), metadata.get("quality"))
    st.caption(
        tr(
            "Les dates ci-dessus sont des dates de traitement/collecte, pas d'observation.",
            "Dates above refer to processing/collection, not observation.",
        )
    )
    with st.expander(tr("Anomalies connues et corrections", "Known anomalies and corrections")):
        st.markdown(
            tr(
                "Distances mètres/km normalisées ; temps entiers remis à l'échelle ; "
                "indices réparés. Le TTI fourni est conservé avec son écart au TTI recalculé. "
                "Aucun rejet silencieux. "
                "La densité calculée par km² est distincte de la densité source d'unité inconnue.",
                "Mixed meter/km distances normalized; scaled integer times corrected; "
                "indices repaired. "
                "Supplied TTI is retained with its recalculated difference. No silent rejection. "
                "Computed density per km² is distinct from source density with unknown units.",
            )
        )
    st.subheader(tr("Données filtrées et export", "Filtered data and export"))
    if st.button(tr("Préparer l'export CSV complet", "Prepare full CSV export")):
        with st.spinner(
            tr("Lecture des observations sélectionnées…", "Reading selected observations…")
        ):
            frame = fetch("export", filters)
        st.dataframe(frame.head(100), hide_index=True, width="stretch")
        st.caption(
            tr(
                "Aperçu limité à 100 lignes ; le fichier contient toute la sélection.",
                "Preview limited to 100 rows; file includes the entire selection.",
            )
        )
        french = st.session_state.language == "fr"
        content = frame.to_csv(
            index=False, sep=";" if french else ",", decimal="," if french else "."
        ).encode("utf-8-sig")
        st.download_button(
            tr("Télécharger CSV", "Download CSV"),
            content,
            "casablanca_traffic.csv",
            "text/csv",
            on_click="ignore",
        )

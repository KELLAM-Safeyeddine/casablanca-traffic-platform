"""Couverture, rapports qualité et exports complets de la sélection."""

import pandas as pd
import streamlit as st

from dashboard.components.formatting import number, timestamp
from dashboard.components.i18n import tr
from dashboard.data.filters import Filters
from dashboard.data.metadata import read_metadata
from dashboard.data.queries import fetch


def render(filters: Filters, catalog: tuple[int, ...]) -> None:
    """Séparer données métier, métadonnées collectées et date d'observation inconnue."""
    st.subheader(tr("Couverture du warehouse", "Warehouse coverage"))
    coverage = fetch("coverage").rename(
        columns={
            "facts": tr("Observations", "Observations"),
            "points": tr("Points", "Points"),
            "trajectories": tr("Trajets", "Routes"),
            "communes": tr("Communes", "Districts"),
        }
    )
    st.dataframe(coverage, hide_index=True, width="stretch")
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
            tr("Métadonnées collectées à", "Metadata collected at")
            + " "
            + timestamp(metadata["collected_at"], st.session_state.language)
        )
        if metadata["stale"]:
            st.warning(
                tr(
                    "Rapport de plus d'une heure : fraîcheur à vérifier.",
                    "Report older than one hour: freshness needs verification.",
                )
            )
        quarantine = metadata.get("quarantine", {})
        st.metric(
            tr("Événements en quarantaine", "Quarantine events"),
            number(quarantine.get("total"), 0, st.session_state.language),
            help=tr(
                "Journal d'anomalies : les événements réparables restent dans les faits.",
                "Anomaly journal: repaired observations remain in the facts.",
            ),
        )
        st.caption(
            f"{number(quarantine.get('repairable'), 0, st.session_state.language)} "
            + tr("réparables", "repairable")
            + " · "
            + f"{number(quarantine.get('warning'), 0, st.session_state.language)} "
            + tr("avertissements", "warnings")
        )
        audit = metadata.get("quality", {})
        if audit.get("status") == "passed" and not metadata["stale"]:
            st.success(
                tr("Contrôles qualité réussis", "Quality checks passed")
                + " · "
                + number(audit.get("facts_checked"), 0, st.session_state.language)
                + " "
                + tr("observations vérifiées", "observations checked")
            )
        else:
            st.warning(tr("Statut qualité à vérifier.", "Quality status needs verification."))
        st.caption(
            tr("Dernier audit : ", "Last audit: ")
            + timestamp(audit.get("checked_at"), st.session_state.language)
            + tr(" · Dernière ingestion : ", " · Latest ingestion: ")
            + timestamp(audit.get("latest_ingestion_end"), st.session_state.language)
        )
        runs = pd.DataFrame(metadata["dags"])
        if not runs.empty:
            states = {"success": tr("Succès", "Success"), "running": tr("En cours", "Running")}
            runs["state"] = runs.state.map(lambda value: states.get(value, value))
            runs["end_date"] = runs.end_date.map(
                lambda value: timestamp(value, st.session_state.language)
            )
            runs = runs[["dag_id", "state", "end_date"]].rename(
                columns={
                    "dag_id": "DAG",
                    "state": tr("État", "State"),
                    "end_date": tr("Dernière fin (UTC)", "Latest end (UTC)"),
                }
            )
            st.dataframe(runs, hide_index=True, width="stretch")
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

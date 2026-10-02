"""Tableaux de lecture localisés ; aucune agrégation ni modification des exports."""

import pandas as pd
import streamlit as st

from dashboard.components.formatting import number
from dashboard.components.i18n import tr


def show(frame: pd.DataFrame) -> None:
    """Présenter uniquement les mesures utiles avec unités et chiffres lisibles."""
    fields = {
        "point_id": (tr("Point", "Point"), 0),
        "commune": (tr("Commune", "District"), None),
        "hour": (tr("Heure", "Hour"), 0),
        "is_weekend": (tr("Période", "Period"), None),
        "measurement_count": (tr("Observations", "Observations"), 0),
        "tti_mean": (tr("TTI moyen", "Mean TTI"), 2),
        "tti_p95": ("TTI p95", 2),
        "speed_mean_kmh": (tr("Vitesse (km/h)", "Speed (km/h)"), 2),
        "travel_mean_min": (tr("Temps (min)", "Time (min)"), 2),
    }
    displayed = frame[[key for key in fields if key in frame]].copy()
    for key in displayed:
        if fields[key][1] is not None:
            displayed[key] = displayed[key].map(
                lambda value, digits=fields[key][1]: number(
                    value, digits, st.session_state.language
                )
            )
    if "is_weekend" in displayed:
        displayed["is_weekend"] = displayed.is_weekend.map(
            lambda value: tr("Week-end", "Weekend") if value else tr("Semaine", "Weekdays")
        )
    displayed = displayed.rename(columns={key: value[0] for key, value in fields.items()})
    st.dataframe(displayed, hide_index=True, width="stretch")

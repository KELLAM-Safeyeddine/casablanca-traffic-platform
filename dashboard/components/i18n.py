"""Libellés français/anglais centralisés."""

import streamlit as st

DAYS = {
    "fr": ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
TABS = {
    "fr": [
        "Vue d'ensemble",
        "Carte",
        "Heures de pointe",
        "Semaine vs Week-end",
        "Communes",
        "Données & qualité",
    ],
    "en": ["Overview", "Map", "Peak hours", "Weekdays vs Weekend", "Districts", "Data & quality"],
}


def tr(french: str, english: str) -> str:
    """Choisir un libellé sans modifier la sélection métier."""
    return english if st.session_state.get("language") == "en" else french

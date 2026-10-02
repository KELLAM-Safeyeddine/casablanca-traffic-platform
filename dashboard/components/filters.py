"""Filtres globaux et contrôles URL : catalogue compact, reset et traduction."""

from collections.abc import Callable
from typing import TypeVar

import pandas as pd
import streamlit as st

from dashboard.components.i18n import DAYS, tr
from dashboard.data.filters import Filters, decode, encode

T = TypeVar("T")
FIELDS = ("appearance", "palette", "period", "days", "hours", "all_communes", "selected_communes")


def widget_key(field: str) -> str:
    """Isoler l'identité affichée pour que les labels traduits ne restent pas en cache."""
    return f"filters_{st.session_state.language}_{field}"


def translate_widgets() -> None:
    """Réinitialiser uniquement les identités visuelles lors d'une bascule de langue."""
    if st.session_state.get("sidebar_language") != st.session_state.language:
        for field in FIELDS:
            st.session_state[widget_key(field)] = st.session_state[field]
        st.session_state.sidebar_language = st.session_state.language


def reset() -> None:
    """Réinitialiser le métier, conserver langue/thème/palette."""
    st.session_state.update(
        all_communes=True,
        selected_communes=[],
        days=list(range(1, 8)),
        hours=(0, 23),
        period="all",
        playing=False,
    )
    for field in FIELDS:
        st.session_state[widget_key(field)] = st.session_state[field]


def initialize(catalog: tuple[int, ...]) -> None:
    """Charger le lien une seule fois ; avertir sur un filtre invalide."""
    if st.session_state.get("filters_initialized"):
        return
    query = dict(st.query_params)
    try:
        selected = decode(query, catalog)
    except (ValueError, KeyError):
        selected = Filters(catalog)
        st.session_state["invalid_url"] = True
    st.session_state.update(
        filters_initialized=True,
        all_communes=selected.communes == catalog,
        selected_communes=list(selected.communes),
        days=list(selected.days),
        hours=selected.hours,
        period=selected.period,
        language=query.get("lang") if query.get("lang") in {"fr", "en"} else "fr",
        palette=query.get("palette")
        if query.get("palette") in {"traffic", "cividis"}
        else "traffic",
        appearance=query.get("theme") if query.get("theme") in {"light", "dark"} else "light",
        playing=False,
    )


def sidebar(catalog: pd.DataFrame) -> Filters:
    """Afficher les contrôles et publier une URL contenant seulement des filtres."""
    ids = tuple(sorted(int(v) for v in catalog.commune_id))
    names = dict(zip(catalog.commune_id, catalog.commune, strict=True))
    initialize(ids)
    with st.sidebar:
        st.markdown("### CASABLANCA\n**TRAFFIC OBSERVATORY**")
        st.selectbox(
            "Langue / Language",
            ["fr", "en"],
            key="language",
            format_func=lambda v: "Français" if v == "fr" else "English",
            help="Langue des libellés et des formats / Labels and number formats",
        )
        day_names = DAYS[st.session_state.language]
        translate_widgets()
        palettes = {"traffic": tr("Trafic", "Traffic"), "cividis": "Cividis · accessible"}
        periods = {
            "all": tr("Toute la semaine", "All"),
            "weekday": tr("Semaine", "Weekdays"),
            "weekend": "Week-end",
        }
        # Le sélecteur natif contrôle aussi les canvas et les portails.
        st.session_state.appearance = st.context.theme.type or "light"
        st.caption(
            tr("Thème : menu ⋮ en haut à droite.", "Theme: ⋮ menu at the top right.")
        )
        st.session_state.palette = st.selectbox(
            tr("Palette", "Palette"),
            ["traffic", "cividis"],
            key=widget_key("palette"),
            format_func=palettes.get,
            help=tr("Cividis facilite la lecture daltonienne.", "Cividis is colorblind friendly."),
        )
        st.divider()
        st.session_state.period = st.selectbox(
            tr("Type de période", "Period"),
            ["all", "weekday", "weekend"],
            key=widget_key("period"),
            format_func=periods.get,
            help=tr("Intersection avec les jours sélectionnés.", "Intersect with selected days."),
        )
        st.session_state.days = st.multiselect(
            tr("Jours", "Days"),
            list(range(1, 8)),
            key=widget_key("days"),
            format_func=lambda d: day_names[d - 1],
            placeholder=tr("Choisir les jours", "Choose days"),
            help=tr("Aucun jour = aucune donnée.", "No days means no data."),
        )
        st.session_state.hours = st.slider(
            tr("Plage d'heures", "Hour range"),
            0,
            23,
            key=widget_key("hours"),
            help=tr(
                "Bornes incluses ; heures de la semaine type.",
                "Inclusive bounds within the typical week.",
            ),
        )
        st.session_state.all_communes = st.checkbox(
            tr("Toutes les communes", "All districts"),
            key=widget_key("all_communes"),
            help=tr("Désactiver pour choisir des communes.", "Uncheck to choose districts."),
        )
        if not st.session_state.all_communes:
            st.session_state.selected_communes = st.multiselect(
                tr("Communes", "Districts"),
                ids,
                key=widget_key("selected_communes"),
                format_func=names.get,
                placeholder=tr("Rechercher", "Search"),
                help=tr("Aucune commune = aucune donnée.", "No districts means no data."),
            )
        st.button(tr("Réinitialiser les filtres", "Reset filters"), on_click=reset, width="stretch")
        if st.button(tr("Actualiser les données", "Refresh data"), width="stretch"):
            st.cache_data.clear()
            st.rerun()
        st.caption(
            tr(
                "Une semaine type, pas un flux en temps réel.",
                "A typical week, not a live traffic feed.",
            )
        )
    selected = Filters(
        ids if st.session_state.all_communes else tuple(sorted(st.session_state.selected_communes)),
        tuple(sorted(st.session_state.days)),
        st.session_state.hours,
        st.session_state.period,
    )
    if st.session_state.get("previous_filters") != selected:
        st.session_state.playing = False
    st.session_state.previous_filters = selected
    params = dict(st.query_params)
    params.update(
        encode(selected, ids),
        lang=st.session_state.language,
        palette=st.session_state.palette,
        theme=st.session_state.appearance,
    )
    if params != dict(st.query_params):
        st.query_params.from_dict(params)
    return selected


def local_choice(
    key: str,
    label: str,
    options: list[T],
    help_text: str,
    format_func: Callable[[T], str] = str,
    default: T | None = None,
) -> T:
    """Restaurer puis partager un sélecteur local, même après changement d'onglet."""
    if key not in st.session_state or st.session_state[key] not in options:
        fallback = default if default in options else options[0]
        match = next((v for v in options if str(v) == st.query_params.get(key)), fallback)
        st.session_state[key] = match
    display_key = f"{key}_{st.session_state.language}"
    if display_key not in st.session_state or st.session_state[display_key] not in options:
        st.session_state[display_key] = st.session_state[key]
    result = st.selectbox(label, options, key=display_key, help=help_text, format_func=format_func)
    st.session_state[key] = result
    if st.query_params.get(key) != str(result):
        st.query_params[key] = str(result)
    return result

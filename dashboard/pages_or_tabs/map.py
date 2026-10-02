"""Carte PostGIS animée par fragment Streamlit, avec alternative tabulaire."""

import pydeck as pdk
import streamlit as st

from dashboard.components.charts import labels, rgba
from dashboard.components.filters import local_choice
from dashboard.components.i18n import DAYS, tr
from dashboard.data.filters import Filters
from dashboard.data.queries import fetch


def draw(filters: Filters, day: int, hour: int, mode: str) -> None:
    """Afficher les points ou leur intensité ; préserver les mesures non écrêtées."""
    points = fetch("points", Filters(filters.communes, (day,), (hour, hour)))
    if points.empty:
        st.info(tr("Aucune donnée pour ces filtres.", "No matching data."))
        return
    points = points.copy()
    points["color"] = points.tti_mean.map(rgba)
    points["radius"] = 80 + (points.tti_mean - 1).clip(0, 1) * 170
    for metric in ["tti_mean", "speed_mean_kmh", "travel_mean_min"]:
        points[metric + "_label"] = labels(points[metric])
    layer = pdk.Layer(
        "ScatterplotLayer",
        points,
        get_position="[longitude, latitude]",
        get_fill_color="color",
        get_radius="radius",
        radius_min_pixels=4,
        radius_max_pixels=18,
        pickable=True,
    )
    if mode == "heatmap":
        layer = pdk.Layer(
            "HeatmapLayer",
            points,
            get_position="[longitude, latitude]",
            get_weight="tti_mean",
            radius_pixels=45,
            threshold=0.05,
            color_range=[rgba(v) for v in [1, 1.2, 1.4, 1.6, 1.8, 2]],
        )
    dark = st.session_state.appearance == "dark"
    style = "dark-matter" if dark else "positron"
    deck = pdk.Deck(
        layers=[layer],
        map_style=f"https://basemaps.cartocdn.com/gl/{style}-gl-style/style.json",
        initial_view_state=pdk.ViewState(latitude=33.57, longitude=-7.58, zoom=10.5),
        tooltip={
            "text": "{commune} · #{point_id}\nTTI {tti_mean_label}\n"
            "{speed_mean_kmh_label} km/h · {travel_mean_min_label} min"
        },
    )
    st.pydeck_chart(deck, height=480)
    st.caption(
        tr(
            "Échelle TTI : 1–≥2 · valeurs exactes au survol. Fond Internet/WebGL.",
            "TTI scale: 1–≥2 · exact values on hover. Internet/WebGL basemap.",
        )
    )
    if mode == "heatmap":
        st.caption(
            tr(
                "Intensité lissée ; consulter les valeurs exactes dans le tableau.",
                "Smoothed intensity; exact point values are in the table.",
            )
        )
    st.dataframe(points.drop(columns=["color", "radius"]), hide_index=True, width="stretch")


def render(filters: Filters, catalog: tuple[int, ...]) -> None:
    """Rejouer seulement le fragment carte, une heure par seconde après Lecture."""
    day_names = DAYS[st.session_state.language]
    day = local_choice(
        "map_day",
        tr("Jour de carte", "Map day"),
        list(filters.effective_days),
        tr("Jours admissibles selon les filtres globaux.", "Days allowed by global filters."),
        lambda d: day_names[d - 1],
    )
    mode = local_choice(
        "map_mode",
        tr("Affichage", "Display"),
        ["points", "heatmap"],
        tr("Points exacts ou intensité lissée.", "Exact points or smoothed intensity."),
    )
    st.toggle(
        tr("Lecture / pause", "Play / pause"),
        key="playing",
        help=tr(
            "Avance d'une heure par seconde, puis boucle.",
            "Advance one hour per second, then loop.",
        ),
    )

    @st.fragment(run_every=1 if st.session_state.playing else None)
    def frame() -> None:
        """Ne rerendre que la tranche active, sans sleep ni requête de tous les onglets."""
        start, end = filters.hours
        current = st.session_state.get("map_hour", st.query_params.get("map_hour", str(start)))
        try:
            hour = max(start, min(end, int(current)))
        except (TypeError, ValueError):
            hour = start
        if st.session_state.playing:
            hour = start if hour == end else hour + 1
        st.session_state["map_hour"] = hour
        if start < end:
            hour = st.slider(
                tr("Heure de carte", "Map hour"),
                start,
                end,
                key="map_hour",
                help=tr("Heure locale de la semaine type.", "Typical-week local hour."),
            )
        st.query_params["map_hour"] = str(hour)
        st.markdown(f"**{DAYS[st.session_state.language][day - 1]} · {hour:02d} h**")
        draw(filters, day, hour, mode)

    frame()

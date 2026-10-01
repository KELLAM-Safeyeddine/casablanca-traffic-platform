"""Dashboard de la semaine type de Casablanca : carte, heatmap et comparaisons."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from src.load.dashboard_data import aggregate, point_summary, read_measures, select_measures

DAYS = {1: "Lundi", 2: "Mardi", 3: "Mercredi", 4: "Jeudi", 5: "Vendredi",
        6: "Samedi", 7: "Dimanche"}


@st.cache_data(ttl=60)
def snapshot() -> pd.DataFrame:
    """Rafraîchir les observations au plus tard après une minute."""
    return read_measures()


def map_points(frame: pd.DataFrame) -> None:
    """Afficher les points PostGIS ; couleur stable, infobulle et navigation."""
    points = point_summary(frame)
    deck = pdk.Deck(
        layers=[pdk.Layer("ScatterplotLayer", points, get_position="[longitude, latitude]",
                          get_fill_color="color", get_radius=110, radius_min_pixels=4,
                          radius_max_pixels=12, pickable=True)],
        initial_view_state=pdk.ViewState(latitude=float(points.latitude.mean()),
                                        longitude=float(points.longitude.mean()), zoom=10.5),
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={"html": "<b>{commune}</b><br>Point {point_id}<br>TTI moyen : {tti_label}"},
    )
    st.pydeck_chart(deck, height=440)
    st.caption(f"{len(points)} points d'origine · Bleu : TTI 1, rouge : TTI ≥ 2. "
               "Le TTI exact est disponible au survol.")


def heatmap(frame: pd.DataFrame, hours: tuple[int, int]) -> None:
    """Colorer le TTI moyen de chaque commune à chaque heure sélectionnée."""
    hourly = aggregate(frame, ["commune", "hour"])
    matrix = hourly.pivot(index="commune", columns="hour", values="tti_mean")
    matrix = matrix.reindex(columns=list(range(hours[0], hours[1] + 1)))
    figure = go.Figure(go.Heatmap(
        z=matrix.values, x=[f"{hour:02d}h" for hour in matrix.columns], y=matrix.index,
        colorscale="YlOrRd", colorbar={"title": "TTI"},
        hovertemplate="%{y} · %{x}<br>TTI moyen : %{z:.3f}<extra></extra>",
    ))
    figure.update_layout(height=max(360, len(matrix) * 22 + 100),
                         margin={"l": 0, "r": 0, "t": 10, "b": 0}, xaxis_title="Heure")
    st.plotly_chart(figure, width="stretch")


def comparisons(frame: pd.DataFrame, baseline: pd.DataFrame) -> None:
    """Comparer les périodes et classer les communes sans moyenner des p95."""
    left, right = st.columns(2)
    with left:
        st.subheader("Semaine vs week-end")
        grouped = baseline.assign(period=baseline.day_of_week.map(
            lambda day: "Semaine · lun–ven" if day < 6 else "Week-end · sam–dim"))
        comparison = aggregate(grouped, ["period"])
        figure = px.bar(comparison, x="period", y="tti_mean", color="period",
                        color_discrete_sequence=["#188b91", "#d8743b"],
                        labels={"period": "", "tti_mean": "TTI moyen", "tti_p95": "TTI p95",
                                "measurement_count": "Mesures",
                                "speed_mean_kmh": "Vitesse moyenne (km/h)"},
                        hover_data=["tti_p95", "measurement_count", "speed_mean_kmh"])
        figure.update_layout(showlegend=False, height=390)
        st.plotly_chart(figure, width="stretch")
        st.caption("Même sélection de communes et d'heures ; les deux périodes "
                   "sont conservées, indépendamment du filtre Jours.")
    with right:
        st.subheader("Classement des communes")
        ranking = aggregate(frame, ["commune"]).sort_values("tti_mean", ascending=True)
        figure = px.bar(ranking, x="tti_mean", y="commune", orientation="h",
                        labels={"tti_mean": "TTI moyen", "commune": "", "tti_p95": "TTI p95",
                                "measurement_count": "Mesures",
                                "speed_mean_kmh": "Vitesse moyenne (km/h)"},
                        hover_data=["tti_p95", "measurement_count", "speed_mean_kmh"])
        figure.update_traces(marker_color="#188b91")
        figure.update_layout(height=max(390, len(ranking) * 22 + 80))
        st.plotly_chart(figure, width="stretch")


def main() -> None:
    """Construire une vue filtrable ; expliciter les sélections vides/incomplètes."""
    st.set_page_config(page_title="Casablanca Traffic", page_icon="🚦", layout="wide")
    st.title("Casablanca · Traffic Data Platform")
    st.caption("Une semaine type, 22 communes, 110 points · TTI recalculé depuis "
               "le minimum hebdomadaire de chaque trajet · Source Waze / fichier Excel")
    try:
        data = snapshot()
    except Exception:
        st.error("Le warehouse est indisponible. Vérifier PostgreSQL et le compte dashboard.")
        st.stop()
    if len(data) != 73920:
        st.warning(f"Semaine incomplète : {len(data):,} mesures sur 73 920. "
                   "Terminer une ingestion complète avant d'interpréter les graphiques.")
    with st.sidebar:
        st.header("Explorer le trafic")
        communes = st.multiselect("Communes", sorted(data.commune.unique()),
                                  default=sorted(data.commune.unique()))
        days = st.multiselect("Jours", list(DAYS), default=list(DAYS),
                              format_func=lambda day: DAYS[day])
        hours = st.slider("Heures", 0, 23, (0, 23))
        if st.button("Actualiser les données"):
            snapshot.clear()
            st.rerun()
        st.caption("Semaine type : aucune date d'observation n'est disponible. "
                   "Un TTI de 1,5 signifie un trajet 50 % plus long que sa référence.")
    selected = select_measures(data, communes, days, hours)
    if selected.empty:
        st.info("Aucune mesure pour cette sélection. Sélectionner une commune et un jour.")
        st.stop()
    metrics = st.columns(4)
    metrics[0].metric("Mesures sélectionnées", f"{len(selected):,}".replace(",", " "))
    metrics[1].metric("TTI moyen", f"{selected.tti.mean():.3f}")
    metrics[2].metric("TTI p95", f"{selected.tti.quantile(.95):.3f}")
    metrics[3].metric("Points d'origine", str(selected.point_id.nunique()))
    st.subheader("Carte des points · TTI moyen")
    map_points(selected)
    st.subheader("Congestion par commune et par heure")
    heatmap(selected, hours)
    comparisons(selected, select_measures(data, communes, list(DAYS), hours))
    with st.expander("Données et méthode"):
        ranking = aggregate(selected, ["commune"]).sort_values("tti_mean", ascending=False)
        ranking = ranking.rename(columns={"commune": "Commune", "tti_mean": "TTI moyen",
                                          "tti_p95": "TTI p95", "measurement_count": "Mesures",
                                          "speed_mean_kmh": "Vitesse moyenne (km/h)"})
        st.dataframe(ranking, hide_index=True, width="stretch")
        st.download_button("Télécharger le classement CSV", ranking.to_csv(index=False),
                           "casablanca_classement.csv", "text/csv")
        st.caption("Poids égal par observation ; p95 interpolé depuis les faits. "
                   "La commune est celle du point d'origine. Les moyennes comparent "
                   "cinq jours de semaine et deux jours de week-end.")


if __name__ == "__main__":
    main()

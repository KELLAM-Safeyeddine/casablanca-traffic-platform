# Dictionnaire provisoire — phase 0

Ce document définit le modèle cible du plan. Le mapping exact des colonnes Excel,
les types observés et les règles de nettoyage seront confirmés en phases 2 à 5.

| Objet | Grain / clé | Attributs et unités |
|---|---|---|
| Source Table 0 | Point, 110 attendus | Commune, index, latitude/longitude WGS84 |
| Source Table 1 | Commune, 22 attendues | Population, ménages, densité : unités à confirmer |
| Source Table 2 | Commune | Nombre de stations tram/bus |
| Source Table 3 | Commune | Routes primaires, secondaires, autoroutes |
| Source Table 4 | Commune | Surfaces par usage, commerces : unités à confirmer |
| Source Tables 5–11 | Trajet × jour, 440 par jour attendus | Origine, destination, distance mixte, 24 temps et 24 TTI |
| dim_commune | commune_id | Nom normalisé, zip texte, population, ménages, densité, surfaces, stations, routes |
| dim_point | point_id | commune_id, lat/lon en degrés, geom Point SRID 4326 |
| dim_time | (day_of_week, hour) | Jour ISO 1–7, heure 0–23, is_weekend, période |
| dim_trajectory | trajectory_id | origin_point_id, dest_point_id, distance_km |
| fact_travel_time | (trajectory_id, day_of_week, hour) | travel_time_min, tti sans unité, speed_kmh |
| quarantine | Identifiant de rejet | Charge brute, source/feuille/ligne, motif, horodatage |

Métadonnées RAW prévues : `_ingested_at` UTC, `_source_file`, `_sheet`.
Les identifiants doivent être stables entre deux exécutions.
Les mesures sont une semaine type ; aucune date réelle ne sera inventée.

Marts prévus : `mart_commune_hourly_congestion`, `mart_peak_hours`,
`mart_weekday_vs_weekend`, `mart_commune_features`.

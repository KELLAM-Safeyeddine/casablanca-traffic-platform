# Dictionnaire provisoire — phase 0

Ce document définit le modèle cible du plan. La phase 2 confirme les colonnes et
cardinalités de la source ; les règles seront implémentées en phases 3 à 5.

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

## Mapping confirmé en phase 2

- Table 0 : B Commune, C ZIP code, D Index, E Latitude, F Longitude, G Coordinates.
  Les coordonnées E/F sont des textes numériques. En-tête ligne 12, données 13–122.
- Tables 1–4 : en-tête ligne 10, 22 lignes 11–32. Population et ménages doivent
  accepter les fractions. Density est sans unité confirmée. Table 4 indique des m².
- Trafic : B Commune, C ZIP, D index origine, E coordonnées concaténées (formule),
  F/G latitude/longitude origine, H index destination, I coordonnées concaténées,
  J/K latitude/longitude destination, L distance mixte, M:AJ temps, AK:BH TTI fourni.
- Lundi : en-tête ligne 10, données 11–450. Autres jours : en-tête ligne 12,
  données 13–452. Les 24 heures sont explicitement 0–23 pour chaque métrique.
- Les indices trajets 110–114 correspondent aux points 105–109 de Table 0.
- `dim_trajectory.distance_km` : référence du lundi. Ajouter la distance observée
  à chaque fait pour garder les variations quotidiennes et calculer la vitesse.
- Champs d'audit futurs : temps/distance bruts, indicateurs de conversion,
  TTI fourni et écart, référence de temps libre, feuille, ligne source.
- `density_source` : valeur Density conservée, unité non confirmée.
  `population_density_per_km2` : population / (Region area / 1 000 000), distincte.

Le rapport `docs/data_quality_report.md` contient les preuves et limites de ces règles.

## Journal qualité implémenté en phase 4

`traffic.public.quarantine`, clé primaire `event_id` SHA-256 stable :
`source_sha256`, `source_file`, `sheet`, `excel_row`, `hour` (-1 = ligne entière),
`column_name`, `reason`, `severity` (rejected/repairable/warning), `raw_payload` JSONB,
`first_seen_at`, `last_seen_at` UTC et `last_run_id`.
Le payload garde les valeurs RAW et leur provenance. Les métriques réparables restent
à corriger en phase 5 ; aucune mesure n'est encore chargée dans l'entrepôt.

Marts prévus : `mart_commune_hourly_congestion`, `mart_peak_hours`,
`mart_weekday_vs_weekend`, `mart_commune_features`.

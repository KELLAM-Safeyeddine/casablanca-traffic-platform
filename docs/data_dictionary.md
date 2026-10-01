# Dictionnaire de données livré

Ce document décrit le modèle implémenté et vérifié. Le mapping source, les unités
normalisées, les champs de provenance et les marts sont détaillés ci-dessous.

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

Métadonnées RAW : `_ingested_at` UTC, `_source_file`, `_sheet`, `_source_sha256`,
`_payload_sha256`, `_excel_row`, `_commune_raw` et `_zip_raw` pour les mesures.
Les identifiants sont stables entre deux exécutions.
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
- `dim_trajectory.distance_km` : référence du lundi. La distance observée est
  conservée dans chaque fait pour garder les variations et calculer la vitesse.
- Champs d'audit : temps/distance bruts, indicateurs de conversion,
  TTI fourni et écart, référence de temps libre, feuille, ligne source.
- `density_source` : valeur Density conservée, unité non confirmée.
  `population_density_per_km2` : population / (Region area / 1 000 000), distincte.

Le rapport `docs/data_quality_report.md` contient les preuves et limites de ces règles.

## Journal qualité implémenté en phase 4

`traffic.public.quarantine`, clé primaire `event_id` SHA-256 stable :
`source_sha256`, `source_file`, `sheet`, `excel_row`, `hour` (-1 = ligne entière),
`column_name`, `reason`, `severity` (rejected/repairable/warning), `raw_payload` JSONB,
`first_seen_at`, `last_seen_at` UTC et `last_run_id`.
Le payload garde les valeurs RAW et leur provenance. Les métriques réparables
restent présentes dans les faits après correction.

Marts livrés : `mart_commune_hourly_congestion`, `mart_peak_hours`,
`mart_weekday_vs_weekend`, `mart_commune_features`.

## Modèle implémenté en phase 5

- `public.dim_commune` : commune_id = ZIP numérique, nom, nom_key, zip texte,
  population, households, density_source, population_density_per_km2, tram_stations,
  bus_stations, primary_roads, secondary_roads, highways, surfaces *_area_m2,
  commercial_buildings. Précision des populations/ménages conservée.
- `public.dim_point` : point_id 0–109, commune_id, lat, lon, geom Point SRID 4326
  générée ; longitude X, latitude Y ; index GiST.
- `public.dim_time` : clé (day_of_week, hour), is_weekend, period.
- `public.dim_trajectory` : trajectory_id = origine ×110 + destination +1,
  origin_point_id, dest_point_id, distance_km du lundi, free_flow_reference_min
  figée et reference_source_sha256.
- `staging.travel_time` : clé (source_sha256, trajectory_id, day_of_week, hour),
  travel_time_min, distance_km et les valeurs/indicateurs d'audit ; 73 920 lignes.
- `public.fact_travel_time` : clé (trajectory_id, day_of_week, hour), travel_time_min,
  tti, speed_kmh, distance_observed_km, free_flow_reference_min, tti_provided,
  tti_delta = recalculé − fourni, tti_gap_flag (écart absolu >0,1), source_tti_flag
  (fourni <1 ou >5), travel_time_raw, distance_raw, time_scaled, distance_scaled,
  index_repaired, origin_index_raw, dest_index_raw, source_sha256, source_file,
  sheet, excel_row. 73 920 lignes chargées et vérifiées.

Les tables staging.commune, staging.point et staging.trajectory précèdent leurs
dimensions CORE. Le DDL et les deux transformations SQL sont dans sql/ddl/02–04.

## Marts implémentés en phase 6

| Table public | Clé | Mesures / attributs |
|---|---|---|
| mart_commune_hourly_congestion | commune_id, day_of_week, hour | measurement_count, tti_mean, tti_p95, speed_mean_kmh, tti_gap_count |
| mart_peak_hours | commune_id, day_of_week, hour | tti_mean, tti_p95, measurement_count ; toutes les heures au maximum journalier |
| mart_weekday_vs_weekend | commune_id, is_weekend | day_count, measurement_count, tti_mean, tti_p95, speed_mean_kmh |
| mart_commune_features | commune_id | Tous les attributs dim_commune, measurement_count, tti_mean, tti_p95, speed_mean_kmh, tti_gap_count |

Grains et effectifs observés : 3 696 groupes horaires de 20 faits, 154 pointes,
44 comparaisons (2 400 faits en semaine, 960 en week-end par commune), 22 profils
de 3 360 faits. Les p95 sont calculés directement au grain de chaque mart.
L'heure est celle de la semaine type ; aucune date d'observation n'est ajoutée.
Les valeurs sont remplacées atomiquement après une ingestion, avec CORE complet.

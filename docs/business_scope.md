# Phase 0 — cadrage métier

## Questions

1. Quelles communes sont les plus congestionnées, et à quelles heures ?
2. Comment les jours ouvrés (lundi–vendredi) diffèrent-ils du week-end (samedi–dimanche) ?
3. Quelles associations observe-t-on entre TTI, tram/bus, routes, population et occupation du sol ?

Un trajet est attribué à sa commune d'origine pour les classements et agrégats.
Les mesures ont un poids identique ; aucun volume de véhicules n'est fourni.

## KPI et granularité

| KPI | Définition | Grain de restitution |
|---|---|---|
| TTI moyen | Moyenne des TTI recalculés valides | Commune × jour × heure |
| TTI p95 | Percentile continu 0,95 des TTI valides | Commune × jour × heure |
| Heure de pointe | Heure au TTI moyen maximal ; toutes les égalités conservées | Commune × jour |
| Vitesse | distance_km / (travel_time_min / 60) | Trajet × jour × heure |
| Vitesse moyenne | Moyenne arithmétique des vitesses valides | Commune × jour × heure |

Le temps de référence est le minimum empirique corrigé du trajet sur les
168 créneaux de la source, figé dans dim_trajectory. Ce n'est pas une mesure
indépendante de circulation fluide.
TTI = temps observé / temps de référence du même trajet. Conserver le TTI fourni,
le recalculé et leur écart pour audit. Ne pas traiter les valeurs annoncées comme vérifiées.

## Contrat de qualité cible

- Clé du fait : (trajectory_id, day_of_week, hour).
- Jour ISO : lundi=1, dimanche=7 ; heure locale 0 à 23.
- Aucune ligne invalide supprimée sans trace : quarantine avec source et motif.
- Rechargement d'une partition sans doublon ; preuve par second run.
- Cibles du plan : 22 communes, 110 points, 440 trajets, 73 920 faits.
- Validation de chaque phase avant le commit et avant la phase suivante.

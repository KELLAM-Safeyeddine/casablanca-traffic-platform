# Phase 5 — vérifications du 1 octobre 2026

Commandes locales exécutées avec CasaTraffic\Scripts\python.exe, Python 3.11.
Airflow, PostgreSQL/PostGIS et Metabase restent dans Docker.

```text
-m ruff check .
All checks passed!

-m pytest -q
43 passed in 8.08s

scripts/verify_phase5.py
OK CORE : 22 communes, 110 points, 168 heures, 440 trajets, 73 920 faits
OK panne SQL injectée : rollback STAGING/CORE, contenu intégral conservé
OK quatre runs réels en succès, contenu complet inchangé après relance/rejeu

scripts/verify_phase1.py
4 services healthy ; airflow-init exited 0 ; PostGIS 3.5
Connection casatraffic et endpoints HTTP disponibles
Aucune erreur d'import DAG ; source en lecture seule avec SHA-256 intact
```

Le rapport `phase5_runs.json` garde l'état initial vide, les comptes/empreintes finaux,
les métriques calculées en PostgreSQL et les huit runs Airflow réalisés en deux séries.
Chaque série est full/full/replay tick 0/replay tick 168 ; toutes les tâches sont en succès.
Dernière série, avec prévalidation du TTI CORE et test de rollback :

| Run | Mode | État |
|---|---|---|
| phase5_ba11293b90fc4313a2cbe5b828fe4462 | full | success |
| phase5_e518a19d3d4e4354b144bc322859f3db | full | success |
| phase5_14d596c26bec4f278ab972a5a00113f0 | replay 0 | success |
| phase5_69b375b87d1d48b68e192b5fad48ad93 | replay 168 | success |

Les runs full ont sept tâches load_traffic mappées ; les rejeux en ont une.
Le bootstrap vérifie la source, les références et la référence libre figée avant chargement.
Les empreintes MD5 portent sur les valeurs de toutes les lignes des quatre dimensions,
des faits et de staging.travel_time, indépendamment de leur ordre physique.
Elles restent identiques après chaque relance et après le test de panne.
Il s'agit d'un contrôle de contenu, pas d'un mécanisme cryptographique de sécurité.

Le test de rollback utilise une copie temporaire de 04_partition_to_core.sql avec
SELECT 1/0 ajouté après DELETE/INSERT. La vraie fonction load_partition est exécutée
contre PostgreSQL pour le lundi 00 h. La DivisionByZero attendue entraîne le rollback
de STAGING et CORE ; aucun remplacement partiel n'est commité. Le SQL versionné n'est
pas modifié. Seuls les horodatages de dernière observation du journal peuvent avancer.
Ce test n'est pas présenté comme un run Airflow de production échoué.

Les métriques en base concordent avec le profilage : 42 174 temps corrigés,
66 336 distances converties au grain horaire, 3 360 indices réparés, 34 TTI source <1,
70 810 écarts TTI >0,1, 254 trajets à distance variable ; zéro erreur des formules.
Les 110 géométries sont valides, SRID 4326, X=lon et Y=lat.
Le journal contient toujours 485 événements, avec valeurs brutes et motifs.

Les nouveaux tests couvrent seuils de conversion, portée par version de source,
Unicode, coordonnées ambiguës/inconnues, conservation des heures manquantes,
TTI et vitesse indépendants du TTI source, référence figée absente ou trop grande.
Les données invalides sont journalisées avant leur exclusion explicite par clé.

Les marts, les trois autres DAGs, la CI et le dashboard restent les phases 6–9.
Le modèle gère une seule semaine type ; les journées mappées commitent séparément,
et un run interrompu se reprend par relance idempotente. Nouvelle source/historique :
migration explicite requise, sans réécriture de la référence figée.

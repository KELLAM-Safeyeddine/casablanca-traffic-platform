# Phase 7 — vérifications du 1 octobre 2026

Toutes les commandes Python locales utilisent CasaTraffic\Scripts\python.exe.
Airflow reste installé uniquement dans Docker.

## Exécutions réelles

```text
scripts/verify_phase7.py
bootstrap_dimensions/phase7_bootstrap_df20ff604375462cbaf3b8e500380102: success
ingest_traffic/phase7_04ee5b28ee73436b862f65a605a1abc9: success
data_quality/dataset_triggered__2026-10-01T22:53:41.414497+00:00: success
build_marts/dataset_triggered__2026-10-01T22:53:49.713046+00:00: success
OK chaîne Dataset et empreintes CORE/marts identiques
ingest_traffic/phase7_5093cda5e8a34e539fceb2be8e7d1366: success
data_quality/dataset_triggered__2026-10-01T22:55:06.245643+00:00: success
build_marts/dataset_triggered__2026-10-01T22:55:15.087233+00:00: success
OK chaîne Dataset et empreintes CORE/marts identiques
OK quatre DAGs réussis, deux chaînes automatiques, idempotence prouvée
```

Bootstrap est lancé manuellement via l'API ; seules les ingestions sont ensuite
lancées à la main. Les runs qualité et marts sont créés par les Datasets et ont
run_type=dataset_triggered. L'API datasets/events relie les deux producteurs
aux deux consommateurs pour chacune des chaînes : quatre événements vérifiés.
Les IDs, dates, états des tâches mappées et événements sont dans phase7_runs.json.

Après chacune des deux chaînes : comptes et empreintes md5 du contenu complet
identiques à ceux avant bootstrap. Dimensions 22/110/168/440 ; faits et STAGING
73 920 ; marts 3 696/154/44/22. Les 13 Parquet source et les tranches de rejeu
existantes gardent leurs empreintes SHA-256. Le fichier Excel conserve le SHA-256
4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d.

Chaque audit a validé les 13 RAW, les bornes/unicité du CORE avec pandera,
les cardinalités des cinq tables et les formules TTI/vitesse/référence/écart.
Ses rapports sont conservés sur le volume data/quarantine/reports.
Les anomalies source sont upsertées, sans supprimer les faits ni créer de doublon.

## Intégrité et services

DagBag exécuté dans airflow-scheduler, puis check_cycle pour les quatre DAGs :
aucune erreur d'import, aucun cycle. Assertions réelles : max_active_runs=1
partout, retries=2, retry_exponential_backoff=True et callback sur chaque tâche.
L'API alimentant l'UI expose les quatre DAGs actifs.

scripts/verify_phase1.py : postgres, airflow-webserver, airflow-scheduler et
metabase healthy ; airflow-init exited 0 ; endpoints HTTP disponibles,
PostGIS 3.5 et Connection casatraffic fonctionnels ; source montée en lecture seule.
Le scheduler a été redémarré pour découvrir les nouveaux fichiers sans attendre
l'intervalle de rafraîchissement. Aucune suppression de volume ni réinitialisation.

Les tests supplémentaires bloquent une semaine incomplète, les formules erronées
et les doublons. Les alertes sont testées sur disque temporaire : noms portables,
idempotence et distinction des runs à microsecondes différentes. Le callback est
configuré dans Airflow ; aucune panne de production n'a été provoquée pour ce test.

Le lint a d'abord signalé une ligne de 104 caractères dans verify_phase7.py :
correction du format, puis ruff check . réussi. Aucun échec de DAG observé.
Les warnings de dépendances/compatibilité Airflow déjà documentés en phase 1
restent non bloquants.

```text
CasaTraffic\Scripts\python.exe -m ruff check .
All checks passed!

CasaTraffic\Scripts\python.exe -m pytest -q
51 passed in 7.72s
```

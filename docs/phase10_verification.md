# Phase 10 — documentation et livraison

Validation locale le 1 octobre 2026 UTC. README réécrit pour le système livré,
architecture Mermaid, installation CasaTraffic Python 3.11, lancement et rejeu,
variables/connexions, unités, limites, dictionnaire final et captures réelles.
Les preuves des premières phases restent disponibles avec leur contexte daté.

## Démarrage vierge et idempotence

Commande : `CasaTraffic\Scripts\python.exe scripts/verify_clean_start.py`.
Projet temporaire : `casatraffic-clean-fcaa55fec8db459aa81ed0918cfe02f0`.
Volume PostgreSQL neuf, RAW et quarantine initialement vides ; nouveaux secrets
et ports distincts. Les images Docker validées dans les phases 8 et 9 sont réutilisées.

Résultat réel, code retour 0 :

```text
OK amorçage réel bootstrap_dimensions
OK amorçage réel ingest_traffic
OK semaine complète, quatre DAGs et deux chaînes idempotentes
OK premier démarrage depuis un volume neuf et RAW vides
OK projet de test supprimé ; plateforme originale conservée
```

Deux ingestions complètes terminées en success :
`bootstrap_f7c3bf4d902b40e5a0a14bb4e7529598` et
`bootstrap_0c425038e7e8448fae0e239c0219a173`.
Chaque run publie CORE ; data_quality réussit puis publie quality_passed ;
build_marts est déclenché automatiquement et réussit. Les événements et leurs
created_dagruns sont contrôlés, pas seulement les derniers états de DAG.
[phase10_clean_start.json](phase10_clean_start.json) contient ces liens et les
empreintes identiques après les deux chaînes.

Effectifs : communes 22, points 110, temps 168, trajets 440, faits 73 920,
STAGING mesures 73 920 ; marts 3 696 / 154 / 44 / 22.

Le premier essai a échoué lors d'une connexion API interrompue au démarrage ;
ses ressources ont été retirées. Gestion de ConnectionError ajoutée à l'attente,
puis contrôle entier relancé avec succès. Aucun échec présenté comme une réussite.

## Contrôles finaux sur la plateforme principale

```text
CasaTraffic\Scripts\python.exe -m ruff check .
All checks passed!
CasaTraffic\Scripts\python.exe -m pip check
No broken requirements found.
CasaTraffic\Scripts\python.exe scripts/run_integration_tests.py
57 passed, 3 skipped in 43.34s
```

Les trois skips sont les tests Airflow, exécutés séparément dans Docker.
Construction locale identique au job CI :
`docker build --file Dockerfile.airflow --tag casatraffic-ci:latest .`, puis
`docker run --rm --entrypoint python -v "${PWD}/tests:/opt/airflow/tests:ro" casatraffic-ci:latest -m unittest discover -s /opt/airflow/tests -p test_dag_integrity.py -v`.
Résultat : `Ran 3 tests ... OK` ; imports, cycles, Datasets et mapping validés.
Un essai préalable sur l'ancienne image Compose sans code embarqué avait échoué
avec KeyError ingest_traffic ; reconstruire l'image CI avec le Dockerfile actuel
a résolu ce contrôle, sans modifier les DAGs. Compose utilisait déjà les montages
du code livré, dont les runs sont en succès. .validation/ est exclu du contexte
Docker pour ne pas transmettre les copies locales contenant des secrets.
verify_phase0 confirme Python 3.11.0, toutes les versions dev et la source SHA-256
inchangée. verify_phase1 confirme PostGIS, healthchecks, Connection, montages
source RO et aucune erreur d'import. verify_phase9 confirme 73 920 mesures,
110 points, 528 cellules heatmap, 22 communes, p95 direct, réconciliation SQL
et interdiction d'écriture du rôle dashboard.

Captures UI réelles : screenshots/airflow_dags.jpg (quatre actifs, zéro échec)
et screenshots/airflow_ingestion.jpg (23 runs affichés, tous success ; tâches
et dynamic mapping visibles). Les trois captures dashboard de phase 9 montrent
la carte, la heatmap et les comparaisons. Aucun mockup n'est utilisé.

CI configurée dans .github/workflows/ci.yml ; exécution GitHub non revendiquée
en l'absence de remote. Metabase est healthy, non initialisé ; les quatre vues
requises sont livrées dans Streamlit, autorisé par le plan et la demande.

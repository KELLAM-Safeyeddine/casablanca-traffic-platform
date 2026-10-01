# Phase 8 — vérifications du 1 octobre 2026

Python local : CasaTraffic\Scripts\python.exe, version 3.11. Aucun paquet
installé globalement ; Airflow est testé uniquement dans Docker.

## Résultats réels

```text
CasaTraffic\Scripts\python.exe scripts/run_integration_tests.py
OK PostGIS isolé 3.5 USE_GEOS=1 USE_PROJ=1 USE_STATS=1
53 passed, 3 skipped in 29.46s
OK conteneur de test supprimé ; volumes de la plateforme conservés

docker build --file Dockerfile.airflow --tag casatraffic-ci:latest .
Image construite avec succès (code 0)

docker run --rm --entrypoint python -v "${PWD}/tests:/opt/airflow/tests:ro" casatraffic-ci:latest -m unittest discover -s /opt/airflow/tests -p test_dag_integrity.py -v
test_dataset_dependencies ... ok
test_imports_and_cycles ... ok
test_mapping_and_failure_policy ... ok
Ran 3 tests in 7.393s
OK

docker run --rm --entrypoint python casatraffic-ci:latest -m pip check
No broken requirements found.

CasaTraffic\Scripts\python.exe -m pre_commit install
pre-commit installed at .git\hooks\pre-commit

CasaTraffic\Scripts\python.exe -m pre_commit run --all-files
Ruff (CasaTraffic) ... Passed
pytest (CasaTraffic) ... Passed

CasaTraffic\Scripts\python.exe -m ruff check .
All checks passed!

CasaTraffic\Scripts\python.exe -m pip check
No broken requirements found.

CasaTraffic\Scripts\python.exe -m pytest -q
51 passed, 5 skipped in 7.64s
```

Les trois skips pendant les 53 tests correspondent exactement aux trois tests
Airflow ensuite exécutés et réussis dans Docker. Pytest sans le lanceur PostGIS
ignore en plus les deux tests d'intégration, explicitement signalés, et exécute
les 51 tests autonomes. Aucune dépendance pytest ajoutée à l'image de production.

## Scénarios couverts

PostGIS démarre dans un conteneur neuf casatraffic-test-<uuid>, lié à localhost
sur un port aléatoire. Secret généré en mémoire, fichier d'environnement temporaire
supprimé après lancement, DSN transmis uniquement au processus pytest.
Les tests refusent un nom de base différent de casatraffic_test_<uuid>.
Dimensions complètes depuis la source versionnée, mais seulement une tranche
horaire de 440 trajets chargée à chaque scénario ; Parquet dans tmp_path pytest.

1. Même partition chargée deux fois : comptes et empreintes du contenu complet
   STAGING/CORE identiques.
2. Temps négatif injecté dans une copie RAW temporaire : 439 mesures admissibles,
   un rejet ; payload brut -1 retrouvé dans quarantine avec sa raison.
   Restauration depuis le RAW original : contenu métier initial rétabli.
3. Division SQL par zéro après remplacement dans une copie du SQL : exception
   attendue et rollback réel de STAGING et CORE, empreintes conservées.
4. Source Excel et Parquet original gardent leurs SHA-256.

Le nettoyage finally supprime uniquement le conteneur nommé par ce lanceur et
ses volumes anonymes avec docker rm --force --volumes. Aucun service, volume
ni table de la plateforme utilisé par ces scénarios. Les quatre services
docker compose sont restés healthy ; aucun conteneur casatraffic-test actif après test.

## Corrections observées

Ruff a signalé une ligne de 101 caractères dans le lanceur : raccourcie, puis
lint vert. Le premier test de Datasets utilisait DAG.schedule : AttributeError
sur Airflow 2.11.2. Inspection de l'image installée, puis assertion sur
DatasetTriggeredTimetable.dataset_condition.objects ; trois tests verts.
Les avertissements de compatibilité déjà présents dans Airflow sont non bloquants.
BuildKit n'a pas capturé les métadonnées Git dans la session Windows élevée
(propriétaire sandbox différent) ; l'image est construite, dépendances et tests verts.

## CI et limites de la vérification

.github/workflows/ci.yml : deux jobs Ubuntu 24.04, sur push/pull_request et
workflow_dispatch, permissions contents:read. Job quality crée CasaTraffic avec
Python 3.11, installe requirements.txt, lance Ruff, pytest avec PostGIS isolé et
pre-commit. Job airflow-image construit Dockerfile.airflow, puis les trois tests
unittest et pip check. Aucun déploiement, push d'image ou secret local requis.
Les YAML CI et pre-commit ont été parsés avec succès.

Hooks local/system avec CasaTraffic en tête du PATH, sans installation parallèle
par pre-commit. Pour la session Windows de vérification, safe.directory est limité
au dépôt via variables GIT_CONFIG_* du processus : aucune modification globale.

git remote -v ne retourne aucun remote. Workflow configuré et commandes exécutées
localement ; aucune exécution GitHub Actions hébergée revendiquée. Le premier push
dans un dépôt GitHub déclenchera les jobs. La restitution reste la phase 9.

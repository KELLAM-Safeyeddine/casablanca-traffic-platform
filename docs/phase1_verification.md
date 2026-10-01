# Phase 1 — vérifications du 1 octobre 2026

## Construction et démarrage réels

```text
docker compose config --quiet                code 0
docker compose up -d --build                 code 0 (image construite, services démarrés)
docker compose up -d --wait --wait-timeout 360 code 0 (second lancement, volume conservé)
```

État constaté par `docker compose ps --all` :

| Service | État | Accès local |
|---|---|---|
| postgres | Up (healthy) | 127.0.0.1:5432 |
| airflow-webserver | Up (healthy) | 127.0.0.1:8080 |
| airflow-scheduler | Up (healthy) | Interne Docker |
| airflow-init | Exited (0) | Initialisation terminée |
| metabase | Up (healthy) | 127.0.0.1:3000 |

Le second démarrage conserve les bases et le compte Airflow ; ce contrôle ne prouve
pas encore l'idempotence des faits métier, qui ne sont pas chargés à cette phase.

## Contrôle via le venv CasaTraffic

```text
CasaTraffic\Scripts\python.exe -m pip check
No broken requirements found.

CasaTraffic\Scripts\python.exe -m pytest -q
4 passed in 0.08s

CasaTraffic\Scripts\python.exe -m ruff check .
All checks passed!

CasaTraffic\Scripts\python.exe scripts/verify_phase1.py
OK postgres healthy
OK airflow-webserver healthy
OK airflow-scheduler healthy
OK metabase healthy
OK airflow-init exited 0
OK http://127.0.0.1:8080/health
OK http://127.0.0.1:3000/api/health
OK PostGIS 3.5 USE_GEOS=1 USE_PROJ=1 USE_STATS=1
OK connexion métadonnées Airflow et aucune erreur d'import DAG
OK Python 3.11, bibliothèques runtime et Connection casatraffic
OK source montée en lecture seule
OK SHA-256 source dans Docker
Phase 1 validée ; DAGs métier à implémenter en phases 3 à 7.
```

`airflow dags list-import-errors --output json` renvoie `[]` après des logs.
Le premier contrôle a échoué avec `JSONDecodeError` en tentant de lire l'horodatage
des logs comme du JSON. Le parseur a été corrigé, quatre tests de régression ajoutés,
puis le contrôle réel relancé avec succès. Il n'existe pas encore de DAG métier.

La CLI Airflow émet des avertissements non bloquants : `RemovedInAirflow3Warning`
et `RequestsDependencyWarning` sur chardet/urllib3 dans l'image officielle contrainte.
L'installation Docker et `pip check` passent ; la Connection et les endpoints ont été
vérifiés réellement. Ces avertissements ne sont pas des erreurs d'import DAG.

Bases constatées via SQL : `airflow`, `metabase`, `traffic`.
Secrets présents uniquement dans .env ignoré ; aucune valeur incluse dans ce rapport.

## Images effectivement téléchargées

| Image | Digest |
|---|---|
| apache/airflow:2.11.2-python3.11 (base du build) | sha256:aac8468234dfa802c5ac4d6318bbf3b620793b55569ac230f584dc3c1f0ca49d |
| postgis/postgis:16-3.5 | sha256:94146ac37bc61e2322f88016056c5920729cb8c64c8542ed590af8fc2abdac07 |
| metabase/metabase:v0.59.31.x | sha256:c6b149c19baef163f14e023c373d57ad7e52dde2ee9770450f23243240e2169f |

Les tags de maintenance peuvent évoluer ; ces digests consignent les images de cette exécution.
Metabase est au stade d'installation initiale. Dashboard, DAGs, CI et modèle métier
restent à réaliser dans l'ordre du plan.

# Décisions techniques

## D001 — périmètre de cette livraison

Exécuter les phases 0 et 1 demandées avant de commencer le profilage de phase 2.
Les objectifs du plan ne sont pas des résultats constatés.

## D002 — source et noms

Copier le classeur fourni sous le nom ASCII demandé, sans modifier son contenu.
Enregistrer son SHA-256 et vérifier l'égalité avec l'original.
Le plan source est conservé intégralement dans `docs/project_plan.md`.

## D003 — Python et dépendances

Le venv `CasaTraffic` utilise Python 3.11.0 installé par l'utilisateur.
Les bibliothèques communes au venv et à Docker auront les mêmes versions.
SQLAlchemy 1.4.54 est retenu pour la compatibilité avec Airflow 2.11.2.
Les outils locaux (pytest, ruff, pre-commit, Jupyter) restent dans le venv.

## D004 — métriques

Agréger par commune d'origine, sans pondération par véhicules (absente de la source).
Utiliser les jours ISO et le calendrier local Africa/Casablanca, sans date réelle inventée.
Choisir le temps de référence TTI après observation des données.

## D005 — Airflow Docker

Airflow 2.11.2, image Python 3.11, pour conserver le service webserver demandé.
LocalExecutor suffit au volume prévu : pas de Redis/worker et parallélisme limité à 4.
Installer `requirements-airflow.txt` dans l'image, conformément à la séparation
explicite demandée entre dev et runtime, plutôt que les outils Jupyter/dev du venv.
Réinstaller Airflow avec sa version exacte et les contraintes officielles 3.11.
Référence : https://airflow.apache.org/docs/apache-airflow/2.11.2/howto/docker-compose/

## D006 — bases et persistance

Un conteneur PostgreSQL 16/PostGIS 3.5 avec trois bases et rôles distincts :
`airflow` (métadonnées), `traffic` (entrepôt), `metabase` (configuration BI).
Le volume nommé `postgres_data` conserve les trois bases. Le SQL d'initialisation
ne s'exécute que sur un volume neuf ; les redémarrages n'écrasent pas les données.
Les migrations métier seront ajoutées en phase 5.

## D007 — secrets et réseau local

Secrets aléatoires générés par `scripts/init_env.py`, jamais affichés ni versionnés.
Le script refuse d'écraser `.env` afin de préserver les clés et mots de passe existants.
Les mots de passe générés sont hexadécimaux et compatibles avec les URI de connexion.
La Connection Airflow `casatraffic` est injectée via `AIRFLOW_CONN_CASATRAFFIC`.
Les ports sont liés uniquement à 127.0.0.1. Le classeur est monté en lecture seule.
Changer un secret dans .env ne change pas automatiquement les rôles d'un volume existant.

## D008 — Metabase

Metabase Open Source, image de la release `v0.59.31.x`, base applicative PostgreSQL
plutôt que fichier H2. Le dashboard et son assistant de configuration sont la phase 9.
Les digests réellement téléchargés seront consignés dans la vérification de phase 1.
Références : https://github.com/metabase/metabase/releases/tag/v0.59.31
et https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker

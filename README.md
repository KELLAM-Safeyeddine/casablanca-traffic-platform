# Casablanca Traffic Data Platform

Plateforme de données de trafic de Casablanca : source Excel immuable, Parquet,
validation pandera, entrepôt PostgreSQL/PostGIS et restitution Metabase.
Le plan de référence complet est dans [docs/project_plan.md](docs/project_plan.md).

## État du projet

Phase 0 validée : cadrage, structure, source et environnement de développement.
Phase 1 validée : infrastructure Docker démarrée et contrôlée.
Preuves : `docs/phase0_verification.md` et `docs/phase1_verification.md`.
Phase 2 validée : les 13 feuilles sont profilées, le notebook est exécuté et les règles
de nettoyage sont documentées dans `docs/data_quality_report.md`.
Les phases 3 à 10 restent à réaliser.
Aucune mesure métier n'est encore chargée ; les cardinalités du plan sont des objectifs.

## Architecture cible

```mermaid
flowchart LR
    Excel[Excel immuable] --> Airflow[Airflow dans Docker]
    Replay[Simulateur horaire - phase 3] --> Airflow
    Airflow --> Raw[RAW Parquet]
    Raw --> Validation[pandera et quarantine]
    Validation --> Staging[STAGING PostgreSQL]
    Staging --> Core[CORE PostGIS]
    Core --> Marts[Marts SQL]
    Marts --> Metabase[Metabase]
```

## Développement local (Windows PowerShell)

Python **3.11** et Docker Desktop avec moteur Linux sont obligatoires.
Toutes les commandes Python utilisent explicitement le venv `CasaTraffic`.

```powershell
cd casablanca-traffic-platform
py -3.11 -m venv CasaTraffic
.\CasaTraffic\Scripts\python.exe --version
.\CasaTraffic\Scripts\python.exe -m pip install -r requirements.txt
.\CasaTraffic\Scripts\python.exe -m pip check
.\CasaTraffic\Scripts\python.exe scripts/verify_phase0.py
.\CasaTraffic\Scripts\python.exe -m ruff check .
.\CasaTraffic\Scripts\python.exe -m pytest -q
```

Linux : créer avec `python3.11 -m venv CasaTraffic` et remplacer l'exécutable
par `CasaTraffic/bin/python`. Airflow est installé exclusivement dans l'image Docker.

## Lancement Docker

```powershell
.\CasaTraffic\Scripts\python.exe scripts/init_env.py
docker compose config --quiet
docker compose up -d --build
docker compose ps --all
.\CasaTraffic\Scripts\python.exe scripts/verify_phase1.py
```

`init_env.py` crée .env avec des secrets aléatoires. S'il existe déjà, conserver
le fichier : ne pas relancer la génération. `.env.example` décrit les variables.
Airflow : http://localhost:8080 (identifiants `AIRFLOW_ADMIN_USERNAME` et
`AIRFLOW_ADMIN_PASSWORD` dans .env). Metabase : http://localhost:3000.
PostgreSQL : localhost:5432 ; base `traffic`, rôle `traffic`, mot de passe
`TRAFFIC_DB_PASSWORD` de .env. Les ports sont configurables et liés à 127.0.0.1.

La configuration suit [la documentation Docker Airflow 2.11.2](https://airflow.apache.org/docs/apache-airflow/2.11.2/howto/docker-compose/)
avec LocalExecutor. Metabase utilise [une base applicative PostgreSQL](https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker).
Prévoir au moins 4 Go de mémoire Docker, idéalement 8 Go.

`airflow-init` se termine avec le code 0 après migration et création du compte.
Les quatre services permanents doivent être healthy. Les dossiers DAGs sont vides
à la phase 1 : les DAGs métier seront ajoutés en phases 3 à 7.
Metabase démarre sur l'assistant initial ; les visualisations seront configurées en phase 9.

```powershell
# Arrêt en conservant les données
docker compose down
# Redémarrage avec les mêmes données et secrets
docker compose up -d
# Diagnostics
docker compose logs --tail 100 airflow-scheduler airflow-webserver metabase
```

Le volume `postgres_data` conserve les bases. Ne pas utiliser `down --volumes`
pour un simple redémarrage. Le SQL initial ne s'exécute que sur un volume vide.
Pour un autre poste neuf : recréer CasaTraffic, installer les requirements, fournir
la source identique et générer un nouveau .env, puis exécuter les commandes de lancement.

## Données et objectifs

Source : `data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx`.
Ne jamais enregistrer de modification dans ce classeur.
SHA-256 : `4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d`.

Objectifs à vérifier après profilage et chargement : 22 communes, 110 points,
440 trajets et 73 920 mesures (7 jours × 24 heures × 440 trajets).
La semaine est une semaine type, sans date d'observation.
Le dictionnaire provisoire est dans `docs/data_dictionary.md` ; les KPI dans
`docs/business_scope.md` ; les décisions dans `docs/decisions.md`.

## Reproduire le profilage (phase 2)

```powershell
.\CasaTraffic\Scripts\python.exe scripts/profile_workbook.py
.\CasaTraffic\Scripts\python.exe -m ipykernel install --prefix .\CasaTraffic --name casatraffic --display-name "CasaTraffic (Python 3.11)"
.\CasaTraffic\Scripts\python.exe scripts/verify_phase2.py
.\CasaTraffic\Scripts\python.exe -m jupyter lab notebooks/02_source_profiling.ipynb
```

Sélectionner `CasaTraffic (Python 3.11)` dans Jupyter. Le vérificateur exécute les
sept cellules de code avec ce kernel, vérifie la source et conserve les sorties.
Les 73 920 diagnostics Parquet sont dans `docs/profiling/` : ce sont des résultats
exploratoires avec valeurs brutes et candidates, pas la couche RAW de production.

## Limites connues et suite

Le profilage constate 2 764 distances en mètres, 42 174 temps ayant perdu leur
séparateur décimal, cinq indices décalés et 254 trajets dont la distance varie.
La suite de maxima TTI 5, 6, …, 23 annoncée dans le plan n'est pas présente dans cette source.
Le simulateur ne représentera pas une collecte réelle. Les relations entre variables
urbaines et congestion seront descriptives et ne prouveront pas de causalité.
Les DAGs, marts, tests métier, CI et dashboard seront implémentés à leurs phases respectives.
Les 11 tests présents contrôlent le parseur Airflow et les risques de lecture de la source.

# Projet : Casablanca Traffic Data Platform

Pipeline ELT complet (ingestion → qualité → modélisation → analytique), orchestré avec **Airflow**, packagé avec **Docker**, codé en **Python**.

---

## 1. Ce que contient le dataset

| Feuille | Contenu | Taille |
|---|---|---|
| Table 0 | Coordonnées GPS : 5 points par commune, soit 110 points pour 22 communes | 110 lignes |
| Table 1 | Population, ménages, densité par commune | ~22 lignes |
| Table 2 | Stations de tram et de bus par commune | ~22 lignes |
| Table 3 | Routes primaires, secondaires, autoroutes par commune | ~22 lignes |
| Table 4 | Occupation du sol (surfaces parking, industrielle, parcs, résidentielle, universitaire, nombre de commerces) | ~22 lignes |
| Tables 5 à 11 | Un onglet par jour (lundi → dimanche) : 440 trajets origine → destination, distance, temps de trajet pour chacune des 24 h (source Waze) et **TTI** (Travel Time Index) pour chaque heure | 440 × 24 × 7 |

Le fait central compte environ **73 920 mesures** (440 trajets × 24 h × 7 jours).

### Problèmes de qualité repérés (à traiter dans le projet)

- **En-têtes sur 3 niveaux** avec cellules fusionnées, et nom de commune renseigné uniquement sur la première ligne du groupe (forward-fill nécessaire).
- **Unités de distance mélangées** dans la colonne « Distance (Km) » : des valeurs comme `9954` (mètres) et `1.27` (km) coexistent.
- **Valeurs TTI suspectes** : dans les colonnes TTI, le maximum de chaque heure suit la suite 5, 6, 7… 23, ce qui ressemble à une erreur de saisie ou de formule. À investiguer.
- **Format « large »** : 24 colonnes d'heures par métrique, à dépivoter en format long.
- Fautes dans les descriptions (« Thurday », « Satuday ») et noms d'onglets tronqués : les clés de jointure sont à normaliser.
- Pas de colonne date : uniquement le jour de la semaine. Il faut modéliser une « semaine type ».

> **Remarque :** ce volume est petit (quelques dizaines de milliers de lignes). Spark ou Kafka seraient du sur-dimensionnement. La valeur du projet réside dans la **qualité de l'architecture, l'idempotence, les tests et l'orchestration**.

---

## 2. Architecture cible

```
 Excel (source)            Simulateur "Waze-like" (Python)
      │                              │ (rejoue les données heure par heure)
      ▼                              ▼
┌──────────────────────────────────────────────┐
│  AIRFLOW (orchestration, dans Docker)        │
└──────────────────────────────────────────────┘
      │ extract
      ▼
 RAW  (Parquet, data lake local ou MinIO)   ← copie brute, immuable
      │ validate (pandera)
      ▼
 STAGING (PostgreSQL)                        ← nettoyé, typé, unités normalisées
      │ transform (SQL)
      ▼
 CORE / WAREHOUSE (PostgreSQL + PostGIS)     ← modèle en étoile
      │
      ▼
 MARTS (agrégats prêts pour l'analyse)  ──►  Metabase / Streamlit (dashboard)
                                        ──►  Dataset ML (prédiction du TTI)
```

### Stack technologique

| Besoin | Outil | Justification |
|---|---|---|
| Langage | **Python 3.11** (pandas, pyarrow, SQLAlchemy) | imposé |
| Orchestration | **Apache Airflow** (TaskFlow API) | imposé |
| Conteneurisation | **Docker + docker-compose** | imposé |
| Entrepôt | **PostgreSQL + PostGIS** | gratuit, SQL standard, géospatial |
| Stockage brut | **Parquet** (dossier monté, ou MinIO en option) | format colonnaire standard |
| Qualité des données | **pandera** (Python) | plus léger que Great Expectations |
| Tests | **pytest** | tests unitaires et d'intégrité des DAG |
| Qualité du code | **ruff + pre-commit** | standard industrie |
| CI | **GitHub Actions** | lint + tests à chaque push |
| Visualisation | **Metabase** (conteneur) ou **Streamlit** | dashboard final |

dbt, Spark et Kafka sont volontairement évités pour rester sur Python / Airflow / Docker. Les transformations se font en SQL versionné, exécuté depuis Airflow.

---

## 3. Plan de A à Z

### Phase 0 : Cadrage (1-2 jours)
- Définir les **questions métier** :
  - Quelles communes sont les plus congestionnées, et à quelles heures ?
  - La semaine et le week-end diffèrent-ils ?
  - Quel est l'impact du tram, des routes et de l'occupation du sol sur le TTI ?
- Définir les KPI : TTI moyen, TTI p95, heure de pointe par commune, vitesse moyenne (distance / temps).
- Créer le repo Git, le README initial et le dossier `docs/` pour le dictionnaire de données.

### Phase 1 : Environnement Docker (2 jours)
- `docker-compose.yml` avec : `postgres` (+PostGIS), `airflow-webserver`, `airflow-scheduler`, `airflow-init`, `metabase`, et optionnellement `minio`.
- Fichier `.env` pour les secrets, volumes pour persister les données.
- `Dockerfile` custom pour Airflow qui installe `requirements.txt`.
- **Livrable :** `docker compose up` démarre toute la plateforme.

### Phase 2 : Profilage et exploration (2 jours)
- Notebook Jupyter pour profiler chaque feuille (valeurs manquantes, outliers, unités).
- Documenter les anomalies dans `docs/data_quality_report.md`.
- Décider des règles de nettoyage :
  - distance > 100 → interpréter comme des mètres, diviser par 1000 ;
  - recalculer le TTI à partir du temps de trajet et d'un temps de référence en circulation fluide, puis comparer au TTI fourni ;
  - signaler les TTI aberrants.

### Phase 3 : Ingestion, couche RAW (3 jours)
- Module Python `extract/excel_reader.py` :
  - lit les 13 feuilles, gère les en-têtes multi-niveaux et le forward-fill des communes ;
  - écrit un Parquet par table dans `data/raw/` avec métadonnées (`_ingested_at`, `_source_file`, `_sheet`).
- Les 7 feuilles de jours sont traitées en parallèle via le **dynamic task mapping** d'Airflow.
- **Simulateur de flux (bonus fort) :** un script qui « rejoue » les données heure par heure. Un DAG planifié toutes les heures ingère la tranche horaire suivante, comme si l'API Waze répondait en temps réel.

### Phase 4 : Qualité des données (2 jours)
- Schémas **pandera** pour chaque table :
  - types, bornes (TTI ≥ 1, temps > 0, latitude/longitude dans Casablanca) ;
  - unicité (commune, point, trajet) ;
  - cohérence référentielle (tous les `origin_index` existent dans la table des coordonnées).
- Les lignes invalides vont dans une table `quarantine`, jamais supprimées silencieusement.
- Le DAG échoue ou alerte si le taux d'erreur dépasse un seuil.

### Phase 5 : Transformation, couches STAGING → CORE (3-4 jours)
- Dépivoter les colonnes 0-23 h en format long.
- Normaliser les unités et les noms de communes (clé de jointure propre).
- Modèle en étoile :

| Table | Rôle | Colonnes clés |
|---|---|---|
| `dim_commune` | attributs de la commune | commune_id, nom, zip, population, ménages, densité, surfaces, nb stations tram/bus, nb routes par type |
| `dim_point` | les 110 points | point_id, commune_id, lat, lon, `geom` (PostGIS) |
| `dim_time` | jour × heure | day_of_week, hour, is_weekend, période (pointe matin/soir, creuse, nuit) |
| `dim_trajectory` | les 440 trajets | trajectory_id, origin_point_id, dest_point_id, distance_km |
| `fact_travel_time` | 73 920 lignes | trajectory_id, day_of_week, hour, travel_time_min, tti, speed_kmh |

- Chargement **idempotent** : relancer un DAG ne crée jamais de doublons (`INSERT … ON CONFLICT` ou delete + insert par partition).

### Phase 6 : Data marts (2 jours)
- `mart_commune_hourly_congestion` : TTI moyen et p95 par commune, jour et heure.
- `mart_peak_hours` : heures de pointe par commune.
- `mart_weekday_vs_weekend`.
- `mart_commune_features` : une ligne par commune avec TTI moyen et variables explicatives (population, tram, routes, occupation du sol), prêt pour l'analyse ou le ML.

### Phase 7 : Orchestration Airflow (2 jours)
Quatre DAGs :

1. `dag_bootstrap_dimensions` (manuel) : tables 0 à 4 → dimensions.
2. `dag_ingest_traffic` (hebdo ou rejoué heure par heure) : tables 5 à 11 → raw → staging → fact.
3. `dag_data_quality` : contrôles pandera et rapport.
4. `dag_build_marts` : déclenché après le DAG d'ingestion (Dataset ou sensor).

Bonnes pratiques : retries avec backoff, alertes en cas d'échec, tâches idempotentes, `max_active_runs=1`, paramètres via Variables/Connections et non en dur.

### Phase 8 : Tests et CI/CD (2 jours)
- `pytest` : tests unitaires des fonctions de nettoyage (conversion d'unités, dépivotage), test d'intégrité des DAG (pas d'erreur d'import, pas de cycles), test d'intégration sur un mini-échantillon.
- `ruff` + `pre-commit`.
- GitHub Actions : lint, tests, build de l'image Docker à chaque push.

### Phase 9 : Restitution (2-3 jours)
- Dashboard Metabase (ou Streamlit) :
  - carte des 110 points colorés par TTI (PostGIS) ;
  - heatmap commune × heure ;
  - comparaison semaine / week-end ;
  - classement des communes les plus congestionnées.
- Analyse bonus : corrélation entre congestion et variables urbaines (tram, densité, routes), ou petit modèle de prédiction du TTI (scikit-learn) orchestré dans un DAG.

### Phase 10 : Documentation et portfolio (1-2 jours)
- README avec schéma d'architecture, instructions `docker compose up`, captures du dashboard et des DAGs.
- Dictionnaire de données, choix techniques justifiés, limites connues.

---

## 4. Structure du dépôt

```
casablanca-traffic-platform/
├── docker-compose.yml
├── Dockerfile.airflow
├── .env.example
├── dags/
│   ├── dag_bootstrap_dimensions.py
│   ├── dag_ingest_traffic.py
│   ├── dag_data_quality.py
│   └── dag_build_marts.py
├── src/
│   ├── extract/        # lecture Excel, simulateur
│   ├── transform/      # nettoyage, dépivotage
│   ├── validate/       # schémas pandera
│   └── load/           # écriture Postgres idempotente
├── sql/
│   ├── ddl/            # création des schémas et tables
│   └── marts/          # requêtes des data marts
├── tests/
├── notebooks/          # profilage exploratoire
├── data/{raw,quarantine}/
├── docs/
└── .github/workflows/ci.yml
```

---

## 5. Squelette d'un DAG

```python
from airflow.decorators import dag, task
from datetime import datetime

DAYS = ["monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday"]

@dag(schedule="@weekly", start_date=datetime(2026, 1, 1),
     catchup=False, max_active_runs=1,
     default_args={"retries": 2})
def ingest_traffic():

    @task
    def extract(day: str) -> str:
        ...  # lit la feuille Excel -> écrit data/raw/traffic_{day}.parquet
        return f"data/raw/traffic_{day}.parquet"

    @task
    def validate(path: str) -> str:
        ...  # pandera -> quarantine pour les lignes invalides
        return path

    @task
    def load(path: str):
        ...  # unpivot + upsert idempotent dans fact_travel_time

    load.expand(path=validate.expand(path=extract.expand(day=DAYS)))

ingest_traffic()
```

---

## 6. Planning indicatif

| Semaine | Phases |
|---|---|
| 1 | 0, 1, 2 (cadrage, Docker, profilage) |
| 2 | 3, 4 (ingestion, qualité) |
| 3 | 5, 6 (modélisation, marts) |
| 4 | 7, 8 (Airflow complet, tests, CI) |
| 5 | 9, 10 (dashboard, documentation) |

---

## 7. Extensions possibles

- Remplacer le simulateur par un vrai appel à une API de trafic.
- Ajouter **MinIO** (compatible S3) comme data lake.
- Ajouter **Kafka** pour un vrai flux temps réel.
- Monitoring avec Prometheus + Grafana.
- Détection d'anomalies sur le TTI avec alertes Airflow.

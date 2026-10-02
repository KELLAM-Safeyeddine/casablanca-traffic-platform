# Étape 4 — déploiement Docker vérifié

Vérifications réalisées le 2 octobre 2026. `docker compose up -d --build`
a construit les images et démarré les six services, tous healthy : PostgreSQL,
Airflow webserver/scheduler, Metabase, dashboard et dashboard-status.
Metabase conserve son port 3000 ; Streamlit répond sur http://localhost:8501.

## Isolation des accès

`dashboard/Dockerfile` utilise Python 3.11 et le compte Linux non privilégié
dashboard (UID 10001). Son répertoire de travail charge la configuration
`dashboard/.streamlit/config.toml`. Les dépendances directes sont épinglées dans
`requirements-dashboard.txt` ; `pip check` passe pendant la construction.

`sql/ddl/05_dashboard_reader.sql`, appliqué par `scripts/init_dashboard.py`,
accorde SELECT sur les quatre dimensions/faits nécessaires et les quatre marts.
Le rôle `traffic_dashboard` a `default_transaction_read_only=on`.
La connexion applicative impose aussi une transaction en lecture seule,
un timeout SQL de 5 secondes et un pool de 1 à 8 connexions.
Le contrôle réel refuse un UPDATE avec WHERE false (aucune ligne modifiable)
et vérifie l'absence de droit SELECT sur quarantine. Les secrets viennent de `.env`.
La création initiale du rôle reste dans le bootstrap SQL existant.

Le collecteur `dashboard-status` lit l'API interne Airflow et quarantine dans une
transaction de lecture seule, puis publie atomiquement un JSON sans secret.
Le dashboard monte ce répertoire en lecture seule ; il ne possède ni les
credentials opérationnels du collecteur, ni un accès SQL à quarantine/Airflow.
La collecte a lieu toutes les 60 secondes par défaut. Un rapport absent,
incohérent ou antérieur à l'ingestion ne produit pas un succès qualité.

## Résultats observés

`scripts/verify_dashboard_deployment.py` : endpoint Streamlit healthy,
110 points, 22 communes, export de 73 920 faits, écriture refusée.
Les huit agrégations SQL retournent les résultats attendus ; les requêtes
mesurées prennent 0,009 à 0,109 seconde, l'export 0,267 seconde.
Ces durées SQL ne prouvent pas encore le délai complet d'une interaction UI.
Le JSON de preuve est `docs/dashboard_deployment.json`.

La collecte retrouve les quatre DAGs en succès, 485 événements quarantine
(314 réparables, 171 avertissements) et un audit passed sur 73 920 faits.
Les dates du JSON sont des dates de traitement UTC, pas des observations terrain.

- pytest local CasaTraffic : **80 passed, 6 skipped** ; sauts attendus Docker/SQL.
- pytest avec PostgreSQL/PostGIS isolé : **83 passed, 3 skipped** (DAGs Docker).
- trois tests d'intégrité des DAGs dans l'image Airflow : **OK**.
- ruff check : **All checks passed**.

Le test DAG affiche des avertissements de dépréciation Airflow/pyparsing et un
RequestsDependencyWarning transitif ; aucune erreur d'import ni échec de test.

## Corrections à l'inspection

Le thème système sombre rendait les labels presque invisibles sur le fond clair
choisi. La CSS applique maintenant les couleurs aux labels/rôles accessibles
et aux groupes de sélection, sans classes Emotion générées. Les captures clair
et sombre montrent le rendu corrigé. Cette compatibilité est liée à la version
Streamlit épinglée et devra être revue à sa mise à jour.

La synchronisation URL changeait le default des onglets et recréait leur widget,
annulant le clic suivant. Le default est désormais fixé pour chaque langue.
Le téléchargement CSV ne déclenche plus un rerun qui faisait disparaître le bouton.
Les erreurs d'une tranche animée sont interceptées dans le fragment carte.

## Relancer

Depuis la racine du dépôt, avec `.env` configuré :

```powershell
.\CasaTraffic\Scripts\python.exe scripts/init_dashboard.py
docker compose up -d --build
.\CasaTraffic\Scripts\python.exe scripts/verify_dashboard_deployment.py
docker compose ps
```

La validation exhaustive des filtres, exports, performance UI et captures de
chaque onglet appartient aux étapes 5 et 6.

# Phase 4 — vérifications du 1 octobre 2026

Toutes les commandes Python locales utilisent `CasaTraffic\Scripts\python.exe`.
Le DAG et ses dépendances Airflow tournent dans Docker, sans Airflow dans le venv.

```text
-m ruff check .
All checks passed!

-m pytest -q
37 passed in 10.31s

scripts/verify_phase4.py
OK 73 920 mesures réconciliées ; 485 événements en quarantine, upsert stable
OK trois runs Airflow qualité en succès ; quarantine stable, RAW/source intacts

scripts/verify_phase1.py
4 services healthy ; airflow-init exited 0 ; PostGIS 3.5
Connexion métadonnées et Connection casatraffic fonctionnelles
Aucune erreur d'import DAG ; source montée en lecture seule et SHA-256 intact
```

Rapport machine complet : `phase4_runs.json`. Dernière série de runs :

| Run | Configuration | Extraction/validation mappées | État |
|---|---|---:|---|
| phase4_1873f417b3a34de9aa15a1b2e8c840e4 | full | 7 / 7 | success |
| phase4_0e71f6cfe0fd484492e07a36df6b43db | full | 7 / 7 | success |
| phase4_699410830fe845fe8522dcccb4665f43 | replay, tick 0 | 1 / 1 | success |

Chaque run valide aussi les références ; toutes ses tâches sont en succès.
Une première série full/full/replay a également réussi avant l'ajout des noms de
dossiers de rapports compatibles Windows ; la série ci-dessus vérifie cette version.

La vérification locale applique le DDL, valide les 13 feuilles et effectue deux upserts
successifs via le rôle traffic. Elle mesure ensuite les comptes après les runs réels :
314 événements repairable, 171 warning, aucun rejected, total 485 inchangé.
Le SHA-256 de la source et les empreintes binaires des 13 RAW sont inchangés.
Les rapports de chaque partition sont conservés sous data/quarantine/reports/.
Les 73 920 mesures sont toutes réconciliées : 70 557 sans réparation obligatoire
dans les contrats RAW, 3 363 réparables, zéro rejet bloquant.

Tests spécifiques : finitude, bornes, types numériques et booléens, comptes entiers,
unicité des points/trajets, références inconnues, TTI réparables, colonnes manquantes,
rejeu sans heure et seuil. Le test du pipeline construit un Parquet synthétique dans
un dossier temporaire, injecte une distance nulle, capture la persistance, puis vérifie
que le gate lève l'exception après journalisation et sauvegarde du rapport.
Ce test ne pollue pas la table PostgreSQL de production. Les données réelles n'ont
aucun rejet bloquant : il serait faux de prétendre qu'un run réel a échoué sur ce seuil.

Le premier lint a signalé des lignes longues et deux formes isinstance ; elles ont
été corrigées. Un test a ensuite révélé qu'une colonne horaire absente était attribuée
à toute la journée au lieu de sa seule heure. L'attribution utilise désormais le nom
de colonne fourni dans failure_case ; les 440 mesures de l'heure sont précisément
journalisées. Après corrections : tests et lint verts.

Les valeurs réparables sont conservées, aucune ligne n'est supprimée silencieusement.
La normalisation, le TTI recalculé, STAGING et CORE restent la phase 5. Le DAG
data_quality séparé reste la phase 7 ; les contrôles qualité sont déjà intégrés
au DAG ingest_traffic comme gate avant sa réconciliation finale.

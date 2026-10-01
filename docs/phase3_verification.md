# Phase 3 — vérifications du 1 octobre 2026

Commandes locales exécutées avec `CasaTraffic\Scripts\python.exe`, Python 3.11.
Airflow est exécuté uniquement dans Docker.

```text
scripts/extract_raw.py
OK 13 feuilles extraites dans RAW
Summary : 17 lignes ; coordonnées : 110 ; tables 1–4 : 22 chacune
Tables 5–11 : 440 lignes chacune, temps et TTI sur 24 heures conservés bruts

scripts/verify_phase3.py
OK 13 feuilles RAW, seconde extraction identique octet par octet
OK 168 tranches de 440 lignes, 73 920 mesures brutes, boucle idempotente
OK quatre runs réels réussis ; RAW et source inchangés

-m pytest -q
22 passed in 0.82s

-m ruff check .
All checks passed!

scripts/verify_phase1.py
4 services healthy ; airflow-init exited 0 ; PostGIS 3.5
API Airflow et Metabase disponibles ; Connection casatraffic fonctionnelle
Aucune erreur d'import DAG ; source SHA-256 intacte et montée en lecture seule
```

Le rapport machine `phase3_runs.json` contient les empreintes des 13 Parquet et
les horodatages/états des tâches des quatre runs réellement exécutés par LocalExecutor :

| Run | Configuration | Tâches mappées | État |
|---|---|---:|---|
| phase3_8f209e82d3e64a799ed8d2dcfadb2554 | full | 7 | success |
| phase3_b2d8b633889748d0ac97099ec1141a69 | full | 7 | success |
| phase3_7e336b8b84ae4e13b721b0300b0e78ea | replay, tick 0 | 1 | success |
| phase3_04072502134f45d3991f0b45da05175c | replay, tick 168 | 1 | success |

Les quatre premières tâches mappées du premier run se chevauchent entre
21:53:12 et 21:53:14 UTC : concurrence réelle, puis les trois autres tâches.
Chaque run est terminé et toutes ses tâches sont en succès.
Les 168 tranches ont aussi été comparées aux colonnes originales correspondantes :
temps et TTI source identiques, aucune clé (jour, heure, ligne Excel) dupliquée.
L'égalité binaire après les runs inclut les horodatages d'ingestion conservés.

Une extraction neuve de Table 5 a été réalisée dans un répertoire temporaire du
volume RAW depuis `airflow-scheduler`, puis répétée : 440 lignes et même contenu
binaire. Le répertoire temporaire a été nettoyé ; les partitions publiées sont conservées.

Le premier essai a échoué sur `MergedCell.column_letter` dans Summary. La lecture
utilise désormais le numéro de colonne, compatible avec les cellules fusionnées.
Une correction intermédiaire avait placé la réutilisation du cache dans l'inventaire
au lieu de l'extracteur (`UnboundLocalError`) ; elle a été replacée avant les tests.
Aucune source ni partition publiée n'a été modifiée pour corriger ces erreurs.

Le DAG `ingest_traffic` est visible et actif sur http://localhost:8080, planifié
chaque heure en mode rejeu. Les 73 920 valeurs sont disponibles en RAW ;
`fact_travel_time` ne sera chargée qu'en phase 5. Quarantine et pandera sont la
phase 4 ; les trois autres DAGs, les marts, la CI et le dashboard restent à réaliser.

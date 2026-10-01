# Phase 6 — vérifications du 1 octobre 2026

Toutes les commandes Python locales utilisent CasaTraffic\Scripts\python.exe.

```text
scripts/build_marts.py
mart_commune_hourly_congestion : 3 696 lignes
mart_peak_hours : 154 lignes
mart_weekday_vs_weekend : 44 lignes
mart_commune_features : 22 lignes

scripts/verify_phase6.py
OK oracle pandas : chaque clé et KPI des quatre marts concorde avec CORE
OK SQL de pointe : égalités conservées sur échantillon temporaire
OK panne SQL : rollback des quatre marts, contenu conservé
OK marts reconstruits sans doublon ; CORE inchangé

-m ruff check .
All checks passed!

-m pytest -q
43 passed in 8.49s

scripts/verify_phase1.py
4 services healthy ; airflow-init exited 0 ; PostGIS 3.5
Connection casatraffic et HTTP disponibles ; aucune erreur d'import DAG
Source intacte et montée en lecture seule
```

Le constructeur build_marts a également été exécuté dans airflow-scheduler via
docker compose exec, avec BaseHook.get_connection('casatraffic'), puis PostgreSQL.
Les cinq scripts SQL se sont exécutés, avec les mêmes cardinalités. Les warnings
RequestsDependencyWarning et RemovedInAirflow3Warning déjà présents dans l'image
de phase 1 restent non bloquants ; ce build s'est terminé avec le code 0.

Le rapport phase6_verification.json garde les comptes, empreintes et confirmations
d'idempotence, d'oracle indépendant, d'égalité, de rollback et de conservation CORE.
L'oracle compare tous les groupes et toutes les colonnes KPI, pas un simple échantillon :
3 696 groupes horaires, 154 pointes, 44 groupes semaine/week-end et 22 profils.
Les attributs des profils sont comparés aux colonnes originales de dim_commune.
Le p95 utilise l'interpolation linéaire de pandas, comparée à percentile_cont SQL.
La somme des effectifs horaires est 73 920 ; toutes les jointures sont réconciliées.

Un test SQL utilise exclusivement des tables temporaires : deux heures de TTI moyen
identique sont conservées comme pointes pour une commune. Ces tables sont annulées
par rollback. Aucun fait ni mart de production n'est remplacé par cet échantillon.

Le test de panne copie les cinq scripts SQL dans un dossier temporaire et ajoute
SELECT 1/0 au dernier. La vraie fonction build_marts reconstruit les tables dans
une transaction ; la DivisionByZero attendue annule les quatre remplacements.
Le SQL versionné reste intact. Les quatre empreintes sont inchangées après rollback.
Les quatre dimensions, les faits et staging.travel_time gardent également leurs
empreintes ; aucune écriture dans la source, le RAW ou quarantine.

La phase 6 n'ajoute pas de nouveau DAG : l'orchestration build_marts et le
déclenchement après ingestion appartiennent à la phase 7. Les données analytiques
sont déjà construites et utilisables dans PostgreSQL ; le dashboard reste la phase 9.

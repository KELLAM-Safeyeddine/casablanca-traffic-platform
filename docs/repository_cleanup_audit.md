# Audit du dépôt avant publication — 2 octobre 2026

Audit effectué avec `git status --ignored --short`, `git ls-files` et un classement
PowerShell des tailles des fichiers suivis (équivalent Windows de `du | sort`).
Git a émis « Function not implemented » sur les liens Airflow
`logs/scheduler/latest` et deux liens sous `.validation/` ; l'inventaire a abouti.
Aucun fichier n'a été supprimé du disque.

## Fichiers inutiles dans le suivi

Ces exports reproductibles ont été retirés avec `git rm --cached`, sans suppression
locale :

- `docs/profiling/anomaly_examples.csv`
- `docs/profiling/daily_diagnostics.csv`
- `docs/profiling/hourly_tti_diagnostics.csv`
- `docs/profiling/measurement_diagnostics.parquet`

Le notebook `notebooks/02_source_profiling.ipynb` reste versionné avec ses cellules,
mais sans sorties ni compteurs d'exécution : 12 854 octets au lieu de 425 668.
La version exécutée originale est conservée, identique, dans le dossier ignoré
`.validation/repo_cleanup/02_source_profiling.executed.ipynb`.

Les environnements, `.env`, caches, logs, RAW, quarantaine et métadonnées de
supervision étaient déjà ignorés. Les nouvelles règles couvrent également les
volumes locaux, fichiers de clés/certificats, dumps, données traitées, caches de
couverture, IDE et fichiers temporaires. Les CSV ne sont ignorés que dans les
dossiers de données générées et `docs/profiling/` ; les fixtures CSV éventuelles
restent autorisées ailleurs. Les `.gitkeep` et README des dossiers générés restent
autorisés. Les configurations VS Code `settings.json` et `extensions.json`
restent autorisées.

## Éléments conservés

Code, SQL, DAGs, tests, configurations, dépendances épinglées, notebook source,
documentation et captures restent versionnés. Les rapports JSON documentaires
restent conservés pour expliquer les anomalies et les validations historiques.
Les sept captures préexistantes `dashboard_after_*.jpg` sont ajoutées au suivi.
Les deux modifications Python préexistantes (`dashboard/components/filters.py`,
`dashboard/tests/test_views.py`) ne font pas partie de ce nettoyage.

L'utilisateur a expressément autorisé la publication du classeur Excel source.
Il reste suivi et inchangé, SHA-256 :
`4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d`.

Aucun `.env`, `*.env`, `*.pem` ou `*.key` réel n'est suivi ; `.env.example`
reste suivi. La recherche de ces chemins secrets dans l'historique n'a rien
retourné. Une recherche textuelle des clés privées et affectations de secrets
littéraux longs n'a trouvé aucun candidat dans les fichiers texte suivis.
Les quatre exports retirés contiennent des diagnostics de trafic, pas des secrets.
Cette recherche ciblée n'est pas une garantie exhaustive de détection de secrets.
Le retrait du suivi ne purge pas l'historique des exports.

## Les 20 plus gros fichiers suivis avant nettoyage

| Octets | Chemin |
| ---: | --- |
| 2 763 401 | docs/profiling/measurement_diagnostics.parquet |
| 1 720 067 | data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx |
| 425 668 | notebooks/02_source_profiling.ipynb |
| 209 877 | docs/profiling/workbook_profile.json |
| 98 197 | docs/screenshots/dark_after/08_help.jpg |
| 96 267 | docs/screenshots/light_after/13_expander.jpg |
| 95 729 | docs/screenshots/dark_after/09_export.jpg |
| 95 729 | docs/screenshots/dark_after/13_expander.jpg |
| 91 140 | docs/screenshots/dark_after/12_map_tooltip.jpg |
| 87 906 | docs/screenshots/light_after/12_map_tooltip.jpg |
| 85 167 | docs/screenshots/dark_after/11_map_table.jpg |
| 84 890 | docs/screenshots/dashboard_map.jpg |
| 82 880 | docs/screenshots/dashboard_before_redesign.jpg |
| 82 527 | docs/screenshots/dark_after/06_quality.jpg |
| 82 143 | docs/screenshots/light_after/06_quality.jpg |
| 81 794 | docs/screenshots/dashboard_heatmap.jpg |
| 80 492 | docs/screenshots/dark_after/10_plotly_tooltip.jpg |
| 79 837 | docs/screenshots/airflow_ingestion.jpg |
| 79 415 | docs/screenshots/bug_light_before/06_quality.jpg |
| 79 164 | docs/screenshots/light_after/06_quality_hot_switch.jpg |

## Vérifications

- `CasaTraffic\Scripts\python.exe --version` : Python 3.11.0.
- `CasaTraffic\Scripts\python.exe -m ruff check .` : All checks passed!
- `CasaTraffic\Scripts\python.exe -m pytest -q` : 102 passed, 6 skipped, 15,72 s.
- `docker compose config --quiet` : code retour 0, sans exposer les secrets.
- `git check-ignore -v` : `.env`, `CasaTraffic/`, logs, Parquet, CSV de profilage
  et copie exécutée du notebook sont ignorés.
- `.env.example`, captures et classeur source restent suivis.

Pour régénérer les exports après un clone, depuis la racine du dépôt :

```powershell
.\CasaTraffic\Scripts\python.exe scripts/profile_workbook.py
```

Le script `scripts/verify_phase2.py` réexécute et enregistre les sorties du notebook.
Avant de versionner ensuite le notebook, vider ses sorties :

```powershell
.\CasaTraffic\Scripts\python.exe -m nbconvert --clear-output --inplace notebooks/02_source_profiling.ipynb
```

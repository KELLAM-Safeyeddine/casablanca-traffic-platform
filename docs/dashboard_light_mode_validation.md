# Vérification visuelle des thèmes

Les captures proviennent du dashboard Docker sur `http://localhost:8501`,
avec les données réelles du warehouse, le 2 octobre 2026. Les premières
captures ont été prises avant modification. Aucun résultat de données n'a
été simulé pour les captures. [Diagnostic et exceptions](dashboard_light_mode_bugs.md).

| Onglet | Clair avant | Clair après | Sombre avant | Sombre après |
| --- | --- | --- | --- | --- |
| Vue d'ensemble | [avant](screenshots/bug_light_before/01_overview.jpg) | [après](screenshots/light_after/01_overview.jpg) | [avant](screenshots/dark_before/01_overview.jpg) | [après](screenshots/dark_after/01_overview.jpg) |
| Carte | [avant](screenshots/bug_light_before/02_map.jpg) | [après](screenshots/light_after/02_map.jpg) | [avant](screenshots/dark_before/02_map.jpg) | [après](screenshots/dark_after/02_map.jpg) |
| Heures de pointe | [avant](screenshots/bug_light_before/03_peak_hours.jpg) | [après](screenshots/light_after/03_peak_hours.jpg) | [avant](screenshots/dark_before/03_peak_hours.jpg) | [après](screenshots/dark_after/03_peak_hours.jpg) |
| Semaine vs Week-end | [avant](screenshots/bug_light_before/04_weekend.jpg) | [après](screenshots/light_after/04_weekend.jpg) | [avant](screenshots/dark_before/04_weekend.jpg) | [après](screenshots/dark_after/04_weekend.jpg) |
| Communes | [avant](screenshots/bug_light_before/05_communes.jpg) | [après](screenshots/light_after/05_communes.jpg) | [avant](screenshots/dark_before/05_communes.jpg) | [après](screenshots/dark_after/05_communes.jpg) |
| Données & qualité | [avant](screenshots/bug_light_before/06_quality.jpg) | [après](screenshots/light_after/06_quality.jpg) | [avant](screenshots/dark_before/06_quality.jpg) | [après](screenshots/dark_after/06_quality.jpg) |

Chaque dossier après contient aussi les six variantes `*_dropdown.jpg` :
menu déroulant ouvert dans chacun des onglets. Le screenshot avant
[`07_dropdown.jpg`](screenshots/bug_light_before/07_dropdown.jpg) montre le
portail sombre sur la page artificiellement claire.

| Vérification complémentaire | Clair | Sombre |
| --- | --- | --- |
| Aide `help=` ouverte | [capture](screenshots/light_after/08_help.jpg) | [capture](screenshots/dark_after/08_help.jpg) |
| Tableau filtré et téléchargement CSV | [capture](screenshots/light_after/09_export.jpg) | [capture](screenshots/dark_after/09_export.jpg) |
| Tooltip Plotly | [capture](screenshots/light_after/10_plotly_tooltip.jpg) | [capture](screenshots/dark_after/10_plotly_tooltip.jpg) |
| Fond de carte et tableau | [capture](screenshots/light_after/11_map_table.jpg) | [capture](screenshots/dark_after/11_map_table.jpg) |
| Tooltip de point | [capture](screenshots/light_after/12_map_tooltip.jpg) | [capture](screenshots/dark_after/12_map_tooltip.jpg) |
| Expander ouvert | [capture](screenshots/light_after/13_expander.jpg) | [capture](screenshots/dark_after/13_expander.jpg) |
| État vide et bannière info | [capture](screenshots/light_after/14_empty_info.jpg) | [capture](screenshots/dark_after/14_empty_info.jpg) |

Le menu natif affiche directement **Theme → Light / Dark** dans Streamlit
1.64.0. Les bascules des tableaux, graphiques et de la carte ont été faites
par ce menu, sans recharger la page. Le fond CARTO dépend d'Internet/WebGL.
Les observations de couleurs sont dans `dashboard_theme_observations.json`.

La comparaison sombre vérifie les couleurs des fonds, KPI, filtres, tableaux,
gradations et tooltips, ainsi que l'absence de modification des données.
Les timestamps de collecte et la commande native de thème diffèrent entre
captures : il ne s'agit pas d'une comparaison bit à bit des fichiers JPEG.
Les puces cyan et les icônes Plotly inactives restent les exceptions de
contraste documentées, conformément à la priorité donnée au sombre inchangé.

## Résultats des commandes

- `docker compose up -d --build dashboard` : construction et démarrage réussis.
- `docker compose ps dashboard` : **healthy**, port `127.0.0.1:8501`.
- `CasaTraffic\Scripts\python.exe -m pytest -q` : **102 passed, 6 skipped**,
  en 17,73 secondes sur le workspace courant, incluant les tests FR/EN
  préexistants laissés hors des commits de thème.
- `CasaTraffic\Scripts\python.exe -m pytest dashboard/tests/test_theme.py -q` :
  les **11 cas** font partie de la suite complète ci-dessus.
- `CasaTraffic\Scripts\python.exe -m ruff check .` : **All checks passed**.
- `git diff --check` : aucune erreur.

Les six skips concernent les tests d'intégration conditionnels PostGIS/Airflow ;
ils ne sont pas présentés comme exécutés. Les contrôles pre-commit du code
effectivement indexé ont aussi réussi, sans inclure les changements FR/EN
antérieurs. Aucun secret, requête métier, modèle de données ou DAG n'a été modifié.

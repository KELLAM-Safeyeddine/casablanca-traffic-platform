# Phase 9 — vérifications du 1 octobre 2026

Dashboard livré : Streamlit dans Docker, http://localhost:8501, option autorisée
par le plan. Metabase reste healthy sur 3000, non initialisé. Ses cartes de points
ne répondent pas directement au besoin de couleur par TTI : choix documenté D028.

## Résultats réels

```text
CasaTraffic\Scripts\python.exe -m pip install -r requirements.txt
streamlit 1.64.0, plotly 7.1.0, pydeck 0.9.3 installés dans CasaTraffic

CasaTraffic\Scripts\python.exe scripts/init_dashboard.py
OK compte traffic_dashboard : SELECT uniquement, secret dans .env

docker compose up -d --build dashboard
Image casablanca-traffic-dashboard:python3.11 construite ; conteneur démarré
pip check pendant build : No broken requirements found.

CasaTraffic\Scripts\python.exe scripts/verify_phase9.py
73 920 observations ; 110 points ; 528 cellules commune/heure ; 22 communes
52 800 observations en semaine ; 21 120 en week-end
TTI moyen 1.3238901006988721 ; p95 1.8153766027826665
sql_oracle_matches: true
write_permission_denied: true
filter_sample_measures: 60

CasaTraffic\Scripts\python.exe scripts/run_integration_tests.py
57 passed, 3 skipped in 34.23s
OK conteneur de test supprimé ; volumes de la plateforme conservés

CasaTraffic\Scripts\python.exe -m pytest -q
55 passed, 5 skipped in 12.32s

CasaTraffic\Scripts\python.exe -m ruff check .
All checks passed!

CasaTraffic\Scripts\python.exe -m pip check
No broken requirements found.

docker compose exec -T dashboard python -m pip check
No broken requirements found.
```

Les skips correspondent aux tests PostGIS quand le lanceur n'est pas utilisé et
aux trois tests Airflow exécutés dans Docker en phase 8. Aucun test échoué.
Le SQL DDL modifié est inclus dans les tests d'intégration sur une base isolée.
Les autres bibliothèques, la source Excel et les fichiers RAW ne sont pas modifiés.

verify_phase1.py : les quatre services existants healthy, init exited 0,
PostGIS 3.5, API Airflow et Connection casatraffic disponibles, aucune erreur
d'import DAG, source montée en lecture seule et SHA-256 inchangé.
docker compose ps confirme également dashboard healthy : cinq services actifs.
Compose a recréé PostgreSQL après ajout de l'environnement du rôle dashboard,
en conservant le volume ; les 73 920 faits sont toujours présents et vérifiés.

## Réconciliation et permissions

Le SQL versionné lit les faits joints aux trajectoires, points et communes ;
ST_Y/ST_X extrait latitude/longitude depuis les géométries PostGIS.
Chaque point agrège 672 mesures ; chaque cellule commune/heure, 140 mesures
sur la semaine complète. Le classement compare chaque commune et ses KPI à
mart_commune_features avec tolérance 1e-12, p95 calculé depuis les observations.
Un filtre une commune/lundi/7–9 h donne 60 mesures et cinq points, sans perte.

Le compte traffic_dashboard lit seulement quatre tables CORE, pas STAGING ni
quarantine. Une tentative UPDATE ... WHERE false avec ce compte, même sans le
mode read-only du client, produit InsufficientPrivilege : aucun fait n'est écrit.
Les connexions de l'application activent en plus default_transaction_read_only.
Secret généré dans .env, jamais dans le code, les rapports ou les captures.
Le conteneur utilise un utilisateur non root et le port est lié à localhost.

## Vérification visuelle et filtres

Navigateur in-app, page réelle http://localhost:8501/ : quatre graphiques rendus.
Carte sur fond CARTO, points de couleurs variables par TTI, légende et zoom ;
heatmap avec 22 lignes et 24 heures ; deux barres semaine/week-end ; classement
complet, Al Fida en tête et Echchallalate en bas pour la sélection hebdomadaire.
Les KPI visibles sont 73 920 / 1.324 / 1.815 / 110, cohérents avec PostgreSQL.

Retrait d'Ahl Laghlam dans la sélection Communes : 70 560 mesures et 105 points,
TTI moyen 1.330 et p95 1.825. Retour à la sélection complète par rechargement.
AppTest vérifie aussi le filtre Jours et la sélection vide sans exception.
La comparaison conserve les deux périodes indépendamment du filtre Jours,
avec les communes/heures sélectionnées ; cette règle est affichée dans l'UI.
L'onglet dashboard est laissé ouvert comme livrable.

Captures réelles enregistrées dans screenshots :

- [Carte et KPI](screenshots/dashboard_map.jpg)
- [Heatmap](screenshots/dashboard_heatmap.jpg)
- [Semaine/week-end et classement](screenshots/dashboard_comparison.jpg)

## Corrections et limites

Ruff a signalé deux lignes trop longues dans verify_phase9.py : corrigées, lint
vert. La première ouverture du navigateur avant la fin du build a renvoyé
Connection refused ; le dashboard est ensuite ouvert et vérifié après démarrage.
Le build initial a téléchargé ses dépendances pendant environ cinq minutes ;
le build final des libellés français a réutilisé le cache et réussi.

Le fond CARTO nécessite Internet et la carte WebGL ; les KPI/plots utilisent
les observations locales. Couleur plafonnée au TTI 2 pour une échelle stable,
sans modifier les valeurs affichées au survol ou les agrégats. Cache 60 secondes
et bouton d'actualisation. Absence de dates réelles, semaine type uniquement.
Aucune analyse causale ni modèle ML ajouté à ce petit jeu descriptif.
La CI reçoit un troisième job pour construire l'image dashboard et vérifier
ses dépendances ; pas d'exécution distante revendiquée sans remote GitHub.

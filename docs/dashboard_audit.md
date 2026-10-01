# Audit du dashboard avant refonte

Audit du 1 octobre 2026 : inspection du code, de Compose et de l'interface réelle
sur http://localhost:8501/. Aucune modification du dashboard ni de données lors
de cette étape. Capture de référence :
[dashboard_before_redesign.jpg](screenshots/dashboard_before_redesign.jpg).

## Existant et points à conserver

Le dashboard livré est **Streamlit**, pas Metabase. Il sera refondu en place.
Metabase reste un service distinct et disponible, non initialisé dans ce projet.
Le service dashboard tourne déjà dans Docker, port localhost 8501, sous un
utilisateur Linux non root, avec healthcheck et dépendance Postgres healthy.
Versions épinglées : Streamlit 1.64.0, Plotly 7.1.0, pydeck 0.9.3, pandas 2.1.4,
psycopg2-binary 2.9.11 ; Python local 3.11 dans CasaTraffic.

L'écran comporte, dans cet ordre :

1. Titre et sous-titre indiquant la semaine type et la référence TTI empirique.
2. Quatre métriques : mesures sélectionnées, TTI moyen, TTI p95, points d'origine.
3. Carte pydeck des points d'origine, couleur selon le TTI moyen.
4. Heatmap commune × heure du TTI moyen.
5. Deux graphiques côte à côte : semaine/week-end et classement des communes.
6. Expander « Données et méthode », tableau de classement et téléchargement CSV.

La barre latérale propose communes, jours, plage horaire et actualisation du cache.
Toutes les communes et tous les jours sont préselectionnés. La comparaison des
périodes garde les deux périodes même si le filtre jours en exclut une ; une
légende le précise. Les moyennes sont pondérées par observation et les p95 sont
calculés directement à partir des faits. La géométrie vient bien de PostGIS.
L'avertissement de semaine incomplète et l'explication de la semaine type doivent
être conservés. Une exception SQL est interceptée avec un message lisible.

## Diagnostic visuel et confort d'utilisation

| Observation vérifiée | Conséquence | Priorité |
|---|---|---|
| Page unique longue, sans onglets | Défilement nécessaire pour retrouver classement ou méthode | Haute |
| 22 chips de communes et 7 de jours dans la barre latérale | Contrôles volumineux et sélection difficile à résumer | Haute |
| Titre long, quatre métriques sur une seule rangée | À la largeur observée, titre sur deux lignes et libellé de métrique tronqué | Haute |
| KPI natifs sans delta ni help | Niveau de congestion difficile à situer par rapport au global | Haute |
| Carte bleu→rouge, heatmap jaune→rouge, barres turquoise/orange | Pas de langage de couleur commun | Haute |
| Points de rayon constant, tooltip limité à commune/point/TTI | Intensité et vitesse/temps peu faciles à comparer | Moyenne |
| Aucun reset, filtre de période ni état partageable dans l'URL | Retour aux valeurs initiales et partage laborieux | Haute |
| Présentation Streamlit standard, menu Deploy visible | Hiérarchie et identité visuelle peu travaillées | Moyenne |
| Décimales avec point dans KPI/axes, aide incomplète | Interface française mais formats et interactions non harmonisés | Haute |
| Pas de commande de thème ni palette accessible dans l'application | Préférence clair/sombre et daltonisme non traités par le produit | Haute |

Ces observations concernent le rendu réellement inspecté ; elles ne constituent
pas une certification de contraste ou un test sur plusieurs appareils.
Streamlit peut proposer son thème via son menu standard, mais aucun thème
clair/sombre personnalisé n'est défini dans le dépôt.

## Écart fonctionnel avec la demande

| Demande | État actuel |
|---|---|
| Six onglets | Absents |
| KPI vitesse, commune, pointe et écart de période ; résumé automatique | Absents |
| Carte jour/heure animée, lecture/pause, bascule heatmap | Absents |
| Courbes horaires, bandes matin/soir | Absentes |
| Comparaison de deux communes | Absente |
| Top/bottom N et corrélations urbaines | Absents |
| Quarantaine, derniers DAGs, fraîcheur et résultat qualité | Absents de l'interface |
| Langue FR/EN et help sur les filtres | Absents |
| Export CSV des faits filtrés | CSV du classement seulement |
| Export PNG | Déjà disponible via la barre d'outils Plotly, à rendre explicite |
| État vide | Vérifié : retirer tous les jours affiche un message sans graphique ni traceback |
| Chargement | Pas de spinner métier explicite |

## Accès aux données, sécurité et performance

`src/dashboard.py` regroupe toute la présentation ; `src/load/dashboard_data.py`
contient lecture et agrégations. La requête est externalisée dans
`sql/marts/dashboard_measures.sql` : faits, dimensions point/trajet/commune et
ST_X/ST_Y, sans lecture RAW, STAGING ou tables Airflow. Les marts ne sont pas
encore utilisés par l'application ; leur concordance est contrôlée séparément.

Le rôle `traffic_dashboard` dispose actuellement de SELECT sur les quatre tables
CORE nécessaires, pas d'écriture. Chaque connexion impose une transaction en
lecture seule. La vérification existante confirme le refus d'un UPDATE sans
modifier de ligne. Le secret provient de .env, sans exposition dans l'interface.
Les futurs droits sur les marts doivent rester limités à SELECT.

Un cache `st.cache_data(ttl=60)` stocke les **73 920 faits**. Une nouvelle connexion
psycopg2 est créée et fermée à chaque cache miss ; aucun `st.cache_resource`.
Filtres, moyennes, p95, points et heatmap sont recalculés dans pandas à chaque
rerun. Cela ne respecte pas la nouvelle exigence d'agrégation SQL. L'objectif de
rechargement inférieur à 2 s n'a pas été mesuré pendant cet audit : il devra être
contrôlé sur l'application refondue, cache chaud et cache froid distingués.

Les tables métier sont dans `public` (CORE logique), et STAGING dans `staging` ;
il n'existe pas de schéma PostgreSQL nommé `core` dans le modèle livré. La refonte
gardera ce modèle et limitera ses requêtes aux tables CORE et marts autorisées.
Le comptage quarantine et les dates de DAG ne peuvent pas être déduits de ces
tables métier. Pour conserver cette restriction, prévoir des métadonnées
d'exploitation en fichiers JSON montés en lecture seule, produits par les
contrôles/pipelines, sans accès SQL à quarantine ni aux bases Airflow. Distinguer
date de traitement et date d'observation, inexistante dans cette semaine type.

## Vérifications effectuées avant refonte

Commandes locales avec CasaTraffic :

```text
CasaTraffic\Scripts\python.exe scripts/verify_phase9.py
73 920 mesures ; 110 points ; 528 cellules heatmap ; 22 communes
TTI moyen 1,3238901006988721 ; p95 1,8153766027826665
sql_oracle_matches=true ; write_permission_denied=true
filter_sample_measures=60
docker compose ps dashboard
dashboard Up (healthy), 127.0.0.1:8501
```

Le navigateur affiche les quatre graphiques et les trois filtres. Les anciennes
captures carte, heatmap et comparaison restent dans screenshots/ pour comparaison.
La capture avant refonte est ajoutée sans remplacer ces preuves historiques.
Le retrait de tous les jours affiche « Aucune mesure pour cette sélection » :
[capture de l'état vide](screenshots/dashboard_before_empty.jpg). Le placeholder
du sélecteur vide est toutefois « Choose options », en anglais. Les filtres par
défaut sont rétablis par rechargement après ce contrôle.

## Direction retenue pour la suite

Refonte modulaire dans `dashboard/`, six onglets avec contenu chargé à la demande,
cartes KPI lisibles et contexte explicite, palette unique et alternative cividis,
thèmes cohérents, filtres URL et reset. La base agrégera les faits pour les
sélections arbitraires, avec p95 exact au grain demandé ; les marts fourniront
les agrégats et attributs urbains appropriés. Le SQL restera hors des vues.
Les fichiers de métadonnées afficheront leur provenance et signaleront toute
absence ou obsolescence au lieu d'inventer un succès qualité ou une date fraîche.

La maquette textuelle, l'implémentation, l'intégration Docker et les captures
après refonte feront l'objet des étapes et commits suivants.

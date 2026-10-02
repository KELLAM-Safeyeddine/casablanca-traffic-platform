# Refonte — étape 3 : implémentation modulaire

Le 2 octobre 2026, ajout de dashboard/app.py et six modules d'onglets. Cette
étape ne remplace pas encore le service Docker existant : intégration et
captures sur données réelles seront effectuées à l'étape 4 puis à l'étape 6.

## Code livré

- data/filters.py : filtres immuables, période/jours par intersection, URL
  validée ; `none` représente explicitement une sélection vide.
- data/database.py : ThreadedConnectionPool en cache_resource, rollback et
  retour au pool, transactions read-only, timeout de connexion/requête.
- data/queries.py et data/sql/ : SELECT paramétrés, avg/percentile_cont et
  statistiques corr/regr_* calculés par PostgreSQL. Aucun SQL dans les vues.
- components/ : traduction, formats, filtres, six cartes et graphiques cohérents.
- Vue d'ensemble : deltas globaux, résumé du vrai couple commune/heure maximal.
- Carte : points PostGIS, TTI/rayon, tooltip vitesse/temps ; heatmap et animation
  via fragment, sans sleep bloquant. Une sélection globale modifiée arrête la lecture.
- Heures de pointe : courbes et p95, bandes 07–09 / 17–19, heatmap filtrable.
- Semaine/week-end : deux périodes explicites et comparaison de deux communes
  dans une courbe partagée et deux panneaux côte à côte, axes identiques.
- Communes : top/bottom N, corrélation descriptive SQL et garde sur X constant.
- Qualité : couverture SQL, contrat de JSON d'exploitation en lecture seule,
  rapport absent/ancien signalé, aperçu 100 lignes et export CSV complet.

Les onglets utilisent st.tabs(on_change="rerun") et tab.open pour ne rendre
que la vue active. Les bibliothèques nécessaires sont déjà épinglées dans les
requirements du projet ; aucune nouvelle dépendance ni installation globale.
Thèmes TOML clair/sombre et CSS légère : composants possédés par l'application,
plus deux ancres Streamlit explicites pour fond/sidebar. Pas d'API privée ni
st.set_option(theme.base). Leur rendu et leurs contrastes doivent encore être
vérifiés dans le navigateur lors du déploiement Docker ; les tests AppTest ne
certifient pas la mise en page CSS ni WebGL.

## Vérification réelle

```text
CasaTraffic\Scripts\python.exe -m ruff check .
All checks passed!

CasaTraffic\Scripts\python.exe scripts/run_integration_tests.py
82 passed, 3 skipped in 59.65s
OK conteneur de test supprimé ; volumes de la plateforme conservés

CasaTraffic\Scripts\python.exe -m pytest -q
79 passed, 6 skipped in 11.42s
```

Les trois skips du lanceur isolé sont les tests Airflow exécutés dans son image.
Le pytest local saute en plus les trois tests nécessitant PostGIS temporaire.
Les 24 nouveaux tests autonomes couvrent formats FR/EN, URL invalides/vides,
résumé stable en cas d'égalité, métadonnées absentes/périmées, rendu réel AppTest
des six onglets, langue/reset et interception d'erreur de base sans traceback UI.

Le nouveau test SQL crée dimensions et 440 faits dans la base casatraffic_test_
du conteneur temporaire. Il exécute les huit variantes d'agrégation, catalogue,
couverture, export et trois corrélations, compare moyenne/p95 SQL à un oracle
pandas indépendant, conserve la sélection vide et prouve le refus d'UPDATE
dans une transaction read-only. Aucun accès aux tables de production pour ce test.

## Échecs corrigés pendant le travail

Ruff : lignes longues et ordre d'import, corrigés puis lint vert.
Premier AppTest : trois KeyError hour dus au simulateur de requêtes qui prenait
le préfixe court d'un groupe ; priorité au groupe le plus spécifique corrigée.
Une valeur URL vide était retirée par la sérialisation ; ajout du marqueur
explicite none, avec test de roundtrip. Un dernier échec d'AppTest venait d'un
formatter de jours lisant session_state hors contexte lors de la simulation ;
les libellés sont maintenant capturés à la création du widget, sans état global
pendant le formatage. Les 24 tests passent après ces corrections.

## Vérifications restant aux étapes suivantes

Configurer Docker pour dashboard/app.py, installer les droits SELECT des marts,
publier les métadonnées opérationnelles sans credentials administrateur dans
le dashboard, puis démarrer réellement et contrôler chaque interaction.
Le rôle de production existant ne possède pas encore SELECT sur les marts ;
les tests d'UI utilisent des fixtures, pas une fausse connexion revendiquée.
L'animation, les palettes, les modes clair/sombre, les exports navigateur et
le budget de rechargement de 2 s ne sont pas déclarés validés sur cette étape.

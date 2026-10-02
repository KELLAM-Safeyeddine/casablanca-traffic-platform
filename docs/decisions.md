# Décisions techniques

## D001 — périmètre de cette livraison

Exécuter les phases 0 et 1 demandées avant de commencer le profilage de phase 2.
Les objectifs du plan ne sont pas des résultats constatés.

## D002 — source et noms

Copier le classeur fourni sous le nom ASCII demandé, sans modifier son contenu.
Enregistrer son SHA-256 et vérifier l'égalité avec l'original.
Le plan source est conservé intégralement dans `docs/project_plan.md`.

## D003 — Python et dépendances

Le venv `CasaTraffic` utilise Python 3.11.0 installé par l'utilisateur.
Les bibliothèques communes au venv et à Docker auront les mêmes versions.
SQLAlchemy 1.4.54 est retenu pour la compatibilité avec Airflow 2.11.2.
Les outils locaux (pytest, ruff, pre-commit, Jupyter) restent dans le venv.

## D004 — métriques

Agréger par commune d'origine, sans pondération par véhicules (absente de la source).
Utiliser les jours ISO et le calendrier local Africa/Casablanca, sans date réelle inventée.
Choisir le temps de référence TTI après observation des données.

## D005 — Airflow Docker

Airflow 2.11.2, image Python 3.11, pour conserver le service webserver demandé.
LocalExecutor suffit au volume prévu : pas de Redis/worker et parallélisme limité à 4.
Installer `requirements-airflow.txt` dans l'image, conformément à la séparation
explicite demandée entre dev et runtime, plutôt que les outils Jupyter/dev du venv.
Réinstaller Airflow avec sa version exacte et les contraintes officielles 3.11.
Référence : https://airflow.apache.org/docs/apache-airflow/2.11.2/howto/docker-compose/

## D006 — bases et persistance

Un conteneur PostgreSQL 16/PostGIS 3.5 avec trois bases et rôles distincts :
`airflow` (métadonnées), `traffic` (entrepôt), `metabase` (configuration BI).
Le volume nommé `postgres_data` conserve les trois bases. Le SQL d'initialisation
ne s'exécute que sur un volume neuf ; les redémarrages n'écrasent pas les données.
Les migrations métier seront ajoutées en phase 5.

## D007 — secrets et réseau local

Secrets aléatoires générés par `scripts/init_env.py`, jamais affichés ni versionnés.
Le script refuse d'écraser `.env` afin de préserver les clés et mots de passe existants.
Les mots de passe générés sont hexadécimaux et compatibles avec les URI de connexion.
La Connection Airflow `casatraffic` est injectée via `AIRFLOW_CONN_CASATRAFFIC`.
Les ports sont liés uniquement à 127.0.0.1. Le classeur est monté en lecture seule.
Changer un secret dans .env ne change pas automatiquement les rôles d'un volume existant.

## D008 — Metabase

Metabase Open Source, image de la release `v0.59.31.x`, base applicative PostgreSQL
plutôt que fichier H2. Le dashboard et son assistant de configuration sont la phase 9.
Les digests réellement téléchargés seront consignés dans la vérification de phase 1.
Références : https://github.com/metabase/metabase/releases/tag/v0.59.31
et https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker

## D009 — lecture structurée et noms (phase 2)

13 feuilles = sommaire + tables 0–11. Détecter la ligne Commune et contrôler les
blocs d'heures. Propager les communes/ZIP seulement dans les plages fusionnées.
Conserver feuille et numéro de ligne Excel ; identifier les jours par numéro de table.
Les couples commune/ZIP sont cohérents entre tables, donc pas de correction floue
des noms. Garder les libellés bruts et normaliser les clés Unicode/espaces/casse.

## D010 — temps, distances et audit (phase 2)

Distance >100 : diviser par 1000 conformément au plan. Pour cette source vérifiée
par SHA-256, temps entier >=1000 : diviser par 1000, car les 42 174 valeurs concernées
présentent un séparateur décimal perdu. Ne pas déduire un temps du TTI fourni.
Conserver valeurs brutes et motif ; toute valeur non interprétable reste visible.
Les outliers statistiques ne sont pas supprimés. Ces règles seront implémentées
et validées avant chargement, et ne sont pas universelles pour de nouvelles sources.

## D011 — référence TTI (phase 2)

Minimum du temps valide corrigé de chaque trajet dirigé sur les 168 heures.
La référence est indépendante du TTI fourni, puis figée pour le rejeu.
Conserver TTI source, recalculé et écart. Écart absolu >0,1 : signal de qualité.
TTI source >5 : signal, pas rejet automatique. TTI source <1 : anomalie à tracer,
sans supprimer la mesure si le temps valide permet un recalcul conforme.
Le minimum est un proxy empirique ; le rapport documente le changement de référence
et la fuite d'information à éviter pour une extension ML.

## D012 — clés de points et distances variables (phase 2)

Résoudre l'index trajet 110–114 vers les points 105–109 par correspondance unique
des coordonnées arrondies à huit décimales. Ne pas appliquer un décalage global.
254 trajets changent de distance selon le jour : distance du lundi dans dim_trajectory,
distance observée et valeur brute conservées dans les faits pour calculer la vitesse.

## D013 — attributs urbains et kernel (phase 2)

Population et ménages fractionnaires : conserver leur précision. Surfaces en m².
Density sans unité vérifiée : conserver comme density_source et exposer séparément
population/superficie en km². Aucune longueur de route n'est fournie.
Le kernel Jupyter casatraffic est installé seulement sous CasaTraffic/share/jupyter
et sa commande Python est contrôlée avant d'exécuter le notebook.

## D014 — RAW immuable et concurrence (phase 3)

Un répertoire par SHA-256 de source ; un Parquet pour chacune des 13 feuilles.
Summary conserve ses 17 lignes physiques, les tables conservent toutes les lignes
de données et leurs numéros Excel. Le forward-fill est limité aux plages fusionnées,
avec les labels commune/ZIP originaux conservés séparément. Pas de nettoyage numérique
dans RAW. Publication par fichier temporaire complet puis lien dur atomique : une cible
existante n'est jamais écrasée, y compris avec deux producteurs concurrents.
Un hash du contenu et la provenance sont vérifiés à chaque lecture/réutilisation.
Le lien dur a été vérifié sous Windows et depuis Docker sur le volume monté.
Une source identique et une partition existante valide évitent une nouvelle lecture Excel.
Le dossier RAW est une couche gérée par l'application, pas un stockage WORM matériel.

## D015 — mapping et horloge du simulateur (phase 3)

Un seul DAG `ingest_traffic`, TaskFlow, mapping généré à l'exécution : sept jobs
en mode full ; un job en mode replay. `max_active_tasks=4` limite la mémoire
et exécute les jours en deux vagues. Référence :
https://airflow.apache.org/docs/apache-airflow/2.11.2/authoring-and-scheduling/dynamic-task-mapping.html
La planification horaire utilise une ancre UTC configurable via Variable ; elle sert
seulement de compteur de simulation. Tick 0 = lundi 00 h, tick 167 = dimanche 23 h,
tick 168 = retour au lundi 00 h. Les chemins restent stables ; aucune multiplication
des mesures par des semaines/dates fictives. Les 168 tranches permettent de tester
toute la semaine sans attendre sept jours. La référence TTI restera figée en phase 5.

## D016 — contrats RAW et classes de qualité (phase 4)

Pandera valide une copie typée du RAW, en mode lazy pour collecter tous les échecs :
https://pandera.readthedocs.io/en/stable/lazy_validation.html
Un échec numérique reste NaN dans la vue et produit un rejet explicite ; jamais de dropna.
Des contraintes de finitude complètent les bornes. Les identifiants et comptes exigent
une valeur entière sans arrondi ; population/ménages conservent leurs fractions.
Enveloppe plausible Casablanca : latitude [33.3, 33.8], longitude [-7.9, -7.2],
sans prétendre vérifier les limites administratives exactes. Cardinalités fixées à cette
source : 110 points, 22 communes par table d'attributs, 440 trajets par jour/tranche.
Summary est une feuille de navigation conservée et non une table métier à valider.

`rejected` : valeur impossible, manquante, non finie, doublon ou référence inconnue.
`repairable` : TTI source positif <1 ou indice du crosswalk D012, uniquement si la
source connue et la correspondance géographique sont confirmées pour ce dernier.
`warning` : TTI source >5. Tout est journalisé dans quarantine, sans modifier le RAW.
Une mesure réparée ne sera admissible au CORE qu'après la validation normalisée de phase 5.
Ces sévérités évitent d'éliminer les temps valides à cause du seul TTI fourni.

## D017 — journal PostgreSQL et seuil (phase 4)

Créer dès la phase 4 `public.quarantine` dans la base traffic ; STAGING/CORE attendent
la phase 5. Conserver payload JSON brut, raison, colonne, feuille, ligne et heure.
Une anomalie de ligne entière utilise hour=-1. L'identifiant SHA-256 inclut source,
feuille, ligne, heure, règle, colonne et sévérité ; les colonnes de rejeu sont rattachées
aux noms de colonnes horaires source pour ne pas doubler un même événement full/replay.
Upsert actualise last_seen_at/last_run_id, sans changer first_seen_at ni la charge initiale.
Pas de purge automatique. Une ligne peut produire plusieurs événements ; les compteurs
de mesures utilisent l'union des clés ligne/heure, avec priorité au rejet bloquant.

Seuil standard choisi : rejet >1 % par partition fait échouer la tâche après persistance.
Configurable via `traffic_max_error_rate`, bornée entre 0 et 1. Réparables et warnings
sont exposés séparément. Le DDL idempotent est appliqué à l'exécution, ce qui fonctionne
aussi sur le volume PostgreSQL déjà créé. Les tâches utilisent la Connection casatraffic.
Les rapports par run gardent le run_id original dans le JSON ; leur dossier remplace les
caractères incompatibles Windows et ajoute un hash pour éviter les collisions de noms.

## D018 — modèle et clés déterministes (phase 5)

CORE dans public, STAGING dans le schéma staging ; SQL métier versionné sous sql/ddl
pour respecter l'arborescence imposée. commune_id = ZIP numérique (unique dans cette
source), point_id = index Table 0, trajectory_id = origine ×110 + destination +1.
Ces identifiants ne dépendent ni de l'ordre d'exécution ni des séquences PostgreSQL.
Les libellés originaux et ZIP texte sont conservés ; clé Unicode NFKC/espaces/casse.
Conserver population/ménages fractionnaires et les deux champs de densité D013.
Géométrie générée Point SRID 4326, index GiST, longitude X / latitude Y :
https://postgis.net/docs/ST_MakePoint.html
Périodes dim_time : matin 7–9, soir 17–19, nuit <6 ou >=22, creuse sinon.
Ces plages sont des conventions analytiques, pas des heures de pointe mesurées.

## D019 — référence, prévalidation et rejeu (phase 5)

Minimum des temps corrigés admissibles sur les 168 heures, indépendant du TTI fourni.
Stocker le minimum et le SHA-256 dans dim_trajectory ; une relance vérifie leur égalité
et ne les remplace pas. Distance de référence du lundi ; distance observée dans le fait.
Le bootstrap vérifie les références et prépare la semaine entière même lors d'un rejeu.
Ce petit volume rend ce choix simple et reproductible ; le rejeu charge une seule heure.
Avant CORE : validation normalisée, puis prévalidation TTI/vitesse avec référence
en base ; les formules finales restent exécutées en SQL, contrôlées par contraintes.
Les rejets sont persistés avant le seuil et exclus par clé explicite ligne/heure.
Les alertes RAW réparables restent dans le journal historique ; les valeurs corrigées
et leurs indicateurs sont dans les faits. Aucun temps n'est reconstruit depuis le TTI.

## D020 — transactions et version de source (phase 5)

Remplacement delete+insert de la partition (source, jour, heures) STAGING, puis
transformation SQL et remplacement CORE, dans la même transaction. Verrou advisory
transactionnel par heure, acquis en ordre croissant ; bootstrap/DDL ont leurs verrous.
Rollback des deux couches sur erreur, sans effacer les événements déjà journalisés.
Référence : https://www.postgresql.org/docs/16/explicit-locking.html
Les jours mappés commitent indépendamment ; la relance reprend une ingestion interrompue.
Les dimensions utilisent ON CONFLICT DO NOTHING car la source est immuable et unique ;
la référence TTI figée est comparée à chaque bootstrap. Une autre source/semaine/historique
requiert un modèle versionné et une migration explicite : pas d'écrasement implicite.
Le vérificateur conserve le premier état vide et les runs successifs dans son rapport,
compare les empreintes des données métier, et injecte une division par zéro dans une
copie SQL temporaire pour tester le rollback réel après remplacement de la partition.

## D021 — marts SQL persistants et KPI (phase 6)

Quatre tables public à clés primaires stables, créées et reconstruites par SQL versionné
dans sql/marts. Ce volume permet une reconstruction complète transactionnelle, avec
les mêmes tables visibles dans Metabase entre deux builds. Pas de DROP ni de renommage.
Le constructeur exige les 73 920 faits de la semaine type ; un CORE incomplet bloque
le build et conserve les marts existants. Verrou advisory pour sérialiser les builds,
SHARE sur les tables CORE pour éviter de mélanger plusieurs états de leurs données.
Les quatre remplacements sont atomiques ; pas d'écriture dans les faits ou les RAW.

Commune d'origine, poids égal par observation, TTI recalculé et moyenne des vitesses.
Le p95 est percentile_cont(0.95), calculé directement sur les observations de chaque
grain, jamais depuis la moyenne des p95 de groupes plus petits :
https://www.postgresql.org/docs/16/functions-aggregate.html
Moyennes avec ordre explicite des clés pour stabiliser les additions flottantes.
Pointes au grain commune/jour, dense_rank=1, toutes les égalités conservées :
https://www.postgresql.org/docs/16/functions-window.html
La comparaison semaine/week-end expose deux lignes par commune, effectif, nombre
de jours, TTI moyen/p95 et vitesse moyenne. Cinq jours contre deux : les sommes
ne sont pas des mesures comparables de congestion ; les moyennes le sont.
Les caractéristiques joignent les KPI hebdomadaires aux attributs de dim_commune,
sans arrondi ni unité supposée pour density_source. C'est un dataset descriptif à
22 lignes ; pour ML, isoler la cible et éviter les autres KPI du même jeu comme prédicteurs.

## D022 — vérification indépendante et orchestration (phase 6)

Un oracle pandas calcule chaque KPI depuis les 73 920 faits et compare chaque clé,
avec tolérance flottante 1e-12. Les caractéristiques urbaines sont comparées à CORE.
Les empreintes des quatre marts restent stables après build local et depuis Docker.
Un échantillon SQL temporaire vérifie les pointes ex æquo ; une copie temporaire du
SQL final avec division par zéro prouve le rollback des quatre tables réelles.
Le constructeur réutilisable est exécuté localement avec .env et dans Docker avec
la Connection Airflow. Le DAG et le déclenchement automatique sont la phase 7.

## D023 — chaîne de Datasets et gate qualité (phase 7)

Identifiants conformes à la demande : bootstrap_dimensions, ingest_traffic,
data_quality, build_marts ; les fichiers portent le préfixe dag_ du plan.
Bootstrap manuel ; ingestion horaire avec mode full manuel ; sa dernière tâche
publie casatraffic://warehouse/core après toutes les partitions chargées.
data_quality consomme ce Dataset, valide les 13 RAW et le CORE avec pandera,
vérifie cardinalités et formules, puis publie quality_passed uniquement en succès.
build_marts consomme quality_passed. Cette étape intermédiaire évite de publier
des agrégats issus d'une semaine incomplète. Premier lancement : bootstrap puis full.
L'ingestion conserve son bootstrap idempotent pour rester relançable seule.
Le minimum hebdomadaire exige de lire les sept jours pour figer la référence,
même si seuls les attributs des tables 0–4 servent aux communes/points.

Les Datasets représentent l'état courant, peuvent coalescer des événements et
ne garantissent pas un run consommateur par événement. Les runs sont limités
à un par DAG ; le contrôle CORE et les builds verrouillent leur lecture contre
les écritures. Pas de snapshot historique ajouté à cette semaine type.
Les contrôles CORE ne suppriment ni ne réparent les faits : une incohérence fait
échouer la tâche et conserve les données pour investigation. Les rejets de
sources continuent à être persistés en quarantine avant le contrôle de seuil.

## D024 — alertes locales et paramètres tardifs (phase 7)

Pas de service mail/Slack configuré : callback de tâche en échec après retries,
log ERROR et fichier JSON local idempotent, consultable sur le volume quarantine.
Le payload expose seulement DAG/run/tâche/index/état, jamais la chaîne d'exception
qui pourrait contenir une URL de connexion. Pas de communication externe.
Variables lues dans les tâches, connexions issues de casatraffic ; aucune
lecture Excel, connexion PostgreSQL ou accès Variable pendant l'import des DAGs.

## D025 — intégration PostGIS isolée (phase 8)

Tests pytest sur une tranche horaire de 440 mesures, avec dimensions complètes
pour conserver les vrais contrats de production. Le bootstrap lit la source
versionnée et écrit uniquement dans un dossier temporaire. Le test refuse un
DSN dont le nom de base ne commence pas par casatraffic_test_. Le lanceur crée
un conteneur PostGIS 16/3.5 indépendant, port aléatoire lié à 127.0.0.1 et secret
généré en mémoire, transmis par fichier temporaire et environnement du sous-processus.
Le conteneur est supprimé dans finally ; aucun volume applicatif n'est touché.
Les noms et mot de passe ne sont pas versionnés. Pas de base de test préconfigurée.

Les assertions comparent le contenu complet de STAGING et CORE après relance,
injectent un temps négatif et retrouvent son payload en quarantine, restaurent
la partition, puis provoquent une division SQL par zéro dans une copie temporaire
du SQL pour vérifier le rollback. Ni source ni SQL versionné ne sont modifiés.

## D026 — tests de DAGs dans l'image Airflow (phase 8)

unittest standard est disponible dans l'image sans pytest ni dépendance de dev.
Le même fichier est collecté localement par pytest, avec trois skips explicites
quand Airflow n'est pas installé ; ils sont réellement exécutés dans Docker.
DagBag vérifie exactement les quatre DAGs ; check_cycle, types des tâches mappées,
callbacks, retries, et DatasetTriggeredTimetable complètent les contrats.
Le test initial utilisant DAG.schedule a échoué : Airflow 2.11.2 expose la
condition via timetable.dataset_condition.objects. Correction validée sur l'image.

## D027 — pre-commit et CI sans environnement Python supplémentaire (phase 8)

Hooks repo: local, language: system ; python résout CasaTraffic par le PATH de
la session activée. Ruff et pytest sont les versions requirements.txt. Pas de
téléchargement de dépôt de hooks ni de venv créé par pre-commit. La CI crée
CasaTraffic avec Python 3.11 sur Ubuntu 24.04 et exécute toutes les commandes
Python locales via ce venv. Un second job construit l'image et teste les DAGs.
La CI ne publie ni image ni site. Le workflow est configuré pour push, PR et
workflow_dispatch ; aucune exécution distante revendiquée sans remote GitHub.
Actions checkout v6 / setup-python v5 suivent l'exemple officiel consulté :
https://docs.github.com/en/actions/tutorials/build-and-test-code/python

Dans la session de vérification Windows, les commandes pre-commit/Git élevées
utilisent safe.directory limité à ce dépôt via GIT_CONFIG_* du processus pour
le dépôt appartenant au compte sandbox. Aucun changement de configuration Git globale.

## D028 — dashboard Streamlit en Docker (phase 9)

Le plan autorise Metabase ou Streamlit. La documentation Metabase indique que
les valeurs supplémentaires d'un pin map alimentent les infobulles et non la
couleur des points. Pour respecter exactement la carte des 110 points colorés
par TTI et la heatmap commune/heure, Streamlit + pydeck + Plotly sont retenus :
https://www.metabase.com/docs/latest/questions/visualizations/map
https://docs.streamlit.io/develop/api-reference/charts/st.pydeck_chart
Metabase est conservé dans Compose, disponible mais non initialisé. Pas de compte
Metabase créé ni de dashboard revendiqué dans son UI. Le dashboard livré est
Streamlit, service Docker supplémentaire, port local 8501.

Python 3.11 dans l'image ; versions streamlit 1.64.0, plotly 7.1.0 et pydeck 0.9.3
vérifiées dans les métadonnées officielles PyPI et épinglées dans requirements.txt
et requirements-dashboard.txt. Packages locaux installés uniquement dans CasaTraffic.
Le SQL de lecture est versionné dans sql/marts/dashboard_measures.sql, séparé
des scripts 00–04 reconstruisant les marts. Les coordonnées viennent de ST_X/ST_Y.

Lecture des 73 920 observations dans un snapshot PostgreSQL ; chaque vue agrège
les faits filtrés pour conserver la pondération et le p95 exact. Les valeurs
hebdomadaires sont réconciliées avec mart_commune_features. Cache d'une minute
avec bouton d'actualisation. Comparaison semaine/week-end indépendante du filtre
jours, mais même communes/heures, règle explicite dans l'UI pour comparer les
deux périodes. Aucun filtre de dates inventées ni analyse causale/ML ajoutée.

Palette continue commune aux cartes : bleu TTI=1, rouge TTI>=2, valeur exacte
en infobulle. Le plafonnement est visuel uniquement, aucun écrêtage des faits.
Fond CARTO public ; Internet et WebGL requis pour le fond cartographique.
Les autres graphiques et métriques sont calculés depuis les faits locaux.

## D029 — compte dashboard limité à SELECT (phase 9)

Secret aléatoire dans .env ; rôle traffic_dashboard sans écriture, limité aux
dim_commune, dim_point, dim_trajectory et fact_travel_time. Pas d'accès quarantine,
STAGING ni bases Airflow/Metabase. Connexions configurées en lecture seule.
sql/ddl/00_platform.sql crée le rôle sur volume neuf ; bootstrap_warehouse donne
les droits si le rôle existe, sans modifier les tests PostGIS isolés.
init_dashboard.py migre le volume existant et réutilise le secret à la relance.
Les erreurs de connexion dans l'UI sont génériques pour ne pas exposer de secret.
L'image tourne sous un utilisateur non root ; port lié à 127.0.0.1 seulement.

## D030 — premier démarrage reproductible et validation isolée (phase 10)

La qualité globale exige 73 920 faits. Sur volume vierge, l'ingestion horaire
seule ne peut donc pas précéder le chargement de la semaine entière.
bootstrap_platform.py attend les quatre DAGs, charge réellement dimensions et
semaine complète via airflow dags test pendant que les DAGs consommateurs sont
pausés, puis les active et prouve deux chaînes Dataset automatiques. Sur un
CORE déjà complet, il conserve les dimensions et vérifie les deux chaînes.
Les empreintes comparées excluent les horodatages techniques de journalisation.

verify_clean_start.py copie le code et la source dans .validation/, crée un
projet Compose UUID avec nouveaux secrets, quatre ports libres et un volume
PostgreSQL neuf. Les images déjà construites sont réutilisées. Son finally
retire exclusivement les conteneurs, le réseau et le volume de ce projet,
après contrôle du préfixe et du chemin. La plateforme principale reste active.
Les copies locales de diagnostic sont ignorées par Git. Le rapport JSON conserve
les identifiants de runs, événements Dataset, effectifs et empreintes, sans secrets.

Un premier essai a rencontré une interruption de connexion pendant le démarrage
du webserver. L'attente API tolère désormais ConnectionError en plus de URLError
et TimeoutError ; le second essai complet a réussi. Le bonus ML/corrélation reste
une extension : les marts livrés permettent une analyse ultérieure sans
présenter d'association statistique ou de causalité non vérifiée.

## D031 — contrat UX du dashboard refondu (maquette)

dashboard_wireframe.md définit les six onglets avant implémentation. Référence
globale fixe pour les deltas, p95 calculé au grain réel des faits, attribution
par commune d'origine et période comparative explicitement indépendante du
filtre jours/période. Une sélection vide ne signifie jamais toutes les communes.
Les valeurs maximales ex æquo sont signalées et triées de façon déterministe.

Les métadonnées d'exploitation proviendront de JSON en lecture seule pour ne
pas élargir les lectures SQL du dashboard à quarantine ou à la base Airflow.
La date de traitement n'est pas une date d'observation. Les corrélations
descriptives prévues par la nouvelle demande ne seront pas présentées comme
des causes ; ajustement/corrélation en SQL et absence de droite sur X constant.

Streamlit 1.64.0 installé possède st.tabs(on_change=...), permettant un rendu
différé. Inspection locale : st.set_option n'autorise pas theme.base ; aucun
changement par cette API privée/invalide ne sera utilisé. Le mécanisme de thème
compatible sera vérifié pendant l'implémentation. La maquette décrit une cible,
pas des performances, contrastes ou fonctions déjà vérifiés en production.

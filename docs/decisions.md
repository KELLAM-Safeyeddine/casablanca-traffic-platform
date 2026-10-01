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

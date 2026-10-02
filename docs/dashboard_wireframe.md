# Maquette textuelle — Casablanca Traffic

Étape 2 de la refonte, après [l'audit](dashboard_audit.md). Ce document spécifie
l'interface à construire ; il ne prétend pas que les nouvelles fonctions sont
déjà déployées. Le dashboard Streamlit existant reste opérationnel.

## Structure commune

```text
┌───────────────────────────┬───────────────────────────────────────────────┐
│ CASABLANCA / TRAFFIC       │ Casablanca Traffic                            │
│                           │ Comprendre la congestion d'une semaine type   │
│ Langue : Français / EN    │ 22 communes · 110 points · sélection résumée   │
│ Palette accessible        │                                               │
│                           │ Vue d'ensemble | Carte | Heures de pointe     │
│ Période : Tous / Semaine / │ Semaine vs Week-end | Communes | Données       │
│           Week-end        │                                               │
│ Jours : lun … dim         │ Contenu du seul onglet actif                   │
│ Heures : [00 h … 23 h]     │                                               │
│ Toutes les communes ☑     │ Valeurs + unités + comparaison + aide          │
│ Communes : rechercher     │                                               │
│                           │ Graphiques interactifs et tableau accessible  │
│ Réinitialiser les filtres │                                               │
│ Actualiser les données    │ Comment lire ce dashboard ?                    │
│                           │ Source : semaine type, référence empirique     │
└───────────────────────────┴───────────────────────────────────────────────┘
```

Le titre produit reste court ; les détails techniques sont dans l'onglet qualité.
Une ligne résume les communes/jours/heures actifs et l'effectif obtenu. Les valeurs
restent explicites et lisibles sans couleur. Les six onglets sont de vrais
conteneurs Streamlit ; seul l'onglet actif déclenche ses requêtes et graphiques.
À largeur réduite, la barre latérale se replie, les KPI reviennent à la ligne et
les comparaisons empilées gardent les mêmes axes. Aucun défilement horizontal
nécessaire pour lire un KPI ; les tableaux conservent leur propre défilement.

## Filtres et partage

Valeurs initiales : tous les jours, 00–23 h, toutes les communes, toutes les périodes,
français et palette trafic. « Toutes les communes » évite d'afficher 22 chips
préselectionnées ; désactiver cette option permet une recherche multisélection.
Une sélection explicite vide signifie zéro commune, jamais « toutes » implicitement.
Les filtres jours et période se combinent par intersection : une intersection
vide provoque un état vide, sans changer silencieusement la sélection.

Chaque contrôle possède help, libellé traduit et état clavier visible. Le reset
rétablit les filtres métier et arrête l'animation ; il conserve la langue et la
palette choisies. L'actualisation invalide les caches de données, pas les filtres.

L'URL encode des identifiants stables : `days`, `hours`, `communes`, `period`,
`lang`, `palette`, `tab` et les contrôles locaux (jour/heure de carte, mode carte,
communes comparées, top/bottom, N, variable urbaine). La sélection de toutes les
communes est distincte d'une sélection vide. Décodage validé : IDs inconnus ou
heures invalides sont signalés et remplacés par une valeur sûre. Aucune donnée
sensible, aucun secret ni identifiant Airflow n'est placé dans l'URL. Recharger
un lien doit reproduire les mêmes données, unités et contrôles.

## 1. Vue d'ensemble

```text
TTI moyen              TTI p95                Commune la plus congestionnée
1,32                   1,82                   Nom de commune · TTI 1,56
Δ contre global        Δ contre global       Δ contre global

Heure de pointe        Vitesse moyenne        Écart week-end / semaine
18 h · TTI 1,68        28,4 km/h              −8,2 %
Δ contre global        Δ contre global       Δ contre écart global

« X présente le TTI moyen le plus élevé de cette sélection, … »
Courbe horaire synthétique + repères de pointe matin/soir
```

Les nombres ci-dessus illustrent la mise en page ; ce ne sont pas des résultats.
Les six cartes utilisent les mesures filtrées, sauf la comparaison de périodes
qui conserve les deux périodes sur les communes/heures sélectionnées.

| Carte | Valeur et delta définis |
|---|---|
| TTI moyen | Moyenne des faits filtrés ; différence avec la moyenne globale non filtrée |
| TTI p95 | Percentile continu des faits filtrés ; différence avec le TTI moyen global, référence explicitement nommée |
| Commune la plus congestionnée | Nom et TTI moyen maximal ; différence de ce TTI avec la moyenne globale |
| Heure de pointe | Heure au TTI moyen maximal sur les jours filtrés, TTI associé ; delta de ce TTI avec la moyenne globale |
| Vitesse moyenne | Moyenne arithmétique en km/h ; delta avec la vitesse moyenne globale |
| Écart week-end/semaine | 100 × (TTI week-end / TTI semaine −1) ; delta en points de pourcentage avec l'écart global |

Les deltas TTI sont en unités TTI, ceux de vitesse en km/h : pas de soustraction
entre unités différentes. Les égalités sont signalées ; un tri stable fournit
un nom/une heure déterministe dans la carte et le détail liste les ex æquo.
Le résumé est généré sans modèle externe à partir des agrégats SQL, traduit,
et n'associe pas l'heure maximale globale à une commune sans requête vérifiant
ce couple. Un résumé commune × heure utilise le vrai maximum de ces groupes.

## 2. Carte

Une carte dominante, fond clair/sombre cohérent, mêmes valeurs et couleurs dans
les deux modes. Vue initiale centrée sur Casablanca. Coordonnées ST_X/ST_Y depuis
dim_point ; mesures regroupées par point d'origine. Les 110 points apparaissent
lorsque toutes les communes sont sélectionnées. Les filtres réduisent cet ensemble.

Au-dessus : jour de carte parmi les jours admissibles, curseur heure dans la
plage globale, lecture/pause et choix Points / Heatmap. L'animation avance d'une
heure puis boucle dans la plage sélectionnée, sans attente bloquante du serveur.
Changer d'onglet ou modifier les filtres arrête la lecture. Le jour et l'heure
actifs sont visibles en permanence et synchronisés dans l'URL.

Points : couleur **et** rayon selon TTI ; tooltip commune, identifiant du point,
TTI, vitesse km/h, temps moyen minutes et nombre d'observations. Une légende
numérique explique l'échelle. Heatmap : poids TTI, nom « intensité agrégée » ;
elle n'est pas présentée comme une mesure exacte par pixel. Un tableau des
points complète la carte pour clavier/lecture assistée et vérification des valeurs.
Fond indisponible : garder le tableau, expliquer la dépendance Internet/WebGL.

## 3. Heures de pointe

Courbes de TTI moyen par heure, option p95, repères TTI=1 et bandes matin/soir
cohérentes avec le modèle : 07–09 h et 17–19 h. Les bandes sont des périodes de référence et non une
affirmation que le maximum observé s'y trouve. Un tableau donne les vrais maxima.

Heatmap commune × heure filtrable par une commune locale (« toutes » disponible),
même palette TTI que la carte. Tooltip : commune, heure, moyenne, p95 et effectif.
Le filtre global reste visible ; la sélection locale est nommée et partagée dans
l'URL. Les p95 sont toujours calculés à partir des observations au grain demandé.
Les lignes horaires manquantes restent des trous, pas des valeurs nulles inventées.

## 4. Semaine vs Week-end

Deux cartes récapitulatives et deux courbes comparables : lundi–vendredi et
samedi–dimanche, mêmes communes et mêmes heures. Une annotation persistante
précise que cette comparaison conserve les deux périodes, indépendamment du
filtre global jours/période. Les effectifs sont affichés : cinq jours ne pèsent
pas comme deux dans un total, mais les moyennes restent par observation.

Deux sélecteurs choisissent une commune A et une commune B parmi le catalogue.
Leurs noms, effectifs et courbes sont affichés côte à côte, mêmes axes et unités.
Cette comparaison locale conserve les jours/heures admissibles mais remplace
le filtre global communes, avec mention explicite. Si A=B, demander de choisir
une autre commune ; s'il n'y a pas assez de communes, afficher un état adapté.

## 5. Communes

Classement horizontal trié par TTI moyen : choix Plus congestionnées / Moins
congestionnées et curseur N, borné au nombre de communes disponibles. Valeurs
sur les barres, tooltip p95/vitesse/effectif, tableau trié et CSV d'agrégats.

Analyse urbaine : axe X au choix densité calculée habitants/km², stations de tram
ou routes primaires ; axe Y TTI moyen filtré. Une observation par commune, noms
au survol et droite ajustée. Calculs statistiques en SQL (`corr`, `regr_slope`,
`regr_intercept`) ; présentation uniquement en Python. Afficher le nombre de
communes, r et une lecture descriptive de l'association. Si X est constant,
moins de trois paires admissibles ou valeurs absentes : pas de droite ni de
conclusion inventée. Mention « association observée, pas preuve de causalité ».

## 6. Données & qualité

Résumé couverture : 73 920 attendus / compte réel, 22 communes, 110 points,
440 trajets. Tableau des quatre DAGs : dernier run observé, état et date UTC
convertie pour l'affichage. Afficher quand la métadonnée a été collectée.

Quarantaine : effectif du journal, réparti en rejet / réparable / avertissement.
Ne pas appeler 485 événements « 485 lignes rejetées ». Résultat du dernier audit,
sa portée/source, date et nombre de faits contrôlés. Un succès historique ne
garantit pas la qualité de données modifiées depuis cet audit : rapport périmé
ou absent affiche « à vérifier »/« indisponible », pas un badge vert par défaut.

Ces informations viennent de JSON d'exploitation montés en lecture seule et
produits par un script/pipeline séparé. Le dashboard n'interroge ni quarantine,
ni STAGING, ni la base Airflow et ne reçoit pas de credentials administrateur.
Date de traitement, date de collecte et semaine type sont séparées : pas de
fausse date de mesure ou de prétendu flux temps réel.

Expander « Comment lire ce dashboard » : TTI>1 signifie plus lent que la
référence ; ici le minimum empirique hebdomadaire corrigé, pas une mesure libre
indépendante. Expliquer mètres/km, temps remis à l'échelle, indices réparés,
TTI fourni/recalculé et variations de distances. Les chiffres proviennent des
faits/rapports vérifiés ; le diagnostic source reste accessible depuis le README.

Table paginée/limitée pour l'aperçu, puis export **de tous les faits filtrés**
par téléchargement CSV, sans silencieuse limitation à l'aperçu. Français :
séparateur `;`, UTF-8 BOM, décimales `,` ; anglais : CSV standard. Les filtres
et unités sont indiqués avant le téléchargement. Les graphiques Plotly exposent
le téléchargement PNG par leur modebar, avec nom de fichier explicite.

## Design et accessibilité

Thèmes natifs clair/sombre dans `dashboard/.streamlit/config.toml` ; coins
arrondis, font sans serif système pour disponibilité hors ligne, titres nets.
Inter peut être ajouté comme police locale si disponible, sans requête externe
nécessaire à la lisibilité. CSS limité aux classes de composants possédées par
l'application et clés de containers documentées ; aucun sélecteur Emotion
généré ou dépendance à la position du DOM. Le menu de déploiement et footer
standard sont masqués via options natives lorsque possible. La préférence
de thème doit rester accessible malgré le masquage du menu standard ; choisir
le mécanisme public compatible pendant l'implémentation, sans API privée.

| Élément | Clair | Sombre |
|---|---|---|
| Fond | #F5F7FA | #0B1220 |
| Surface KPI | #FFFFFF | #162033 |
| Texte principal | #172538 | #F1F5F9 |
| Texte secondaire | #526174 | #B5C1D1 |
| Accent interface | #087F8C | #58CCD4 |

TTI : vert #1B9E77 → jaune #E6C84F → orange #E77932 → rouge #C52F40.
Alternative cividis activable en barre latérale, sur toutes les vues TTI.
Une échelle commune fixée à TTI 1–2 facilite les comparaisons ; les valeurs
supérieures sont signalées ≥2 et conservées exactement au survol/tableau.
Les courbes comparatives utilisent également tirets, noms et légendes ; jamais
une distinction rouge/vert seule. Contraste à mesurer avant validation, pas
revendiqué uniquement parce qu'une palette paraît lisible.

Plotly : fond transparent, police héritée, axes avec unités, légendes simples,
pas de quadrillage lourd. Format FR : espaces pour milliers et virgule décimale,
avec libellés préformatés dans les tooltips ; EN traduit libellés et formats.

## Architecture de l'implémentation

```text
dashboard/
├── app.py
├── pages_or_tabs/{overview,map,peak_hours,weekend,communes,quality}.py
├── components/{filters,kpis,charts,formatting,i18n}.py
├── data/{database,queries,metadata}.py
├── data/sql/                       # SELECT paramétrés, agrégation PostgreSQL
├── assets/style.css
├── .streamlit/config.toml
├── Dockerfile
└── tests/
```

Le rôle traffic_dashboard garde SELECT seulement sur CORE/marts utiles ; droits
et utilisateur sont gérés hors dashboard via SQL/script d'installation. Pas de
nouveau schéma core : les tables CORE livrées restent dans public.
Connexion/pool sûr pour sessions concurrentes avec `st.cache_resource`, résultats
`st.cache_data` TTL, clés de cache comprenant les filtres et contrôle local de
l'invalidation. Pas de connexion transactionnelle unique partagée sans verrou.
Moyennes et p95 sont agrégés en SQL, pandas sert uniquement à organiser les
résultats pour l'affichage/CSV. Les marts complets ne suffisent pas à recalculer
un p95 arbitraire : les filtres combinés utilisent les faits.

Au premier chargement : spinner nommé. Après cache chaud : objectif <2 s par
navigation, mesuré sur chaque onglet. Une animation ne recharge pas tous les
onglets. Export volumineux déclenché explicitement, hors budget d'un simple
changement d'onglet. Erreurs SQL : message court + action Réessayer, aucune
trace brute affichée. Log technique côté serveur sans credentials.

## Vérification de cette étape et suite

Maquette confrontée aux DDL existants : champs population_density_per_km2,
tram_stations, primary_roads et attributs fact_travel_time disponibles ; géométrie
SRID 4326. Les quatre marts existent, mais les droits reader doivent être étendus
à SELECT sur ces tables lors de l'intégration. Inspection locale Streamlit 1.64.0 :
st.tabs possède key/on_change ; st.set_option ne permet pas de changer theme.base
en cours d'exécution. Ne pas utiliser cette fausse solution de bascule.

Références officielles consultées pour les thèmes et l'exécution différée :
[thèmes](https://docs.streamlit.io/develop/concepts/configuration/theming),
[config.toml](https://docs.streamlit.io/develop/api-reference/configuration/config.toml),
[layouts](https://docs.streamlit.io/develop/concepts/design/layouts-and-containers).

Un premier nom de fichier supposé `00_create_marts.sql` était absent ; lecture
corrigée sur le fichier réellement présent `sql/marts/00_tables.sql`. Aucun SQL
n'a été exécuté ni donnée modifiée. Étape suivante : implémentation modulaire,
puis migration du service Docker, tests, captures clair/sombre et README final.

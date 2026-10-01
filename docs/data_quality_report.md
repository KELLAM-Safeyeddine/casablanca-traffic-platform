# Qualité de la source — phase 2

Profilage effectué le 1 octobre 2026 sur la copie source immuable.
SHA-256 : `4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d`.
Notebook exécuté : `notebooks/02_source_profiling.ipynb` avec Python 3.11 dans CasaTraffic.
Les diagnostics sont reproductibles via `scripts/profile_workbook.py`.
Ce rapport décrit des observations et des règles candidates, aucun chargement métier.

## Inventaire et complétude

| Feuille | En-tête Excel | Lignes du corps | Communes manquantes avant propagation | Après propagation |
|---|---:|---:|---:|---:|
| Summary | Navigation | 0 mesure | — | — |
| Table 0. Coordinates | 12 | 110 | 88 | 0 |
| Table 1. Population size in eac | 10 | 22 | 0 | 0 |
| Table 2. Number of Tram and Bus | 10 | 22 | 0 | 0 |
| Table 3. Type of roads | 10 | 22 | 0 | 0 |
| Table 4. Land use variables | 10 | 22 | 0 | 0 |
| Table 5. Monday | 10 | 440 | 418 | 0 |
| Table 6. Tuesday | 12 | 440 | 418 | 0 |
| Table 7. Wednesday | 12 | 440 | 285 | 0 |
| Table. 8 Thursday | 12 | 440 | 418 | 0 |
| Table. 9 Friday | 12 | 440 | 418 | 0 |
| Table. 10 Saturday | 12 | 440 | 418 | 0 |
| Table. 11 Sunday | 12 | 440 | 418 | 0 |

Les 13 feuilles comprennent **12 tables et un sommaire**. Il n'existe pas de Table 12.
Les blocs d'heures M:AJ (temps) et AK:BH (TTI) contiennent exactement 0–23.
Les titres et descriptions fusionnés ne sont pas des lignes de données.
La propagation des communes et ZIP se limite aux plages fusionnées : un manque réel
hors de ces plages ne doit pas être remplacé par la commune précédente.

Résultats : 22 communes, 5 points par commune, 110 points, 440 trajets dirigés distincts,
3 080 lignes trajet/jour et **73 920 mesures horaires candidates**. Aucune clé candidate
(jour, origine normalisée, destination normalisée, heure) n'est manquante ou dupliquée.
Les 73 920 temps et TTI sont numériques, finis, non manquants et strictement positifs.
Les coordonnées sont des textes numériques. Les 880 formules par jour concatènent
les coordonnées E/I, soit 6 160 formules ; les champs F/G et J/K fournissent les
coordonnées nécessaires sans recalculer ces formules. Aucune erreur Excel typée détectée.

## Distances : unités mixtes et variation réelle de la source

Parmi les 3 080 lignes trajet/jour, **2 764** distances dépassent 100 et **316** sont déjà
en kilomètres. Appliquer la règle du plan : `distance_raw > 100 → /1000`, sinon conserver.
Exemple : Monday!L11 = 9954 devient 9,954 km. Les distances candidates vont de
**0,617 à 15,169 km**, médiane 2,892 km.

Après conversion, **254 trajets sur 440** ont plusieurs distances selon le jour :
186 ont une seule distance, 115 en ont 2, 81 en ont 3, 38 en ont 4, 17 en ont 5 et 3 en ont 6.
Cette variation ne se résout pas par la conversion d'unités. La cause n'est pas fournie.
Choix pour le futur modèle : `dim_trajectory.distance_km` prend la distance du lundi
comme référence déterministe ; conserver aussi la distance observée par jour dans les
faits et l'utiliser pour la vitesse. Ne pas écraser les distances sources par une moyenne.

## Temps : séparateur décimal perdu

**42 174 valeurs** sont de grands entiers (>=1000), uniquement du mardi au dimanche.
Exemple : Tuesday!M13 = 10283, alors que le TTI fourni AK13 vaut 1,0330855 et que la
distance est 9,954 km. Le candidat 10,283 minutes donne 10,283/9,954 = 1,0330855.
Monday!M11 = 12,583 est déjà un nombre décimal correctement stocké.

| Jour | Mesures | Temps à remettre à l'échelle |
|---|---:|---:|
| Lundi | 10 560 | 0 |
| Mardi | 10 560 | 6 921 |
| Mercredi | 10 560 | 7 027 |
| Jeudi | 10 560 | 7 061 |
| Vendredi | 10 560 | 7 081 |
| Samedi | 10 560 | 7 008 |
| Dimanche | 10 560 | 7 076 |

Règle candidate spécifique à cette version de source : un temps entier >=1000 est
divisé par 1000, avec conservation de `travel_time_raw` et d'un motif de correction.
Il ne s'agit pas d'une conversion déclarée de secondes vers minutes : la source dit
minutes. Les valeurs candidates vont de **1,017 à 27,383 min**, médiane 7,017 min,
p95 13,817 min. Aucun autre temps >100 ne reste sans candidat de correction.

28 743 des 42 174 valeurs ainsi corrigées concordent avec le diagnostic indépendant
`temps / distance_km` à 0,002 près. Cette concordance et l'échelle du lundi soutiennent
l'hypothèse du séparateur perdu. Les discordances restantes sont conservées, sans
reconstruire les temps à partir des TTI. Cette hypothèse doit être réexaminée pour
toute nouvelle source. La vitesse candidate va de 7,804 à 93,715 km/h.

## Indices de points incohérents entre tables

Table 0 possède les indices 0–109. Les trajets utilisent 110 indices distincts,
mais les cinq derniers sont **110–114**, à la place de **105–109** pour Moulay Youssef.
Le crosswalk établi par coordonnées à huit décimales est :

| Index des trajets | Index Table 0 |
|---:|---:|
| 110 | 105 |
| 111 | 106 |
| 112 | 107 |
| 113 | 108 |
| 114 | 109 |

140 lignes d'origine (20 par jour, soit 3 360 mesures) ont un index incompatible avec
Table 0. La correspondance géographique retrouve **100 %** des origines/destinations,
sans indice ambigu ni collision de coordonnées après arrondi. Les autres indices sont
inchangés. Utiliser ce crosswalk contrôlé ; une coordonnée inconnue ou ambiguë doit
aller en quarantine, sans soustraction globale de 5 sur les indices.

## TTI fourni, anomalie annoncée et TTI recalculé

Les maxima TTI horaires **ne suivent pas la suite 5, 6, …, 23 dans ce fichier**.
Le minimum fourni vaut 0,967785 et le maximum 7,688588 (heure 10). Les maxima par heure
sont consignés dans `docs/profiling/hourly_tti_diagnostics.csv`, après exclusion des
en-têtes. Une inclusion accidentelle de la ligne d'heures dans un calcul de maximum
pourrait produire une suite artificielle ; c'est une hypothèse de parsing, pas une
erreur de formule démontrée ici. Ne pas rejeter des cellules parce qu'elles sont égales à l'heure.

Les vraies alertes sont **34 TTI fournis <1** et **171 TTI fournis >5**.
Un seuil >5 sert au signalement et ne prouve pas à lui seul que le temps est invalide.
49 821 mesures sur 73 920 concordent avec `temps corrigé / distance_km` à 0,002 près,
ce qui suggère souvent une référence correspondant à 60 km/h. Le classeur ne déclare
pas cette référence et 24 099 cellules ne concordent pas : ne pas l'affirmer comme méthode source.

Référence choisie pour le projet : **minimum des temps valides corrigés sur les
168 heures de chaque trajet dirigé**, puis `tti = travel_time_min / reference_min`.
Elle est calculée indépendamment du TTI fourni et figée pour le simulateur.
C'est une approximation empirique de circulation fluide, pas une vérité terrain.

| Mesure | TTI fourni | TTI recalculé candidat |
|---|---:|---:|
| Minimum | 0,967785 | 1,000000 |
| Moyenne | 2,443970 | 1,323890 |
| Médiane | 2,413080 | 1,261519 |
| p95 | 3,620450 | 1,815377 |
| Maximum | 7,688588 | 4,548759 |

Écart `recalculé - fourni` : moyenne **−1,120080**.
Écart absolu : moyenne **1,125586**, p95 **2,097218**.
**70 810 mesures** ont un écart absolu >0,1. La forte différence vient notamment
du changement de référence ; elle ne signifie pas 70 810 erreurs de temps de trajet.
Conserver `tti_provided`, `tti`, `tti_delta`, la référence et les drapeaux de qualité.

## Attributs urbains et noms

Les couples commune/ZIP des tables 0–4 concordent exactement : aucune jointure perdue.
Les noms d'onglets sont tronqués ou ponctués différemment ; utiliser le numéro de table,
pas un nom reconstitué. « Thurday », « Satuday », « Descriprion » et « Secondery » sont
des fautes de libellés. Les noms de commune restent ceux de la source, sans correction
géographique inventée ni rapprochement flou. Pour les clés, normaliser Unicode,
espaces et casse, et garder le libellé original et le ZIP comme texte.

**14 populations et 14 nombres de ménages sont fractionnaires** : conserver les
valeurs numériques plutôt que les arrondir silencieusement. Elles peuvent être des
estimations issues d'un traitement géographique, mais le classeur ne l'établit pas.
Les surfaces de Table 4 sont explicitement en m² ; stations, routes et commerces sont
des comptes. Les longueurs de routes annoncées dans la description de Table 3 ne
figurent pas dans les colonnes : ne pas en inventer.

L'unité de Density n'est pas précisée. Pour **22 communes sur 22**, elle diffère de
`population / superficie_km²` de plus de 1. Conserver `density_source` avec unité
non confirmée ; proposer séparément `population_density_per_km2` dérivée, sans
écraser Density. Les deux valeurs ne sont pas interchangeables.

Coordonnées observées : latitude [33,481472 ; 33,647921], longitude
[−7,706392 ; −7,395306]. Une enveloppe géographique plausible vérifiera les valeurs
en phase 4 ; elle ne remplace pas une vérification de limites administratives.

## Outliers, traçabilité et limites

L'IQR signale 140 distances candidates sur 3 080 lignes, 959 temps candidats,
1 257 TTI fournis et 3 053 TTI recalculés sur 73 920 mesures. Ce sont des diagnostics
statistiques, pas des règles de suppression. Un TTI supérieur à sa borne IQR peut
être un épisode de congestion réel.

`docs/profiling/workbook_profile.json` contient le profil de chaque colonne et le
crosswalk. `measurement_diagnostics.parquet` conserve les 73 920 observations, valeurs
originales, propositions de conversion, clé source feuille/ligne/heure et drapeaux.
Les CSV quotidiens, horaires et exemples rendent les résultats faciles à inspecter.
Aucune écriture dans l'Excel, aucune suppression de ligne et aucune insertion dans
la base n'ont eu lieu pendant cette phase.

Les rejets et corrections seront tracés en phases 4–5. Les références empiriques
utilisent toute la semaine : pour un futur modèle prédictif, les recalculer sur
l'ensemble d'entraînement pour éviter une fuite de données. Le jeu ne fournit ni
date, ni historique, ni volume de véhicules, ni certitude sur l'échantillonnage.

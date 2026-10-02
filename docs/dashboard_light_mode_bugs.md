# Diagnostic du mode clair — 2 octobre 2026

## Reproduction avant correction

`docker compose up -d --build dashboard` : succès. Streamlit installé : **1.64.0**.
Le navigateur neuf affiche « Apparence : Clair » et `theme=light` dans l'URL.
Le fond personnalisé vaut `rgb(245, 247, 250)`, mais `.stApp` expose
`color-scheme: dark`. Les six onglets ont été capturés dans
`docs/screenshots/bug_light_before/`; les références sombres sont dans
`docs/screenshots/dark_before/`.

Le chemin demandé ⋮ → Settings est inaccessible avant correction :
`toolbarMode = "minimal"` et `#MainMenu { display: none }` cachent le menu.
La reproduction utilise donc le sélecteur existant de la barre latérale.
Ce sélecteur ne change **jamais** le thème natif Streamlit.

## Défauts observés et causes exactes

| Élément | Observation | Cause |
| --- | --- | --- |
| Tableaux des onglets Carte, Pointe, Communes, Qualité | Canvas sombre, en-têtes gris, cellules claires au milieu d'une page claire | `st.dataframe` utilise le thème natif sombre. Aucun Styler ne fixe ces couleurs. Le CSS ne peut pas recolorer son canvas. |
| Selectbox et multiselect | Les champs fermés ont été partiellement blanchis ; leurs menus et puces conservent la palette sombre | Les règles `.stApp` ne touchent pas les portails. Les règles de groupe recolorent seulement une partie des composants natifs. |
| Aides `help=` | Icônes presque invisibles sur la barre latérale claire | Icônes natives du thème sombre sur un fond remplacé par CSS. |
| Navigation entre onglets | Dégradé sombre des boutons de défilement sur fond clair | Décoration native sombre, indépendante des variables `--ct-*`. |
| Sliders, champs, boutons, expanders et bannières | Mélange de couleurs natives et de texte forcé par le sélecteur large `.stApp p, label, button` | Deux sources de thème ; le sélecteur global écrase des couleurs sémantiques natives. Certaines bannières restent lisibles, sans que cela valide toutes leurs variantes. |
| KPI | Les cartes suivent correctement le choix Apparence, mais pas un futur changement natif | `skin()` construit les variables une fois par exécution à partir de `session_state.appearance`. |
| Plotly | Le profil clair est lisible avec Apparence Clair ; son thème ne suit pas le menu natif | `show()` fixe le template et la couleur de police selon la session, pas selon le thème frontal. |
| Carte | Fond clair avec Apparence Clair, indépendant du thème natif | URL CARTO fixée côté Python selon la session. |
| Menu de thème | Inaccessible | Masquage CSS et configuration `minimal`. |

## Stratégie de correction

Une seule source : le thème natif sélectionné dans le menu Streamlit.
Conserver la palette sombre TOML et renforcer le contraste de la palette claire.
Supprimer les recolorations globales du mode clair ; conserver explicitement
les couleurs historiques en sombre avec `light-dark(currentColor, ...)`.
et faire suivre les cartes HTML au `color-scheme` natif avec des variables
CSS `light-dark()`. Les portails et les tableaux restent entièrement natifs.
Plotly utilise le thème frontal Streamlit ; PyDeck reçoit `map_style=None`,
ce qui sélectionne automatiquement les mêmes fonds CARTO clair/sombre.
Ne pas dépendre de `st.context.theme.type` pour les couleurs : sa documentation
installée signale un possible retard pendant un changement de thème.

Références : [thèmes Streamlit](https://docs.streamlit.io/develop/concepts/configuration/theming),
[contexte de thème](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.context).

Les modifications FR/EN et captures déjà présentes avant cette intervention
appartiennent au travail précédent ; elles ne sont pas des corrections de ce bug.

## Diagnostic complémentaire avant validation

Le DOM des menus de 1.64.0 utilise **React Aria** (`div[role=listbox]` et
`div[role=option]`), pas seulement les anciens portails BaseWeb. Leurs couleurs
doivent rester natives ; les recolorer par des variables de `:root` serait
incorrect car ce portail n'hérite pas du `color-scheme` de `.stApp`.

Le frontend installé confirme que `map_style=None` choisit les mêmes URL CARTO
selon le thème et que `theme="streamlit"` remet à jour les couleurs Plotly
côté navigateur. `st.context.theme` n'est utilisé que pour la compatibilité
du paramètre d'URL, jamais pour le rendu à chaud.

Autre défaut mesuré : l'accent clair initial `#087F8C` atteint **4,42:1** sur
`#F5F7FA`. Les graduations Plotly natives claires sont `rgb(128,132,149)`.
Les graduations sombres sont `rgb(230,234,241)`, à préserver exactement.
Les en-têtes canvas utilisent le texte natif à 60 % d'opacité : leur contraste
doit être testé après composition avec le fond, pas seulement en comparant
deux couleurs opaques.

Le menu de Streamlit 1.64 affiche directement **Theme → System / Light / Dark**,
sans sous-écran Settings. Ce chemin est utilisé pour les essais à chaud.

## Causes supplémentaires observées pendant les essais

- Les tooltips PyDeck ont des couleurs fixes par défaut : fond `#29323C`,
  texte `#A0A7B4`, même quand CARTO passe au clair. Le sélecteur public
  `.deck-tooltip` utilise désormais des variables à deux variantes ; les deux
  couleurs sombres mesurées restent exactement celles d'origine.
- Les tooltips Plotly utilisent aussi le gris natif clair à contraste trop
  faible. Les classes SVG publiques des graduations, labels et tooltips
  suivent une variable `light-dark()` ; le sombre conserve `#E6EAF1`.
- La barre de boutons Plotly conserve par défaut un fond noir à 50 % et des
  icônes blanches à 30 %/70 %, même en clair. Sa variante claire utilise
  blanc, gris lisible et accent ; ses valeurs sombres restent identiques.

## Décision utilisateur : priorité au sombre identique

L'utilisateur a choisi : **« Conserver le sombre identique et documenter cette
exception »**. Les puces de jours blanches sur cyan `#58CCD4` restent donc à
**1,91:1**. Les icônes Plotly inactives conservent également leur contraste
hérité, environ **2,58:1** selon la composition alpha du fond sombre, sous le
seuil UI de 3:1. Elles deviennent plus contrastées au survol/à l'activation.
Ces exceptions empêchent de déclarer le dashboard sombre entièrement conforme
WCAG AA. Les bordures décoratives ne sont pas utilisées comme seul indicateur.

La palette, les cartes KPI, les graphiques et les couleurs des tableaux/menus
sombres sont préservés. Le seul changement de commande visible est l'accès
au menu natif à la place du sélecteur Apparence désynchronisé : les captures
entières ne sont donc pas promises identiques pixel par pixel.

## Validation finale

Les six onglets ont été ouverts dans chaque mode, puis capturés avec une liste
ouverte. Les aides, tableaux, tooltips Plotly/PyDeck, expanders et export CSV
ont des captures complémentaires dans `light_after/` et `dark_after/`.
La carte et les tableaux ont été basculés via le menu natif sans appel de
rechargement de page. Les couleurs calculées du DOM sont enregistrées dans
[`dashboard_theme_observations.json`](dashboard_theme_observations.json).

La vérification porte sur les composants présents : le dashboard utilise
`st.dataframe`, les champs d'autocomplétion des filtres, les sliders, les onglets,
les expanders et les bannières info/succès. Il n'a pas de `st.table`, de radio
métier ou de champ texte libre supplémentaire. Les erreurs et sélections vides
restent couvertes par AppTest ; aucune panne de production n'a été provoquée.

Les couleurs principales/secondaires, les graduations, les tooltips et les
en-têtes canvas composés respectent les seuils testés. Exemples mesurés :
accent clair **4,73:1**, graduations claires **5,89:1**, tooltip de carte sombre
**5,37:1**. Les onze tests de thème contrôlent aussi l'absence de littéraux
couleur hors des variables CSS et la palette sombre historique.

Voir la [galerie de validation](dashboard_light_mode_validation.md).

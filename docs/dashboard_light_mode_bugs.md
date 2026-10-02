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
Conserver les palettes TOML existantes, supprimer les recolorations globales,
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

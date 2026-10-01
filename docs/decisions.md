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

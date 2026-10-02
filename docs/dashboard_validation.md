# Étape 5 — validation réelle du dashboard

Contrôles du 2 octobre 2026 sur le service Docker et les données chargées.

## Résultats

- Six onglets ouverts dans le navigateur, avec contenu effectivement affiché.
- Carte PostGIS rendue, lecture horaire passée de 00 h à 14 h, puis pause.
- Thèmes clair/sombre inspectés et palette Cividis activée dans la sidebar.
- Filtre week-end : 21 120 observations ; tous les jours : 73 920.
- Jours vides et communes vides : message explicite et paramètres `none`.
- Anfa seule : 3 360 observations ; plage 01–23 h : 3 220.
- Rechargement : commune, plage, thème, palette et onglet restaurés par l'URL.
- Réinitialisation : sept jours, toutes communes, 00–23 h ; préférences conservées.
- CSV téléchargé réellement : 73 920 lignes, 110 points, 440 trajets,
  sept jours/24 heures, aucune clé trajet/jour/heure dupliquée.
  Format UTF-8 BOM, séparateur point-virgule et virgule décimale.
  Preuve : `dashboard_export_validation.json` ; contrôle reproductible par
  `scripts/verify_dashboard_exports.py` après téléchargement du CSV.
- Quatre DAGs en succès et dernier audit passed affichés ; 485 événements
  quarantine, dont 314 réparables et 171 avertissements.

## Performance mesurée

Après une première visite des six onglets, trois répétitions : clic navigateur
jusqu'au contenu de la vue visible, temps des appels d'automatisation compris.
18 valeurs entre **0,179 et 0,477 seconde**. Les mesures individuelles et la
méthode sont dans `dashboard_ui_timings.json`. Le fond de carte Internet
n'entre pas dans cette mesure ; ce résultat local ne garantit pas une durée
universelle sur une autre machine/réseau ou sous forte concurrence.

## Tests et corrections

pytest CasaTraffic : **84 passed, 6 skipped** ; ruff check : **All checks passed**.
Avec PostgreSQL/PostGIS isolé : **87 passed, 3 skipped**, conteneur temporaire
supprimé et volumes de la plateforme conservés.
Les sauts correspondent aux trois tests Airflow exécutés dans Docker et aux
trois tests SQL nécessitant la base isolée. Le déploiement précédent a aussi
validé les huit requêtes SQL et l'absence de droits d'écriture en base réelle.

Quatre tests supplémentaires couvrent les dates UTC/absences, le maintien de
la navigation après synchronisation URL, les pannes du fragment animé et le
refus d'afficher un succès qualité lorsque les métadonnées sont anciennes.
Le test de panne a d'abord échoué : modification de `playing` après création
du widget. Un indicateur distinct interrompt désormais les nouvelles lectures
SQL du fragment ; le prochain rerun complet met la lecture en pause avant
création du widget. Après correction, les 28 tests des vues/contrats passent.

L'inspection a aussi corrigé l'opposition entre thème système et choix visuel,
le chevauchement titre/légende Plotly et les choix de carte/classement non traduits.
Les statuts qualité et dates sont présentés en français/anglais avec UTC explicite.

## Limite de vérification PNG

Le bouton natif Plotly produit la notification « Image download succeeded »
pour `casablanca_overview_hourly.png`. Le navigateur intégré ne remonte aucun
événement de téléchargement ni fichier PNG dans Downloads ; le contrôle de
téléchargement a expiré, alors que le CSV est bien récupéré.
La génération côté Plotly est observée, la récupération du fichier PNG dans
ce navigateur reste **non validée**. Utiliser un navigateur standard pour
ce téléchargement ; aucune dépendance serveur supplémentaire n'a été ajoutée.

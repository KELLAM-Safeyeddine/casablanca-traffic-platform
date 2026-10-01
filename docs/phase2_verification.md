# Phase 2 — vérifications du 1 octobre 2026

Commandes exécutées avec le venv CasaTraffic Python 3.11 :

```text
scripts/profile_workbook.py
code 0 : profils JSON des 13 feuilles, 73 920 diagnostics Parquet et 3 CSV d'audit

-m ipykernel install --prefix .\CasaTraffic --name casatraffic
kernel installé sous CasaTraffic/share/jupyter/kernels/casatraffic

scripts/build_profiling_notebook.py
code 0 : notebook créé

scripts/verify_phase2.py
OK notebook : 7 cellules exécutées, kernel CasaTraffic Python 3.11
OK 13 feuilles profilées, 22 communes, 110 points, 440 trajets, 73 920 mesures
OK 73 920 clés candidates uniques et complètes
OK source SHA-256 intact : 4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d

-m pytest -q
11 passed in 0.63s

-m ruff check .
All checks passed!

scripts/verify_phase1.py
4 services permanents healthy, airflow-init exited 0,
endpoints HTTP accessibles, PostGIS 3.5, Connection casatraffic fonctionnelle,
aucune erreur d'import DAG, source intacte en lecture seule dans Docker
```

Le premier lint a signalé E501 sur une ligne du générateur de notebook. La ligne
a été divisée, le notebook régénéré et exécuté, puis les tests et le lint relancés.
Le vérificateur ferme explicitement son kernel après exécution.

Le notebook n'utilise pas un Python global : la commande du kernelspec est comparée
à `sys.executable`, puis le notebook vérifie Python 3.11 et le préfixe CasaTraffic.
Le kernel local émet un avertissement sur son transport TCP non chiffré ; il ne
modifie pas le résultat des contrôles et le notebook a été exécuté jusqu'au bout.

Aucun enregistrement de l'Excel ni chargement métier pendant cette phase.
Les diagnostics conservent les valeurs originales et les candidats de correction.
Les faits en base et les quatre DAGs métier restent à implémenter aux phases suivantes.

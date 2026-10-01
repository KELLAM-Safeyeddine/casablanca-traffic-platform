# Phase 0 — vérifications du 1 octobre 2026

Commandes exécutées avec `CasaTraffic\Scripts\python.exe` :

```text
--version                         Python 3.11.0
-m pip install -r requirements.txt Successfully installed (code 0)
-m pip check                      No broken requirements found.
scripts/verify_phase0.py          OK cadrage et arborescence — phase 0 validée
-m ruff check .                   All checks passed!
```

Les douze dépendances directes épinglées sont présentes. Airflow est absent du venv.
Le dossier `CasaTraffic/` et `.env` sont ignorés par Git.
Le SHA-256 de la copie source est égal à celui du fichier original :
`4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d`.

Limitation de l'outil d'exécution : le bac à sable ne peut pas lancer l'interpréteur
Python 3.11 sous AppData (`Unable to create process`). Les commandes réussissent
hors du bac à sable, toujours via le venv CasaTraffic, sans installation globale.

Les tests métier et DAGs ne sont pas encore implémentés à cette phase.

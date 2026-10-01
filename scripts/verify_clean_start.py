"""Reproduire le premier démarrage dans un projet Compose et un volume isolés."""

import json
import os
import shutil
import socket
import subprocess
import sys
import uuid
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def free_ports() -> list[int]:
    """Réserver brièvement quatre ports différents pour le projet de test."""
    sockets = [socket.socket() for _ in range(4)]
    try:
        for handle in sockets:
            handle.bind(("127.0.0.1", 0))
        return [handle.getsockname()[1] for handle in sockets]
    finally:
        for handle in sockets:
            handle.close()


def main() -> None:
    """Conserver le rapport, supprimer exclusivement le projet Compose créé ici."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    project = "casatraffic-clean-" + uuid.uuid4().hex
    workspace = ROOT / ".validation" / project
    workspace.mkdir(parents=True)
    for directory in ("dags", "src", "sql"):
        shutil.copytree(ROOT / directory, workspace / directory,
                        ignore=shutil.ignore_patterns("__pycache__"))
    for directory in ("scripts", "data/source", "data/raw", "data/quarantine", "logs"):
        (workspace / directory).mkdir(parents=True, exist_ok=True)
    for filename in ("docker-compose.yml", ".env.example"):
        shutil.copyfile(ROOT / filename, workspace / filename)
    for filename in ("init_env.py", "init_postgres.sh"):
        shutil.copyfile(ROOT / "scripts" / filename, workspace / "scripts" / filename)
    source = "Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
    shutil.copyfile(ROOT / "data/source" / source, workspace / "data/source" / source)
    subprocess.run([sys.executable, str(workspace / "scripts/init_env.py")], check=True)
    content = (workspace / ".env").read_text(encoding="utf-8")
    for key, port in zip(("POSTGRES_PORT", "AIRFLOW_PORT", "METABASE_PORT", "DASHBOARD_PORT"),
                         free_ports(), strict=True):
        old = dotenv_values(workspace / ".env")[key]
        content = content.replace(f"{key}={old}", f"{key}={port}")
    (workspace / ".env").write_text(content, encoding="utf-8")
    environment = os.environ.copy()
    environment["COMPOSE_PROJECT_NAME"] = project
    environment["PYTHONUNBUFFERED"] = "1"
    command = ["docker", "compose", "-p", project]
    started = False
    try:
        started = True
        subprocess.run([*command, "up", "-d", "--no-build"], cwd=workspace,
                       env=environment, check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts/bootstrap_platform.py"),
                        "--workspace", str(workspace)], cwd=ROOT, env=environment, check=True)
        result = json.loads((workspace / "data/quarantine/bootstrap_verification.json").read_text())
        result["clean_compose_project"] = project
        result["fresh_volume"] = True
        (ROOT / "docs/phase10_clean_start.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("OK premier démarrage depuis un volume neuf et RAW vides", flush=True)
    finally:
        if started:
            assert project.startswith("casatraffic-clean-")
            assert workspace.parent == ROOT / ".validation"
            subprocess.run([*command, "down", "--volumes", "--remove-orphans"], cwd=workspace,
                           env=environment, check=True)
            print("OK projet de test supprimé ; plateforme originale conservée", flush=True)


if __name__ == "__main__":
    main()

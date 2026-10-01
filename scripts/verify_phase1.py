"""Contrôler la plateforme Docker démarrée sans exposer les secrets locaux."""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def compose(*arguments: str) -> str:
    """Exécuter la CLI Docker et propager ses erreurs."""
    result = subprocess.run(
        ["docker", "compose", *arguments], cwd=ROOT,
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    return result.stdout.strip()


def parse_import_errors(output: str) -> list[dict[str, object]]:
    """Lire le tableau JSON final en conservant les éventuelles erreurs d'import."""
    for position, character in enumerate(output):
        if character != "[":
            continue
        try:
            payload = json.loads(output[position:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            return payload
    raise ValueError("La CLI Airflow n'a pas renvoyé de tableau JSON valide")


def main() -> None:
    """Vérifier santé, migrations, PostGIS, imports DAG et montage source."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic avec Python 3.11")
    compose("config", "--quiet")
    running = set(compose("ps", "--status", "running", "--services").splitlines())
    for service in ("postgres", "airflow-webserver", "airflow-scheduler", "metabase"):
        if service not in running:
            raise RuntimeError(f"Service non démarré : {service}")
        container = compose("ps", "-q", service)
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container],
            check=True, capture_output=True, text=True,
        )
        if result.stdout.strip() != "healthy":
            raise RuntimeError(f"{service}: {result.stdout.strip()}")
        print(f"OK {service} healthy")
    init_id = compose("ps", "--all", "-q", "airflow-init")
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}} {{.State.ExitCode}}", init_id],
        check=True, capture_output=True, text=True,
    )
    if result.stdout.strip() != "exited 0":
        raise RuntimeError(f"airflow-init: {result.stdout.strip()}")
    print("OK airflow-init exited 0")
    settings = dotenv_values(ROOT / ".env")
    for port_key, path in (("AIRFLOW_PORT", "/health"), ("METABASE_PORT", "/api/health")):
        url = f"http://127.0.0.1:{settings[port_key]}{path}"
        with urllib.request.urlopen(url, timeout=20) as response:
            payload = json.load(response)
        if port_key == "AIRFLOW_PORT":
            for component in ("metadatabase", "scheduler"):
                if payload[component]["status"] != "healthy":
                    raise RuntimeError(f"Airflow {component}: {payload}")
        elif payload.get("status") != "ok":
            raise RuntimeError(f"Metabase: {payload}")
        print(f"OK {url}")
    sql = "SELECT PostGIS_Version();"
    spatial_version = compose(
        "exec", "-T", "postgres", "psql", "-U", "platform_admin",
        "-d", "traffic", "-At", "-c", sql,
    )
    print(f"OK PostGIS {spatial_version}")
    compose("exec", "-T", "airflow-scheduler", "airflow", "db", "check")
    imports = compose(
        "exec", "-T", "airflow-scheduler", "airflow", "dags", "list-import-errors",
        "--output", "json",
    )
    if parse_import_errors(imports):
        raise RuntimeError(f"Erreurs d'import DAG : {imports}")
    print("OK connexion métadonnées Airflow et aucune erreur d'import DAG")
    runtime_check = (
        "import sys; import pandas; import pyarrow; import openpyxl; "
        "import pandera.pandas; import sqlalchemy; import psycopg2; "
        "from airflow.hooks.base import BaseHook; "
        "assert sys.version_info[:2] == (3, 11); "
        "c = BaseHook.get_connection('casatraffic'); "
        "db = psycopg2.connect(host=c.host, port=c.port, dbname=c.schema, "
        "user=c.login, password=c.password); "
        "cur = db.cursor(); cur.execute('SELECT 1'); "
        "assert cur.fetchone() == (1,); db.close()"
    )
    compose("exec", "-T", "airflow-scheduler", "python", "-c", runtime_check)
    print("OK Python 3.11, bibliothèques runtime et Connection casatraffic")
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{json .Mounts}}",
         compose("ps", "-q", "airflow-scheduler")],
        check=True, capture_output=True, text=True,
    )
    mounts = json.loads(result.stdout)
    source = next(m for m in mounts if m["Destination"] == "/opt/airflow/data/source")
    if source["RW"]:
        raise RuntimeError("Le montage source doit être en lecture seule")
    print("OK source montée en lecture seule")
    source_hash = compose(
        "exec", "-T", "airflow-scheduler", "sha256sum",
        "/opt/airflow/data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx",
    ).split()[0]
    if source_hash != "4778abffbe3d7791afa58069fc8a98b6e89995174d4c64401d9367221c42d17d":
        raise RuntimeError("La source dans Docker diffère de l'original")
    print("OK SHA-256 source dans Docker")
    print("Phase 1 validée ; DAGs métier à implémenter en phases 3 à 7.")


if __name__ == "__main__":
    main()

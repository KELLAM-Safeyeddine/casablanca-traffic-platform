"""Exécuter pytest sur PostGIS isolé, avec secret éphémère et nettoyage garanti."""

import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import psycopg2
from psycopg2.extensions import make_dsn

ROOT = Path(__file__).resolve().parents[1]


def docker(*arguments: str) -> str:
    """Exécuter Docker sans inclure de mot de passe dans ses arguments."""
    result = subprocess.run(["docker", *arguments], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def main() -> None:
    """Créer un conteneur jetable distinct des services de la plateforme."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    name = "casatraffic-test-" + uuid.uuid4().hex
    database = "casatraffic_test_" + uuid.uuid4().hex
    password = secrets.token_urlsafe(32)
    started = False
    try:
        with TemporaryDirectory(prefix="casatraffic-test-") as directory:
            env_file = Path(directory) / "postgres.env"
            env_file.write_text(
                f"POSTGRES_USER=test_admin\nPOSTGRES_DB={database}\nPOSTGRES_PASSWORD={password}\n",
                encoding="utf-8",
            )
            docker("run", "--detach", "--name", name, "--env-file", str(env_file),
                   "--publish", "127.0.0.1::5432", "postgis/postgis:16-3.5")
            started = True
        ports = json.loads(docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", name))
        port = ports["5432/tcp"][0]["HostPort"]
        dsn = make_dsn(host="127.0.0.1", port=port, dbname=database,
                       user="test_admin", password=password)
        deadline = time.monotonic() + 90
        while True:
            try:
                with psycopg2.connect(dsn) as ready:
                    with ready.cursor() as query:
                        query.execute("SELECT PostGIS_Version()")
                        version = query.fetchone()[0]
                ready.close()
                break
            except psycopg2.OperationalError:
                if time.monotonic() > deadline:
                    raise RuntimeError("PostGIS temporaire indisponible après 90 s") from None
                time.sleep(1)
        print(f"OK PostGIS isolé {version}; conteneur={name}", flush=True)
        environment = os.environ.copy()
        environment["CASATRAFFIC_TEST_DSN"] = dsn
        result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                                env=environment, check=False)
        if result.returncode:
            raise RuntimeError(f"pytest intégration a échoué (code {result.returncode})")
    finally:
        if started:
            docker("rm", "--force", "--volumes", name)
            print("OK conteneur de test supprimé ; volumes de la plateforme conservés", flush=True)


if __name__ == "__main__":
    main()

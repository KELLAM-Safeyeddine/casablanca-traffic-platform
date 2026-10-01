"""Générer les secrets locaux dans .env sans écraser une configuration existante."""

import base64
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_NAMES = {
    "POSTGRES_PASSWORD", "AIRFLOW_DB_PASSWORD", "TRAFFIC_DB_PASSWORD",
    "METABASE_DB_PASSWORD", "AIRFLOW_WEBSERVER_SECRET_KEY", "AIRFLOW_ADMIN_PASSWORD",
}


def main() -> None:
    """Créer exclusivement .env, sans afficher les valeurs des secrets."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic avec Python 3.11")
    lines: list[str] = []
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        name = line.split("=", 1)[0]
        if name in SECRET_NAMES:
            line = f"{name}={secrets.token_hex(24)}"
        elif name == "AIRFLOW_FERNET_KEY":
            key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
            line = f"{name}={key}"
        lines.append(line)
    destination = ROOT / ".env"
    with destination.open("x", encoding="utf-8", newline="\n") as output:
        output.write("\n".join(lines) + "\n")
    destination.chmod(0o600)
    print(".env créé avec secrets aléatoires ; aucune valeur affichée.")


if __name__ == "__main__":
    main()

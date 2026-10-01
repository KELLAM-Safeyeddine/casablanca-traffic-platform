"""Construire les marts depuis CasaTraffic et les secrets locaux .env."""

import logging
import sys
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.load.marts import build_marts  # noqa: E402


def main() -> None:
    """Ouvrir une connexion locale, reconstruire et afficher uniquement les compteurs."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = dotenv_values(ROOT / ".env")
    database = psycopg2.connect(
        host="127.0.0.1",
        port=settings["POSTGRES_PORT"],
        dbname="traffic",
        user="traffic",
        password=settings["TRAFFIC_DB_PASSWORD"],
    )
    try:
        print(build_marts(database))
    finally:
        database.close()


if __name__ == "__main__":
    main()

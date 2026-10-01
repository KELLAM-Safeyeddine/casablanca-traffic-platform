"""Créer le compte SQL en lecture seule et compléter .env sans exposer les secrets."""

import secrets
import sys
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Configurer le dashboard sur un volume existant ou après un bootstrap neuf."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    env_path = ROOT / ".env"
    settings = dotenv_values(env_path)
    additions = []
    if not settings.get("DASHBOARD_DB_PASSWORD"):
        settings["DASHBOARD_DB_PASSWORD"] = secrets.token_urlsafe(32)
        additions.append(f"DASHBOARD_DB_PASSWORD={settings['DASHBOARD_DB_PASSWORD']}")
    if not settings.get("DASHBOARD_PORT"):
        additions.append("DASHBOARD_PORT=8501")
    if additions:
        with env_path.open("a", encoding="utf-8") as output:
            output.write("\n" + "\n".join(additions) + "\n")
    database = psycopg2.connect(host="127.0.0.1", port=settings["POSTGRES_PORT"],
                               dbname="traffic", user="platform_admin",
                               password=settings["POSTGRES_PASSWORD"])
    try:
        with database, database.cursor() as query:
            query.execute("SELECT 1 FROM pg_roles WHERE rolname='traffic_dashboard'")
            if query.fetchone() is None:
                query.execute("CREATE ROLE traffic_dashboard LOGIN")
            query.execute("ALTER ROLE traffic_dashboard PASSWORD %s",
                          (settings["DASHBOARD_DB_PASSWORD"],))
            query.execute("GRANT CONNECT ON DATABASE traffic TO traffic_dashboard")
            query.execute("GRANT USAGE ON SCHEMA public TO traffic_dashboard")
            query.execute("GRANT SELECT ON dim_commune, dim_point, dim_trajectory, "
                          "fact_travel_time TO traffic_dashboard")
    finally:
        database.close()
    print("OK compte traffic_dashboard : SELECT uniquement, secret dans .env")


if __name__ == "__main__":
    main()

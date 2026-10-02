"""Vérifier les lectures réelles du dashboard et ses droits sans modifier de données."""

import json
import sys
import time
import urllib.request
from pathlib import Path

import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.data.filters import Filters  # noqa: E402
from dashboard.data.queries import GROUPS, correlation_statement, statement  # noqa: E402


def main() -> None:
    """Contrôler toutes les variantes SQL avec le rôle reader réel, pas un mock."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    settings = dotenv_values(ROOT / ".env")
    database = psycopg2.connect(
        host="127.0.0.1",
        port=settings["POSTGRES_PORT"],
        dbname="traffic",
        user="traffic_dashboard",
        password=settings["DASHBOARD_DB_PASSWORD"],
    )
    result = {"sql_seconds": {}, "counts": {}}
    try:
        with database.cursor() as query:
            query.execute("SHOW default_transaction_read_only")
            assert query.fetchone()[0] == "on"
            query.execute("SELECT has_table_privilege(current_user, 'public.quarantine', 'SELECT')")
            assert query.fetchone()[0] is False
            query.execute(statement("catalog"))
            ids = tuple(sorted(row[0] for row in query.fetchall()))
            assert len(ids) == 22
            filters = Filters(ids)
            for kind in [*GROUPS, "coverage", "export"]:
                start = time.perf_counter()
                query.execute(statement(kind), filters.parameters())
                rows = query.fetchall()
                result["sql_seconds"][kind] = round(time.perf_counter() - start, 4)
                result["counts"][kind] = len(rows)
                assert rows, kind
            assert result["counts"]["export"] == 73920
            assert result["counts"]["points"] == 110
            for variable in ["population_density_per_km2", "tram_stations", "primary_roads"]:
                query.execute(correlation_statement(variable), filters.parameters())
                assert len(query.fetchall()) == 22
            query.execute(statement("points"), Filters((), ()).parameters())
            assert query.fetchall() == []
            try:
                query.execute("UPDATE public.fact_travel_time SET tti=tti WHERE false")
            except psycopg2.errors.ReadOnlySqlTransaction:
                result["write_denied"] = True
            else:
                raise AssertionError("Transaction d'écriture non bloquée")
    finally:
        database.rollback()
        database.close()
    with urllib.request.urlopen(
        f"http://127.0.0.1:{settings['DASHBOARD_PORT']}/_stcore/health", timeout=5
    ) as response:
        assert response.read().decode() == "ok"
    metadata = json.loads(
        (ROOT / "data/monitoring/dashboard_status.json").read_text(encoding="utf-8")
    )
    assert metadata["available"] and metadata["quarantine"]["total"] == 485
    result["metadata"] = metadata
    result["readonly_role"] = "traffic_dashboard"
    (ROOT / "docs/dashboard_deployment.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "metadata"}, indent=2))
    print("OK dashboard healthy, 110 points, 73920 faits, métadonnées et refus d'écriture")


if __name__ == "__main__":
    main()

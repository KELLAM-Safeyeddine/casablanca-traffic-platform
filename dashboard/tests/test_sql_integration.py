"""Exécuter les requêtes dashboard sur PostGIS temporaire, jamais sur traffic."""

import os
from pathlib import Path

import pandas as pd
import psycopg2
import pytest
from psycopg2.extensions import parse_dsn

from dashboard.data.filters import Filters
from dashboard.data.queries import GROUPS, correlation_statement, statement
from src.extract.excel_reader import extract_sheet, verify_raw
from src.extract.flow_simulator import replay_hour
from src.load.warehouse import bootstrap_warehouse, load_partition

ROOT = Path(__file__).parents[2]


@pytest.mark.integration
def test_sql_groups_exact_percentile_bound_filters_and_readonly(tmp_path: Path) -> None:
    """Vérifier toutes les variantes SQL et la parité avec les 440 faits tests."""
    dsn = os.environ.get("CASATRAFFIC_TEST_DSN")
    if not dsn:
        pytest.skip("PostGIS isolé requis : scripts/run_integration_tests.py")
    assert parse_dsn(dsn)["dbname"].startswith("casatraffic_test_")
    source = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
    database = psycopg2.connect(dsn)
    try:
        bootstrap_warehouse(source, tmp_path, database, "dashboard_test", 0.01)
        points = verify_raw(extract_sheet(source, tmp_path, 0))
        load_partition(replay_hour(source, tmp_path, 0), points, database, "dashboard_test", 0.01)
        with database, database.cursor() as query:
            for file in ["00_tables.sql", "04_commune_features.sql"]:
                query.execute((ROOT / "sql/marts" / file).read_text(encoding="utf-8"))
        database.set_session(readonly=True)
        with database.cursor() as query:
            query.execute(statement("catalog"))
            catalog = tuple(sorted(row[0] for row in query.fetchall()))
            filters = Filters(catalog, (1,), (0, 0))
            for kind in [*GROUPS, "export", "coverage"]:
                query.execute(statement(kind), filters.parameters())
                assert query.fetchall(), kind
            query.execute(statement("export"), filters.parameters())
            facts = pd.DataFrame(query.fetchall(), columns=[c.name for c in query.description])
            query.execute(statement("summary"), filters.parameters())
            summary = dict(zip([c.name for c in query.description], query.fetchone(), strict=True))
            assert summary["measurement_count"] == len(facts) == 440
            assert summary["tti_mean"] == pytest.approx(facts.tti.mean(), rel=1e-12)
            assert summary["tti_p95"] == pytest.approx(facts.tti.quantile(0.95), rel=1e-12)
            for variable in ["population_density_per_km2", "tram_stations", "primary_roads"]:
                query.execute(correlation_statement(variable), filters.parameters())
                assert len(query.fetchall()) == 22
            query.execute(statement("points"), Filters((), ()).parameters())
            assert query.fetchall() == []
            with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
                query.execute("UPDATE fact_travel_time SET tti=tti WHERE false")
    finally:
        database.rollback()
        database.close()

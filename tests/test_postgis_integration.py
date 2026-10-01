"""Une tranche de 440 mesures teste réellement RAW → quarantaine → SQL CORE."""

import hashlib
import os
from pathlib import Path

import psycopg2
import pytest
from psycopg2.extensions import parse_dsn

from src.extract.excel_reader import (
    METADATA_COLUMNS,
    extract_sheet,
    verify_raw,
    write_immutable_parquet,
)
from src.extract.flow_simulator import replay_hour
from src.load import warehouse

pytestmark = pytest.mark.integration
SOURCE = Path(__file__).resolve().parents[1] / "data/source/" \
    "Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"


@pytest.fixture(scope="module")
def isolated_warehouse(tmp_path_factory):
    """Refuser tout accès aux bases applicatives ; initialiser un modèle neuf."""
    dsn = os.environ.get("CASATRAFFIC_TEST_DSN")
    if not dsn:
        pytest.skip("Lancer scripts/run_integration_tests.py pour PostGIS isolé")
    if not parse_dsn(dsn)["dbname"].startswith("casatraffic_test_"):
        pytest.fail("Les tests exigent une base casatraffic_test_ isolée")
    database = psycopg2.connect(dsn)
    raw_root = tmp_path_factory.mktemp("integration_raw")
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    dimensions = warehouse.bootstrap_warehouse(SOURCE, raw_root, database, "test_bootstrap", .01)
    assert dimensions == {"dim_commune": 22, "dim_point": 110,
                          "dim_time": 168, "dim_trajectory": 440}
    points = verify_raw(extract_sheet(SOURCE, raw_root, 0))
    yield database, raw_root, points
    database.close()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash


def business_snapshot(database) -> list[tuple]:
    """Comparer tout STAGING/CORE y compris les valeurs, pas uniquement les comptes."""
    result = []
    with database.cursor() as query:
        for table in ("staging.travel_time", "public.fact_travel_time"):
            query.execute(f"SELECT count(*), md5(string_agg(h, '' ORDER BY h)) "
                          f"FROM (SELECT md5(row_to_json(t)::text) h FROM {table} t) q")
            result.append(query.fetchone())
    database.commit()
    return result


def test_partition_idempotence_and_explicit_quarantine(isolated_warehouse, tmp_path: Path) -> None:
    database, raw_root, points = isolated_warehouse
    path = replay_hour(SOURCE, raw_root, 0)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    first = warehouse.load_partition(path, points, database, "first", .01)
    assert first["loaded"] == 440 and first["rejected"] == 0
    before = business_snapshot(database)
    warehouse.load_partition(path, points, database, "repeat", .01)
    assert business_snapshot(database) == before
    raw = verify_raw(path)
    damaged = raw.drop(columns=list(METADATA_COLUMNS)).copy()
    damaged.loc[0, "travel_time_raw"] = -1.0
    rejected = write_immutable_parquet(damaged, tmp_path / "damaged.parquet",
                                      raw["_source_file"].iloc[0], raw["_sheet"].iloc[0],
                                      raw["_source_sha256"].iloc[0])
    summary = warehouse.load_partition(rejected, points, database, "reject_test", .01)
    assert summary["loaded"] == 439 and summary["rejected"] == 1
    with database.cursor() as query:
        query.execute("SELECT reason, raw_payload FROM quarantine WHERE severity='rejected' "
                      "AND excel_row=%s AND hour=0", (int(raw.loc[0, "_excel_row"]),))
        events = query.fetchall()
    assert events and all(event[1]["travel_time_raw"] == -1 for event in events)
    warehouse.load_partition(path, points, database, "restore_test", .01)
    assert business_snapshot(database) == before
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_sql_failure_rolls_back_staging_and_core(
    isolated_warehouse, tmp_path: Path, monkeypatch,
) -> None:
    database, raw_root, points = isolated_warehouse
    path = replay_hour(SOURCE, raw_root, 1)
    warehouse.load_partition(path, points, database, "before_failure", .01)
    before = business_snapshot(database)
    sql_path = tmp_path / "sql/ddl/04_partition_to_core.sql"
    sql_path.parent.mkdir(parents=True)
    sql_path.write_text((warehouse.ROOT / "sql/ddl/04_partition_to_core.sql").read_text(
        encoding="utf-8") + "\nSELECT 1/0;\n", encoding="utf-8")
    monkeypatch.setattr(warehouse, "ROOT", tmp_path)
    with pytest.raises(psycopg2.errors.DivisionByZero):
        warehouse.load_partition(path, points, database, "sql_failure", .01)
    assert business_snapshot(database) == before

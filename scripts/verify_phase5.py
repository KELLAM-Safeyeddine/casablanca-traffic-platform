"""Prouver le chargement réel et l'idempotence du modèle STAGING/CORE."""

import json
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import psycopg2
from dotenv import dotenv_values
from psycopg2.extensions import connection

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_phase3 import api, fingerprint, run_dag  # noqa: E402
from src.extract.excel_reader import extract_workbook, source_digest, verify_raw  # noqa: E402
from src.extract.flow_simulator import replay_hour  # noqa: E402
from src.extract.workbook_profile import SOURCE_SHA256  # noqa: E402
from src.load.warehouse import initialize_warehouse, load_partition  # noqa: E402

TABLES = {
    "dim_commune": 22,
    "dim_point": 110,
    "dim_time": 168,
    "dim_trajectory": 440,
    "fact_travel_time": 73920,
    "staging.travel_time": 73920,
}


def snapshot(database: connection) -> dict:
    """Hacher tout le contenu métier, pas seulement le nombre de lignes."""
    state = {}
    with database.cursor() as query:
        for table in TABLES:
            query.execute(
                f"SELECT count(*), md5(string_agg(hash, '' ORDER BY hash)) "
                f"FROM (SELECT md5(row_to_json(t)::text) AS hash FROM {table} t) hashes"
            )
            count, digest = query.fetchone()
            state[table] = {"rows": count, "digest": digest}
    return state


def metrics(database: connection) -> dict:
    """Vérifier les corrections, formules et géométries effectivement stockées."""
    with database.cursor() as query:
        query.execute("""SELECT count(*) FILTER (WHERE time_scaled),
            count(*) FILTER (WHERE distance_scaled), count(*) FILTER (WHERE index_repaired),
            count(*) FILTER (WHERE tti_provided < 1), count(*) FILTER (WHERE tti_gap_flag),
            min(tti), avg(tti), max(tti), avg(abs(tti_delta)),
            count(*) FILTER (WHERE abs(tti - travel_time_min / free_flow_reference_min) > 1e-12
              OR abs(speed_kmh - 60 * distance_observed_km / travel_time_min) > 1e-12)
            FROM public.fact_travel_time""")
        values = query.fetchone()
        result = dict(
            zip(
                [
                    "time_scaled",
                    "distance_scaled",
                    "index_repaired",
                    "source_tti_below_one",
                    "tti_gap_flag",
                    "tti_min",
                    "tti_mean",
                    "tti_max",
                    "mean_abs_tti_delta",
                    "formula_errors",
                ],
                values,
                strict=True,
            )
        )
        query.execute(
            "SELECT count(*) FROM public.dim_point WHERE ST_SRID(geom)=4326 "
            "AND ST_X(geom)=lon AND ST_Y(geom)=lat AND ST_IsValid(geom)"
        )
        result["valid_geometries"] = query.fetchone()[0]
        query.execute(
            "SELECT count(*) FROM (SELECT trajectory_id FROM public.fact_travel_time "
            "GROUP BY trajectory_id HAVING count(DISTINCT distance_observed_km)>1) t"
        )
        result["trajectories_with_variable_distance"] = query.fetchone()[0]
        query.execute(
            "SELECT count(*) FROM public.quarantine WHERE source_sha256=%s", (SOURCE_SHA256,)
        )
        result["quarantine_events"] = query.fetchone()[0]
    assert result["time_scaled"] == 42174 and result["distance_scaled"] == 66336
    assert result["index_repaired"] == 3360 and result["source_tti_below_one"] == 34
    assert result["tti_gap_flag"] == 70810 and result["formula_errors"] == 0
    assert result["valid_geometries"] == 110 and result["quarantine_events"] == 485
    assert result["trajectories_with_variable_distance"] == 254
    assert result["tti_min"] == 1 and np.isclose(result["tti_mean"], 1.323890, atol=1e-6)
    return result


def verify_rollback(database: connection, source: Path, paths: list[Path]) -> None:
    """Injecter un échec après les DELETE/INSERT puis vérifier le rollback complet."""
    before = snapshot(database)
    path = replay_hour(source, ROOT / "data/raw", 0)
    with TemporaryDirectory(prefix="phase5_sql_") as temporary:
        directory = Path(temporary)
        (directory / "sql/ddl").mkdir(parents=True)
        statement = (ROOT / "sql/ddl/04_partition_to_core.sql").read_text(encoding="utf-8")
        (directory / "sql/ddl/04_partition_to_core.sql").write_text(
            statement + "\nSELECT 1 / 0;\n", encoding="utf-8"
        )
        with patch("src.load.warehouse.ROOT", directory):
            try:
                load_partition(path, verify_raw(paths[1]), database, "phase5_rollback_probe", 0.01)
            except psycopg2.errors.DivisionByZero:
                pass
            else:
                raise AssertionError("La panne SQL injectée devait interrompre la transaction")
    assert snapshot(database) == before
    print("OK panne SQL injectée : rollback STAGING/CORE, contenu intégral conservé", flush=True)


def main() -> None:
    """Exécuter full/full/replay/replay et comparer chaque snapshot complet."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    settings = dotenv_values(ROOT / ".env")
    database = psycopg2.connect(
        host="127.0.0.1",
        port=settings["POSTGRES_PORT"],
        dbname="traffic",
        user="traffic",
        password=settings["TRAFFIC_DB_PASSWORD"],
    )
    try:
        initialize_warehouse(database)
        source = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
        paths = extract_workbook(source, ROOT / "data/raw")
        immutable = fingerprint(paths)
        initial = snapshot(database)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            tasks = api("dags/ingest_traffic/tasks")["tasks"]
            if {"bootstrap_model", "load_traffic"}.issubset({task["task_id"] for task in tasks}):
                break
            time.sleep(3)
        else:
            raise TimeoutError("Le DAG de phase 5 n'est pas encore sérialisé")
        api("dags/ingest_traffic", "PATCH", {"is_paused": False})
        runs = [run_dag({"mode": "full"}, "phase5")]
        first = snapshot(database)
        assert {table: state["rows"] for table, state in first.items()} == TABLES
        print(
            "OK CORE : 22 communes, 110 points, 168 heures, 440 trajets, 73 920 faits", flush=True
        )
        for conf in (
            {"mode": "full"},
            {"mode": "replay", "tick": 0},
            {"mode": "replay", "tick": 168},
        ):
            run = run_dag(conf, "phase5")
            mapped = [task for task in run["tasks"] if task["task_id"] == "load_traffic"]
            assert len(mapped) == (7 if conf["mode"] == "full" else 1)
            runs.append(run)
            assert snapshot(database) == first
        measurements = metrics(database)
        verify_rollback(database, source, paths)
        assert fingerprint(paths) == immutable and source_digest(source) == SOURCE_SHA256
        report = {
            "initial": initial,
            "final": first,
            "metrics": measurements,
            "idempotent_content": True,
            "source_and_raw_unchanged": True,
            "runs": runs,
            "rollback_verified": True,
        }
        report_path = ROOT / "docs/phase5_runs.json"
        if report_path.exists():
            previous = json.loads(report_path.read_text(encoding="utf-8"))
            report["initial"] = previous["initial"]
            report["runs"] = previous["runs"] + runs
        (ROOT / "docs/phase5_runs.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            "OK quatre runs réels en succès, contenu complet inchangé après relance/rejeu",
            flush=True,
        )
        print(json.dumps(measurements, ensure_ascii=False), flush=True)
    finally:
        database.close()


if __name__ == "__main__":
    main()

"""Vérifier pandera, quarantine PostgreSQL et runs Airflow idempotents."""

import json
import sys
from pathlib import Path

import psycopg2
from dotenv import dotenv_values
from psycopg2.extensions import connection

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.verify_phase3 import api, fingerprint, run_dag  # noqa: E402
from src.extract.excel_reader import extract_workbook, source_digest, verify_raw  # noqa: E402
from src.extract.workbook_profile import SOURCE_SHA256  # noqa: E402
from src.load.quarantine import initialize_quarantine, persist_events  # noqa: E402
from src.validate.quality import enforce_threshold, validate_table  # noqa: E402


def quarantine_counts(database: connection) -> dict[str, int]:
    """Compter seulement les événements de la source de production."""
    with database.cursor() as cursor:
        cursor.execute("SELECT severity, count(*) FROM public.quarantine "
                       "WHERE source_sha256 = %s GROUP BY severity", (SOURCE_SHA256,))
        return dict(cursor.fetchall())


def main() -> None:
    """Valider, persister deux fois puis exécuter full/full/replay via le scheduler."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    settings = dotenv_values(ROOT / ".env")
    database = psycopg2.connect(host="127.0.0.1", port=settings["POSTGRES_PORT"],
                                dbname="traffic", user="traffic",
                                password=settings["TRAFFIC_DB_PASSWORD"])
    try:
        initialize_quarantine(database)
        source = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
        paths = extract_workbook(source, ROOT / "data/raw")
        immutable = fingerprint(paths)
        points = verify_raw(paths[1])
        results = [validate_table(verify_raw(path), points) for path in paths]
        summaries = [result.summary for result in results]
        events = [event for result in results for event in result.events]
        totals = {key: sum(summary[key] for summary in summaries if
                           summary["table_number"] is not None and summary["table_number"] >= 5)
                  for key in ("total", "valid", "repairable", "rejected")}
        assert totals == {"total": 73920, "valid": 70557, "repairable": 3363, "rejected": 0}
        assert len(events) == 485
        for summary in summaries:
            assert summary["total"] == sum(summary[key] for key in
                                           ("valid", "repairable", "rejected"))
            enforce_threshold(summary, 0.01)
        persist_events(database, events, "phase4_local_first")
        before = quarantine_counts(database)
        persist_events(database, events, "phase4_local_second")
        assert quarantine_counts(database) == before == {"repairable": 314, "warning": 171}
        print("OK 73 920 mesures réconciliées ; 485 événements en quarantine, upsert stable",
              flush=True)
        api("dags/ingest_traffic", "PATCH", {"is_paused": False})
        runs = [run_dag({"mode": "full"}, "phase4"), run_dag({"mode": "full"}, "phase4"),
                run_dag({"mode": "replay", "tick": 0}, "phase4")]
        for run in runs:
            mapped = [task for task in run["tasks"] if task["task_id"] == "validate_traffic"]
            assert len(mapped) == (7 if run["conf"]["mode"] == "full" else 1)
            assert any(task["task_id"] == "validate_static" for task in run["tasks"])
        assert quarantine_counts(database) == before
        assert fingerprint(paths) == immutable
        assert source_digest(source) == SOURCE_SHA256
        report = {"source_sha256": SOURCE_SHA256, "traffic_totals": totals,
                  "table_summaries": summaries, "quarantine_counts": before,
                  "idempotence": True, "source_and_raw_unchanged": True, "runs": runs}
        (ROOT / "docs/phase4_runs.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("OK trois runs Airflow qualité en succès ; quarantine stable, RAW/source intacts",
              flush=True)
    finally:
        database.close()


if __name__ == "__main__":
    main()

"""Prouver le RAW immuable et le mapping via le scheduler Airflow réel."""

import base64
import hashlib
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pandas as pd
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.extract.excel_reader import extract_workbook, source_digest, verify_raw  # noqa: E402
from src.extract.flow_simulator import replay_hour  # noqa: E402
from src.extract.workbook_profile import SOURCE_SHA256  # noqa: E402


def fingerprint(paths: list[Path]) -> dict[str, str]:
    """Empreintes binaires, incluant les horodatages persistés."""
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths}


def api(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    """Appeler l'API locale sans écrire les secrets dans le rapport."""
    settings = dotenv_values(ROOT / ".env")
    credentials = f"{settings['AIRFLOW_ADMIN_USERNAME']}:{settings['AIRFLOW_ADMIN_PASSWORD']}"
    request = urllib.request.Request(
        f"http://127.0.0.1:{settings['AIRFLOW_PORT']}/api/v1/{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode(),
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def run_dag(conf: dict, phase: str = "phase3") -> dict:
    """Déclencher un run et attendre ses tâches effectivement exécutées."""
    run_id = phase + "_" + uuid.uuid4().hex
    prefix = "dags/ingest_traffic/dagRuns"
    api(prefix, "POST", {"dag_run_id": run_id, "conf": conf})
    deadline = time.monotonic() + 480
    previous = None
    while time.monotonic() < deadline:
        run = api(f"{prefix}/{run_id}")
        state = run["state"]
        if state != previous:
            print(f"Airflow {run_id}: {state}", flush=True)
            previous = state
        if state in {"success", "failed"}:
            instances = api(f"{prefix}/{run_id}/taskInstances")["task_instances"]
            if state != "success" or any(item["state"] != "success" for item in instances):
                raise RuntimeError(f"Run échoué : {run_id}, tâches={instances}")
            mapped = [item for item in instances if item["task_id"] == "extract_partition"]
            expected = 7 if conf["mode"] == "full" else 1
            assert sorted(item["map_index"] for item in mapped) == list(range(expected))
            return {"run_id": run_id, "conf": conf, "state": state,
                    "start_date": run["start_date"], "end_date": run["end_date"],
                    "mapped_tasks": expected,
                    "tasks": [{key: item[key] for key in
                               ("task_id", "map_index", "state", "start_date", "end_date")}
                              for item in instances]}
        time.sleep(3)
    raise TimeoutError(f"Run Airflow trop long : {run_id}")


def main() -> None:
    """Contrôler 13 tables, 168 tranches, puis deux runs complets et deux rejeux."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    source = ROOT / "data/source/Dataset_for_traffic_analysis_in_Casablanca__Morocco.xlsx"
    raw = ROOT / "data/raw"
    paths = extract_workbook(source, raw)
    before = fingerprint(paths)
    assert len(paths) == 13
    assert [len(verify_raw(path)) for path in paths] == [17, 110, *([22] * 4), *([440] * 7)]
    assert fingerprint(extract_workbook(source, raw)) == before
    print("OK 13 feuilles RAW, seconde extraction identique octet par octet", flush=True)
    replay_paths = []
    for tick in range(168):
        replay_paths.append(replay_hour(source, raw, tick))
    frames = [verify_raw(path) for path in replay_paths]
    replay = pd.concat(frames, ignore_index=True)
    assert len(replay) == 73920
    assert not replay.duplicated(["day_of_week", "hour", "_excel_row"]).any()
    for tick, frame in enumerate(frames):
        daily = verify_raw(paths[6 + tick // 24])
        pd.testing.assert_series_equal(frame["travel_time_raw"], daily[f"time_{tick % 24:02d}"],
                                       check_names=False)
        pd.testing.assert_series_equal(frame["tti_provided"], daily[f"tti_{tick % 24:02d}"],
                                       check_names=False)
    replay_before = fingerprint(replay_paths)
    assert replay_hour(source, raw, 168) == replay_paths[0]
    assert fingerprint(replay_paths) == replay_before
    print("OK 168 tranches de 440 lignes, 73 920 mesures brutes, boucle idempotente", flush=True)
    api("dags/ingest_traffic", "PATCH", {"is_paused": False})
    runs = [run_dag({"mode": "full"}), run_dag({"mode": "full"}),
            run_dag({"mode": "replay", "tick": 0}),
            run_dag({"mode": "replay", "tick": 168})]
    assert fingerprint(paths) == before
    assert fingerprint(replay_paths) == replay_before
    assert source_digest(source) == SOURCE_SHA256
    report = {"source_sha256": SOURCE_SHA256, "raw_files": before,
              "replay_partitions": 168, "replay_rows": len(replay),
              "immutable_raw": True, "runs": runs}
    (ROOT / "docs/phase3_runs.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("OK quatre runs réels réussis ; RAW et source inchangés", flush=True)


if __name__ == "__main__":
    main()

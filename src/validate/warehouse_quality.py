"""Contrôle RAW et CORE cohérent avant publication aux consommateurs."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from psycopg2.extensions import connection

from src.extract.excel_reader import extract_workbook, verify_raw
from src.validate.normalized import normalized_schema
from src.validate.pipeline import safe_run_name, validate_partition
from src.validate.schemas import validation_view

EXPECTED = {"dim_commune": 22, "dim_point": 110, "dim_time": 168,
            "dim_trajectory": 440, "fact_travel_time": 73920}


def check_core_frame(frame: pd.DataFrame) -> None:
    """Vérifier grain, bornes, cardinalité et formules indépendamment du SQL de load."""
    schema = normalized_schema(core=True)
    schema.validate(validation_view(frame, schema), lazy=True)
    if len(frame) != EXPECTED["fact_travel_time"]:
        raise ValueError(f"CORE incomplet : {len(frame)} mesures, attendu 73920")
    comparisons = {
        "tti": frame.travel_time_min / frame.reference_min,
        "speed_kmh": frame.distance_km / frame.travel_time_min * 60,
        "free_flow_reference_min": frame.reference_min,
        "tti_delta": frame.tti - frame.tti_provided,
    }
    for column, expected in comparisons.items():
        if not np.isclose(frame[column], expected, rtol=1e-12, atol=1e-12).all():
            raise ValueError(f"Formule CORE incohérente : {column}")


def warehouse_quality(
    database: connection, source: Path, raw_root: Path, run_id: str,
    threshold: float, reports: Path,
) -> dict[str, Any]:
    """Valider toutes les sources puis contrôler un snapshot CORE verrouillé."""
    paths = extract_workbook(source, raw_root)
    points = verify_raw(paths[1])
    destination = reports / safe_run_name(run_id)
    summaries = [validate_partition(path, points, database, run_id, threshold, destination)
                 for path in paths]
    with database, database.cursor() as query:
        query.execute("LOCK TABLE fact_travel_time, dim_commune, dim_point, "
                      "dim_time, dim_trajectory IN SHARE MODE")
        counts = {}
        for table, expected in EXPECTED.items():
            # Noms issus exclusivement de la constante interne EXPECTED.
            query.execute(f"SELECT count(*) FROM public.{table}")
            counts[table] = query.fetchone()[0]
            if counts[table] != expected:
                raise ValueError(f"{table}: {counts[table]}, attendu {expected}")
        query.execute("SELECT f.*, t.origin_point_id, t.dest_point_id, "
                      "t.free_flow_reference_min reference_min, "
                      "f.distance_observed_km distance_km FROM fact_travel_time f "
                      "JOIN dim_trajectory t USING (trajectory_id)")
        frame = pd.DataFrame(query.fetchall(), columns=[col.name for col in query.description])
        check_core_frame(frame)
    result = {"run_id": run_id, "status": "passed", "counts": counts,
              "raw_partitions": len(paths), "raw_summaries": summaries,
              "tti_gap_count": int(frame.tti_gap_flag.sum())}
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "warehouse_quality.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result

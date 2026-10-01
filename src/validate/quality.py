"""Collecter les anomalies et réconcilier chaque ligne/heure, sans suppression."""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import pandera.pandas as pa

from src.extract.workbook_profile import SOURCE_SHA256, coordinate_key, table_number
from src.validate.schemas import source_schema, validation_view

LOGGER = logging.getLogger(__name__)
KNOWN_POINT_REPAIRS = {110: 105, 111: 106, 112: 107, 113: 108, 114: 109}


@dataclass
class ValidationResult:
    """Résultat réconcilié : RAW complet, événements et compteurs par mesure."""

    summary: dict[str, Any]
    events: list[dict[str, Any]]


def raw_payload(row: pd.Series) -> dict[str, Any]:
    """Encoder les valeurs brutes en JSON strict, y compris NaN et infinis."""
    payload = {}
    for key, value in row.items():
        if value is None or value is pd.NA or value is pd.NaT:
            value = None
        elif isinstance(value, pd.Timestamp):
            value = value.isoformat()
        elif isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            value = str(value)  # conserver le diagnostic sans JSON NaN non standard
        payload[str(key)] = value
    return payload


def event_for(
    frame: pd.DataFrame,
    index: int,
    column: str,
    reason: str,
    severity: str = "rejected",
    hour: int = -1,
) -> dict[str, Any]:
    """Identifier stablement une anomalie par source, ligne, heure, règle et colonne."""
    row = frame.iloc[index]
    if hour >= 0 and column in {"tti_provided", "travel_time_raw"}:
        column = f"{'tti' if column == 'tti_provided' else 'time'}_{hour:02d}"
    identity = [
        str(row["_source_sha256"]),
        str(row["_sheet"]),
        int(row["_excel_row"]),
        hour,
        column,
        reason,
        severity,
    ]
    event_id = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
    return {
        "event_id": event_id,
        "source_sha256": identity[0],
        "source_file": row["_source_file"],
        "sheet": identity[1],
        "excel_row": identity[2],
        "hour": hour,
        "column_name": column,
        "reason": reason,
        "severity": severity,
        "raw_payload": raw_payload(row),
    }


def failure_events(frame: pd.DataFrame, number: int, replay: bool) -> list[dict[str, Any]]:
    """Collecter tous les échecs pandera, y compris structure et doublons."""
    schema = source_schema(number, replay)
    view = validation_view(frame, schema)
    try:
        schema.validate(view, lazy=True)
        return []
    except pa.errors.SchemaErrors as error:
        failures = error.failure_cases
    events = []
    for failure in failures.itertuples(index=False):
        column = str(failure.column)
        if str(failure.check) == "column_in_dataframe":
            column = str(failure.failure_case)
        indices = range(len(frame)) if pd.isna(failure.index) else [int(failure.index)]
        hour = (
            int(column[-2:])
            if column.startswith(("tti_", "time_")) and column[-2:].isdigit()
            else -1
        )
        for index in indices:
            if replay:
                value_hour = pd.to_numeric(
                    pd.Series([frame.iloc[index].get("hour")]), errors="coerce"
                )[0]
                hour = (
                    int(value_hour)
                    if pd.notna(value_hour)
                    and np.isfinite(value_hour)
                    and value_hour % 1 == 0
                    and 0 <= value_hour <= 23
                    else -1
                )
            value = pd.to_numeric(pd.Series([frame.iloc[index].get(column)]), errors="coerce")[0]
            repairable = (
                column.startswith("tti_")
                and str(failure.check) == "greater_than_or_equal_to(1)"
                and pd.notna(value)
                and np.isfinite(value)
                and 0 < value < 1
            )
            severity = "repairable" if repairable else "rejected"
            events.append(
                event_for(frame, index, column, f"pandera:{failure.check}", severity, hour)
            )
    return events


def reference_events(
    frame: pd.DataFrame, points: pd.DataFrame, number: int
) -> list[dict[str, Any]]:
    """Vérifier commune/ZIP et indices/coordonnées sans réparation implicite."""
    events = []
    pairs = set(zip(points.get("Commune", []), points.get("ZIP code", []), strict=True))
    candidates: dict[tuple[float, float] | None, list[int]] = {}
    reference_points = (
        points if {"Latitude", "Longitude", "Index"}.issubset(points) else pd.DataFrame()
    )
    for row in reference_points.itertuples(index=False):
        key = coordinate_key(row.Latitude, row.Longitude)
        numeric_id = pd.to_numeric(pd.Series([row.Index]), errors="coerce")[0]
        if (
            key is not None
            and pd.notna(numeric_id)
            and np.isfinite(numeric_id)
            and numeric_id % 1 == 0
            and 0 <= numeric_id <= 109
        ):
            candidates.setdefault(key, []).append(int(numeric_id))
    traffic = number >= 5
    for index, row in frame.iterrows():
        commune, zipcode = ("commune", "zip") if traffic else ("Commune", "ZIP code")
        if (row.get(commune), row.get(zipcode)) not in pairs:
            events.append(event_for(frame, index, commune, "commune_zip_unknown"))
        if not traffic:
            continue
        for role in ("origin", "dest"):
            key = coordinate_key(row.get(f"{role}_lat"), row.get(f"{role}_lon"))
            matches = candidates.get(key, []) if key is not None else []
            raw_id = row.get(f"{role}_index")
            if len(matches) != 1:
                events.append(
                    event_for(
                        frame, index, f"{role}_index", "point_coordinates_unknown_or_ambiguous"
                    )
                )
            elif raw_id != matches[0]:
                known = (
                    row["_source_sha256"] == SOURCE_SHA256
                    and KNOWN_POINT_REPAIRS.get(raw_id) == matches[0]
                )
                events.append(
                    event_for(
                        frame,
                        index,
                        f"{role}_index",
                        "point_index_coordinate_mismatch",
                        "repairable" if known else "rejected",
                    )
                )
    return events


def validate_table(frame: pd.DataFrame, points: pd.DataFrame) -> ValidationResult:
    """Réconcilier les lignes valides, réparables et rejetées au grain de la mesure."""
    frame = frame.reset_index(drop=True)
    number = table_number(str(frame["_sheet"].iloc[0]))
    if number is None:
        return ValidationResult(
            {
                "table_number": None,
                "navigation_rows": len(frame),
                "total": 0,
                "valid": 0,
                "repairable": 0,
                "rejected": 0,
            },
            [],
        )
    replay = "travel_time_raw" in frame
    events = failure_events(frame, number, replay)
    events += reference_events(frame, points, number)
    if number >= 5:
        columns = ["tti_provided"] if replay else [f"tti_{hour:02d}" for hour in range(24)]
        for column in columns:
            if column not in frame:
                continue
            values = pd.to_numeric(frame[column], errors="coerce")
            for index in frame.index[values > 5]:
                value_hour = (
                    pd.to_numeric(pd.Series([frame.loc[index].get("hour")]), errors="coerce")[0]
                    if replay
                    else int(column[-2:])
                )
                hour = (
                    int(value_hour)
                    if pd.notna(value_hour)
                    and np.isfinite(value_hour)
                    and value_hour % 1 == 0
                    and 0 <= value_hour <= 23
                    else -1
                )
                events.append(
                    event_for(frame, index, column, "source_tti_above_five", "warning", hour)
                )
    events = list({event["event_id"]: event for event in events}.values())
    rejected, repairable = set(), set()
    for event in events:
        if event["severity"] == "warning":
            continue
        hours = (
            [event["hour"]]
            if event["hour"] != -1
            else (list(range(24)) if number >= 5 and not replay else [-1])
        )
        target = rejected if event["severity"] == "rejected" else repairable
        target.update((event["excel_row"], hour) for hour in hours)
    # Une règle portant sur toute la ligne d'un rejeu porte sur son heure effective.
    if replay:
        actual_hours = dict(zip(frame["_excel_row"],
                                frame.get("hour", pd.Series(-1, index=frame.index)), strict=True))
        rejected = {(row, actual_hours[row] if hour == -1 else hour) for row, hour in rejected}
        repairable = {(row, actual_hours[row] if hour == -1 else hour) for row, hour in repairable}
    repairable -= rejected
    total = len(frame) * (24 if number >= 5 and not replay else 1)
    summary = {
        "table_number": number,
        "sheet": str(frame["_sheet"].iloc[0]),
        "total": total,
        "valid": total - len(rejected) - len(repairable),
        "repairable": len(repairable),
        "rejected": len(rejected),
        "events": len(events),
        "warning_events": sum(e["severity"] == "warning" for e in events),
    }
    LOGGER.info("Validation %s : %s", summary["sheet"], summary)
    return ValidationResult(summary, events)


def enforce_threshold(summary: dict[str, Any], max_error_rate: float) -> None:
    """Échouer après persistance des rejets si leur taux dépasse le seuil configuré."""
    if not np.isfinite(max_error_rate) or not 0 <= max_error_rate <= 1:
        raise ValueError("Le seuil qualité doit être compris entre 0 et 1")
    rate = summary["rejected"] / summary["total"] if summary["total"] else 0
    if rate > max_error_rate:
        raise ValueError(f"Taux de rejet {rate:.2%} > seuil {max_error_rate:.2%}")

"""Contrat des mesures normalisées et journalisation des échecs avant chargement."""

from typing import Any

import pandas as pd
import pandera.pandas as pa

from src.validate.quality import event_for
from src.validate.schemas import INTEGER, numeric, validation_view


def normalized_schema(core: bool = False) -> pa.DataFrameSchema:
    """Exiger clés, temps et distances valides au grain trajet/jour/heure."""
    columns = {
        "trajectory_id": numeric(INTEGER, pa.Check.gt(0)),
        "origin_point_id": numeric(INTEGER, pa.Check.in_range(0, 109)),
        "dest_point_id": numeric(INTEGER, pa.Check.in_range(0, 109)),
        "day_of_week": numeric(INTEGER, pa.Check.in_range(1, 7)),
        "hour": numeric(INTEGER, pa.Check.in_range(0, 23)),
        "distance_km": numeric(pa.Check.gt(0)),
        "travel_time_min": numeric(pa.Check.gt(0)),
    }
    if core:
        columns.update(
            {
                "free_flow_reference_min": numeric(pa.Check.gt(0)),
                "tti": numeric(pa.Check.ge(1)),
                "speed_kmh": numeric(pa.Check.gt(0)),
            }
        )
    return pa.DataFrameSchema(
        columns,
        unique=["trajectory_id", "day_of_week", "hour"],
        report_duplicates="all",
        strict=False,
    )


def normalized_events(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Recueillir chaque échec sans retirer la valeur brute de son payload."""
    schema = normalized_schema(core="tti" in frame)
    try:
        schema.validate(validation_view(frame, schema), lazy=True)
        return []
    except pa.errors.SchemaErrors as error:
        failures = error.failure_cases
    events = []
    for failure in failures.itertuples(index=False):
        indices = range(len(frame)) if pd.isna(failure.index) else [int(failure.index)]
        for index in indices:
            value = frame.iloc[index].get("hour")
            hour = int(value) if pd.notna(value) and 0 <= value <= 23 else -1
            events.append(
                event_for(
                    frame,
                    index,
                    str(failure.column),
                    f"normalized:{failure.check}",
                    "rejected",
                    hour,
                )
            )
    return list({event["event_id"]: event for event in events}.values())


def admissible_rows(frame: pd.DataFrame, events: list[dict[str, Any]]) -> pd.DataFrame:
    """Exclure seulement les clés explicitement journalisées comme rejetées."""
    whole_rows = {
        event["excel_row"]
        for event in events
        if event["severity"] == "rejected" and event["hour"] == -1
    }
    hours = {
        (event["excel_row"], event["hour"])
        for event in events
        if event["severity"] == "rejected" and event["hour"] >= 0
    }
    blocked = [
        row in whole_rows or (row, hour) in hours
        for row, hour in zip(frame["_excel_row"], frame["hour"], strict=True)
    ]
    return frame.loc[[not value for value in blocked]].copy()

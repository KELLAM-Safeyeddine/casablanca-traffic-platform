"""Normaliser une copie des valeurs source avec des règles explicites et auditées."""

import unicodedata

import numpy as np
import pandas as pd

from src.extract.workbook_profile import (
    SOURCE_SHA256,
    TRAFFIC_BASE_COLUMNS,
    coordinate_key,
    table_number,
)
from src.validate.quality import KNOWN_POINT_REPAIRS


def commune_key(value: object) -> str:
    """Normaliser Unicode, espaces et casse sans correction géographique inventée."""
    return (
        " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
        if isinstance(value, str)
        else ""
    )


def with_reference(frame: pd.DataFrame, references: dict[int, float]) -> pd.DataFrame:
    """Prévalider les formules CORE avec la référence figée chargée en base."""
    frame = frame.copy()
    frame["free_flow_reference_min"] = frame["trajectory_id"].map(references)
    frame["tti"] = frame["travel_time_min"] / frame["free_flow_reference_min"]
    frame["speed_kmh"] = 60 * frame["distance_km"] / frame["travel_time_min"]
    return frame


def normalize_distance(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Interpréter exclusivement les distances >100 comme des mètres."""
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    scaled = numeric > 100
    return numeric.where(~scaled, numeric / 1000), scaled


def normalize_time(values: pd.Series, source_sha256: str) -> tuple[pd.Series, pd.Series]:
    """Corriger les grands entiers uniquement pour la version de source diagnostiquée."""
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    scaled = (numeric >= 1000) & (numeric.mod(1) == 0) & (source_sha256 == SOURCE_SHA256)
    return numeric.where(~scaled, numeric / 1000), scaled


def resolve_point(raw_id: float, lat: float, lon: float, points: dict) -> float:
    """Exiger une correspondance unique et autoriser seulement le crosswalk confirmé."""
    matches = points.get(coordinate_key(lat, lon), [])
    if len(matches) != 1:
        return np.nan
    target = matches[0]
    return (
        float(target) if raw_id == target or KNOWN_POINT_REPAIRS.get(raw_id) == target else np.nan
    )


def unpivot_traffic(raw: pd.DataFrame) -> pd.DataFrame:
    """Produire toutes les heures, même lorsqu'une valeur attendue est manquante."""
    if "travel_time_raw" in raw:
        return raw.copy().reset_index(drop=True)
    number = table_number(str(raw["_sheet"].iloc[0]))
    if number is None or number < 5:
        raise ValueError("Une table de trafic est nécessaire")
    base_columns = [*TRAFFIC_BASE_COLUMNS, *[name for name in raw if name.startswith("_")]]
    frames = []
    for hour in range(24):
        frame = raw[base_columns].copy()
        frame["day_of_week"] = number - 4
        frame["hour"] = hour
        frame["travel_time_raw"] = raw.get(f"time_{hour:02d}", np.nan)
        frame["tti_provided"] = raw.get(f"tti_{hour:02d}", np.nan)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def normalize_traffic(raw: pd.DataFrame, point_frame: pd.DataFrame) -> pd.DataFrame:
    """Dépivoter et normaliser les valeurs sans filtrer une seule mesure."""
    frame = unpivot_traffic(raw)
    source_hash = str(raw["_source_sha256"].iloc[0])
    frame["distance_km"], frame["distance_scaled"] = normalize_distance(frame["distance_raw"])
    frame["travel_time_min"], frame["time_scaled"] = normalize_time(
        frame["travel_time_raw"], source_hash
    )
    lookup = {}
    for row in point_frame.itertuples(index=False):
        lookup.setdefault(coordinate_key(row.Latitude, row.Longitude), []).append(int(row.Index))
    for role in ("origin", "dest"):
        frame[f"{role}_point_id"] = [
            resolve_point(raw_id, lat, lon, lookup)
            for raw_id, lat, lon in zip(
                frame[f"{role}_index"], frame[f"{role}_lat"], frame[f"{role}_lon"], strict=True
            )
        ]
        if source_hash != SOURCE_SHA256:
            changed = frame[f"{role}_point_id"] != pd.to_numeric(
                frame[f"{role}_index"], errors="coerce"
            )
            frame.loc[changed, f"{role}_point_id"] = np.nan
    frame["trajectory_id"] = frame["origin_point_id"] * 110 + frame["dest_point_id"] + 1
    frame["commune_key"] = frame["commune"].map(commune_key)
    frame["index_repaired"] = (frame["origin_point_id"] != frame["origin_index"]) | (
        frame["dest_point_id"] != frame["dest_index"]
    )
    return frame

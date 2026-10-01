"""Rejouer une semaine type par partitions horaires stables, sans horloge métier fictive."""

import argparse
import logging
from pathlib import Path

from src.extract.excel_reader import extract_sheet, verify_raw, write_immutable_parquet
from src.extract.workbook_profile import DAYS, SOURCE_SHA256, TRAFFIC_BASE_COLUMNS

LOGGER = logging.getLogger(__name__)


def slot_for_tick(tick: int) -> tuple[int, int]:
    """Transformer un tick non négatif en jour ISO/heure, avec répétition sur 168 heures."""
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        raise ValueError("Le tick doit être un entier positif ou nul")
    slot = tick % 168
    return slot // 24 + 1, slot % 24


def replay_hour(source: Path, raw_root: Path, tick: int) -> Path:
    """Émettre les 440 valeurs brutes d'une tranche, idempotente au sein de la semaine type."""
    day, hour = slot_for_tick(tick)
    source_path = extract_sheet(source, raw_root, day + 4)
    daily = verify_raw(source_path)
    selected = daily[[*TRAFFIC_BASE_COLUMNS, "_excel_row", "_commune_raw", "_zip_raw"]].copy()
    selected["day_of_week"] = day
    selected["hour"] = hour
    selected["travel_time_raw"] = daily[f"time_{hour:02d}"]
    selected["tti_provided"] = daily[f"tti_{hour:02d}"]
    selected["_replay_slot"] = (day - 1) * 24 + hour
    target = source_path.parent / "replay" / f"day={day}" / f"hour={hour:02d}.parquet"
    path = write_immutable_parquet(selected, target, source.name, daily["_sheet"].iloc[0],
                                   daily["_source_sha256"].iloc[0])
    LOGGER.info("Rejeu tick=%d, %s %02dh, %d trajets : %s", tick, DAYS[day - 1], hour,
                len(selected), path)
    return path


def main() -> None:
    """Rejouer une tranche ou toute la semaine depuis la CLI locale du venv."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--tick", type=int, default=0)
    parser.add_argument("--steps", type=int, default=1)
    arguments = parser.parse_args()
    if arguments.steps < 1:
        parser.error("--steps doit être >=1")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for tick in range(arguments.tick, arguments.tick + arguments.steps):
        print(replay_hour(arguments.source, arguments.raw_root, tick))
    print(f"Source attendue : {SOURCE_SHA256}")


if __name__ == "__main__":
    main()

"""Vérifier publication immuable, corruption et frontières du rejeu."""

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from src.extract.excel_reader import verify_raw, write_immutable_parquet
from src.extract.flow_simulator import slot_for_tick


def test_publication_preserves_rows_and_bytes(tmp_path):
    frame = pd.DataFrame({"commune": ["Casa", None], "distance_raw": [9954.0, 1.27]})
    target = tmp_path / "raw.parquet"
    write_immutable_parquet(frame, target, "source.xlsx", "Monday", "a" * 64)
    initial = target.read_bytes()
    write_immutable_parquet(frame, target, "source.xlsx", "Monday", "a" * 64)
    assert target.read_bytes() == initial
    pd.testing.assert_frame_equal(verify_raw(target)[frame.columns], frame)
    with pytest.raises(ValueError, match="altéré"):
        write_immutable_parquet(frame.fillna("changed"), target,
                                "source.xlsx", "Monday", "a" * 64)
    assert target.read_bytes() == initial


def test_concurrent_publication_and_corruption(tmp_path):
    target = tmp_path / "raw.parquet"
    frame = pd.DataFrame({"time": [1.0, 2000.0]})
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda _: write_immutable_parquet(frame, target, "s.xlsx", "day", "b" * 64),
            range(2),
        ))
    assert results == [target, target]
    stored = verify_raw(target)
    stored.loc[0, "time"] = 99
    stored.to_parquet(target, index=False)
    with pytest.raises(ValueError, match="altéré"):
        verify_raw(target)
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("tick, expected", [(0, (1, 0)), (23, (1, 23)),
                         (24, (2, 0)), (167, (7, 23)), (168, (1, 0))])
def test_week_boundaries(tick, expected):
    assert slot_for_tick(tick) == expected


@pytest.mark.parametrize("tick", [-1, True, 1.5, "0"])
def test_invalid_ticks(tick):
    with pytest.raises(ValueError):
        slot_for_tick(tick)

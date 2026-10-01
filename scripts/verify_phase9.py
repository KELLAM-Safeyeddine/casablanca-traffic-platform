"""Réconcilier le dashboard avec les marts SQL et vérifier sa connexion lecture seule."""

import json
import os
import sys
import urllib.request
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.load.dashboard_data import (  # noqa: E402
    aggregate,
    point_summary,
    read_measures,
    select_measures,
)


def main() -> None:
    """Vérifier chaque commune/KPI et l'effectif de chaque visualisation."""
    if sys.version_info[:2] != (3, 11) or Path(sys.prefix).name != "CasaTraffic":
        raise RuntimeError("Utiliser CasaTraffic Python 3.11")
    settings = dotenv_values(ROOT / ".env")
    os.environ.update({"DASHBOARD_DB_HOST": "127.0.0.1",
                       "DASHBOARD_DB_PORT": settings["POSTGRES_PORT"],
                       "DASHBOARD_DB_PASSWORD": settings["DASHBOARD_DB_PASSWORD"]})
    data = read_measures()
    assert len(data) == 73920 and data.point_id.nunique() == 110
    points = point_summary(data)
    assert len(points) == 110 and points.measurement_count.eq(672).all()
    hourly = aggregate(data, ["commune", "hour"])
    assert len(hourly) == 528 and hourly.measurement_count.eq(140).all()
    ranking = aggregate(data, ["commune"])
    database = psycopg2.connect(
        host="127.0.0.1", port=settings["POSTGRES_PORT"], dbname="traffic", user="traffic",
        password=settings["TRAFFIC_DB_PASSWORD"],
    )
    try:
        with database.cursor() as query:
            query.execute("SELECT nom commune, tti_mean, tti_p95, speed_mean_kmh, "
                          "measurement_count FROM mart_commune_features ORDER BY nom")
            expected = pd.DataFrame(
                query.fetchall(), columns=[col.name for col in query.description],
            )
        pd.testing.assert_frame_equal(ranking.sort_values("commune").reset_index(drop=True),
                                      expected[ranking.columns], check_dtype=False,
                                      check_exact=False, atol=1e-12, rtol=1e-12)
    finally:
        database.close()
    reader = psycopg2.connect(host="127.0.0.1", port=settings["POSTGRES_PORT"],
                             dbname="traffic", user="traffic_dashboard",
                             password=settings["DASHBOARD_DB_PASSWORD"])
    try:
        with reader.cursor() as query:
            try:
                query.execute("UPDATE fact_travel_time SET tti=tti WHERE false")
            except psycopg2.errors.InsufficientPrivilege:
                reader.rollback()
            else:
                raise AssertionError("Le compte dashboard peut écrire")
    finally:
        reader.close()
    selected = select_measures(data, [sorted(data.commune.unique())[0]], [1], (7, 9))
    assert len(selected) == 60 and selected.point_id.nunique() == 5
    url = f"http://127.0.0.1:{settings['DASHBOARD_PORT']}"
    with urllib.request.urlopen(url + "/_stcore/health", timeout=15) as response:
        assert response.read() == b"ok"
    summary = {"url": url, "measures": len(data), "points": len(points),
               "heatmap_cells": len(hourly), "communes": len(ranking),
               "weekday_measures": int((data.day_of_week < 6).sum()),
               "weekend_measures": int((data.day_of_week >= 6).sum()),
               "tti_mean": float(data.tti.mean()), "tti_p95": float(data.tti.quantile(.95)),
               "sql_oracle_matches": True, "write_permission_denied": True,
               "filter_sample_measures": len(selected)}
    (ROOT / "docs/phase9_verification.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

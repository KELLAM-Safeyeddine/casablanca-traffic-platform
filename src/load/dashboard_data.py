"""Lectures PostgreSQL et agrégations du dashboard au grain des observations."""

import os
from pathlib import Path

import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parents[2]


def read_measures() -> pd.DataFrame:
    """Lire un snapshot cohérent avec le compte SQL du dashboard, sans secret affiché."""
    database = psycopg2.connect(
        host=os.environ["DASHBOARD_DB_HOST"], port=os.environ.get("DASHBOARD_DB_PORT", "5432"),
        dbname="traffic", user="traffic_dashboard", password=os.environ["DASHBOARD_DB_PASSWORD"],
        options="-c default_transaction_read_only=on", connect_timeout=10,
    )
    try:
        with database, database.cursor() as query:
            query.execute((ROOT / "sql/marts/dashboard_measures.sql").read_text(encoding="utf-8"))
            return pd.DataFrame(query.fetchall(), columns=[col.name for col in query.description])
    finally:
        database.close()


def select_measures(
    frame: pd.DataFrame, communes: list[str], days: list[int], hours: tuple[int, int],
) -> pd.DataFrame:
    """Appliquer les filtres inclusifs sans modifier le snapshot lu."""
    return frame.loc[frame.commune.isin(communes) & frame.day_of_week.isin(days)
                     & frame.hour.between(*hours)].copy()


def aggregate(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Calculer moyenne, p95 interpolé et effectif directement depuis les faits."""
    return frame.groupby(keys, as_index=False).agg(
        tti_mean=("tti", "mean"), tti_p95=("tti", lambda values: values.quantile(.95)),
        speed_mean_kmh=("speed_kmh", "mean"), measurement_count=("tti", "size"),
    )


def point_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par point d'origine avec couleur continue du TTI moyen."""
    points = aggregate(frame, ["point_id", "commune", "latitude", "longitude"])
    # Palette continue commune aux vues : bleu à TTI=1, rouge à TTI>=2.
    intensity = ((points.tti_mean - 1) / 1).clip(0, 1)
    points["color"] = [[int(35 + 200 * value), int(150 - 95 * value),
                        int(180 - 120 * value), 220] for value in intensity]
    points["tti_label"] = points.tti_mean.map(lambda value: f"{value:.3f}")
    return points

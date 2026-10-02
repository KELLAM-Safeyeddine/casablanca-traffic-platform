"""Requêtes analytiques : SQL séparé des vues, résultats et percentiles côté serveur."""

from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.data.database import reading
from dashboard.data.filters import Filters

SQL = Path(__file__).parent / "sql"
# Les seuls fragments dynamiques sont des constantes internes, jamais des entrées utilisateur.
GROUPS = {
    "summary": "",
    "hourly": "hour",
    "communes": "commune_id, commune",
    "heatmap": "commune_id, commune, hour",
    "points": "point_id, commune, latitude, longitude",
    "periods": "(day_of_week >= 6) is_weekend",
    "period_hourly": "(day_of_week >= 6) is_weekend, hour",
    "features": "commune_id, commune, population_density_per_km2, tram_stations, primary_roads",
}


def text_file(name: str) -> str:
    """Lire les fichiers SQL versionnés."""
    return (SQL / name).read_text(encoding="utf-8").strip().rstrip(";")


def execute(statement: str, parameters: dict[str, object]) -> pd.DataFrame:
    """Ne renvoyer que des résultats ; le pool refuse les transactions d'écriture."""
    with reading() as database, database.cursor() as cursor:
        cursor.execute(statement, parameters)
        return pd.DataFrame(cursor.fetchall(), columns=[col.name for col in cursor.description])


def statement(kind: str) -> str:
    """Assembler un SELECT autorisé et une agrégation à partir de constantes."""
    if kind in {"catalog", "coverage"}:
        return text_file(f"{kind}.sql")
    selected = f"WITH selected AS ({text_file('selected.sql')}) "
    if kind == "export":
        return selected + text_file("export.sql")
    keys = GROUPS[kind]
    columns = f"{keys}, " if keys else ""
    # GROUP BY position fonctionne aussi pour les expressions avec alias.
    groups = (
        " GROUP BY " + ",".join(str(i + 1) for i in range(len(keys.split(",")))) if keys else ""
    )
    return selected + f"SELECT {columns}{text_file('metrics.sql')} FROM selected{groups}"


@st.cache_data(ttl=60, max_entries=256, show_spinner=False)
def fetch(kind: str, filters: Filters | None = None) -> pd.DataFrame:
    """Mettre en cache le résultat SQL par sélection complète pendant une minute."""
    if filters is None and kind not in {"catalog", "coverage"}:
        raise ValueError("Filters required")
    return execute(statement(kind), filters.parameters() if filters else {})


def correlation_statement(variable: str) -> str:
    """Utiliser uniquement un attribut urbain explicitement autorisé."""
    if variable not in {"population_density_per_km2", "tram_stations", "primary_roads"}:
        raise ValueError("Unknown explanatory variable")
    return (
        f"WITH groups AS ({statement('features')}) "
        f"SELECT *, corr(tti_mean, {variable}) OVER () correlation, "
        f"regr_slope(tti_mean, {variable}) OVER () slope, "
        f"regr_intercept(tti_mean, {variable}) OVER () intercept, "
        f"count(*) OVER () pair_count FROM groups ORDER BY {variable}, commune"
    )


@st.cache_data(ttl=60, max_entries=128, show_spinner=False)
def correlations(variable: str, filters: Filters) -> pd.DataFrame:
    """Calculer les statistiques descriptives dans PostgreSQL, une paire par commune."""
    return execute(correlation_statement(variable), filters.parameters())

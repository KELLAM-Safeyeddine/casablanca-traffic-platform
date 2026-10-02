"""Formats localisés et résumés déterministes, sans agrégation métier en pandas."""

from html import escape
from math import isfinite

import pandas as pd


def number(value: object, digits: int = 2, language: str = "fr") -> str:
    """Formater une valeur finie ; les absences sont visibles plutôt qu'inventées."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "—"
    if not isfinite(numeric):
        return "—"
    formatted = f"{numeric:,.{digits}f}"
    return formatted.replace(",", " ").replace(".", ",") if language == "fr" else formatted


def summary(groups: pd.DataFrame, language: str = "fr") -> str:
    """Décrire le vrai groupe commune/heure maximal, avec tri stable des égalités."""
    if groups.empty:
        return "Aucune donnée pour ces filtres." if language == "fr" else "No matching data."
    row = groups.sort_values(["tti_mean", "commune", "hour"], ascending=[False, True, True]).iloc[0]
    name = escape(str(row.commune))
    tti = number(row.tti_mean, language=language)
    if language == "fr":
        return f"{name} atteint le TTI moyen maximal de cette sélection à {row.hour:02d} h : {tti}."
    return f"{name} has the highest mean TTI in this selection at {row.hour:02d}:00: {tti}."
